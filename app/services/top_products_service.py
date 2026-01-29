from decimal import Decimal
from datetime import datetime, timedelta
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
        list of objects (DTOs) compatible with Product model interface:
        - id, name, sale_price, on_hand_qty, image_url, sku, barcode
    """
    try:
        # Calculate date threshold in Python (safer than SQL interval casting)
        cutoff_date = datetime.now() - timedelta(days=90)
        
        # Query for top selling products (tenant-scoped)
        query = (
            session.query(
                Product.id.label('product_id'),
                Product.name.label('name'),
                Product.sale_price.label('sale_price'),
                Product.image_path.label('image_path'),
                Product.sku.label('sku'),
                Product.barcode.label('barcode'),
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
            .filter(Sale.datetime >= cutoff_date) # Last 90 days
            .group_by(
                Product.id,
                Product.name,
                Product.sale_price,
                Product.image_path,
                Product.sku,
                Product.barcode,
                ProductStock.on_hand_qty
            )
            .order_by(desc('total_sold'))
            .limit(limit)
        )
        
        results = query.all()
        
        # Helper class to mimic Product model interface for templates
        class ProductDTO:
            def __init__(self, row):
                self.id = row.product_id
                self.name = row.name
                self.sale_price = row.sale_price
                self.sku = row.sku
                self.barcode = row.barcode
                self.on_hand_qty = row.stock if row.stock is not None else Decimal('0')
                self.image_path = row.image_path
                
            @property
            def image_url(self):
                if not self.image_path:
                    return None
                
                # Logic copied from Product model
                if self.image_path.startswith(('http://', 'https://')):
                    return self.image_path
                    
                from flask import current_app
                public_url = current_app.config.get('S3_PUBLIC_URL', 'http://localhost:9000')
                bucket = current_app.config.get('S3_BUCKET', 'uploads')
                
                base = public_url.rstrip('/')
                collection = bucket.strip('/')
                path = self.image_path.lstrip('/')
                
                return f"{base}/{collection}/{path}"

        # Convert to list of DTOs
        top_products = [ProductDTO(row) for row in results]
        
        return top_products, False
        
    except Exception as e:
        # Return empty list on error
        from flask import current_app
        current_app.logger.error(f"Error getting top selling products: {e}", exc_info=True)
        return [], True
