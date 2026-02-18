"""
Subscription and Payment models for tenant monetization.
"""
from sqlalchemy import Column, BigInteger, String, Numeric, Date, DateTime, ForeignKey, CheckConstraint, Text, Boolean
from sqlalchemy.orm import relationship, backref
from sqlalchemy.sql import func
from app.database import Base


class Subscription(Base):
    """
    Tenant subscription plan and billing status.
    
    Relationship: One-to-One with Tenant
    """
    __tablename__ = 'tenant_subscriptions'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id', ondelete='CASCADE'), nullable=False, unique=True)
    
    # Plan and Status
    plan_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    
    # Plan Reference (new)
    plan_id = Column(BigInteger, ForeignKey('plans.id'))
    
    # Dates
    trial_ends_at = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    next_billing_date = Column(DateTime(timezone=True), nullable=True)
    
    # Pricing
    amount = Column(Numeric(10, 2), default=0.00)
    
    # Mercado Pago Integration (new)
    mp_subscription_id = Column(String(255))
    mp_payer_id = Column(String(255))
    mp_status = Column(String(50))
    auto_recurring = Column(Boolean, default=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    # Use backref to avoid circular import in Tenant model
    tenant = relationship('Tenant', backref=backref('subscription', uselist=False))
    plan = relationship('Plan', back_populates='subscriptions')
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("plan_type IN ('free', 'basic', 'pro')", name='check_plan_type'),
        CheckConstraint("status IN ('trial', 'active', 'past_due', 'canceled')", name='check_status'),
    )
    
    def __repr__(self):
        return f'<Subscription tenant_id={self.tenant_id} plan={self.plan_type} status={self.status}>'
    
    @property
    def is_trial(self):
        """Check if subscription is in trial period."""
        return self.status == 'trial'
    
    @property
    def is_active(self):
        """Check if subscription is active (trial or paid)."""
        return self.status in ('trial', 'active')
    
    @property
    def is_past_due(self):
        """Check if subscription payment is overdue."""
        return self.status == 'past_due'
    
    @property
    def is_canceled(self):
        """Check if subscription is canceled."""
        return self.status == 'canceled'


class Payment(Base):
    """
    Manual payment records for tenants.
    
    Registered by admin users for tracking tenant payments.
    """
    __tablename__ = 'tenant_payments'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id', ondelete='CASCADE'), nullable=False)
    
    # Payment Details
    amount = Column(Numeric(10, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    payment_method = Column(String(50), nullable=False, default='transfer')
    reference = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Status
    status = Column(String(20), nullable=False, default='paid')
    
    # Audit
    created_by = Column(BigInteger, ForeignKey('admin_users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    # Use backref to avoid circular import in Tenant model
    tenant = relationship('Tenant', backref=backref('payments', order_by='Payment.payment_date.desc()'))
    admin_user = relationship('AdminUser', foreign_keys=[created_by])
    
    # Table constraints
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'paid', 'void')", name='check_payment_status'),
        CheckConstraint("payment_method IN ('transfer', 'cash', 'stripe_manual', 'other')", name='check_payment_method'),
    )
    
    def __repr__(self):
        return f'<Payment id={self.id} tenant_id={self.tenant_id} amount={self.amount} status={self.status}>'
    
    @property
    def is_paid(self):
        """Check if payment is marked as paid."""
        return self.status == 'paid'
    
    @property
    def is_pending(self):
        """Check if payment is pending."""
        return self.status == 'pending'
