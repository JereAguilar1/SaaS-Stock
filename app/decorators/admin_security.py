"""
Admin security decorators.
Provides authentication and authorization for admin panel routes.
"""

from functools import wraps
from flask import session, redirect, url_for, flash, request, g


def admin_required(f):
    """
    Decorator: Require admin user to be logged in.
    
    Redirects to admin login page if not authenticated.
    Handles HTMX requests by returning 401 and an HX-Redirect header.
    
    IMPORTANT: This checks session['admin_user_id'], NOT g.user or g.tenant_id.
    Admin authentication is completely separate from tenant user authentication.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        admin_user_id = session.get('admin_user_id')
        
        if not admin_user_id:
            # Not authenticated as admin
            if request.headers.get('HX-Request'):
                # HTMX request - use HX-Redirect to force full page reload
                response = redirect(url_for('admin.login'))
                response.headers['HX-Redirect'] = url_for('admin.login')
                return response
            
            flash('Debes iniciar sesión como administrador.', 'warning')
            return redirect(url_for('admin.login'))
        
        # Admin is authenticated - load admin user into request context
        from app.database import db_session
        from app.models import AdminUser
        
        admin_user = db_session.query(AdminUser).filter_by(id=admin_user_id).first()
        
        if not admin_user:
            # Admin user no longer exists in database
            session.pop('admin_user_id', None)
            flash('Sesión de administrador inválida.', 'danger')
            return redirect(url_for('admin.login'))
        
        # Store admin user in g for use in route
        g.admin_user = admin_user
        
        return f(*args, **kwargs)
    
    return decorated_function


def load_admin_user():
    """
    Load admin user into g if admin is logged in.
    
    This should be called in a before_request handler for admin routes only.
    Alternative to @admin_required decorator if you want to check manually.
    """
    g.admin_user = None
    
    admin_user_id = session.get('admin_user_id')
    if admin_user_id:
        from app.database import db_session
        from app.models import AdminUser
        
        admin_user = db_session.query(AdminUser).filter_by(id=admin_user_id).first()
        if admin_user:
            g.admin_user = admin_user
