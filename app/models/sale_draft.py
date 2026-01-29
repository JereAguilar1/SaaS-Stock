"""Sale Draft model for persistent cart (multi-tenant)."""
from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class SaleDraft(Base):
    """
    Sale Draft - Persistent cart for POS.
    
    Allows cart to survive page refreshes and provides a robust
    foundation for the POS workflow.
    
    One draft per user per tenant (enforced by UNIQUE constraint).
    """
    
    __tablename__ = 'sale_draft'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey('app_user.id'), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Global discount (applied to entire cart)
    discount_type = Column(String(10))  # 'PERCENT' or 'AMOUNT' or NULL
    discount_value = Column(Numeric(10, 2), default=0)
    
    # Relationships
    tenant = relationship('Tenant')
    user = relationship('AppUser')
    lines = relationship('SaleDraftLine', back_populates='draft', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f"<SaleDraft(id={self.id}, tenant_id={self.tenant_id}, user_id={self.user_id})>"
