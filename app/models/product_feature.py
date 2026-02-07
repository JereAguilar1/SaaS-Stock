"""Product Feature model."""
from sqlalchemy import Column, BigInteger, String, ForeignKey
from app.database import Base


class ProductFeature(Base):
    """Product Feature model (custom specifications)."""
    
    __tablename__ = 'product_feature'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False)
    title = Column(String(100), nullable=False)  # e.g., "Color"
    description = Column(String(255), nullable=False)  # e.g., "Space Gray"

    def __repr__(self):
        return f"<ProductFeature(id={self.id}, product_id={self.product_id}, title='{self.title}')>"
