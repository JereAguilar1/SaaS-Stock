"""Product Packaging model."""
from sqlalchemy import Column, BigInteger, String, Numeric, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class ProductPackaging(Base):
    """
    Product Packaging model (e.g., Box of 12, Case of 24).
    Used for fractional sales and different presentation units.
    """
    __tablename__ = 'product_packaging'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False)
    name = Column(String(100), nullable=False)  # e.g., "Caja x 12"
    quantity = Column(Numeric(12, 3), nullable=False)  # e.g., 12
    barcode = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    product = relationship('Product', backref='packagings')
    
    def __repr__(self):
        return f"<ProductPackaging(id={self.id}, name='{self.name}', qty={self.quantity})>"
