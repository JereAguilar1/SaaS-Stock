"""
Admin Blueprint - Backoffice panel for SaaS owner.

Routes:
- /admin/login - Admin authentication
- /admin/logout - Admin logout
- /admin/dashboard - Global KPIs and metrics
- /admin/tenants - Tenant list with search
- /admin/tenants/<id> - Tenant detail
- /admin/tenants/<id>/suspend - Suspend tenant
- /admin/tenants/<id>/reactivate - Reactivate tenant
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from app.database import db_session
from app.models import AdminUser, Tenant
from app.decorators.admin_security import admin_required
from app.services import admin_dashboard_service
from datetime import datetime


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page - separate from tenant user login."""
    # If already authenticated as admin, redirect to dashboard
    if session.get('admin_user_id'):
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email y contraseña son requeridos.', 'danger')
            return render_template('admin/login.html'), 400
        
        # Find admin user
        admin_user = db_session.query(AdminUser).filter_by(email=email).first()
        
        if not admin_user or not admin_user.check_password(password):
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('admin/login.html'), 401
        
        # Authentication successful
        session.clear()  # Clear any existing session
        session['admin_user_id'] = admin_user.id
        session.permanent = True
        
        # Update last login timestamp
        admin_user.last_login = datetime.utcnow()
        db_session.commit()
        
        flash(f'Bienvenido, {admin_user.email}!', 'success')
        return redirect(url_for('admin.dashboard'))
    
    # GET request - show login form
    return render_template('admin/login.html')


@admin_bp.route('/logout', methods=['POST'])
def logout():
    """Admin logout - clear admin session."""
    session.clear()
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('admin.login'))


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    """Admin dashboard - global KPIs and charts."""
    # Get global KPIs
    kpis = admin_dashboard_service.get_global_kpis(db_session)
    
    # Get sales trend for chart
    sales_trend = admin_dashboard_service.get_sales_trend_30d(db_session)
    
    return render_template(
        'admin/dashboard/index.html',
        kpis=kpis,
        sales_trend=sales_trend
    )


@admin_bp.route('/tenants')
@admin_required
def list_tenants():
    """Tenant list - with stats and search capability."""
    search_query = request.args.get('q', '').strip()
    
    # Get tenants with stats
    tenants = admin_dashboard_service.get_tenants_with_stats(
        db_session, 
        search_query=search_query if search_query else None
    )
    
    return render_template(
        'admin/tenants/list.html',
        tenants=tenants,
        search_query=search_query
    )


@admin_bp.route('/tenants/search')
@admin_required
def search_tenants():
    """HTMX endpoint - search tenants and return table rows only."""
    search_query = request.args.get('q', '').strip()
    
    # Get tenants with stats
    tenants = admin_dashboard_service.get_tenants_with_stats(
        db_session, 
        search_query=search_query if search_query else None
    )
    
    # Return partial template (just the table rows)
    return render_template(
        'admin/tenants/_tenant_rows.html',
        tenants=tenants
    )


@admin_bp.route('/tenants/<int:tenant_id>')
@admin_required
def tenant_detail(tenant_id):
    """Tenant detail page - metrics and actions."""
    # Get tenant details
    tenant_data = admin_dashboard_service.get_tenant_detail(db_session, tenant_id)
    
    if not tenant_data:
        flash('Negocio no encontrado.', 'danger')
        return redirect(url_for('admin.list_tenants'))
    
    return render_template(
        'admin/tenants/detail.html',
        tenant=tenant_data
    )


@admin_bp.route('/tenants/<int:tenant_id>/suspend', methods=['POST'])
@admin_required
def suspend_tenant(tenant_id):
    """Suspend a tenant - blocks all user logins for this tenant."""
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    
    if not tenant:
        flash('Negocio no encontrado.', 'danger')
        return redirect(url_for('admin.list_tenants'))
    
    if tenant.is_suspended:
        flash(f'El negocio "{tenant.name}" ya está suspendido.', 'warning')
        return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))
    
    # Suspend tenant
    tenant.is_suspended = True
    db_session.commit()
    
    flash(f'Negocio "{tenant.name}" suspendido exitosamente.', 'success')
    
    # Support HTMX refresh
    if request.headers.get('HX-Request'):
        return '', 204  # No content, triggers hx-swap
    
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/reactivate', methods=['POST'])
@admin_required
def reactivate_tenant(tenant_id):
    """Reactivate a suspended tenant - restores user login access."""
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    
    if not tenant:
        flash('Negocio no encontrado.', 'danger')
        return redirect(url_for('admin.list_tenants'))
    
    if not tenant.is_suspended:
        flash(f'El negocio "{tenant.name}" no está suspendido.', 'warning')
        return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))
    
    # Reactivate tenant
    tenant.is_suspended = False
    db_session.commit()
    
    flash(f'Negocio "{tenant.name}" reactivado exitosamente.', 'success')
    
    # Support HTMX refresh
    if request.headers.get('HX-Request'):
        return '', 204  # No content, triggers hx-swap
    
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/')
def index():
    """Root admin route - redirect to dashboard or login."""
    if session.get('admin_user_id'):
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('admin.login'))
