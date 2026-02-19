"""
Sales service with transactional logic - Multi-Tenant.
Handles sale confirmation, stock movements, and financial records.
"""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple
from sqlalchemy import text
from app.models import (
    Product, ProductStock, Sale, SaleLine, SalePayment, SaleDraft,
    StockMove, StockMoveLine, FinanceLedger,
    SaleStatus, StockMoveType, StockReferenceType, PaymentStatus,
    LedgerType, LedgerReferenceType, normalize_payment_method
)
from app.exceptions import BusinessLogicError, NotFoundError, InsufficientStockError
from app.services.sale_draft_service import calculate_draft_totals


def confirm_sale(cart: dict, session, payment_method: str = 'CASH', tenant_id: int = None, customer_id: int = None) -> int:
    """
    Confirm sale with full transactional processing (tenant-scoped).
    Basic version used for simple carts.
    """
    if not cart or not cart.get('items'):
        raise BusinessLogicError('El carrito está vacío')
    
    if not tenant_id:
        raise BusinessLogicError('tenant_id es requerido')
    
    try:
        session.begin_nested()
        
        # 1. Fetch products and validate in batch
        product_ids = [int(pid) for pid in cart['items'].keys()]
        products = session.query(Product).filter(
            Product.id.in_(product_ids),
            Product.tenant_id == tenant_id
        ).all()
        
        if len(products) != len(product_ids):
            raise NotFoundError('Uno o más productos no encontrados o no pertenecen a su negocio')
            
        products_dict = {p.id: p for p in products}
        for p in products:
            if not p.active:
                raise BusinessLogicError(f'El producto "{p.name}" no está activo')

        # 2. Lock stock levels
        stock_dict = _lock_stocks(session, product_ids, tenant_id)
        
        # 3. Prepare data and validate stock
        sale_lines_data = []
        sale_total = Decimal('0.00')
        
        for pid_str, item in cart['items'].items():
            pid = int(pid_str)
            qty = Decimal(str(item['qty']))
            if qty <= 0:
                raise BusinessLogicError('La cantidad debe ser mayor a 0')
                
            product = products_dict[pid]
            current_stock = stock_dict.get(pid, Decimal('0'))
            
            if current_stock < qty:
                raise InsufficientStockError(f'Stock insuficiente para "{product.name}". Disponible: {current_stock}, Solicitado: {qty}')
                
            line_total = (qty * product.sale_price).quantize(Decimal('0.01'))
            sale_lines_data.append({
                'product_id': pid,
                'product': product,
                'qty': qty,
                'unit_price': product.sale_price,
                'line_total': line_total
            })
            sale_total += line_total
            
        # 4. Create Sale
        sale = Sale(
            tenant_id=tenant_id,
            datetime=datetime.now(),
            total=sale_total.quantize(Decimal('0.01')),
            status='CONFIRMED', # Explicit string
            customer_id=customer_id,
            payment_status=PaymentStatus.PAID,
            amount_paid=sale_total.quantize(Decimal('0.01'))
        )
        session.add(sale)
        session.flush()
        
        # 5. Create SaleLines
        for line in sale_lines_data:
            session.add(SaleLine(
                sale_id=sale.id,
                product_id=line['product_id'],
                qty=line['qty'],
                unit_price=line['unit_price'],
                line_total=line['line_total']
            ))
            
        # 6. Create Stock Movement
        _create_stock_movement(session, tenant_id, sale.id, sale_lines_data)
        
        # 7. Create Finance entries
        payments = [{'method': payment_method, 'amount': sale_total}]
        _create_ledger_entries(session, tenant_id, sale.id, payments, sale_total)
        
        session.commit()
        _invalidate_balance_cache(tenant_id)
        return sale.id
        
    except (BusinessLogicError, NotFoundError, InsufficientStockError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        raise Exception(f'Error al confirmar venta: {str(e)}')


def confirm_sale_from_draft(
    draft_id: int,
    payments: List[Dict[str, Any]],
    idempotency_key: str,
    session,
    tenant_id: int,
    user_id: int,
    customer_id: int = None
) -> int:
    """
    Confirm sale from draft with idempotency and mixed payments.
    """
    try:
        # 1. Idempotency check
        existing_sale = session.query(Sale).filter_by(idempotency_key=idempotency_key).first()
        if existing_sale:
            raise BusinessLogicError(f'Esta venta ya fue procesada (ID: {existing_sale.id})')
            
        # 2. Get draft
        draft = session.query(SaleDraft).filter_by(id=draft_id, tenant_id=tenant_id, user_id=user_id).first()
        if not draft or not draft.lines:
            raise NotFoundError('Carrito no encontrado o vacío')
            
        # 3. Calculate and validate payments
        totals = calculate_draft_totals(draft)
        sale_total = totals['total']
        if sale_total <= 0:
            raise BusinessLogicError('El total de la venta debe ser mayor a 0')
        
        # Detect if this is a Cuenta Corriente (credit) sale
        is_cuenta_corriente = (
            len(payments) == 1 and
            payments[0].get('method', '').upper() == 'CUENTA_CORRIENTE'
        )
        
        if is_cuenta_corriente:
            # Cuenta Corriente requires a customer
            if not customer_id:
                raise BusinessLogicError('Para usar Cuenta Corriente debe seleccionar un Cliente registrado')
        else:
            payments_total = sum(Decimal(str(p.get('amount', 0))) for p in payments)
            if payments_total != sale_total:
                raise BusinessLogicError(f'La suma de pagos (${payments_total}) no coincide con el total (${sale_total})')
            
        # 4. Lock and validate stock
        product_ids = [line['product_id'] for line in totals['lines']]
        stock_dict = _lock_stocks(session, product_ids, tenant_id)
        
        for line in totals['lines']:
            if stock_dict.get(line['product_id'], Decimal('0')) < line['qty']:
                raise InsufficientStockError(f'Stock insuficiente para "{line["product_name"]}"')
                
        # 5. Create Sale
        sale = Sale(
            tenant_id=tenant_id,
            datetime=datetime.now(),
            total=sale_total,
            status='CONFIRMED', # Explicit string
            idempotency_key=idempotency_key,
            customer_id=customer_id,
            payment_status=PaymentStatus.PENDING if is_cuenta_corriente else PaymentStatus.PAID,
            amount_paid=Decimal('0') if is_cuenta_corriente else sale_total
        )
        session.add(sale)
        session.flush()
        
        # 6. Create SaleLines & Payments
        sale_lines_data = []
        for line in totals['lines']:
            final_unit_price = (line['line_total'] / line['qty']).quantize(Decimal('0.01'))
            session.add(SaleLine(
                sale_id=sale.id,
                product_id=line['product_id'],
                qty=line['qty'],
                unit_price=final_unit_price,
                line_total=line['line_total']
            ))
            # Cache for stock movement
            product = session.query(Product).get(line['product_id'])
            sale_lines_data.append({
                'product_id': line['product_id'],
                'qty': line['qty'],
                'product': product
            })
            
        # Create SalePayments (skip for Cuenta Corriente)
        if not is_cuenta_corriente:
            for p in payments:
                method = p['method'].upper()
                if method not in ['CASH', 'TRANSFER', 'CARD']:
                    raise BusinessLogicError(f'Método de pago inválido: {method}')
                session.add(SalePayment(
                    sale_id=sale.id,
                    payment_method=method,
                    amount=Decimal(str(p['amount'])),
                    amount_received=Decimal(str(p.get('amount_received', 0))) if method == 'CASH' else None,
                    change_amount=Decimal(str(p.get('change_amount', 0))) if method == 'CASH' else None
                ))
            
        # 7. Create Stock Movement & Finance Entries
        _create_stock_movement(session, tenant_id, sale.id, sale_lines_data)
        if not is_cuenta_corriente:
            _create_ledger_entries(session, tenant_id, sale.id, payments, sale_total)
        else:
            # Register CC sale in ledger as devengado income
            session.add(FinanceLedger(
                tenant_id=tenant_id,
                datetime=datetime.now(),
                type=LedgerType.INVOICE,
                amount=sale_total,
                category='Ventas',
                reference_type=LedgerReferenceType.SALE,
                reference_id=sale.id,
                notes='Creacion de factura',
                payment_method='CUENTA_CORRIENTE'
            ))
        
        # 8. Clean up
        session.delete(draft)
        session.commit()
        _invalidate_balance_cache(tenant_id)
        
        return sale.id
        
    except (BusinessLogicError, NotFoundError, InsufficientStockError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        raise Exception(f'Error al confirmar venta: {str(e)}')


# =====================================================
# PRIVATE HELPERS
# =====================================================

def _lock_stocks(session, product_ids: List[int], tenant_id: int) -> Dict[int, Decimal]:
    """Lock product_stock rows FOR UPDATE and return current levels."""
    if not product_ids:
        return {}
        
    placeholders = ', '.join([f':pid{i}' for i in range(len(product_ids))])
    query = text(f"""
        SELECT ps.product_id, ps.on_hand_qty 
        FROM product_stock ps
        INNER JOIN product p ON p.id = ps.product_id
        WHERE ps.product_id IN ({placeholders})
          AND p.tenant_id = :tenant_id
        FOR UPDATE OF ps
    """)
    
    params = {f'pid{i}': pid for i, pid in enumerate(product_ids)}
    params['tenant_id'] = tenant_id
    results = session.execute(query, params).fetchall()
    return {row[0]: Decimal(str(row[1])) for row in results}


def _create_stock_movement(session, tenant_id: int, sale_id: int, lines: List[Dict[str, Any]]):
    """Generate stock movement and lines for a sale."""
    move = StockMove(
        tenant_id=tenant_id,
        date=datetime.now(),
        type=StockMoveType.OUT,
        reference_type=StockReferenceType.SALE,
        reference_id=sale_id,
        notes=f'Venta #{sale_id}'
    )
    session.add(move)
    session.flush()
    
    for line in lines:
        session.add(StockMoveLine(
            stock_move_id=move.id,
            product_id=line['product_id'],
            qty=line['qty'],
            uom_id=line['product'].uom_id
        ))


def _create_ledger_entries(session, tenant_id: int, sale_id: int, payments: List[Dict[str, Any]], total: Decimal):
    """Generate financial ledger entries for each payment."""
    for p in payments:
        method = p.get('method', 'CASH').upper()
        amount = Decimal(str(p.get('amount', total)))
        
        session.add(FinanceLedger(
            tenant_id=tenant_id,
            datetime=datetime.now(),
            type=LedgerType.INCOME,
            amount=amount,
            category='Ventas',
            reference_type=LedgerReferenceType.SALE,
            reference_id=sale_id,
            notes=f'Ingreso por venta #{sale_id} ({method})',
            payment_method=normalize_payment_method(method)
        ))


def _invalidate_balance_cache(tenant_id: int):
    """Gracefully attempt to invalidate the balance cache."""
    try:
        from app.services.cache_service import get_cache
        cache = get_cache()
        cache.invalidate_module(tenant_id, 'balance')
    except Exception:
        pass
