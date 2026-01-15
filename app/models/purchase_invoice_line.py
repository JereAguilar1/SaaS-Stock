"""Purchase Invoice Line model."""
from sqlalchemy import Column, BigInteger, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class PurchaseInvoiceLine(Base):
    """Purchase Invoice Line (detalle de boleta de compra)."""
    
    __tablename__ = 'purchase_invoice_line'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    invoice_id = Column(BigInteger, ForeignKey('purchase_invoice.id'), nullable=False)
    product_id = Column(BigInteger, ForeignKey('product.id'), nullable=False)
    qty = Column(Numeric(12, 3), nullable=False)
    unit_cost = Column(Numeric(14, 4), nullable=False)
    line_total = Column(Numeric(14, 2), nullable=False)
    
    # Relationships
    invoice = relationship('PurchaseInvoice', back_populates='lines')
    product = relationship('Product')
    
    def __repr__(self):
        return f"<PurchaseInvoiceLine(id={self.id}, product_id={self.product_id}, qty={self.qty})>"

