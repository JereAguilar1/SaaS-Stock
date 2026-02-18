"""
Subscription Service for managing tenant subscriptions and trial periods.
Handles business logic for plan activation, trial management, and Mercado Pago integration.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.services.mercadopago_service import MercadoPagoService
from app.exceptions import BusinessLogicError, NotFoundError

logger = logging.getLogger(__name__)


def create_trial_subscription(tenant_id: int, session: Session) -> Subscription:
    """
    Create a new trial subscription for a tenant (30 days).
    
    Args:
        tenant_id: ID of the tenant
        session: Database session
        
    Returns:
        Subscription: Created subscription object
    """
    # Check if subscription already exists
    existing = session.query(Subscription).filter_by(tenant_id=tenant_id).first()
    if existing:
        raise BusinessLogicError(f"Tenant {tenant_id} already has a subscription")
    
    # Get free plan
    free_plan = session.query(Plan).filter_by(code='free').first()
    if not free_plan:
        raise NotFoundError("Free plan not found in database")
    
    trial_end = datetime.utcnow() + timedelta(days=30)
    
    subscription = Subscription(
        tenant_id=tenant_id,
        plan_type='free',
        plan_id=free_plan.id,
        status='trial',
        trial_ends_at=trial_end,
        amount=0.00,
        auto_recurring=False
    )
    
    session.add(subscription)
    session.flush()
    
    logger.info(f"Created trial subscription for tenant {tenant_id}, expires {trial_end}")
    return subscription


def activate_paid_subscription(
    tenant_id: int,
    plan_code: str,
    mp_subscription_id: str,
    mp_payer_id: str,
    session: Session
) -> Subscription:
    """
    Activate a paid subscription after successful payment.
    
    Args:
        tenant_id: ID of the tenant
        plan_code: Plan code ('basic', 'pro', etc.)
        mp_subscription_id: Mercado Pago subscription ID
        mp_payer_id: Mercado Pago payer ID
        session: Database session
        
    Returns:
        Subscription: Updated subscription object
    """
    subscription = session.query(Subscription).filter_by(tenant_id=tenant_id).first()
    if not subscription:
        raise NotFoundError(f"Subscription not found for tenant {tenant_id}")
    
    plan = session.query(Plan).filter_by(code=plan_code, is_active=True).first()
    if not plan:
        raise NotFoundError(f"Plan '{plan_code}' not found or inactive")
    
    # Update subscription
    subscription.plan_type = plan_code
    subscription.plan_id = plan.id
    subscription.status = 'active'
    subscription.mp_subscription_id = mp_subscription_id
    subscription.mp_payer_id = mp_payer_id
    subscription.mp_status = 'authorized'
    subscription.auto_recurring = True
    subscription.amount = plan.price
    subscription.trial_ends_at = None  # Clear trial
    subscription.next_billing_date = datetime.utcnow() + timedelta(days=30)
    subscription.updated_at = datetime.utcnow()
    
    session.flush()
    
    logger.info(f"Activated paid subscription for tenant {tenant_id}: {plan_code}")
    return subscription


def check_trial_expiration(tenant_id: int, session: Session) -> Dict[str, Any]:
    """
    Check if trial has expired and return status.
    
    Args:
        tenant_id: ID of the tenant
        session: Database session
        
    Returns:
        dict: Status information
    """
    subscription = session.query(Subscription).filter_by(tenant_id=tenant_id).first()
    if not subscription:
        return {'exists': False, 'expired': False}
    
    if subscription.status != 'trial':
        return {'exists': True, 'expired': False, 'status': subscription.status}
    
    if not subscription.trial_ends_at:
        return {'exists': True, 'expired': False, 'status': 'trial', 'no_end_date': True}
    
    now = datetime.utcnow()
    expired = now > subscription.trial_ends_at
    
    if expired and subscription.status == 'trial':
        # Auto-transition to past_due
        subscription.status = 'past_due'
        subscription.updated_at = now
        session.flush()
        logger.warning(f"Trial expired for tenant {tenant_id}, status changed to past_due")
    
    return {
        'exists': True,
        'expired': expired,
        'status': subscription.status,
        'trial_ends_at': subscription.trial_ends_at,
        'days_remaining': (subscription.trial_ends_at - now).days if not expired else 0
    }


def cancel_subscription(tenant_id: int, session: Session) -> Subscription:
    """
    Cancel a subscription (mark as canceled, keep data).
    
    Args:
        tenant_id: ID of the tenant
        session: Database session
        
    Returns:
        Subscription: Updated subscription object
    """
    subscription = session.query(Subscription).filter_by(tenant_id=tenant_id).first()
    if not subscription:
        raise NotFoundError(f"Subscription not found for tenant {tenant_id}")
    
    subscription.status = 'canceled'
    subscription.auto_recurring = False
    subscription.updated_at = datetime.utcnow()
    
    session.flush()
    
    logger.info(f"Canceled subscription for tenant {tenant_id}")
    return subscription


def sync_subscription_from_mp(mp_subscription_id: str, session: Session) -> Optional[Subscription]:
    """
    Sync subscription status from Mercado Pago.
    
    Args:
        mp_subscription_id: Mercado Pago subscription ID
        session: Database session
        
    Returns:
        Subscription: Updated subscription or None
    """
    subscription = session.query(Subscription).filter_by(
        mp_subscription_id=mp_subscription_id
    ).first()
    
    if not subscription:
        logger.warning(f"Subscription not found for MP ID: {mp_subscription_id}")
        return None
    
    try:
        mp_service = MercadoPagoService()
        mp_data = mp_service.get_subscription(mp_subscription_id)
        
        if not mp_data:
            logger.error(f"Failed to fetch MP subscription: {mp_subscription_id}")
            return subscription
        
        # Map MP status to our status
        mp_status = mp_data.get('status')
        status_map = {
            'authorized': 'active',
            'paused': 'past_due',
            'cancelled': 'canceled',
            'pending': 'past_due'
        }
        
        new_status = status_map.get(mp_status, subscription.status)
        
        subscription.mp_status = mp_status
        subscription.status = new_status
        subscription.updated_at = datetime.utcnow()
        
        session.flush()
        
        logger.info(f"Synced subscription {subscription.id} from MP: {mp_status} -> {new_status}")
        return subscription
        
    except Exception as e:
        logger.exception(f"Error syncing subscription from MP: {e}")
        return subscription


def sync_subscription_status(tenant_id: int, session: Session) -> Optional[Subscription]:
    """
    Sync subscription status for a tenant by finding their MP ID.
    """
    subscription = session.query(Subscription).filter_by(tenant_id=tenant_id).first()
    if subscription and subscription.mp_subscription_id:
        return sync_subscription_from_mp(subscription.mp_subscription_id, session)
    return subscription


def get_subscription_status(tenant_id: int, session: Session) -> Dict[str, Any]:
    """
    Get comprehensive subscription status for a tenant.
    
    Args:
        tenant_id: ID of the tenant
        session: Database session
        
    Returns:
        dict: Subscription status details
    """
    subscription = session.query(Subscription).filter_by(tenant_id=tenant_id).first()
    
    if not subscription:
        return {
            'exists': False,
            'status': None,
            'plan': None,
            'is_active': False
        }
    
    plan = session.query(Plan).filter_by(id=subscription.plan_id).first() if subscription.plan_id else None
    
    return {
        'exists': True,
        'status': subscription.status,
        'plan': {
            'code': plan.code if plan else subscription.plan_type,
            'name': plan.name if plan else subscription.plan_type.title(),
            'price': float(plan.price) if plan else 0.0,
            'currency': plan.currency if plan else 'ARS',
            'features': [{'key': f.feature_key, 'value': f.feature_value} for f in plan.features] if plan and plan.features else []
        },
        'is_active': subscription.is_active,
        'is_trial': subscription.is_trial,
        'trial_ends_at': subscription.trial_ends_at,
        'next_billing_date': subscription.next_billing_date,
        'mp_subscription_id': subscription.mp_subscription_id,
        'auto_recurring': subscription.auto_recurring
    }


# Alias for compatibility
get_subscription_details = get_subscription_status
