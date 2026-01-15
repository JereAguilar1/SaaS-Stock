"""Supplier model."""
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Supplier(Base):
    """Supplier (proveedor)."""
    
    __tablename__ = 'supplier'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    name = Column(String, nullable=False)
    tax_id = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    email = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    tenant = relationship('Tenant')
    invoices = relationship('PurchaseInvoice', back_populates='supplier')
    
    def __repr__(self):
        return f"<Supplier(id={self.id}, name='{self.name}')>"

