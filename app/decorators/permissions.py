"""
Permission decorators for role-based access control.
Extends the basic require_login and require_tenant decorators with role checks.
"""

from functools import wraps
from flask import g, abort, flash, redirect, url_for


def require_role(*allowed_roles):
    """
    Decorator to restrict access to specific roles.
    
    Usage:
        @require_role('OWNER')
        @require_role('OWNER', 'ADMIN')
    
    Args:
        *allowed_roles: Variable number of role strings (OWNER, ADMIN, STAFF)
    
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Must be logged in
            if not g.get('user'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Must have tenant selected
            if not g.get('tenant_id'):
                flash('Debes seleccionar un negocio primero.', 'warning')
                return redirect(url_for('auth.select_tenant'))
            
            # Check role
            user_role = g.get('user_role')
            
            if not user_role or user_role not in allowed_roles:
                flash('No tienes permisos para acceder a esta función.', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def require_permission(permission_name):
    """
    Decorator to check for specific permission.
    
    Permission mapping by role:
    - OWNER: All permissions
    - ADMIN: All except manage_users, delete_tenant
    - STAFF: Only view and pos permissions
    
    Usage:
        @require_permission('edit_products')
        @require_permission('view_balance')
    
    Args:
        permission_name: Name of the required permission
    
    Returns:
        Decorator function
    """
    # Permission map
    PERMISSION_MAP = {
        'OWNER': 'all',  # Owner has all permissions
        'ADMIN': [
            'view_catalog', 'edit_products', 'create_products', 'delete_products',
            'view_sales', 'create_sales', 'edit_sales', 'delete_sales',
            'view_quotes', 'create_quotes', 'convert_quotes', 'delete_quotes',
            'view_suppliers', 'edit_suppliers', 'create_suppliers', 'delete_suppliers',
            'view_invoices', 'pay_invoices', 'create_invoices', 'delete_invoices',
            'view_balance', 'edit_balance', 'create_ledger_entries',
            'view_settings', 'edit_settings',
            'view_missing_products', 'resolve_missing_products'
        ],
        'STAFF': [
            'view_catalog',
            'create_sales',  # POS access
            'view_sales',
            'create_quotes',
            'view_quotes',
            'view_missing_products'
        ]
    }
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Must be logged in
            if not g.get('user'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Must have tenant selected
            if not g.get('tenant_id'):
                flash('Debes seleccionar un negocio primero.', 'warning')
                return redirect(url_for('auth.select_tenant'))
            
            # Get user role
            user_role = g.get('user_role')
            
            if not user_role:
                flash('No se pudo determinar tu rol.', 'danger')
                abort(403)
            
            # Check permission
            role_permissions = PERMISSION_MAP.get(user_role, [])
            
            # OWNER has all permissions
            if role_permissions == 'all':
                return f(*args, **kwargs)
            
            # Check if permission in user's role permissions
            if permission_name not in role_permissions:
                flash(f'No tienes permiso para: {permission_name}', 'danger')
                abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def owner_only(f):
    """
    Shortcut decorator for OWNER-only routes.
    
    Usage:
        @owner_only
        def manage_users():
            ...
    """
    return require_role('OWNER')(f)


def admin_or_owner(f):
    """
    Shortcut decorator for ADMIN or OWNER access.
    
    Usage:
        @admin_or_owner
        def edit_product():
            ...
    """
    return require_role('OWNER', 'ADMIN')(f)


def staff_or_higher(f):
    """
    Shortcut decorator for STAFF, ADMIN, or OWNER access.
    
    Usage:
        @staff_or_higher
        def view_catalog():
            ...
    """
    return require_role('OWNER', 'ADMIN', 'STAFF')(f)


# ============================================================================
# PLAN FEATURE-BASED PERMISSIONS (SUBSCRIPTIONS_V1)
# ============================================================================

def has_feature(tenant_id, feature_key):
    """
    Check if a tenant's plan includes a specific feature.
    
    Args:
        tenant_id: ID of the tenant
        feature_key: Feature key to check (e.g., 'module_sales', 'api_access')
        
    Returns:
        bool: True if feature is active for tenant's plan
    """
    from app.database import get_session
    from app.models.subscription import Subscription
    from app.models.plan_feature import PlanFeature
    
    session = get_session()
    
    try:
        # Get tenant's subscription
        subscription = session.query(Subscription).filter_by(
            tenant_id=tenant_id
        ).first()
        
        if not subscription or not subscription.plan_id:
            # No subscription or plan, deny access
            return False
        
        # Check if plan has the feature
        feature = session.query(PlanFeature).filter_by(
            plan_id=subscription.plan_id,
            feature_key=feature_key,
            is_active=True
        ).first()
        
        return feature is not None
        
    except Exception:
        # On error, deny access
        return False


def get_feature_value(tenant_id, feature_key, default=None):
    """
    Get the value of a feature for a tenant's plan.
    Useful for numeric limits (e.g., 'max_users' -> '5').
    
    Args:
        tenant_id: ID of the tenant
        feature_key: Feature key to check
        default: Default value if feature not found
        
    Returns:
        Feature value (str) or default
    """
    from app.database import get_session
    from app.models.subscription import Subscription
    from app.models.plan_feature import PlanFeature
    
    session = get_session()
    
    try:
        subscription = session.query(Subscription).filter_by(
            tenant_id=tenant_id
        ).first()
        
        if not subscription or not subscription.plan_id:
            return default
        
        feature = session.query(PlanFeature).filter_by(
            plan_id=subscription.plan_id,
            feature_key=feature_key,
            is_active=True
        ).first()
        
        if feature:
            return feature.feature_value or default
        
        return default
        
    except Exception:
        return default


def require_feature(feature_key, upgrade_message=None):
    """
    Decorator to restrict access based on plan features.
    
    Usage:
        @require_feature('module_sales')
        def sales_dashboard():
            ...
        
        @require_feature('api_access', upgrade_message='Actualiza a Pro para acceder a la API')
        def api_endpoint():
            ...
    
    Args:
        feature_key: Feature key required
        upgrade_message: Custom message to show when feature is not available
        
    Returns:
        Decorator function
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Must be logged in
            if not g.get('user'):
                flash('Debes iniciar sesión para acceder a esta página.', 'warning')
                return redirect(url_for('auth.login'))
            
            # Must have tenant selected
            if not g.get('tenant_id'):
                flash('Debes seleccionar un negocio primero.', 'warning')
                return redirect(url_for('auth.select_tenant'))
            
            # Check if tenant's plan has the feature
            if not has_feature(g.tenant_id, feature_key):
                message = upgrade_message or f'Tu plan actual no incluye acceso a esta funcionalidad. Actualiza tu plan para desbloquear: {feature_key}'
                flash(message, 'warning')
                abort(403)
            
            return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def check_feature_limit(feature_key, current_count):
    """
    Check if current usage is within plan limits.
    
    Usage:
        if not check_feature_limit('max_users', current_user_count):
            flash('Has alcanzado el límite de usuarios de tu plan', 'warning')
            return redirect(...)
    
    Args:
        feature_key: Feature key with limit (e.g., 'max_users')
        current_count: Current usage count
        
    Returns:
        bool: True if within limit, False if exceeded
    """
    if not g.get('tenant_id'):
        return False
    
    limit_str = get_feature_value(g.tenant_id, feature_key)
    
    if limit_str is None:
        # No limit defined, allow
        return True
    
    try:
        limit = int(limit_str)
        return current_count < limit
    except (ValueError, TypeError):
        # Invalid limit value, allow
        return True
