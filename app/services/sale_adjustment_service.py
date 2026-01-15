"""
Sale Adjustment Service (MEJORA 16) - Multi-Tenant

Allows correction of confirmed sales by:
- Adjusting quantities
- Adding/removing lines
- Creating compensating stock moves (ADJUST)
- Creating compensating ledger entries
"""

from decimal import Decimal
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import (
    Sale, SaleLine, SaleStatus, Product, ProductStock,
    StockMove, StockMoveLine, StockMoveType, StockReferenceType,
    FinanceLedger, LedgerType, LedgerReferenceType, normalize_payment_method
)


def adjust_sale(sale_id: int, new_lines: list, session: Session, tenant_id: int) -> None:
    """
    Adjust a confirmed sale by modifying its lines (tenant-scoped).
    
    Creates compensating stock moves and ledger entries for traceability.
    
    Args:
        sale_id: ID of the sale to adjust
        new_lines: List of dicts with {'product_id': int, 'qty': Decimal}
        session: SQLAlchemy session (must be in transaction)
        tenant_id: Tenant ID (REQUIRED for multi-tenant enforcement)
    
    Raises:
        ValueError: If validation fails
        Exception: For other errors
    
    Process:
        1. Lock sale and validate tenant
        2. Calculate delta qty per product
        3. Validate stock for increases (tenant-scoped)
        4. Delete old sale_lines and create new ones
        5. Update sale.total
        6. Create ADJUST stock_move with delta lines (tenant_id)
        7. Create compensating ledger entry (tenant_id)
    """
    
    try:
        session.begin_nested()
        
        # Step 1: Lock sale and validate tenant
        sale = session.query(Sale).filter(
            Sale.id == sale_id,
            Sale.tenant_id == tenant_id
        ).with_for_update().first()
        
        if not sale:
            raise ValueError(f'Venta con ID {sale_id} no encontrada o no pertenece a su negocio.')
        
        # Compare with Enum value
        if sale.status != SaleStatus.CONFIRMED:
            status_str = sale.status.value if hasattr(sale.status, 'value') else str(sale.status)
            raise ValueError(f'Solo se pueden ajustar ventas confirmadas. Estado actual: {status_str}')
        
        # Step 2: Read current lines and build map
        old_lines = {}
        for line in sale.lines:
            old_lines[line.product_id] = {
                'qty': line.qty,
                'unit_price': line.unit_price
            }
        
        old_total = sale.total
        
        # Step 3: Build new lines map and validate (tenant-scoped products)
        new_lines_map = {}
        products_cache = {}
        
        for line_data in new_lines:
            product_id = int(line_data['product_id'])
            qty = Decimal(str(line_data['qty']))
            
            if qty <= 0:
                raise ValueError(f'La cantidad debe ser mayor a 0 para producto ID {product_id}')
            
            # Get product and validate tenant
            if product_id not in products_cache:
                product = session.query(Product).filter(
                    Product.id == product_id,
                    Product.tenant_id == tenant_id
                ).first()
                
                if not product:
                    raise ValueError(f'Producto con ID {product_id} no encontrado o no pertenece a su negocio.')
                if not product.active:
                    raise ValueError(f'El producto "{product.name}" no está activo.')
                products_cache[product_id] = product
            else:
                product = products_cache[product_id]
            
            # Use original unit_price if product was in old sale, else use current sale_price
            if product_id in old_lines:
                unit_price = old_lines[product_id]['unit_price']
            else:
                unit_price = product.sale_price
            
            # Merge if duplicate
            if product_id in new_lines_map:
                new_lines_map[product_id]['qty'] += qty
            else:
                new_lines_map[product_id] = {
                    'qty': qty,
                    'unit_price': unit_price,
                    'product_name': product.name,
                    'product': product
                }
        
        # Step 4: Calculate deltas and validate stock (tenant-scoped)
        deltas = {}
        
        # Products in new lines
        for product_id, new_data in new_lines_map.items():
            old_qty = old_lines.get(product_id, {}).get('qty', Decimal('0'))
            delta_qty = new_data['qty'] - old_qty
            if delta_qty != 0:
                deltas[product_id] = delta_qty
        
        # Products removed (in old but not in new)
        for product_id, old_data in old_lines.items():
            if product_id not in new_lines_map:
                deltas[product_id] = -old_data['qty']  # Full return
        
        # Validate stock for increases (tenant-scoped via product join)
        for product_id, delta_qty in deltas.items():
            if delta_qty > 0:  # Selling more
                # Lock product_stock via join with Product for tenant validation
                product_stock = session.query(ProductStock).join(
                    Product, Product.id == ProductStock.product_id
                ).filter(
                    ProductStock.product_id == product_id,
                    Product.tenant_id == tenant_id
                ).with_for_update().first()
                
                if not product_stock:
                    raise ValueError(f'Stock no encontrado para producto ID {product_id}')
                
                # Check available stock
                if product_stock.on_hand_qty < delta_qty:
                    product = products_cache[product_id]
                    raise ValueError(
                        f'Stock insuficiente para "{product.name}". '
                        f'Necesita {delta_qty} adicionales, disponible: {product_stock.on_hand_qty}'
                    )
        
        # Step 5: Delete old sale_lines and create new ones
        session.query(SaleLine).filter(SaleLine.sale_id == sale_id).delete()
        
        # Create new lines
        new_total = Decimal('0.00')
        for product_id, line_data in new_lines_map.items():
            qty = line_data['qty']
            unit_price = line_data['unit_price']
            line_total = qty * unit_price
            
            sale_line = SaleLine(
                sale_id=sale_id,
                product_id=product_id,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            )
            session.add(sale_line)
            new_total += line_total
        
        # Step 6: Update sale.total
        sale.total = new_total
        session.flush()
        
        # Step 7: Create ADJUST stock_move if there are deltas (with tenant_id)
        if deltas:
            adjustment_datetime = datetime.now()
            
            stock_move = StockMove(
                tenant_id=tenant_id,  # CRITICAL
                date=adjustment_datetime,
                type=StockMoveType.ADJUST,
                reference_type=StockReferenceType.MANUAL,
                reference_id=sale_id,
                notes=f'Ajuste de venta #{sale_id} - Corrección de líneas'
            )
            session.add(stock_move)
            session.flush()
            
            # Create stock_move_lines for deltas
            # delta_qty > 0 means sold MORE -> reduce stock (negative qty)
            # delta_qty < 0 means sold LESS -> increase stock (positive qty)
            for product_id, delta_qty in deltas.items():
                product = products_cache[product_id]
                stock_adjustment_qty = -delta_qty
                
                stock_move_line = StockMoveLine(
                    stock_move_id=stock_move.id,
                    product_id=product_id,
                    qty=stock_adjustment_qty,
                    uom_id=product.uom_id,
                    unit_cost=None
                )
                session.add(stock_move_line)
        
        # Step 8: Create ledger adjustment (with tenant_id)
        diff = new_total - old_total
        
        if diff != 0:
            adjustment_datetime = datetime.now()
            payment_method_normalized = normalize_payment_method(None)
            
            if diff > 0:
                # Sold more -> additional INCOME
                ledger_entry = FinanceLedger(
                    tenant_id=tenant_id,  # CRITICAL
                    datetime=adjustment_datetime,
                    type=LedgerType.INCOME,
                    amount=abs(diff),
                    category='Ajuste de Venta',
                    reference_type=LedgerReferenceType.MANUAL,
                    reference_id=sale_id,
                    notes=f'Ajuste positivo de venta #{sale_id} (+${abs(diff)})',
                    payment_method=payment_method_normalized
                )
            else:
                # Sold less -> register as EXPENSE
                ledger_entry = FinanceLedger(
                    tenant_id=tenant_id,  # CRITICAL
                    datetime=adjustment_datetime,
                    type=LedgerType.EXPENSE,
                    amount=abs(diff),
                    category='Ajuste de Venta',
                    reference_type=LedgerReferenceType.MANUAL,
                    reference_id=sale_id,
                    notes=f'Ajuste negativo de venta #{sale_id} (-${abs(diff)})',
                    payment_method=payment_method_normalized
                )
            
            session.add(ledger_entry)
        
        # Commit nested transaction
        session.commit()
        
    except ValueError:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise


def get_sale_summary(sale_id: int, session: Session, tenant_id: int) -> dict:
    """
    Get detailed summary of a sale for display/editing (tenant-scoped).
    
    Args:
        sale_id: Sale ID
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant enforcement)
    
    Returns:
        dict with sale info, lines, and totals
    
    Raises:
        ValueError: If sale not found or doesn't belong to tenant
    """
    sale = session.query(Sale).filter(
        Sale.id == sale_id,
        Sale.tenant_id == tenant_id
    ).first()
    
    if not sale:
        raise ValueError(f'Venta con ID {sale_id} no encontrada o no pertenece a su negocio.')
    
    lines_data = []
    for line in sale.lines:
        lines_data.append({
            'product_id': line.product_id,
            'product_name': line.product.name,
            'product_sku': line.product.sku,
            'product_uom': line.product.uom.symbol if line.product.uom else '-',
            'qty': line.qty,
            'unit_price': line.unit_price,
            'line_total': line.line_total,
            'current_stock': line.product.on_hand_qty
        })
    
    return {
        'id': sale.id,
        'datetime': sale.datetime,
        'total': sale.total,
        'status': sale.status,
        'lines': lines_data
    }
