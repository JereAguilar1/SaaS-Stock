"""Sale Line model."""
from sqlalchemy import Column, BigInteger, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class SaleLine(Base):
    """Sale Line (detalle de venta)."""
    
    __tablename__ = 'sale_line'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sale_id = Column(BigInteger, ForeignKey('sale.id'), nullable=False)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False)
    qty = Column(Numeric(10, 2), nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    line_total = Column(Numeric(10, 2), nullable=False)
    
    # Relationships
    sale = relationship('Sale', back_populates='lines')
    product = relationship('Product')
    
    def __repr__(self):
        return f"<SaleLine(id={self.id}, product_id={self.product_id}, qty={self.qty})>"

