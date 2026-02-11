"""Customer service for default customer management."""
from app.models import Customer
from sqlalchemy.exc import IntegrityError


def get_or_create_default_customer_id(session, tenant_id: int) -> int:
    """
    Get or create default customer "Consumidor Final" for a tenant.
    
    This function is idempotent and thread-safe thanks to the unique constraint
    on (tenant_id) WHERE is_default = true.
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant ID
        
    Returns:
        customer_id: ID of default customer
        
    Raises:
        Exception: If unable to create or retrieve default customer
    """
    # Try to get existing default customer
    default_customer = session.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.is_default == True
    ).first()
    
    if default_customer:
        return default_customer.id
    
    # Create default customer if not exists
    try:
        customer = Customer(
            tenant_id=tenant_id,
            name='Consumidor Final',
            is_default=True,
            notes='Cliente por defecto del sistema'
        )
        session.add(customer)
        session.flush()  # Get ID without committing
        return customer.id
        
    except IntegrityError:
        # Race condition: another process/thread created it simultaneously
        # Rollback this transaction and query again
        session.rollback()
        
        default_customer = session.query(Customer).filter(
            Customer.tenant_id == tenant_id,
            Customer.is_default == True
        ).first()
        
        if default_customer:
            return default_customer.id
        
        # This should never happen, but handle it gracefully
        raise Exception(f'No se pudo crear o recuperar cliente por defecto para tenant {tenant_id}')
