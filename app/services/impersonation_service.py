"""
Impersonation service for admin support functionality.

Allows admins to temporarily log in as a tenant owner for support purposes.
All impersonation actions are logged in the audit trail.
"""
from flask import session, g
from flask_login import login_user, logout_user
from app.database import db_session
from app.models import AppUser, AdminUser, Tenant, AdminAuditLog, AdminAuditAction


def is_impersonating():
    """
    Check if current session is in impersonation mode.
    
    Returns:
        bool: True if impersonating, False otherwise
    """
    return 'original_admin_id' in session


def get_original_admin():
    """
    Get the original admin user if impersonating.
    
    Returns:
        AdminUser or None: The original admin user, or None if not impersonating
    """
    if not is_impersonating():
        return None
    
    admin_id = session.get('original_admin_id')
    return db_session.query(AdminUser).filter_by(id=admin_id).first()


def start_impersonation(admin_user, tenant_id, ip_address=None):
    """
    Start impersonating a tenant as an admin user.
    
    This function:
    1. Validates the admin user
    2. Finds the tenant owner
    3. Saves the original admin session
    4. Logs the impersonation start
    5. Logs in as the tenant owner
    
    Args:
        admin_user: AdminUser instance performing the impersonation
        tenant_id: ID of the tenant to impersonate
        ip_address: Optional IP address of the admin
    
    Returns:
        tuple: (success: bool, message: str, redirect_url: str or None)
    
    Raises:
        ValueError: If already impersonating or tenant not found
    """
    # Prevent nested impersonation
    if is_impersonating():
        return False, "Ya estás impersonando un tenant. Sal del modo soporte primero.", None
    
    # Validate admin user
    if not isinstance(admin_user, AdminUser):
        return False, "Solo administradores pueden impersonar tenants.", None
    
    # Find tenant
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        return False, f"Tenant con ID {tenant_id} no encontrado.", None
    
    # Find tenant owner
    from app.models import UserTenant, UserRole
    owner_relation = db_session.query(UserTenant).filter_by(
        tenant_id=tenant_id,
        role=UserRole.OWNER
    ).first()
    
    if not owner_relation:
        return False, f"No se encontró el owner del tenant '{tenant.name}'.", None
    
    owner_user = db_session.query(AppUser).filter_by(id=owner_relation.user_id).first()
    if not owner_user:
        return False, f"Usuario owner no encontrado para tenant '{tenant.name}'.", None
    
    # Save original admin session
    session['original_admin_id'] = admin_user.id
    session['original_admin_email'] = admin_user.email
    
    # Log impersonation start
    audit_log = AdminAuditLog.log_action(
        admin_user_id=admin_user.id,
        action=AdminAuditAction.IMPERSONATION_START,
        target_tenant_id=tenant_id,
        details={
            'tenant_name': tenant.name,
            'tenant_slug': tenant.slug,
            'owner_email': owner_user.email,
            'admin_email': admin_user.email
        },
        ip_address=ip_address
    )
    db_session.add(audit_log)
    db_session.commit()
    
    # Login as tenant owner
    login_user(owner_user, remember=False)
    
    return True, f"Ahora estás impersonando a '{tenant.name}' como {owner_user.email}", "/dashboard"


def stop_impersonation(ip_address=None):
    """
    Stop impersonating and return to admin session.
    
    This function:
    1. Validates impersonation is active
    2. Logs the impersonation end
    3. Logs out the tenant user
    4. Restores the admin session
    
    Args:
        ip_address: Optional IP address of the admin
    
    Returns:
        tuple: (success: bool, message: str, redirect_url: str or None)
    """
    # Validate impersonation is active
    if not is_impersonating():
        return False, "No estás en modo impersonación.", None
    
    # Get original admin info
    original_admin_id = session.get('original_admin_id')
    original_admin_email = session.get('original_admin_email')
    
    # Get current tenant info before logout
    current_tenant_id = g.tenant.id if hasattr(g, 'tenant') and g.tenant else None
    current_tenant_name = g.tenant.name if hasattr(g, 'tenant') and g.tenant else 'Unknown'
    
    # Log impersonation end
    audit_log = AdminAuditLog.log_action(
        admin_user_id=original_admin_id,
        action=AdminAuditAction.IMPERSONATION_END,
        target_tenant_id=current_tenant_id,
        details={
            'tenant_name': current_tenant_name,
            'admin_email': original_admin_email
        },
        ip_address=ip_address
    )
    db_session.add(audit_log)
    db_session.commit()
    
    # Logout tenant user
    logout_user()
    
    # Restore admin session
    admin_user = db_session.query(AdminUser).filter_by(id=original_admin_id).first()
    if admin_user:
        # Clear impersonation flags
        session.pop('original_admin_id', None)
        session.pop('original_admin_email', None)
        
        # Set admin session
        session['admin_user_id'] = admin_user.id
        session.permanent = True
        
        return True, f"Has salido del modo soporte. Bienvenido de nuevo, {admin_user.email}", "/admin/tenants"
    else:
        # Admin user not found, clear session
        session.clear()
        return False, "Error al restaurar sesión de admin. Por favor, inicia sesión nuevamente.", "/admin/login"


def get_impersonation_banner_data():
    """
    Get data for displaying the impersonation banner.
    
    Returns:
        dict or None: Banner data if impersonating, None otherwise
    """
    if not is_impersonating():
        return None
    
    admin_email = session.get('original_admin_email', 'Admin')
    tenant_name = g.tenant.name if hasattr(g, 'tenant') and g.tenant else 'Unknown Tenant'
    
    return {
        'admin_email': admin_email,
        'tenant_name': tenant_name,
        'is_impersonating': True
    }
