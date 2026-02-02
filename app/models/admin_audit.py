"""
Admin audit log model for tracking sensitive admin actions.
"""
from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AdminAuditLog(Base):
    """
    Audit trail for all sensitive admin actions.
    
    Tracks impersonation, tenant suspension, and other critical operations.
    """
    __tablename__ = 'admin_audit_logs'
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Who performed the action
    admin_user_id = Column(BigInteger, ForeignKey('admin_users.id'), nullable=False)
    
    # What action was performed
    action = Column(String(100), nullable=False)
    
    # Target tenant (if applicable)
    target_tenant_id = Column(BigInteger, ForeignKey('tenant.id'), nullable=True)
    
    # Additional details in JSON format
    details = Column(JSONB, nullable=True)
    
    # Network information
    ip_address = Column(String(45), nullable=True)
    
    # When it happened
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    
    # Relationships
    admin_user = relationship('AdminUser', foreign_keys=[admin_user_id])
    tenant = relationship('Tenant', foreign_keys=[target_tenant_id])
    
    def __repr__(self):
        return f'<AdminAuditLog id={self.id} action={self.action} admin_id={self.admin_user_id}>'
    
    @staticmethod
    def log_action(admin_user_id, action, target_tenant_id=None, details=None, ip_address=None):
        """
        Helper method to create audit log entries.
        
        Args:
            admin_user_id: ID of the admin user performing the action
            action: Action type (e.g., 'IMPERSONATION_START', 'SUSPEND_TENANT')
            target_tenant_id: Optional tenant ID if action targets a specific tenant
            details: Optional dict with additional context
            ip_address: Optional IP address of the admin user
        
        Returns:
            AdminAuditLog instance (not committed)
        """
        return AdminAuditLog(
            admin_user_id=admin_user_id,
            action=action,
            target_tenant_id=target_tenant_id,
            details=details,
            ip_address=ip_address
        )


# Common action types (for reference)
class AuditAction:
    """Constants for common audit actions."""
    IMPERSONATION_START = 'IMPERSONATION_START'
    IMPERSONATION_END = 'IMPERSONATION_END'
    SUSPEND_TENANT = 'SUSPEND_TENANT'
    REACTIVATE_TENANT = 'REACTIVATE_TENANT'
    UPDATE_SUBSCRIPTION = 'UPDATE_SUBSCRIPTION'
    REGISTER_PAYMENT = 'REGISTER_PAYMENT'
    CREATE_ADMIN_USER = 'CREATE_ADMIN_USER'
