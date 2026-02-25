"""Sale Draft Line model for cart items (multi-tenant via draft)."""
from sqlalchemy import Column, BigInteger, Numeric, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SaleDraftLine(Base):
    """
    Sale Draft Line - Individual items in the cart.
    
    Each line represents a product with quantity and optional discount.
    """
    
    __tablename__ = 'sale_draft_line'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    draft_id = Column(BigInteger, ForeignKey('sale_draft.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False, index=True)
    
    qty = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=True)
    
    # Item-level discount (applied to this line only)
    discount_type = Column(String(10))  # 'PERCENT' or 'AMOUNT' or NULL
    discount_value = Column(Numeric(10, 2), default=0)
    
    # Relationships
    draft = relationship('SaleDraft', back_populates='lines')
    product = relationship('Product')
    
    def __repr__(self):
        return f"<SaleDraftLine(id={self.id}, product_id={self.product_id}, qty={self.qty})>"
