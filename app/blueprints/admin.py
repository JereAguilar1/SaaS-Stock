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


# =====================================================
# IMPERSONATION (SUPPORT MODE)
# =====================================================

@admin_bp.route('/tenants/<int:tenant_id>/impersonate', methods=['POST'])
@admin_required
def impersonate_tenant(tenant_id):
    """
    Start impersonating a tenant for support purposes.
    
    This allows an admin to log in as the tenant owner to troubleshoot issues.
    All actions are logged in the audit trail.
    """
    from app.services.impersonation_service import start_impersonation
    from flask import g
    
    # Get client IP
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    # Start impersonation
    success, message, redirect_url = start_impersonation(
        admin_user=g.admin_user,
        tenant_id=tenant_id,
        ip_address=ip_address
    )
    
    if success:
        flash(message, 'success')
        return redirect(redirect_url)
    else:
        flash(message, 'danger')
        return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


# =====================================================
# SUBSCRIPTIONS & PAYMENTS
# =====================================================

@admin_bp.route('/tenants/<int:tenant_id>/subscription', methods=['POST'])
@admin_required
def update_subscription(tenant_id):
    """Update tenant subscription details."""
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        return '', 404
        
    subscription = tenant.subscription
    if not subscription:
        # Create if not exists (should have been created by migration)
        from app.models import Subscription
        subscription = Subscription(tenant_id=tenant.id, plan_type='free', status='trial')
        db_session.add(subscription)
    
    # Update fields
    subscription.plan_type = request.form.get('plan_type')
    subscription.status = request.form.get('status')
    
    # Parse dates
    trial_ends = request.form.get('trial_ends_at')
    if trial_ends:
        subscription.trial_ends_at = datetime.strptime(trial_ends, '%Y-%m-%d')
    else:
        subscription.trial_ends_at = None
        
    period_end = request.form.get('current_period_end')
    if period_end:
        subscription.current_period_end = datetime.strptime(period_end, '%Y-%m-%d')
    else:
        subscription.current_period_end = None
    
    # Audit log
    from app.models import AdminAuditLog, AdminAuditAction
    from flask import g
    
    audit = AdminAuditLog.log_action(
        admin_user_id=g.admin_user.id,
        action=AdminAuditAction.UPDATE_SUBSCRIPTION,
        target_tenant_id=tenant.id,
        details={
            'plan_type': subscription.plan_type,
            'status': subscription.status,
            'trial_ends_at': str(subscription.trial_ends_at),
            'current_period_end': str(subscription.current_period_end)
        },
        ip_address=request.remote_addr
    )
    db_session.add(audit)
    db_session.commit()
    
    flash('Suscripción actualizada correctamente', 'success')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/payments', methods=['POST'])
