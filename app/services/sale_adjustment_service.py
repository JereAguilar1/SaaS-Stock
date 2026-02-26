"""Sale Adjustment Service - Multi-Tenant.
Allows correction of confirmed sales with traceability.
"""

from decimal import Decimal
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models import (
    Sale, SaleLine, SaleStatus, Product, ProductStock,
    StockMove, StockMoveLine, StockMoveType, StockReferenceType,
    FinanceLedger, LedgerType, LedgerReferenceType, normalize_payment_method
)
from app.exceptions import BusinessLogicError, NotFoundError, InsufficientStockError


def adjust_sale(sale_id: int, new_lines_data: List[Dict[str, Any]], session: Session, tenant_id: int) -> None:
    """
    Adjust a confirmed sale by modifying its lines (tenant-scoped).
    Creates compensating stock moves and ledger entries for traceability.
    """
    try:
        session.begin_nested()
        
        # 1. Lock sale and validate tenant
        sale = session.query(Sale).filter(
            Sale.id == sale_id,
            Sale.tenant_id == tenant_id
        ).with_for_update().first()
        
        if not sale:
            raise NotFoundError(f'Venta #{sale_id} no encontrada.')
        
        if sale.status != SaleStatus.CONFIRMED:
            raise BusinessLogicError(f'Solo se pueden ajustar ventas confirmadas.')
        
        # 2. Map current state
        old_lines = {line.product_id: line for line in sale.lines}
        old_total = sale.total
        
        # 3. Batch fetch products and validate
        new_prod_ids = [int(l['product_id']) for l in new_lines_data]
        all_involved_ids = list(set(new_prod_ids) | set(old_lines.keys()))
        
        products = session.query(Product).filter(
            Product.id.in_(all_involved_ids),
            Product.tenant_id == tenant_id
        ).all()
        products_dict = {p.id: p for p in products}
        
        if len(products_dict) < len(set(new_prod_ids)):
             raise NotFoundError('Uno o más productos no encontrados.')

        # 4. Calculate deltas and build new lines map
        new_lines_map = {}
        deltas = {}
        
        for line_data in new_lines_data:
            pid = int(line_data['product_id'])
            qty = Decimal(str(line_data['qty']))
            if qty <= 0: 
                raise BusinessLogicError(f'La cantidad debe ser mayor a 0 para el producto {pid}.')
            
            product = products_dict[pid]
            if not product.active: 
                raise BusinessLogicError(f'El producto "{product.name}" está inactivo.')
            
            # Keep original unit price if exists, else current
            unit_price = old_lines[pid].unit_price if pid in old_lines else product.sale_price
            
            if pid in new_lines_map:
                new_lines_map[pid]['qty'] += qty
            else:
                new_lines_map[pid] = {'qty': qty, 'unit_price': unit_price}

        # Calculate deltas for stock adjustment
        for pid in all_involved_ids:
            old_qty = old_lines[pid].qty if pid in old_lines else Decimal('0')
            new_qty = new_lines_map[pid]['qty'] if pid in new_lines_map else Decimal('0')
            delta = new_qty - old_qty
            if delta != 0:
                deltas[pid] = delta

        # 5. Lock and validate stock for increases
        if deltas:
            pids_to_lock = sorted(deltas.keys())
            stocks = session.query(ProductStock).filter(
                ProductStock.product_id.in_(pids_to_lock)
            ).with_for_update().all()
            stocks_dict = {s.product_id: s for s in stocks}
            
            for pid, delta in deltas.items():
                if delta > 0: # Sold more -> needs more stock
                    product = products_dict[pid]
                    if not product.is_unlimited_stock:
                        stock = stocks_dict.get(pid)
                        if not stock or stock.on_hand_qty < delta:
                            raise InsufficientStockError(f'Stock insuficiente para "{product.name}" (necesita {delta} más).')

        # 6. Rebuild Sale Lines
        session.query(SaleLine).filter(SaleLine.sale_id == sale_id).delete()
        new_total = Decimal('0.00')
        for pid, data in new_lines_map.items():
            line_total = (data['qty'] * data['unit_price']).quantize(Decimal('0.01'))
            session.add(SaleLine(
                sale_id=sale_id, product_id=pid, qty=data['qty'],
                unit_price=data['unit_price'], line_total=line_total
            ))
            new_total += line_total
            
        sale.total = new_total.quantize(Decimal('0.01'))
        session.flush()

        # 7. Create Adjustment Stock Move
        if deltas:
            move = StockMove(
                tenant_id=tenant_id, date=datetime.now(), type=StockMoveType.ADJUST,
                reference_type=StockReferenceType.MANUAL, reference_id=sale_id,
                notes=f'Ajuste automático de venta #{sale_id}'
            )
            session.add(move)
            session.flush()
            for pid, delta in deltas.items():
                if products_dict[pid].is_unlimited_stock:
                    continue  # Don't adjust stock for unlimited products
                session.add(StockMoveLine(
                    stock_move_id=move.id, product_id=pid, qty=-delta, # Sold more means stock moves OUT (-)
                    uom_id=products_dict[pid].uom_id
                ))

        # 8. Create Ledger Adjustment
        diff = new_total - old_total
        if diff != 0:
            session.add(FinanceLedger(
                tenant_id=tenant_id, datetime=datetime.now(),
                type=LedgerType.INCOME if diff > 0 else LedgerType.EXPENSE,
                amount=abs(diff).quantize(Decimal('0.01')), category='Ajuste de Venta',
                reference_type=LedgerReferenceType.MANUAL, reference_id=sale_id,
                notes=f'Ajuste {"positivo" if diff > 0 else "negativo"} de venta #{sale_id}',
                payment_method=normalize_payment_method(None)
            ))

        session.commit()
    except (BusinessLogicError, NotFoundError, InsufficientStockError) as e:
        session.rollback()
        raise e
    except Exception:
        session.rollback()
        raise


def get_sale_summary(sale_id: int, session: Session, tenant_id: int) -> Dict[str, Any]:
    """Get detailed summary of a sale for display/editing (tenant-scoped)."""
    sale = session.query(Sale).filter(Sale.id == sale_id, Sale.tenant_id == tenant_id).first()
    if not sale: 
        raise NotFoundError(f'Venta #{sale_id} no encontrada.')
    
    return {
        'id': sale.id,
        'datetime': sale.datetime,
        'total': sale.total,
        'status': sale.status,
        'lines': [
            {
                'product_id': l.product_id,
                'product_name': l.product.name,
                'product_sku': l.product.sku,
                'product_uom': l.product.uom.symbol if l.product.uom else '-',
                'qty': l.qty,
                'unit_price': l.unit_price,
                'line_total': l.line_total,
                'current_stock': l.product.on_hand_qty
            } for l in sale.lines
        ]
    }
