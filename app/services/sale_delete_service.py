"""Service for deleting sales with stock reversal - Multi-Tenant."""
from decimal import Decimal
from sqlalchemy import and_
from app.models import (
    Sale, SaleLine, StockMove, StockMoveLine, FinanceLedger,
    Product, ProductStock, SaleStatus, StockMoveType, StockReferenceType,
    LedgerReferenceType
)


def delete_sale_with_reversal(sale_id: int, session, tenant_id: int) -> dict:
    """
    Delete sale and reverse stock movements (tenant-scoped).
    
    Steps:
    1. Validate sale exists and belongs to tenant
    2. Validate sale can be deleted (status check)
    3. Begin transaction
    4. Reverse stock for each sale line (add back to inventory)
    5. Delete finance ledger entries
    6. Delete stock move and lines
    7. Delete sale lines
    8. Delete sale
    9. Commit transaction
    
    Args:
        sale_id: Sale ID to delete
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for security)
    
    Returns:
        dict with success message and details
    
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    
    try:
        # Step 1: Get sale and validate tenant ownership
        sale = session.query(Sale).filter(
            Sale.id == sale_id,
            Sale.tenant_id == tenant_id
        ).first()
        
        if not sale:
            raise ValueError(
                f'Venta #{sale_id} no encontrada o no pertenece a su negocio'
            )
        
        # Step 2: Validate sale can be deleted
        if sale.status == SaleStatus.CANCELLED:
            raise ValueError(
                f'La venta #{sale_id} ya está cancelada y no puede eliminarse'
            )
        
        # Step 3: Get all sale lines first (before deletion)
        sale_lines = session.query(SaleLine).filter(
            SaleLine.sale_id == sale_id
        ).all()
        
        if not sale_lines:
            raise ValueError(
                f'La venta #{sale_id} no tiene líneas de venta asociadas'
            )
        
        # Step 4: Reverse stock for each sale line
        reversed_products = []
        for line in sale_lines:
            # Get product and validate tenant
            product = session.query(Product).filter(
                Product.id == line.product_id,
                Product.tenant_id == tenant_id
            ).first()
            
            if not product:
                raise ValueError(
                    f'Producto ID {line.product_id} no encontrado o no pertenece a su negocio'
                )
            
            # Get product stock (lock for update)
            product_stock = session.query(ProductStock).filter(
                ProductStock.product_id == line.product_id
            ).with_for_update().first()
            
            if not product_stock:
                # Create stock record if it doesn't exist
                product_stock = ProductStock(
                    product_id=line.product_id,
                    on_hand_qty=Decimal('0')
                )
                session.add(product_stock)
                session.flush()
            
            # Add back the quantity (reverse the OUT movement)
            old_stock = product_stock.on_hand_qty
            product_stock.on_hand_qty += line.qty
            new_stock = product_stock.on_hand_qty
            
            reversed_products.append({
                'product_name': product.name,
                'qty': line.qty,
                'old_stock': old_stock,
                'new_stock': new_stock
            })
        
        # Step 5: Delete finance ledger entries (using enum)
        ledger_entries = session.query(FinanceLedger).filter(
            and_(
                FinanceLedger.reference_type == LedgerReferenceType.SALE,
                FinanceLedger.reference_id == sale_id,
                FinanceLedger.tenant_id == tenant_id
            )
        ).all()
        
        for entry in ledger_entries:
            session.delete(entry)
        
        # Step 6: Delete stock move and lines
        stock_moves = session.query(StockMove).filter(
            and_(
                StockMove.reference_type == StockReferenceType.SALE,
                StockMove.reference_id == sale_id,
                StockMove.tenant_id == tenant_id
            )
        ).all()
        
        for stock_move in stock_moves:
            # Delete stock move lines first (cascade should handle this, but explicit is better)
            stock_move_lines = session.query(StockMoveLine).filter(
                StockMoveLine.stock_move_id == stock_move.id
            ).all()
            
            for sml in stock_move_lines:
                session.delete(sml)
            
            session.delete(stock_move)
        
        # Step 7: Delete sale payments (if any)
        from app.models import SalePayment
        sale_payments = session.query(SalePayment).filter(
            SalePayment.sale_id == sale_id
        ).all()
        
        for payment in sale_payments:
            session.delete(payment)
        
        # Step 8: Delete sale lines
        for line in sale_lines:
            session.delete(line)
        
        # Step 9: Delete sale
        session.delete(sale)
        
        # Step 10: Commit transaction
        session.commit()
        
        # Invalidate cache
        try:
            from app.services.cache_service import get_cache
            cache = get_cache()
            cache.invalidate_module(tenant_id, 'balance')
        except Exception:
            pass  # Graceful degradation
        
        return {
            'success': True,
            'message': f'Venta #{sale_id} eliminada y stock restaurado correctamente',
            'sale_id': sale_id,
            'reversed_products': reversed_products
        }
        
    except ValueError:
        # Business logic errors - rollback and re-raise
        session.rollback()
        raise
        
    except Exception as e:
        # Other errors - rollback and re-raise
        session.rollback()
        raise Exception(f'Error al eliminar venta: {str(e)}')

