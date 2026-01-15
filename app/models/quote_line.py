"""QuoteLine model for quote line items."""
from sqlalchemy import Column, BigInteger, String, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class QuoteLine(Base):
    """
    Quote Line (Línea de Presupuesto).
    
    Stores snapshot of product details at the time of quote creation
    to preserve pricing and product info even if changed later.
    """
    
    __tablename__ = 'quote_line'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    quote_id = Column(BigInteger, ForeignKey('quote.id'), nullable=False)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False)
    product_name_snapshot = Column(String(200), nullable=False)
    uom_snapshot = Column(String(16), nullable=True)
    qty = Column(Numeric(12, 3), nullable=False)
    unit_price = Column(Numeric(14, 2), nullable=False)
    line_total = Column(Numeric(14, 2), nullable=False)
    
    # Relationships
    quote = relationship('Quote', back_populates='lines')
    product = relationship('Product', foreign_keys=[product_id])
    
    def __repr__(self):
        return f"<QuoteLine(id={self.id}, quote_id={self.quote_id}, product='{self.product_name_snapshot}', qty={self.qty}, total={self.line_total})>"
