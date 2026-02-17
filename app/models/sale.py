"""Sale model."""
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
from app.database import Base
import enum


class SaleStatus(enum.Enum):
    """Sale status enum."""
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentStatus(str, enum.Enum):
    """Payment status for cuenta corriente."""
    PAID = 'paid'
    PENDING = 'pending'
    PARTIAL = 'partial'


class Sale(Base):
    """Sale (venta confirmada)."""
    
    __tablename__ = 'sale'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    total = Column(Numeric(10, 2), nullable=False)
    status = Column(Enum(SaleStatus, name='sale_status'), nullable=False, default=SaleStatus.CONFIRMED)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Idempotency key to prevent duplicate sales on double-submit
    idempotency_key = Column(String(64), unique=True, nullable=True, index=True)
    
    customer_id = Column(BigInteger, ForeignKey('customer.id'), nullable=True)
    
    # Cuenta corriente (payment tracking)
    payment_status = Column(String(20), default='paid', nullable=False)
    amount_paid = Column(Numeric(10, 2), nullable=False, default=0, server_default='0')
    
    # Relationships
    tenant = relationship('Tenant')
    customer = relationship('Customer', back_populates='sales')
    lines = relationship('SaleLine', back_populates='sale', cascade='all, delete-orphan')
    payments = relationship('SalePayment', back_populates='sale', cascade='all, delete-orphan')
    
    @hybrid_property
    def amount_due(self):
        """Amount still owed: total - amount_paid."""
        return (self.total or 0) - (self.amount_paid or 0)
    
    @hybrid_property
    def payment_method(self):
        """Derive main payment method from payments relationship."""
        if not self.payments:
            return 'CUENTA_CORRIENTE'
        # Return the first method found (simplification for list view)
        return self.payments[0].payment_method

    def __repr__(self):
        return f"<Sale(id={self.id}, total={self.total}, status={self.status.value})>"

