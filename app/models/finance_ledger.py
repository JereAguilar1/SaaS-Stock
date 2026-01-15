"""Finance Ledger model."""
from sqlalchemy import Column, BigInteger, Numeric, DateTime, String, Text, Enum, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class LedgerType(enum.Enum):
    """Ledger type enum."""
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class LedgerReferenceType(enum.Enum):
    """Ledger reference type enum."""
    SALE = "SALE"
    INVOICE_PAYMENT = "INVOICE_PAYMENT"
    MANUAL = "MANUAL"


class PaymentMethod(enum.Enum):
    """Payment method enum (MEJORA 12)."""
    CASH = "CASH"
    TRANSFER = "TRANSFER"


def normalize_payment_method(value) -> str:
    """
    Normalize payment method value to string for DB storage.
    
    Args:
        value: Can be None, PaymentMethod enum, or string
    
    Returns:
        str: 'CASH' or 'TRANSFER'
    
    Raises:
        ValueError: If value is invalid
    """
    # Default to CASH if None
    if value is None:
        return 'CASH'
    
    # If it's already a PaymentMethod enum, extract the value
    if isinstance(value, PaymentMethod):
        return value.value
    
    # If it's a string, normalize and validate
    if isinstance(value, str):
        normalized = value.upper().strip()
        if normalized in ['CASH', 'TRANSFER']:
            return normalized
        raise ValueError(f"Invalid payment method: {value}. Must be 'CASH' or 'TRANSFER'.")
    
    # Fallback: try to convert to string and validate
    str_value = str(value).upper()
    if str_value in ['CASH', 'TRANSFER']:
        return str_value
    
    raise ValueError(f"Cannot normalize payment method: {value} (type: {type(value).__name__})")


class FinanceLedger(Base):
    """Finance Ledger (libro contable)."""
    
    __tablename__ = 'finance_ledger'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    datetime = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    type = Column(Enum(LedgerType, name='ledger_type'), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    category = Column(String, nullable=True)
    reference_type = Column(Enum(LedgerReferenceType, name='ledger_ref_type'), nullable=False)
    reference_id = Column(BigInteger, nullable=True)
    notes = Column(Text, nullable=True)
    payment_method = Column(String(20), nullable=False, default='CASH', server_default='CASH')  # MEJORA 12
    
    # Relationships
    tenant = relationship('Tenant')
    
    def __repr__(self):
        return f"<FinanceLedger(id={self.id}, type={self.type.value}, amount={self.amount})>"