@admin_required
def register_payment(tenant_id):
    """Register a manual payment for a tenant."""
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        return '', 404
        
    from app.models import Payment, AdminAuditLog, AdminAuditAction
    from flask import g
    from decimal import Decimal
    
    try:
        amount = Decimal(request.form.get('amount', '0'))
        payment_date = datetime.strptime(request.form.get('payment_date'), '%Y-%m-%d').date()
        reference = request.form.get('reference')
        notes = request.form.get('notes')
        
        payment = Payment(
            tenant_id=tenant.id,
            amount=amount,
            payment_date=payment_date,
            reference=reference,
            notes=notes,
            created_by=g.admin_user.id
        )
        db_session.add(payment)
        
        # Update subscription total amount (LTV)
        if not tenant.subscription:
            tenant.subscription.amount = 0
        tenant.subscription.amount = (tenant.subscription.amount or 0) + amount
        
        # Audit log
        audit = AdminAuditLog.log_action(
            admin_user_id=g.admin_user.id,
            action=AdminAuditAction.REGISTER_PAYMENT,
            target_tenant_id=tenant.id,
            details={
                'amount': str(amount),
                'payment_date': str(payment_date),
                'reference': reference
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        flash('Pago registrado correctamente', 'success')
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al registrar pago: {str(e)}', 'danger')
        
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/audit-logs')
@admin_required
def get_tenant_audit_logs(tenant_id):
    """Get audit logs for a specific tenant (HTMX)."""
    from app.models import AdminAuditLog
    
    logs = db_session.query(AdminAuditLog)\
        .filter_by(target_tenant_id=tenant_id)\
        .order_by(AdminAuditLog.created_at.desc())\
        .limit(50)\
        .all()
        
    return render_template('admin/tenants/_audit_rows.html', logs=logs)


# =====================================================
# PAYMENT MANAGEMENT
# =====================================================

@admin_bp.route('/tenants/<int:tenant_id>/payments')
@admin_required
def list_payments(tenant_id):
    """Get payments for a tenant (HTMX endpoint)."""
    from app.services import admin_payment_service
    
    payments = admin_payment_service.get_payments_by_tenant(db_session, tenant_id)
    
    return render_template(
        'admin/tenants/tabs/_payments.html',
        tenant_id=tenant_id,
        payments=payments
    )


@admin_bp.route('/tenants/<int:tenant_id>/payments/new')
@admin_required
def new_payment(tenant_id):
    """Show payment form modal (HTMX endpoint)."""
    return render_template(
        'admin/tenants/modals/_payment_form.html',
        tenant_id=tenant_id
    )


@admin_bp.route('/tenants/<int:tenant_id>/payments', methods=['POST'])
@admin_required
def create_payment(tenant_id):
    """Create a new payment (HTMX endpoint)."""
    from app.services import admin_payment_service
    from flask import g
    from datetime import datetime
    
    # Manual form validation
    try:
        amount = float(request.form.get('amount', 0))
        payment_date_str = request.form.get('payment_date')
        payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date() if payment_date_str else datetime.now().date()
        payment_method = request.form.get('payment_method', 'transfer')
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if amount <= 0:
            raise ValueError("El monto debe ser mayor a 0")
        
    except (ValueError, TypeError) as e:
        flash(f'Error en los datos del formulario: {str(e)}', 'danger')
        return render_template(
            'admin/tenants/modals/_payment_form.html',
            tenant_id=tenant_id,
            errors={'amount': str(e)}
        )
    
    # Get admin IP
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    # Create payment
    success, message, payment = admin_payment_service.create_payment(
        db_session=db_session,
        tenant_id=tenant_id,
        data={
            'amount': amount,
            'payment_date': payment_date,
            'payment_method': payment_method,
            'reference': reference if reference else None,
            'notes': notes if notes else None
        },
        admin_user_id=g.admin_user.id,
        ip_address=ip_address
    )
    
    if success:
        flash(message, 'success')
        
        # Return updated payments list
        payments = admin_payment_service.get_payments_by_tenant(db_session, tenant_id)
        response = render_template(
            'admin/tenants/tabs/_payments.html',
            tenant_id=tenant_id,
            payments=payments
        )
        
        # Add HX-Trigger header to close modal
        from flask import make_response
        resp = make_response(response)
        resp.headers['HX-Trigger'] = 'closeModal'
        return resp
    else:
        flash(message, 'danger')
        return render_template(
            'admin/tenants/modals/_payment_form.html',
            tenant_id=tenant_id,
            errors={'general': message}
        )


@admin_bp.route('/payments/<int:payment_id>/void', methods=['POST'])
@admin_required
def void_payment(payment_id):
    """Void a payment (HTMX endpoint)."""
    from app.services import admin_payment_service
    from flask import g
    from app.models import Payment
    
    # Get payment to find tenant_id
    payment = db_session.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        flash('Pago no encontrado', 'danger')
        return '', 404
    
    tenant_id = payment.tenant_id
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    success, message = admin_payment_service.void_payment(
        db_session=db_session,
        payment_id=payment_id,
        admin_user_id=g.admin_user.id,
        ip_address=ip_address
    )
    
    flash(message, 'success' if success else 'danger')
    
    # Return updated payments list
    payments = admin_payment_service.get_payments_by_tenant(db_session, tenant_id)
    return render_template(
        'admin/tenants/tabs/_payments.html',
        tenant_id=tenant_id,
        payments=payments
    )

