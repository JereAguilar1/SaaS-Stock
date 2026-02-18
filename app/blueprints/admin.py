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

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response, current_app, abort
from app.exceptions import BusinessLogicError, NotFoundError, UnauthorizedError
from typing import List, Dict, Optional, Union, Any, Tuple
from app.database import get_session
from app.models import AdminUser, Tenant, Subscription, Payment, AdminAuditLog, AdminAuditAction
from app.decorators.admin_security import admin_required
from app.services import admin_dashboard_service, admin_payment_service
from datetime import datetime
from decimal import Decimal


admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _get_tenant_or_404(tenant_id: int) -> Tenant:
    """Fetch tenant or raise NotFoundError."""
    session_db = get_session()
    tenant = session_db.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        raise NotFoundError('Negocio no encontrado')
    return tenant


def _parse_admin_date(date_str: Optional[str]) -> Optional[datetime]:
    """Safely parse admin dashboard date strings."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d')
    except (ValueError, TypeError):
        return None


@admin_bp.route('/login', methods=['GET', 'POST'])
def login() -> Union[str, Response]:
    """Admin login page - separate from tenant user login."""
    session_db = get_session()
    if session.get('admin_user_id'):
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Email y contraseña son requeridos.', 'danger')
            return render_template('admin/login.html'), 400
        
        admin_user = session_db.query(AdminUser).filter_by(email=email).first()
        if not admin_user or not admin_user.check_password(password):
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('admin/login.html'), 401
        
        session.clear()
        session['admin_user_id'] = admin_user.id
        session.permanent = True
        
        admin_user.last_login = datetime.utcnow()
        session_db.commit()
        
        flash(f'Bienvenido, {admin_user.email}!', 'success')
        return redirect(url_for('admin.dashboard'))
    
    return render_template('admin/login.html')


@admin_bp.route('/logout', methods=['POST'])
def logout() -> Response:
    """Admin logout - clear admin session."""
    session.clear()
    flash('Sesión de administrador cerrada.', 'success')
    return redirect(url_for('admin.login'))


@admin_bp.route('/dashboard')
@admin_required
def dashboard() -> str:
    """Admin dashboard - global KPIs and charts."""
    session_db = get_session()
    kpis = admin_dashboard_service.get_global_kpis(session_db)
    sales_trend = admin_dashboard_service.get_sales_trend_30d(session_db)
    
    return render_template('admin/dashboard/index.html', kpis=kpis, sales_trend=sales_trend)


@admin_bp.route('/tenants')
@admin_required
def list_tenants() -> str:
    """Tenant list - with stats and search capability."""
    session_db = get_session()
    search_query = request.args.get('q', '').strip()
    tenants = admin_dashboard_service.get_tenants_with_stats(session_db, search_query=search_query or None)
    
    return render_template('admin/tenants/list.html', tenants=tenants, search_query=search_query)


@admin_bp.route('/tenants/search')
@admin_required
def search_tenants() -> str:
    """HTMX endpoint - search tenants and return table rows only."""
    session_db = get_session()
    search_query = request.args.get('q', '').strip()
    tenants = admin_dashboard_service.get_tenants_with_stats(session_db, search_query=search_query or None)
    
    return render_template('admin/tenants/_tenant_rows.html', tenants=tenants)


@admin_bp.route('/tenants/<int:tenant_id>')
@admin_required
def tenant_detail(tenant_id: int) -> Union[str, Response]:
    """Tenant detail page - metrics and actions."""
    session_db = get_session()
    tenant_data = admin_dashboard_service.get_tenant_detail(session_db, tenant_id)
    if not tenant_data:
        raise NotFoundError('Negocio no encontrado.')
    
    return render_template('admin/tenants/detail.html', tenant=tenant_data)


@admin_bp.route('/tenants/<int:tenant_id>/suspend', methods=['POST'])
@admin_required
def suspend_tenant(tenant_id: int) -> Union[str, Response, Tuple[str, int]]:
    """Suspend a tenant - blocks all user logins for this tenant."""
    session_db = get_session()
    tenant = _get_tenant_or_404(tenant_id)
    
    if tenant.is_suspended:
        raise BusinessLogicError(f'El negocio "{tenant.name}" ya está suspendido.')
    
    tenant.is_suspended = True
    session_db.commit()
    flash(f'Negocio "{tenant.name}" suspendido exitosamente.', 'success')
    
    if request.headers.get('HX-Request') == 'true':
        return '', 204
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/reactivate', methods=['POST'])
@admin_required
def reactivate_tenant(tenant_id: int) -> Union[str, Response, Tuple[str, int]]:
    """Reactivate a suspended tenant - restores user login access."""
    session_db = get_session()
    tenant = _get_tenant_or_404(tenant_id)
    
    if not tenant.is_suspended:
        raise BusinessLogicError(f'El negocio "{tenant.name}" no está suspendido.')

    tenant.is_suspended = False
    session_db.commit()
    flash(f'Negocio "{tenant.name}" reactivado exitosamente.', 'success')
    
    if request.headers.get('HX-Request') == 'true':
        return '', 204
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/')
def index() -> Response:
    """Root admin route - redirect to dashboard or login."""
    if session.get('admin_user_id'):
        return redirect(url_for('admin.dashboard'))
    return redirect(url_for('admin.login'))


# =====================================================
# IMPERSONATION (SUPPORT MODE)
# =====================================================

@admin_bp.route('/tenants/<int:tenant_id>/impersonate', methods=['POST'])
@admin_required
def impersonate_tenant(tenant_id: int) -> Response:
    """Start impersonating a tenant for support purposes."""
    from app.services import impersonation_service
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    success, message, redirect_url = impersonation_service.start_impersonation(
        admin_user=g.admin_user,
        tenant_id=tenant_id,
        ip_address=ip_address
    )
    
    if not success:
        raise BusinessLogicError(message)

    flash(message, 'success')
    return redirect(redirect_url)


# =====================================================
# SUBSCRIPTIONS & PAYMENTS
# =====================================================

@admin_bp.route('/tenants/<int:tenant_id>/subscription', methods=['POST'])
@admin_required
def update_subscription(tenant_id: int) -> Union[Response, Tuple[str, int]]:
    """Update tenant subscription details."""
    session_db = get_session()
    tenant = _get_tenant_or_404(tenant_id)
    subscription = tenant.subscription
    
    if not subscription:
        subscription = Subscription(tenant_id=tenant.id, plan_type='free', status='trial')
        session_db.add(subscription)
    
    subscription.plan_type = request.form.get('plan_type')
    subscription.status = request.form.get('status')
    subscription.trial_ends_at = _parse_admin_date(request.form.get('trial_ends_at'))
    subscription.current_period_end = _parse_admin_date(request.form.get('current_period_end'))
    
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
    session_db.add(audit)
    session_db.commit()
    
    flash('Suscripción actualizada correctamente', 'success')
    return redirect(url_for('admin.tenant_detail', tenant_id=tenant_id))


@admin_bp.route('/tenants/<int:tenant_id>/audit-logs')
@admin_required
def get_tenant_audit_logs(tenant_id: int) -> str:
    """Get audit logs for a specific tenant (HTMX)."""
    session_db = get_session()
    logs = session_db.query(AdminAuditLog).filter_by(target_tenant_id=tenant_id).order_by(AdminAuditLog.created_at.desc()).limit(50).all()
    return render_template('admin/tenants/_audit_rows.html', logs=logs)


# =====================================================
# PAYMENT MANAGEMENT
# =====================================================

@admin_bp.route('/tenants/<int:tenant_id>/payments')
@admin_required
def list_payments(tenant_id: int) -> str:
    """Get payments for a tenant (HTMX endpoint)."""
    session_db = get_session()
    payments = admin_payment_service.get_payments_by_tenant(session_db, tenant_id)
    return render_template('admin/tenants/tabs/_payments.html', tenant_id=tenant_id, payments=payments)


@admin_bp.route('/tenants/<int:tenant_id>/payments/new')
@admin_required
def new_payment(tenant_id: int) -> str:
    """Show payment form modal (HTMX endpoint)."""
    return render_template('admin/tenants/modals/_payment_form.html', tenant_id=tenant_id)


@admin_bp.route('/tenants/<int:tenant_id>/payments', methods=['POST'])
@admin_required
def create_payment(tenant_id: int) -> Union[str, Response]:
    """Create a new payment (HTMX endpoint)."""
    session_db = get_session()
    
    try:
        amount = float(request.form.get('amount', 0))
        p_date_dt = _parse_admin_date(request.form.get('payment_date'))
        payment_date = p_date_dt.date() if p_date_dt else datetime.now().date()
        payment_method = request.form.get('payment_method', 'transfer')
        reference = request.form.get('reference', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if amount <= 0:
            raise BusinessLogicError("El monto debe ser mayor a 0")
        
    except (ValueError, TypeError) as e:
        raise BusinessLogicError(f"Datos de pago inválidos: {str(e)}")
    
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    success, message, payment = admin_payment_service.create_payment(
        db_session=session_db,
        tenant_id=tenant_id,
        data={
            'amount': amount,
            'payment_date': payment_date,
            'payment_method': payment_method,
            'reference': reference or None,
            'notes': notes or None
        },
        admin_user_id=g.admin_user.id,
        ip_address=ip_address
    )
    
    if success:
        flash(message, 'success')
        payments = admin_payment_service.get_payments_by_tenant(session_db, tenant_id)
        response = render_template('admin/tenants/tabs/_payments.html', tenant_id=tenant_id, payments=payments)
        
        from flask import make_response
        resp = make_response(response)
        resp.headers['HX-Trigger'] = 'closeModal'
        return resp
    else:
        raise BusinessLogicError(message)


@admin_bp.route('/payments/<int:payment_id>/void', methods=['POST'])
@admin_required
def void_payment(payment_id: int) -> Union[str, Response, Tuple[str, int]]:
    """Void a payment (HTMX endpoint)."""
    session_db = get_session()
    payment = session_db.query(Payment).filter_by(id=payment_id).first()
    if not payment:
        raise NotFoundError('Pago no encontrado')
    
    tenant_id = payment.tenant_id
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    success, message = admin_payment_service.void_payment(
        db_session=session_db,
        payment_id=payment_id,
        admin_user_id=g.admin_user.id,
        ip_address=ip_address
    )
    
    if not success:
        raise BusinessLogicError(message)

    flash(message, 'success')
    payments = admin_payment_service.get_payments_by_tenant(session_db, tenant_id)
    return render_template('admin/tenants/tabs/_payments.html', tenant_id=tenant_id, payments=payments)


# ============================================================================
# PLAN MANAGEMENT (SUBSCRIPTIONS_V1)
# ============================================================================

@admin_bp.route('/plans')
@admin_required
def list_plans() -> str:
    """List all subscription plans."""
    from app.models.plan import Plan
    session_db = get_session()
    
    plans = session_db.query(Plan).order_by(Plan.price.asc()).all()
    
    return render_template('admin/plans/index.html', plans=plans)


@admin_bp.route('/plans/new', methods=['GET', 'POST'])
@admin_required
def create_plan() -> Union[str, Response]:
    """Create a new subscription plan."""
    from app.models.plan import Plan
    from app.services.mercadopago_service import MercadoPagoService
    
    session_db = get_session()
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        code = request.form.get('code', '').strip()
        price = request.form.get('price', '').strip()
        currency = request.form.get('currency', 'ARS').strip()
        billing_frequency = request.form.get('billing_frequency', 'monthly').strip()
        description = request.form.get('description', '').strip()
        sync_mp = request.form.get('sync_mp') == 'on'
        
        if not name or not code or not price:
            raise BusinessLogicError('Nombre, código y precio son requeridos')
        
        # Check if code already exists
        existing = session_db.query(Plan).filter_by(code=code).first()
        if existing:
            raise BusinessLogicError(f'Ya existe un plan con el código: {code}')
        
        try:
            price_decimal = Decimal(price)
        except:
            raise BusinessLogicError('Precio inválido')
        
        # Create plan in DB
        plan = Plan(
            name=name,
            code=code,
            price=price_decimal,
            currency=currency,
            billing_frequency=billing_frequency,
            description=description,
            is_active=True
        )
        
        session_db.add(plan)
        session_db.flush()
        
        # Optionally sync with Mercado Pago
        mp_plan_id = None
        if sync_mp:
            try:
                mp_service = MercadoPagoService()
                mp_plan_data = mp_service.create_plan(
                    reason=name,
                    auto_recurring={
                        "frequency": 1,
                        "frequency_type": "months",
                        "transaction_amount": float(price_decimal),
                        "currency_id": currency
                    },
                    back_url=current_app.config.get('PREFERRED_URL_SCHEME', 'http') + '://' + request.host + '/subscription/success'
                )
                mp_plan_id = mp_plan_data.get('id')
                plan.mp_preapproval_plan_id = mp_plan_id
            except Exception as e:
                current_app.logger.error(f"Error syncing plan with MP: {e}")
                flash(f'Plan creado localmente, pero falló la sincronización con MP: {str(e)}', 'warning')
        
        session_db.commit()
        
        flash(f'Plan "{name}" creado exitosamente' + (f' (MP ID: {mp_plan_id})' if mp_plan_id else ''), 'success')
        return redirect(url_for('admin.list_plans'))
    
    return render_template('admin/plans/form.html', plan=None)


@admin_bp.route('/plans/<int:plan_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_plan(plan_id: int) -> Union[str, Response]:
    """Edit an existing subscription plan."""
    from app.models.plan import Plan
    
    session_db = get_session()
    plan = session_db.query(Plan).filter_by(id=plan_id).first()
    
    if not plan:
        raise NotFoundError('Plan no encontrado')
    
    if request.method == 'POST':
        plan.name = request.form.get('name', '').strip()
        plan.price = Decimal(request.form.get('price', '0'))
        plan.currency = request.form.get('currency', 'ARS').strip()
        plan.billing_frequency = request.form.get('billing_frequency', 'monthly').strip()
        plan.description = request.form.get('description', '').strip()
        plan.is_active = request.form.get('is_active') == 'on'
        
        session_db.commit()
        
        flash(f'Plan "{plan.name}" actualizado exitosamente', 'success')
        return redirect(url_for('admin.list_plans'))
    
    return render_template('admin/plans/form.html', plan=plan)


@admin_bp.route('/plans/<int:plan_id>/features', methods=['GET', 'POST'])
@admin_required
def manage_plan_features(plan_id: int) -> Union[str, Response]:
    """Manage features for a specific plan."""
    from app.models.plan import Plan
    from app.models.plan_feature import PlanFeature
    
    session_db = get_session()
    plan = session_db.query(Plan).filter_by(id=plan_id).first()
    
    if not plan:
        raise NotFoundError('Plan no encontrado')
    
    if request.method == 'POST':
        feature_key = request.form.get('feature_key', '').strip()
        feature_value = request.form.get('feature_value', '').strip()
        
        if not feature_key:
            raise BusinessLogicError('La clave de feature es requerida')
        
        # Check if feature already exists
        existing = session_db.query(PlanFeature).filter_by(
            plan_id=plan_id,
            feature_key=feature_key
        ).first()
        
        if existing:
            raise BusinessLogicError(f'La feature "{feature_key}" ya existe para este plan')
        
        feature = PlanFeature(
            plan_id=plan_id,
            feature_key=feature_key,
            feature_value=feature_value if feature_value else None,
            is_active=True
        )
        
        session_db.add(feature)
        session_db.commit()
        
        flash(f'Feature "{feature_key}" agregada exitosamente', 'success')
        return redirect(url_for('admin.manage_plan_features', plan_id=plan_id))
    
    features = session_db.query(PlanFeature).filter_by(plan_id=plan_id).all()
    
    return render_template('admin/plans/features.html', plan=plan, features=features)


@admin_bp.route('/plans/<int:plan_id>/features/<int:feature_id>/toggle', methods=['POST'])
@admin_required
def toggle_feature(plan_id: int, feature_id: int) -> Response:
    """Toggle feature active status."""
    from app.models.plan_feature import PlanFeature
    
    session_db = get_session()
    feature = session_db.query(PlanFeature).filter_by(
        id=feature_id,
        plan_id=plan_id
    ).first()
    
    if not feature:
        raise NotFoundError('Feature no encontrada')
    
    feature.is_active = not feature.is_active
    session_db.commit()
    
    status = 'activada' if feature.is_active else 'desactivada'
    flash(f'Feature "{feature.feature_key}" {status}', 'success')
    
    return redirect(url_for('admin.manage_plan_features', plan_id=plan_id))


@admin_bp.route('/plans/<int:plan_id>/features/<int:feature_id>/delete', methods=['POST'])
@admin_required
def delete_feature(plan_id: int, feature_id: int) -> Response:
    """Delete a feature from a plan."""
    from app.models.plan_feature import PlanFeature
    
    session_db = get_session()
    feature = session_db.query(PlanFeature).filter_by(
        id=feature_id,
        plan_id=plan_id
    ).first()
    
    if not feature:
        raise NotFoundError('Feature no encontrada')
    
    feature_key = feature.feature_key
    session_db.delete(feature)
    session_db.commit()
    
    flash(f'Feature "{feature_key}" eliminada', 'success')
    
    return redirect(url_for('admin.manage_plan_features', plan_id=plan_id))


@admin_bp.route('/subscriptions')
@admin_required
def list_subscriptions() -> str:
    """Monitor all tenant subscriptions."""
    from app.models.subscription import Subscription
    from app.models.plan import Plan
    
    session_db = get_session()
    
    # Get filter parameters
    status_filter = request.args.get('status', '')
    plan_filter = request.args.get('plan', '')
    
    query = session_db.query(Subscription).join(Tenant)
    
    if status_filter:
        query = query.filter(Subscription.status == status_filter)
    
    if plan_filter:
        query = query.filter(Subscription.plan_type == plan_filter)
    
    subscriptions = query.order_by(Subscription.created_at.desc()).all()
    plans = session_db.query(Plan).all()
    
    return render_template('admin/subscriptions/index.html', 
                         subscriptions=subscriptions,
                         plans=plans,
                         status_filter=status_filter,
                         plan_filter=plan_filter)


@admin_bp.route('/subscriptions/<int:subscription_id>/sync', methods=['POST'])
@admin_required
def sync_subscription(subscription_id: int) -> Response:
    """Manually sync subscription from Mercado Pago."""
    from app.models.subscription import Subscription
    from app.services.subscription_service import sync_subscription_from_mp
    
    session_db = get_session()
    subscription = session_db.query(Subscription).filter_by(id=subscription_id).first()
    
    if not subscription:
        raise NotFoundError('Suscripción no encontrada')
    
    if not subscription.mp_subscription_id:
        raise BusinessLogicError('Esta suscripción no tiene ID de Mercado Pago')
    
    try:
        sync_subscription_from_mp(subscription.mp_subscription_id, session_db)
        session_db.commit()
        flash('Suscripción sincronizada exitosamente', 'success')
    except Exception as e:
        current_app.logger.error(f"Error syncing subscription: {e}")
        raise BusinessLogicError(f'Error al sincronizar: {str(e)}')
    
    return redirect(url_for('admin.list_subscriptions'))
