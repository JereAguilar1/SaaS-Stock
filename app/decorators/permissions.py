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
