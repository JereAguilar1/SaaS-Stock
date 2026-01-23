"""
Audit logging service for tracking critical actions.
PASO 6: Roles Avanzados
"""
from app.models.audit_log import AuditLog, AuditAction
from flask import request, g
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def log_action(
    session,
    action: AuditAction,
    resource_type: str = None,
    resource_id: int = None,
    details: dict = None
):
    """
    Log an auditable action to the database.
    
    Args:
        session: Database session
        action: AuditAction enum value
        resource_type: Type of resource affected (e.g., 'product', 'sale')
        resource_id: ID of the affected resource
        details: Dict with additional details (will be JSON encoded)
    """
    try:
        # Get current user and tenant from Flask g context
        user_id = g.get('user').id if g.get('user') else None
        tenant_id = g.get('tenant_id')
        
        if not user_id or not tenant_id:
            logger.warning(f"Cannot log action {action}: missing user_id or tenant_id")
            return
        
        # Get request metadata
        ip_address = request.remote_addr if request else None
        user_agent = request.headers.get('User-Agent', '')[:255] if request else None
        
        # Serialize details to JSON
        details_json = None
        if details:
            try:
                details_json = json.dumps(details, default=str)
            except Exception as e:
                logger.warning(f"Failed to serialize audit details: {e}")
                details_json = str(details)
        
        # Create audit log entry
        audit_entry = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details_json,
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.utcnow()
        )
        
        session.add(audit_entry)
        # Note: Caller is responsible for committing the session
        
        logger.info(f"Audit log created: {action.value} by user {user_id} on {resource_type} {resource_id}")
        
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        # Don't raise exception - audit failures should not break business logic


def get_audit_logs(
    session,
    tenant_id: int,
    limit: int = 100,
    offset: int = 0,
    action_filter: AuditAction = None,
    user_id_filter: int = None,
    resource_type_filter: str = None
):
    """
    Retrieve audit logs for a tenant with optional filters.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        limit: Max number of results
        offset: Pagination offset
        action_filter: Filter by specific action
        user_id_filter: Filter by user
        resource_type_filter: Filter by resource type
    
    Returns:
        List of AuditLog objects
    """
    query = session.query(AuditLog).filter(
        AuditLog.tenant_id == tenant_id
    )
    
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    
    if user_id_filter:
        query = query.filter(AuditLog.user_id == user_id_filter)
    
    if resource_type_filter:
        query = query.filter(AuditLog.resource_type == resource_type_filter)
    
    query = query.order_by(AuditLog.created_at.desc())
    query = query.limit(limit).offset(offset)
    
    return query.all()


def get_user_activity(session, tenant_id: int, user_id: int, limit: int = 50):
    """
    Get recent activity for a specific user.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        user_id: User ID
        limit: Max results
    
    Returns:
        List of AuditLog objects
    """
    return get_audit_logs(
        session=session,
        tenant_id=tenant_id,
        user_id_filter=user_id,
        limit=limit
    )
