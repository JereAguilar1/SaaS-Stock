"""Quote model for presupuestos/cotizaciones."""
import enum
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, Date, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class QuoteStatus(enum.Enum):
    """Quote status enum."""
    DRAFT = "DRAFT"
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    CANCELED = "CANCELED"


class Quote(Base):
    """
    Quote (Presupuesto/Cotización).
    
    A quote can be converted to a sale, at which point its status becomes ACCEPTED
    and sale_id is populated.
    """
    
    __tablename__ = 'quote'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    quote_number = Column(String(64), nullable=False)
    status = Column(String(20), nullable=False, default='DRAFT')
    issued_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    valid_until = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    payment_method = Column(String(20), nullable=True)  # CASH, TRANSFER
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)
    sale_id = Column(BigInteger, ForeignKey('sale.id'), nullable=True, unique=True)
    customer_name = Column(String(255), nullable=False)  # MEJORA 14
    customer_phone = Column(String(50), nullable=True)  # MEJORA 14
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    tenant = relationship('Tenant')
    lines = relationship('QuoteLine', back_populates='quote', cascade='all, delete-orphan')
    sale = relationship('Sale', foreign_keys=[sale_id], uselist=False)
    
    def __repr__(self):
        return f"<Quote(id={self.id}, number='{self.quote_number}', status='{self.status}', total={self.total_amount})>"
    
    @property
    def is_expired(self):
        """Check if quote is expired (calculated, not stored)."""
        from datetime import date
        if self.status in ['DRAFT', 'SENT'] and self.valid_until:
            return date.today() > self.valid_until
        return False
    
    @property
    def is_convertible(self):
        """Check if quote can be converted to sale."""
        return (
            self.status in ['DRAFT', 'SENT'] and
            self.sale_id is None and
            not self.is_expired
        )
