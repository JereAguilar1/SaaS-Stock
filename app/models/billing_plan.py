"""Billing Plan model for Mercado Pago subscriptions."""
from sqlalchemy import Column, BigInteger, String, Numeric, Integer, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base


class BillingPlan(Base):
    """Planes de facturación disponibles para suscripción."""
    __tablename__ = 'billing_plan'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(200), nullable=False)
    price_amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default='ARS')
    frequency = Column(Integer, nullable=False, default=1)
    frequency_type = Column(String(20), nullable=False, default='months')
    active = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    def __repr__(self):
        return f"<BillingPlan(code='{self.code}', name='{self.name}', price={self.price_amount})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'code': self.code,
            'name': self.name,
            'price_amount': float(self.price_amount),
            'currency': self.currency,
            'frequency': self.frequency,
            'frequency_type': self.frequency_type,
            'active': self.active
        }
