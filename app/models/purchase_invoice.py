"""Purchase Invoice model."""
from sqlalchemy import Column, BigInteger, String, Date, Numeric, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class InvoiceStatus(enum.Enum):
    """Invoice status enum."""
    PENDING = "PENDING"
    PAID = "PAID"


class PurchaseInvoice(Base):
    """Purchase Invoice (boleta/factura de proveedor)."""
    
    __tablename__ = 'purchase_invoice'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    supplier_id = Column(BigInteger, ForeignKey('supplier.id'), nullable=False)
    invoice_number = Column(String, nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    total_amount = Column(Numeric(14, 2), nullable=False)
    status = Column(Enum(InvoiceStatus, name='invoice_status'), nullable=False, default=InvoiceStatus.PENDING)
    paid_at = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    tenant = relationship('Tenant')
    supplier = relationship('Supplier', back_populates='invoices')
    lines = relationship('PurchaseInvoiceLine', back_populates='invoice', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<PurchaseInvoice(id={self.id}, invoice_number='{self.invoice_number}', status={self.status.value})>"

