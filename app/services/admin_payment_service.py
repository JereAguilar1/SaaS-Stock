"""
Admin Payment Service - Business logic for manual payment management.
"""
from datetime import date
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models import Payment, Tenant, AdminAuditLog, AdminAuditAction


def create_payment(db_session: Session, tenant_id: int, data: dict, admin_user_id: int, ip_address: str = None):
    """
    Create a manual payment record for a tenant.
    
    Args:
        db_session: Database session
        tenant_id: ID of the tenant
        data: Payment data (amount, payment_date, payment_method, reference, notes)
        admin_user_id: ID of the admin creating the payment
        ip_address: IP address of the admin
        
    Returns:
        tuple: (success: bool, message: str, payment: Payment or None)
    """
    # Validate tenant exists
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        return False, 'Tenant no encontrado', None
    
    # Validate amount
    try:
        amount = Decimal(str(data.get('amount', 0)))
        if amount <= 0:
            return False, 'El monto debe ser mayor a 0', None
    except (ValueError, TypeError):
        return False, 'Monto inválido', None
    
    # Create payment
    payment = Payment(
        tenant_id=tenant_id,
        amount=amount,
        payment_date=data.get('payment_date', date.today()),
        payment_method=data.get('payment_method', 'transfer'),
        reference=data.get('reference'),
        notes=data.get('notes'),
        status='paid',
        created_by=admin_user_id
    )
    
    db_session.add(payment)
    
    # Update subscription total amount (LTV)
    if tenant.subscription:
        current_amount = tenant.subscription.amount or Decimal('0.00')
        tenant.subscription.amount = current_amount + amount
    
    # Audit log
    audit = AdminAuditLog.log_action(
        admin_user_id=admin_user_id,
        action=AdminAuditAction.REGISTER_PAYMENT,
        target_tenant_id=tenant_id,
        details={
            'amount': str(amount),
            'payment_date': str(payment.payment_date),
            'payment_method': payment.payment_method,
            'reference': payment.reference
        },
        ip_address=ip_address
    )
    db_session.add(audit)
    
    try:
        db_session.commit()
        return True, 'Pago registrado exitosamente', payment
    except Exception as e:
        db_session.rollback()
        return False, f'Error al registrar pago: {str(e)}', None


def get_payments_by_tenant(db_session: Session, tenant_id: int):
    """
    Get all payments for a specific tenant, ordered by date descending.
    
    Args:
        db_session: Database session
        tenant_id: ID of the tenant
        
    Returns:
        list: List of Payment objects
    """
    return db_session.query(Payment)\
        .filter_by(tenant_id=tenant_id)\
        .order_by(Payment.payment_date.desc())\
        .all()


def void_payment(db_session: Session, payment_id: int, admin_user_id: int, ip_address: str = None):
    """
    Void a payment (soft delete - marks as void instead of deleting).
    
    Args:
        db_session: Database session
        payment_id: ID of the payment to void
        admin_user_id: ID of the admin voiding the payment
        ip_address: IP address of the admin
        
    Returns:
        tuple: (success: bool, message: str)
    """
    payment = db_session.query(Payment).filter_by(id=payment_id).first()
    
    if not payment:
        return False, 'Pago no encontrado'
    
    if payment.status == 'void':
        return False, 'El pago ya está anulado'
    
    # Update payment status
    original_status = payment.status
    payment.status = 'void'
    
    # Reverse subscription amount if it was paid
    if original_status == 'paid' and payment.tenant.subscription:
        current_amount = payment.tenant.subscription.amount or Decimal('0.00')
        payment.tenant.subscription.amount = max(Decimal('0.00'), current_amount - payment.amount)
    
    # Audit log
    audit = AdminAuditLog.log_action(
        admin_user_id=admin_user_id,
        action='VOID_PAYMENT',
        target_tenant_id=payment.tenant_id,
        details={
            'payment_id': payment.id,
            'amount': str(payment.amount),
            'original_status': original_status
        },
        ip_address=ip_address
    )
    db_session.add(audit)
    
    try:
        db_session.commit()
        return True, 'Pago anulado exitosamente'
    except Exception as e:
        db_session.rollback()
        return False, f'Error al anular pago: {str(e)}'
