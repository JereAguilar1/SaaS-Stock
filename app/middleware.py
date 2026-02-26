"""Middleware for authentication and tenant context."""
from functools import wraps
from flask import session, g, redirect, url_for, flash, request
from app.database import get_session
from app.models import AppUser, UserTenant


def load_user_and_tenant():
    """
    Load current user and tenant into g (Flask's per-request global).
    
    Called before each request to establish user and tenant context.
    Sets g.user, g.tenant_id, and g.user_role if authenticated.
    """
    g.user = None
    g.tenant_id = None
    g.user_role = None  # PASO 6: Add role to context
    
    try:
        user_id = session.get('user_id')
        if user_id:
            db_session = get_session()
            if not db_session:
                return

            user = db_session.query(AppUser).filter_by(id=user_id, active=True).first()
            if user:
                g.user = user
                g.user_id = user.id # Expose user_id directly for convenience
                
                # Load tenant_id from session
                tenant_id = session.get('tenant_id')
                if tenant_id:
                    # Verify user has access to this tenant
                    user_tenant = db_session.query(UserTenant).filter_by(
                        user_id=user.id,
                        tenant_id=tenant_id,
                        active=True
                    ).first()
                    
                    if user_tenant:
                        # ADMIN PANEL: Check if tenant is suspended
                        from app.models import Tenant
                        tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
                        
                        if tenant and tenant.is_suspended:
                            # Tenant is suspended - block access immediately
                            session.clear()
                            flash('Este negocio ha sido suspendido. Contacta soporte.', 'danger')
                            # Don't set g.user or g.tenant_id - force re-login
                            return
                        
                        g.tenant_id = tenant_id
                        g.user_role = user_tenant.role  # PASO 6: Set user role
                    else:
                        # User doesn't have access to this tenant, clear it
                        session.pop('tenant_id', None)
    except Exception as e:
        # Avoid crashing the whole app if context loading fails
        # Log it so we can see it in docker logs
        from flask import current_app
        current_app.logger.error(f"Error in load_user_and_tenant: {e}")



def require_login(f):
    """
    Decorator: Require user to be logged in.
    
    Redirects to login page if not authenticated.
    Sets next parameter to return to original page after login.
    Handles HTMX requests by returning 401 and an alert/redirect header.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            if request.headers.get('HX-Request'):
                # HTMX Response
                from flask import render_template
                # Check if we have a shared alert template, otherwise inline simplistic HTML
                # Using HX-Redirect is the cleanest way to force a full page reload to login
                response = redirect(url_for('auth.login', next=request.referrer or request.url))
                response.headers['HX-Redirect'] = url_for('auth.login', next=request.referrer or request.url)
                return response
            
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def require_tenant(f):
    """
    Decorator: Require tenant to be selected.
    
    Must be used AFTER require_login.
    Redirects to tenant selection if no tenant in session.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.tenant_id is None:
            flash('Debes seleccionar un negocio primero.', 'warning')
            return redirect(url_for('auth.select_tenant'))
        return f(*args, **kwargs)
    return decorated_function


def require_role(min_role='STAFF'):
    """
    Decorator: Require minimum role for tenant.
    
    Roles hierarchy: OWNER > ADMIN > STAFF
    
    Args:
        min_role: Minimum role required ('OWNER', 'ADMIN', or 'STAFF')
    
    Must be used AFTER require_login and require_tenant.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is None or g.tenant_id is None:
                flash('Acceso denegado.', 'danger')
                return redirect(url_for('auth.login'))
            
            # Get user's role for current tenant
            db_session = get_session()
            user_tenant = db_session.query(UserTenant).filter_by(
                user_id=g.user.id,
                tenant_id=g.tenant_id,
                active=True
            ).first()
            
            if not user_tenant:
                flash('No tienes acceso a este negocio.', 'danger')
                return redirect(url_for('auth.select_tenant'))
            
            # Check role hierarchy
            role_hierarchy = {'OWNER': 3, 'ADMIN': 2, 'STAFF': 1}
            user_role_level = role_hierarchy.get(user_tenant.role, 0)
            required_level = role_hierarchy.get(min_role, 1)
            
            if user_role_level < required_level:
                flash(f'Necesitas rol de {min_role} o superior para acceder.', 'danger')
                return redirect(url_for('main.index'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_subscription_status():
    """
    Middleware to check if the current tenant has an active subscription.
    Should be registered as @app.before_request in factory.
    """
    # Skip if static assets or certain endpoints
    if not request.endpoint or request.endpoint == 'static':
        return
        
    # List of endpoints that are always accessible even with expired subscription
    exempt_endpoints = [
        'auth.login', 'auth.logout', 'auth.select_tenant', 'auth.register', 
        'main.index', 'settings.billing', 'settings.subscription', 'settings.list_plans',
        'settings.subscribe', 'settings.billing_success',
        'webhooks.mercadopago', 'admin.login', 'static'
    ]
    
    # Allow all auth routes
    if request.endpoint.startswith('auth.') or request.endpoint.startswith('admin.'):
        return

    # Check if exempt
    if request.endpoint in exempt_endpoints:
        return
        
    # Check if tenant is selected
    if not g.get('tenant_id'):
        return
        
    # Check subscription status
    from app.services.subscription_service import check_trial_expiration
    from app.database import get_session
    
    session_db = get_session()
    status_info = check_trial_expiration(g.tenant_id, session_db)
    
    if not status_info['exists']:
        # Enforce plan selection for tenants without any subscription
        if request.endpoint != 'settings.list_plans':
             flash('Debes seleccionar un plan para continuar.', 'warning')
             return redirect(url_for('settings.list_plans'))
        return
        
    if status_info.get('status') in ('past_due', 'canceled'):
        # Block access and redirect to billing
        if request.endpoint != 'settings.list_plans' and request.endpoint != 'settings.billing':
            flash('Tu suscripción ha vencido. Por favor selecciona un plan para continuar.', 'danger')
            return redirect(url_for('settings.list_plans'))
