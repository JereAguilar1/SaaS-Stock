"""
Audit Log model for tracking critical actions in the system.
PASO 6: Roles Avanzados
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum


class AuditAction(enum.Enum):
    """Enumeration of auditable actions."""
    # User management
    USER_INVITED = "USER_INVITED"
    USER_ACCEPTED_INVITE = "USER_ACCEPTED_INVITE"
    USER_ROLE_CHANGED = "USER_ROLE_CHANGED"
    USER_REMOVED = "USER_REMOVED"
    USER_LOGIN = "USER_LOGIN"
    USER_LOGOUT = "USER_LOGOUT"
    
    # Product management
    PRODUCT_CREATED = "PRODUCT_CREATED"
    PRODUCT_UPDATED = "PRODUCT_UPDATED"
    PRODUCT_DELETED = "PRODUCT_DELETED"
    
    # Sales
    SALE_CREATED = "SALE_CREATED"
    SALE_CANCELLED = "SALE_CANCELLED"
    
    # Quotes
    QUOTE_CREATED = "QUOTE_CREATED"
    QUOTE_CONVERTED = "QUOTE_CONVERTED"
    QUOTE_CANCELLED = "QUOTE_CANCELLED"
    
    # Invoices
    INVOICE_CREATED = "INVOICE_CREATED"
    INVOICE_PAID = "INVOICE_PAID"
    INVOICE_CANCELLED = "INVOICE_CANCELLED"
    
    # Finance
    LEDGER_ENTRY_CREATED = "LEDGER_ENTRY_CREATED"
    LEDGER_ENTRY_DELETED = "LEDGER_ENTRY_DELETED"
    
    # Settings
    SETTINGS_CHANGED = "SETTINGS_CHANGED"


from app.database import Base

class AuditLog(Base):
    """
    Audit log for tracking user actions.
    Multi-tenant: filtered by tenant_id.
    """
    __tablename__ = 'audit_log'
    
    id = Column(Integer, primary_key=True)
    tenant_id = Column(Integer, ForeignKey('tenant.id'), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey('app_user.id'), nullable=False)
    action = Column(SQLEnum(AuditAction), nullable=False, index=True)
    resource_type = Column(String(50))  # e.g., 'product', 'sale', 'user'
    resource_id = Column(Integer)  # ID of the affected resource
    details = Column(Text)  # JSON or text with additional details
    ip_address = Column(String(45))  # IPv4 or IPv6
    user_agent = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Relationships
    tenant = relationship('Tenant', backref='audit_logs')
    user = relationship('AppUser', backref='audit_logs')
    
    def __repr__(self):
        return f"<AuditLog {self.action.value} by user {self.user_id} at {self.created_at}>"
