"""Mercado Pago Subscription model."""
from sqlalchemy import Column, BigInteger, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class MPSubscription(Base):
    """Suscripciones de Mercado Pago vinculadas a tenants."""
    __tablename__ = 'mp_subscription'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id', ondelete='CASCADE'), nullable=False, index=True)
    plan_id = Column(BigInteger, ForeignKey('billing_plan.id'), nullable=False)
    status = Column(String(20), nullable=False, default='PENDING', index=True)
    mp_preapproval_id = Column(String(100), unique=True, index=True)
    mp_init_point = Column(Text)
    started_at = Column(DateTime(timezone=True))
    cancelled_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    metadata_json = Column(JSONB, nullable=False, server_default='{}')
    
    # Relationships
    tenant = relationship('Tenant', backref='mp_subscriptions')
    plan = relationship('BillingPlan', backref='subscriptions')
    
    def __repr__(self):
        return f"<MPSubscription(tenant_id={self.tenant_id}, status='{self.status}', plan_id={self.plan_id})>"
    
    def to_dict(self):
        """Convert to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'tenant_id': self.tenant_id,
            'plan_id': self.plan_id,
            'status': self.status,
            'mp_preapproval_id': self.mp_preapproval_id,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'cancelled_at': self.cancelled_at.isoformat() if self.cancelled_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata_json
        }
    
    @property
    def is_active(self):
        """Check if subscription is active."""
        return self.status == 'ACTIVE'
