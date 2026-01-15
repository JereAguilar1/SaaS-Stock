"""Service for fetching top selling products - Multi-Tenant."""
from decimal import Decimal
from sqlalchemy import func, desc
from app.models import Product, Sale, SaleLine, ProductStock


def get_top_selling_products(session, tenant_id: int, limit=10):
    """
    Get top selling products based on total quantity sold (tenant-scoped).
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant filtering)
        limit: Maximum number of results (default 10)
    
    Returns:
        list of dicts with:
        - product_id
        - name
        - sale_price
        - stock (on_hand_qty)
        - total_sold
        - has_stock (bool)
        - image_path
    """
    try:
        # Query for top selling products (tenant-scoped)
        query = (
            session.query(
                Product.id.label('product_id'),
                Product.name.label('name'),
                Product.sale_price.label('sale_price'),
                Product.image_path.label('image_path'),
                func.coalesce(ProductStock.on_hand_qty, Decimal('0')).label('stock'),
                func.sum(SaleLine.qty).label('total_sold')
            )
            .join(SaleLine, SaleLine.product_id == Product.id)
            .join(Sale, Sale.id == SaleLine.sale_id)
            .outerjoin(ProductStock, ProductStock.product_id == Product.id)
            .filter(Sale.tenant_id == tenant_id)  # CRITICAL: tenant filter
            .filter(Sale.status == 'CONFIRMED')  # Only confirmed sales
            .filter(Product.tenant_id == tenant_id)  # CRITICAL: tenant filter
            .filter(Product.active == True)  # Only active products
            .group_by(
                Product.id,
                Product.name,
                Product.sale_price,
                Product.image_path,
                ProductStock.on_hand_qty
            )
            .order_by(desc('total_sold'))
            .limit(limit)
        )
        
        results = query.all()
        
        # Convert to list of dicts
        top_products = []
        for row in results:
            top_products.append({
                'product_id': row.product_id,
                'name': row.name,
                'sale_price': row.sale_price,
                'stock': row.stock if row.stock is not None else Decimal('0'),
                'total_sold': row.total_sold if row.total_sold is not None else Decimal('0'),
                'has_stock': (row.stock if row.stock is not None else Decimal('0')) > 0,
                'image_path': row.image_path
            })
        
        return top_products
        
    except Exception as e:
        # Return empty list on error
        print(f"Error getting top selling products: {e}")
        return []
