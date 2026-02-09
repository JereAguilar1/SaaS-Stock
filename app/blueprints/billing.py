"""Billing blueprint for Mercado Pago subscription management."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify, current_app
from app.database import get_session
from app.models import BillingPlan, MPSubscription
from app.services.billing_service import BillingService
from app.middleware import require_login, require_tenant
from app.models.user_tenant import UserRole

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')


@billing_bp.route('/plans')
@require_login
@require_tenant
def plans():
    """Ver planes disponibles y estado actual de suscripción."""
    db_session = get_session()
    
    try:
        # Obtener planes activos
        plans = db_session.query(BillingPlan).filter(
            BillingPlan.active == True
        ).order_by(BillingPlan.price_amount).all()
        
        # Obtener suscripción actual del tenant
        current_subscription = db_session.query(MPSubscription).filter(
            MPSubscription.tenant_id == g.tenant_id
        ).order_by(MPSubscription.created_at.desc()).first()
        
        # Verificar si es OWNER
        # g.user_role es un string en la DB, UserRole.OWNER es Enum
        is_owner = hasattr(g, 'user_role') and g.user_role == UserRole.OWNER.value
        
        return render_template(
            'billing/plans.html',
            plans=plans,
            current_subscription=current_subscription,
            is_owner=is_owner
        )
        
    except Exception as e:
        current_app.logger.error(f"[BILLING] Error loading plans: {e}")
        flash('Error al cargar planes de facturación', 'danger')
        return render_template('billing/plans.html', plans=[], current_subscription=None, is_owner=False)


@billing_bp.route('/subscribe', methods=['POST'])
@require_login
@require_tenant
def subscribe():
    """Iniciar suscripción (solo OWNER)."""
    # Verificar que sea OWNER
    if not hasattr(g, 'user_role') or g.user_role != UserRole.OWNER.value:
        flash('Solo el propietario del negocio puede suscribirse', 'danger')
        return redirect(url_for('billing.plans'))
    
    db_session = get_session()
    
    try:
        plan_code = request.form.get('plan_code', 'PRO')
        payer_email = g.user.email
        
        billing_service = BillingService(db_session)
        subscription = billing_service.create_subscription(
            tenant_id=g.tenant_id,
            plan_code=plan_code,
            payer_email=payer_email
        )
        
        # Redirigir al init_point de Mercado Pago
        if subscription.mp_init_point:
            return redirect(subscription.mp_init_point)
        else:
            flash('Error: No se generó el link de pago', 'danger')
            return redirect(url_for('billing.plans'))
        
    except ValueError as e:
        flash(str(e), 'warning')
        return redirect(url_for('billing.plans'))
    except Exception as e:
        current_app.logger.error(f"[BILLING] Error creating subscription: {e}")
        flash('Error al crear suscripción. Intente nuevamente.', 'danger')
        return redirect(url_for('billing.plans'))


@billing_bp.route('/return')
@require_login
@require_tenant
def return_page():
    """Página de retorno después de pagar en Mercado Pago."""
    return render_template('billing/return.html')


@billing_bp.route('/status')
@require_login
@require_tenant
def status():
    """API para consultar estado de suscripción (polling)."""
    db_session = get_session()
    
    try:
        subscription = db_session.query(MPSubscription).filter(
            MPSubscription.tenant_id == g.tenant_id
        ).order_by(MPSubscription.created_at.desc()).first()
        
        if not subscription:
            return jsonify({
                'status': None,
                'message': 'No hay suscripción registrada'
            })
        
        return jsonify({
            'status': subscription.status,
            'plan_id': subscription.plan_id,
            'started_at': subscription.started_at.isoformat() if subscription.started_at else None,
            'updated_at': subscription.updated_at.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"[BILLING] Error getting status: {e}")
        return jsonify({'error': 'Error al consultar estado'}), 500


# Webhook endpoint (NO requiere autenticación)
@billing_bp.route('/webhook', methods=['POST'])
def webhook():
    """Recibir notificaciones de Mercado Pago."""
    db_session = get_session()
    
    try:
        # Obtener datos del webhook
        topic = request.args.get('topic')
        payload = request.get_json() or {}
        
        current_app.logger.info(f"[BILLING] Webhook received: topic={topic}")
        
        if not topic:
            current_app.logger.warning("[BILLING] Webhook without topic")
            return jsonify({'status': 'ignored'}), 200
        
        # Procesar webhook
        billing_service = BillingService(db_session)
        processed = billing_service.process_webhook(topic, payload)
        
        if processed:
            return jsonify({'status': 'processed'}), 200
        else:
            return jsonify({'status': 'duplicate'}), 200
        
    except Exception as e:
        current_app.logger.error(f"[BILLING] Webhook error: {e}")
        # Siempre devolver 200 para que MP no reintente
        return jsonify({'status': 'error', 'message': str(e)}), 200


# Ruta alternativa para webhook (MP puede usar diferentes formatos)
@billing_bp.route('/webhooks/mercadopago', methods=['POST'])
def webhook_alt():
    """Ruta alternativa para webhook de Mercado Pago."""
    return webhook()
