"""Tenant model - represents each business/organization using the platform."""
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Tenant(Base):
    """Tenant model - each business/organization."""
    
    __tablename__ = 'tenant'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slug = Column(String(80), nullable=False, unique=True)  # URL-safe identifier
    name = Column(String(200), nullable=False)  # Display name
    active = Column(Boolean, nullable=False, default=True)
    is_suspended = Column(Boolean, nullable=False, default=False)  # Admin can suspend tenant access
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user_tenants = relationship('UserTenant', back_populates='tenant')
    
    def __repr__(self):
        return f"<Tenant(id={self.id}, slug='{self.slug}', name='{self.name}')>"
