"""Product Stock model."""
from sqlalchemy import Column, BigInteger, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class ProductStock(Base):
    """Product Stock - 1:1 with Product."""
    
    __tablename__ = 'product_stock'
    
    product_id = Column(BigInteger, ForeignKey('product.id'), primary_key=True)
    on_hand_qty = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationship
    product = relationship('Product', back_populates='stock')
    
    def __repr__(self):
        return f"<ProductStock(product_id={self.product_id}, on_hand_qty={self.on_hand_qty})>"

