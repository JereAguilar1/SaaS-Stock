"""Purchase Invoice Payment model."""
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class PurchaseInvoicePayment(Base):
    """Payment for a purchase invoice."""
    
    __tablename__ = 'purchase_invoice_payment'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    invoice_id = Column(BigInteger, ForeignKey('purchase_invoice.id'), nullable=False)
    payment_method = Column(String(20), nullable=False)  # CASH, TRANSFER, CARD
    amount = Column(Numeric(12, 2), nullable=False)
    paid_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_by = Column(BigInteger, ForeignKey('app_user.id'), nullable=True)
    
    # Relationships
    invoice = relationship('PurchaseInvoice', back_populates='payments')
    tenant = relationship('Tenant')
    user = relationship('AppUser')
    
    def __repr__(self):
        return f"<PurchaseInvoicePayment(id={self.id}, amount={self.amount}, invoice={self.invoice_id})>"
