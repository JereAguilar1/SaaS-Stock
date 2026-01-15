"""UserTenant model - many-to-many relationship between users and tenants with roles."""
import enum
from sqlalchemy import Column, BigInteger, String, Boolean, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class UserRole(enum.Enum):
    """User roles within a tenant."""
    OWNER = 'OWNER'
    ADMIN = 'ADMIN'
    STAFF = 'STAFF'


class UserTenant(Base):
    """UserTenant model - links users to tenants with roles."""
    
    __tablename__ = 'user_tenant'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey('app_user.id'), nullable=False)
    tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=False)
    role = Column(String(20), nullable=False, default='STAFF')  # OWNER, ADMIN, STAFF
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    user = relationship('AppUser', back_populates='user_tenants')
    tenant = relationship('Tenant', back_populates='user_tenants')
    
    def __repr__(self):
        return f"<UserTenant(user_id={self.user_id}, tenant_id={self.tenant_id}, role='{self.role}')>"
    
    def is_owner(self):
        """Check if user is owner of tenant."""
        return self.role == UserRole.OWNER.value
    
    def is_admin(self):
        """Check if user is admin or owner."""
        return self.role in [UserRole.OWNER.value, UserRole.ADMIN.value]
