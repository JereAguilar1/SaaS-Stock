"""
Plan and PlanFeature models for dynamic subscription management.

This module defines the subscription plans available in the system and their
associated features/permissions. Plans are synchronized with Mercado Pago
for payment processing.
"""
from sqlalchemy import Column, BigInteger, String, Numeric, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Plan(Base):
    """
    Subscription plan definition.
    
    Represents a subscription tier (Basic, Intermediate, Pro) with pricing
    and Mercado Pago integration. Each plan has associated features that
    determine what the tenant can access.
    
    Relationship: One-to-Many with PlanFeature, One-to-Many with Subscription
    """
    __tablename__ = 'plans'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Plan Information
    name = Column(String(100), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    
    # Mercado Pago Integration
    mp_preapproval_plan_id = Column(String(255))
    
    # Pricing
    price = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), default='ARS')
    billing_frequency = Column(String(20), default='monthly')
    
    # Status
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    features = relationship('PlanFeature', back_populates='plan', cascade='all, delete-orphan', lazy='joined')
    subscriptions = relationship('Subscription', back_populates='plan')
    
    def __repr__(self):
        return f'<Plan id={self.id} code={self.code} price={self.price}>'
    
    @property
    def formatted_price(self):
        """Return formatted price with currency symbol."""
        return f"${self.price:,.2f}"
    
    @property
    def feature_count(self):
        """Return count of active features."""
        return sum(1 for f in self.features if f.is_active)
    
    def has_feature(self, feature_key):
        """
        Check if plan has a specific feature.
        
        Args:
            feature_key (str): Feature key to check
            
        Returns:
            bool: True if feature exists and is active
        """
        return any(
            f.feature_key == feature_key and f.is_active
            for f in self.features
        )
    
    def get_feature_value(self, feature_key, default=None):
        """
        Get the value of a specific feature.
        
        Args:
            feature_key (str): Feature key to retrieve
            default: Default value if feature not found
            
        Returns:
            str: Feature value or default
        """
        for feature in self.features:
            if feature.feature_key == feature_key and feature.is_active:
                return feature.feature_value
        return default


class PlanFeature(Base):
    """
    Feature/permission associated with a subscription plan.
    
    Features define what capabilities are available in each plan.
    Examples: 'max_users', 'module_sales', 'api_access', etc.
    
    Relationship: Many-to-One with Plan
    """
    __tablename__ = 'plan_features'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    plan_id = Column(BigInteger, ForeignKey('plans.id', ondelete='CASCADE'), nullable=False)
    
    # Feature Definition
    feature_key = Column(String(100), nullable=False)
    feature_value = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    plan = relationship('Plan', back_populates='features')
    
    def __repr__(self):
        return f'<PlanFeature plan_id={self.plan_id} key={self.feature_key} value={self.feature_value}>'
    
    @property
    def is_boolean_feature(self):
        """Check if feature is a boolean (true/false)."""
        return self.feature_value and self.feature_value.lower() in ('true', 'false')
    
    @property
    def is_numeric_feature(self):
        """Check if feature is numeric."""
        if not self.feature_value:
            return False
        try:
            float(self.feature_value)
            return True
        except ValueError:
            return False
    
    @property
    def boolean_value(self):
        """Get feature value as boolean."""
        if self.is_boolean_feature:
            return self.feature_value.lower() == 'true'
        return False
    
    @property
    def numeric_value(self):
        """Get feature value as number."""
        if self.is_numeric_feature:
            try:
                return float(self.feature_value)
            except ValueError:
                return None
        return None
