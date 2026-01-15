"""Sales service with transactional logic - Multi-Tenant."""
from decimal import Decimal
from datetime import datetime
from sqlalchemy import text
from app.models import (
    Product, ProductStock, Sale, SaleLine, 
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
        
        return sale.id
        
    except ValueError:
        # Business logic errors - rollback and re-raise
        session.rollback()
        raise
        
    except Exception as e:
        # Other errors - rollback and re-raise
        session.rollback()
        raise Exception(f'Error al confirmar venta: {str(e)}')
