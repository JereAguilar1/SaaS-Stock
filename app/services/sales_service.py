"""Sales service with transactional logic - Multi-Tenant."""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict
from sqlalchemy import text
from app.models import (
    Product, ProductStock, Sale, SaleLine, SalePayment, SaleDraft,
    StockMove, StockMoveLine, FinanceLedger,
    SaleStatus, StockMoveType, StockReferenceType,
    LedgerType, LedgerReferenceType
)


def confirm_sale(cart: dict, session, payment_method: str = 'CASH', tenant_id: int = None) -> int:
    """
    Confirm sale with full transactional processing (tenant-scoped).
    
    Steps:
    1. Validate cart and products (tenant-scoped)
    2. Lock product_stock rows (FOR UPDATE) via JOIN with product
    3. Validate sufficient stock
    4. Create sale and sale_lines with tenant_id
    5. Create stock_move and stock_move_lines (OUT) with tenant_id
    6. Create finance_ledger entry (INCOME) with tenant_id
    7. Commit transaction
    
    Args:
        cart: Cart dictionary with items
        session: SQLAlchemy session
        payment_method: 'CASH' or 'TRANSFER'
        tenant_id: Tenant ID (REQUIRED)
    
    Returns:
        sale_id: ID of created sale
        
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    
    # Validate cart not empty
    if not cart or not cart.get('items'):
        raise ValueError('El carrito está vacío')
    
    # Validate tenant_id is provided
    if not tenant_id:
        raise ValueError('tenant_id es requerido')
    
    try:
        # Start transaction
        session.begin_nested()
        
        # Step 1: Get all product IDs and validate they belong to tenant
        product_ids = [int(pid) for pid in cart['items'].keys()]
        
        # Get products and validate tenant
        products_dict = {}
        for pid in product_ids:
            product = session.query(Product).filter(
                Product.id == pid,
                Product.tenant_id == tenant_id
            ).first()
            
            if not product:
                raise ValueError(f'Producto con ID {pid} no encontrado o no pertenece a su negocio')
            if not product.active:
                raise ValueError(f'El producto "{product.name}" no está activo')
            products_dict[pid] = product
        
        # Step 2: Lock product_stock rows FOR UPDATE (via JOIN with product to filter by tenant)
        # Build placeholders for IN clause
        placeholders = ', '.join([f':pid{i}' for i in range(len(product_ids))])
        lock_query = text(f"""
            SELECT ps.product_id, ps.on_hand_qty 
            FROM product_stock ps
            INNER JOIN product p ON p.id = ps.product_id
            WHERE ps.product_id IN ({placeholders})
              AND p.tenant_id = :tenant_id
            FOR UPDATE OF ps
        """)
        
        # Execute with parameters
        params = {f'pid{i}': pid for i, pid in enumerate(product_ids)}
        params['tenant_id'] = tenant_id
        locked_stocks = session.execute(lock_query, params).fetchall()
        
        # Build stock dict
        stock_dict = {row[0]: Decimal(str(row[1])) for row in locked_stocks}
        
        # Step 3: Validate sufficient stock and calculate totals
        sale_lines_data = []
        sale_total = Decimal('0.00')
        
        for product_id_str, item in cart['items'].items():
            product_id = int(product_id_str)
            qty = Decimal(str(item['qty']))
            
            if qty <= 0:
                raise ValueError(f'La cantidad debe ser mayor a 0')
            
            product = products_dict[product_id]
            current_stock = stock_dict.get(product_id, Decimal('0'))
            
            if current_stock < qty:
                raise ValueError(
                    f'Stock insuficiente para "{product.name}". '
                    f'Disponible: {current_stock}, Solicitado: {qty}'
                )
            
            # Calculate line total
            unit_price = product.sale_price
            line_total = (qty * unit_price).quantize(Decimal('0.01'))
            
            sale_lines_data.append({
                'product_id': product_id,
                'product': product,
                'qty': qty,
                'unit_price': unit_price,
                'line_total': line_total
            })
            
            sale_total += line_total
        
        sale_total = sale_total.quantize(Decimal('0.01'))
        
        # Step 4: Create Sale with tenant_id
        sale = Sale(
            tenant_id=tenant_id,  # CRITICAL
            datetime=datetime.now(),
            total=sale_total,
            status=SaleStatus.CONFIRMED
        )
        session.add(sale)
        session.flush()  # Get sale.id
        
        # Step 5: Create SaleLines (no tenant_id, child of Sale)
        for line_data in sale_lines_data:
            sale_line = SaleLine(
                sale_id=sale.id,
                product_id=line_data['product_id'],
                qty=line_data['qty'],
                unit_price=line_data['unit_price'],
                line_total=line_data['line_total']
            )
            session.add(sale_line)
        
        # Step 6: Create StockMove (OUT) with tenant_id
        stock_move = StockMove(
            tenant_id=tenant_id,  # CRITICAL
            date=datetime.now(),
            type=StockMoveType.OUT,
            reference_type=StockReferenceType.SALE,
            reference_id=sale.id,
            notes=f'Venta #{sale.id}'
        )
        session.add(stock_move)
        session.flush()  # Get stock_move.id
        
        # Step 7: Create StockMoveLines (no tenant_id, child of StockMove)
        # Trigger on stock_move_line will update product_stock automatically
        for line_data in sale_lines_data:
            product = line_data['product']
            stock_move_line = StockMoveLine(
                stock_move_id=stock_move.id,
                product_id=line_data['product_id'],
                qty=line_data['qty'],
                uom_id=product.uom_id,
                unit_cost=None  # Not relevant for sales
            )
            session.add(stock_move_line)
        
        # Step 8: Create FinanceLedger entry (INCOME) with tenant_id
        from app.models import normalize_payment_method
        payment_method_normalized = normalize_payment_method(payment_method)
        
        ledger_entry = FinanceLedger(
            tenant_id=tenant_id,  # CRITICAL
            datetime=datetime.now(),
            type=LedgerType.INCOME,
            amount=sale_total,
            category='Ventas',
            reference_type=LedgerReferenceType.SALE,
            reference_id=sale.id,
            notes=f'Ingreso por venta #{sale.id}',
            payment_method=payment_method_normalized
        )
        session.add(ledger_entry)
        
        # Commit transaction
        session.commit()
        
        # PASO 8: Invalidate balance cache (async, non-blocking)
        try:
            from app.services.cache_service import get_cache
            cache = get_cache()
            cache.invalidate_module(tenant_id, 'balance')
        except Exception:
            pass  # Graceful degradation
        
        return sale.id
        
    except ValueError:
        # Business logic errors - rollback and re-raise
        session.rollback()
        raise
        
    except Exception as e:
        # Other errors - rollback and re-raise
        session.rollback()
        raise Exception(f'Error al confirmar venta: {str(e)}')
"""Extended sales service with draft confirmation and mixed payments."""
from decimal import Decimal
from datetime import datetime
from typing import List, Dict
from sqlalchemy import text
from app.models import (
    Product, ProductStock, Sale, SaleLine, SalePayment,
    StockMove, StockMoveLine, FinanceLedger, SaleDraft,
    SaleStatus, StockMoveType, StockReferenceType,
    LedgerType, LedgerReferenceType, normalize_payment_method
)
from app.services.sale_draft_service import calculate_draft_totals


def confirm_sale_from_draft(
    draft_id: int,
    payments: List[Dict[str, any]],
    idempotency_key: str,
    session,
    tenant_id: int,
    user_id: int
) -> int:
    """
    Confirm sale from draft with idempotency and mixed payments.
    
    Steps:
    1. Validate idempotency_key (prevent duplicates)
    2. Get draft and validate ownership
    3. Calculate totals with discounts
    4. Validate payments sum to total
    5. Lock product_stock rows (FOR UPDATE)
    6. Validate stock availability
    7. Create sale with idempotency_key
    8. Create sale_lines (with discounts applied)
    9. Create sale_payments
    10. Create stock_move + stock_move_lines
    11. Create finance_ledger entries (one per payment method)
    12. Delete draft
    13. Commit
    
    Args:
        draft_id: Draft ID
        payments: List of payment dicts:
            [
                {
                    'method': 'CASH',
                    'amount': Decimal('100.00'),
                    'amount_received': Decimal('120.00'),  # CASH only
                    'change_amount': Decimal('20.00')      # CASH only
                },
                {
                    'method': 'TRANSFER',
                    'amount': Decimal('50.00')
                }
            ]
        idempotency_key: UUID string to prevent duplicate sales
        session: SQLAlchemy session
        tenant_id: Tenant ID
        user_id: User ID
    
    Returns:
        sale_id: ID of created sale
    
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    
    try:
        # Step 1: Check idempotency
        existing_sale = session.query(Sale).filter(
            Sale.idempotency_key == idempotency_key
        ).first()
        
        if existing_sale:
            raise ValueError(
                f'Esta venta ya fue procesada (ID: {existing_sale.id}). '
                'No se permiten ventas duplicadas.'
            )
        
        # Step 2: Get draft and validate
        draft = session.query(SaleDraft).filter(
            SaleDraft.id == draft_id,
            SaleDraft.tenant_id == tenant_id,
            SaleDraft.user_id == user_id
        ).first()
        
        if not draft:
            raise ValueError('Carrito no encontrado o no pertenece a su negocio')
        
        if not draft.lines:
            raise ValueError('El carrito estÃ¡ vacÃ­o')
        
        # Step 3: Calculate totals with discounts
        totals = calculate_draft_totals(draft)
        sale_total = totals['total']
        
        if sale_total <= 0:
            raise ValueError('El total de la venta debe ser mayor a 0')
        
        # Step 4: Validate payments
        if not payments:
            raise ValueError('Debe especificar al menos un mÃ©todo de pago')
        
        payments_total = Decimal('0')
        for payment in payments:
            amount = Decimal(str(payment.get('amount', 0)))
            if amount <= 0:
                raise ValueError('Todos los montos de pago deben ser mayores a 0')
            payments_total += amount
        
        if payments_total != sale_total:
            raise ValueError(
                f'La suma de pagos (${payments_total}) no coincide con el total (${sale_total})'
            )
        
        # Step 5: Lock product_stock rows
        product_ids = [line['product_id'] for line in totals['lines']]
        
        placeholders = ', '.join([f':pid{i}' for i in range(len(product_ids))])
        lock_query = text(f"""
            SELECT ps.product_id, ps.on_hand_qty 
            FROM product_stock ps
            INNER JOIN product p ON p.id = ps.product_id
            WHERE ps.product_id IN ({placeholders})
              AND p.tenant_id = :tenant_id
            FOR UPDATE OF ps
        """)
        
        params = {f'pid{i}': pid for i, pid in enumerate(product_ids)}
        params['tenant_id'] = tenant_id
        locked_stocks = session.execute(lock_query, params).fetchall()
        
        stock_dict = {row[0]: Decimal(str(row[1])) for row in locked_stocks}
        
        # Step 6: Validate stock availability
        for line in totals['lines']:
            product_id = line['product_id']
            qty = line['qty']
            current_stock = stock_dict.get(product_id, Decimal('0'))
            
            if current_stock < qty:
                raise ValueError(
                    f'Stock insuficiente para "{line["product_name"]}". '
                    f'Disponible: {current_stock}, Solicitado: {qty}'
                )
        
        # Step 7: Create Sale
        sale = Sale(
            tenant_id=tenant_id,
            datetime=datetime.now(),
            total=sale_total,
            status=SaleStatus.CONFIRMED,
            idempotency_key=idempotency_key
        )
        session.add(sale)
        session.flush()
        
        # Step 8: Create SaleLines (with final prices after discounts)
        for line in totals['lines']:
            # Calculate final unit price after discount
            # This preserves the discount in the historical record
            final_unit_price = (line['line_total'] / line['qty']).quantize(Decimal('0.01'))
            
            sale_line = SaleLine(
                sale_id=sale.id,
                product_id=line['product_id'],
                qty=line['qty'],
                unit_price=final_unit_price,  # Price after discount
                line_total=line['line_total']
            )
            session.add(sale_line)
        
        # Step 9: Create SalePayments
        for payment in payments:
            method = payment['method'].upper()
            amount = Decimal(str(payment['amount']))
            
            # Validate payment method
            if method not in ['CASH', 'TRANSFER', 'CARD']:
                raise ValueError(f'MÃ©todo de pago invÃ¡lido: {method}')
            
            sale_payment = SalePayment(
                sale_id=sale.id,
                payment_method=method,
                amount=amount,
                amount_received=Decimal(str(payment.get('amount_received', 0))) if method == 'CASH' else None,
                change_amount=Decimal(str(payment.get('change_amount', 0))) if method == 'CASH' else None
            )
            session.add(sale_payment)
        
        # Step 10: Create StockMove (OUT)
        stock_move = StockMove(
            tenant_id=tenant_id,
            date=datetime.now(),
            type=StockMoveType.OUT,
            reference_type=StockReferenceType.SALE,
            reference_id=sale.id,
            notes=f'Venta #{sale.id}'
        )
        session.add(stock_move)
        session.flush()
        
        # Step 11: Create StockMoveLines
        for line in totals['lines']:
            product = session.query(Product).get(line['product_id'])
            
            stock_move_line = StockMoveLine(
                stock_move_id=stock_move.id,
                product_id=line['product_id'],
                qty=line['qty'],
                uom_id=product.uom_id,
                unit_cost=None
            )
            session.add(stock_move_line)
        
        # Step 12: Create FinanceLedger entries (one per payment)
        for payment in payments:
            method = payment['method'].upper()
            amount = Decimal(str(payment['amount']))
            payment_method_normalized = normalize_payment_method(method)
            
            ledger_entry = FinanceLedger(
                tenant_id=tenant_id,
                datetime=datetime.now(),
                type=LedgerType.INCOME,
                amount=amount,
                category='Ventas',
                reference_type=LedgerReferenceType.SALE,
                reference_id=sale.id,
                notes=f'Ingreso por venta #{sale.id} ({method})',
                payment_method=payment_method_normalized
            )
            session.add(ledger_entry)
        
        # Step 13: Delete draft
        session.delete(draft)
        
        # Commit transaction
        session.commit()
        
        # Invalidate cache
        try:
            from app.services.cache_service import get_cache
            cache = get_cache()
            cache.invalidate_module(tenant_id, 'balance')
        except Exception:
            pass
        
        return sale.id
        
    except ValueError:
        session.rollback()
        raise
        
    except Exception as e:
        session.rollback()
        raise Exception(f'Error al confirmar venta: {str(e)}')
