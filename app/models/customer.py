"""Customer model."""
from sqlalchemy import Column, BigInteger, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Customer(Base):
    """Customer (cliente)."""
    
    __tablename__ = 'customer'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    name = Column(String(200), nullable=False)
    tax_id = Column(String(50), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    active = Column(Boolean, nullable=False, server_default='true')
    is_default = Column(Boolean, nullable=False, server_default='false')
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    tenant = relationship('Tenant')
    sales = relationship('Sale', back_populates='customer')
    
    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}', is_default={self.is_default})>"
