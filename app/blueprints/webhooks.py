"""
Webhooks Blueprint for Mercado Pago notifications.
Handles subscription events and payment notifications.
"""

import logging
import hmac
import hashlib
from flask import Blueprint, request, jsonify, current_app
from app.database import get_session
from app.services.subscription_service import sync_subscription_from_mp
from app.models.subscription import Subscription

logger = logging.getLogger(__name__)

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


def verify_mp_signature(request_data: bytes, signature: str) -> bool:
    """
    Verify Mercado Pago webhook signature.
    """
    secret = current_app.config.get('MP_WEBHOOK_SECRET')
    
    # If the secret is not set, contains a URL (misconfiguration), or we are in debug mode, skip verification
    if not secret or secret.startswith('http') or current_app.debug:
        logger.info("Skipping MP webhook signature verification (dev mode or misconfigured secret)")
        return True
    
    if not signature:
        logger.warning("Missing X-Signature header in MP webhook")
        return False
    
    try:
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            request_data,
            hashlib.sha256
        ).hexdigest()
        
        is_valid = hmac.compare_digest(signature, expected_signature)
        if not is_valid:
            logger.warning(f"Invalid signature. Expected: {expected_signature}, Received: {signature}")
        return is_valid
    except Exception as e:
        logger.exception(f"Error verifying MP signature: {e}")
        return False


@webhooks_bp.route('/mercadopago', methods=['POST'])
def mercadopago_webhook():
    """
    Handle Mercado Pago webhook notifications.
    
    Expected events:
    - subscription.created
    - subscription.updated
    - subscription.cancelled
    - payment (for subscription payments)
    """
    try:
        # Verify signature
        signature = request.headers.get('X-Signature', '')
        if not verify_mp_signature(request.get_data(), signature):
            logger.warning("Invalid MP webhook signature")
            return jsonify({'error': 'Invalid signature'}), 401
        
        data = request.get_json()
        if not data:
            logger.warning("Empty webhook payload")
            return jsonify({'error': 'Empty payload'}), 400
        
        event_type = data.get('type')
        event_action = data.get('action')
        
        logger.info(f"Received MP webhook: type={event_type}, action={event_action}")
        
        # Handle subscription events
        if event_type in ['subscription', 'subscription_preapproval', 'subscription_authorized_payment']:
            return handle_subscription_event(data)
        
        # Handle payment events
        elif event_type == 'payment':
            return handle_payment_event(data)
        
        else:
            logger.info(f"Unhandled webhook type: {event_type}")
            return jsonify({'status': 'ignored', 'type': event_type}), 200
        
    except Exception as e:
        logger.exception(f"Error processing MP webhook: {e}")
        return jsonify({'error': 'Internal server error'}), 500


def handle_subscription_event(data: dict) -> tuple:
    """
    Handle subscription-related webhook events.
    
    Args:
        data: Webhook payload
        
    Returns:
        tuple: (response, status_code)
    """
    action = data.get('action')
    subscription_data = data.get('data', {})
    
    # Preapproval ID can be in data.id or at the root id depending on the event type
    preapproval_id = subscription_data.get('id') or data.get('id')
    
    if not preapproval_id or str(preapproval_id).startswith('12345'): # Ignore MP test dummy IDs
        logger.warning(f"Missing or dummy preapproval_id in webhook: {preapproval_id}")
        return jsonify({'status': 'acknowledged', 'message': 'Dummy or missing ID'}), 200
    
    session = get_session()
    
    try:
        if action == 'created':
            logger.info(f"Subscription created: {preapproval_id}")
            # Sync from MP to get full details
            sync_subscription_from_mp(preapproval_id, session)
            session.commit()
            return jsonify({'status': 'processed'}), 200
        
        elif action == 'updated':
            logger.info(f"Subscription updated: {preapproval_id}")
            sync_subscription_from_mp(preapproval_id, session)
            session.commit()
            return jsonify({'status': 'processed'}), 200
        
        elif action == 'cancelled':
            logger.info(f"Subscription cancelled: {preapproval_id}")
            subscription = session.query(Subscription).filter_by(
                mp_subscription_id=preapproval_id
            ).first()
            
            if subscription:
                subscription.status = 'canceled'
                subscription.mp_status = 'cancelled'
                session.commit()
                logger.info(f"Marked subscription {subscription.id} as canceled")
            
            return jsonify({'status': 'processed'}), 200
        
        else:
            logger.info(f"Unhandled subscription action: {action}")
            return jsonify({'status': 'ignored'}), 200
    
    except Exception as e:
        logger.exception(f"Error handling subscription event: {e}")
        session.rollback()
        return jsonify({'error': 'Processing failed'}), 500
    finally:
        session.remove()


def handle_payment_event(data: dict) -> tuple:
    """
    Handle payment-related webhook events.
    
    Args:
        data: Webhook payload
        
    Returns:
        tuple: (response, status_code)
    """
    action = data.get('action')
    payment_data = data.get('data', {})
    payment_id = payment_data.get('id')
    
    if not payment_id:
        logger.warning("Missing payment_id in payment webhook")
        return jsonify({'error': 'Missing payment_id'}), 400
    
    logger.info(f"Payment event: action={action}, payment_id={payment_id}")
    
    # For now, just log payment events
    # In the future, we can:
    # 1. Fetch payment details from MP
    # 2. Update subscription next_billing_date
    # 3. Send confirmation emails
    # 4. Record payment in ledger
    
    if action == 'payment.created':
        logger.info(f"Payment created: {payment_id}")
    elif action == 'payment.updated':
        logger.info(f"Payment updated: {payment_id}")
    
    return jsonify({'status': 'acknowledged'}), 200


@webhooks_bp.route('/test', methods=['GET'])
def test_webhook():
    """Test endpoint to verify webhook is accessible."""
    return jsonify({
        'status': 'ok',
        'message': 'Webhook endpoint is active'
    }), 200
