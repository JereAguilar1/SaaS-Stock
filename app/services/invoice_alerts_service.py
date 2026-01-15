"""
Service for invoice alerts and critical invoice tracking.
"""
from datetime import date, timedelta
from sqlalchemy import and_, or_
from app.models import PurchaseInvoice, InvoiceStatus


def get_invoice_alert_counts(session, today: date = None, tenant_id=None):
    """
    Get counts of critical invoices (due tomorrow or overdue) for a specific tenant.
    
    Args:
        session: SQLAlchemy session
        today: Date to use as reference (defaults to date.today())
        tenant_id: Tenant ID to filter by (required for multi-tenant)
    
    Returns:
        dict with keys:
            - due_tomorrow_count: int
            - overdue_count: int
            - total_critical: int
    """
    if today is None:
        today = date.today()
    
    tomorrow = today + timedelta(days=1)
    
    # Base query filters
    base_filters = [PurchaseInvoice.status == InvoiceStatus.PENDING]
    
    # Add tenant filter if provided
    if tenant_id is not None:
        base_filters.append(PurchaseInvoice.tenant_id == tenant_id)
    
    # Count invoices due tomorrow (PENDING only)
    due_tomorrow_count = session.query(PurchaseInvoice).filter(
        and_(
            *base_filters,
            PurchaseInvoice.due_date == tomorrow
        )
    ).count()
    
    # Count overdue invoices (PENDING only)
    overdue_count = session.query(PurchaseInvoice).filter(
        and_(
            *base_filters,
            PurchaseInvoice.due_date < today,
            PurchaseInvoice.due_date.isnot(None)
        )
    ).count()
    
    return {
        'due_tomorrow_count': due_tomorrow_count,
        'overdue_count': overdue_count,
        'total_critical': due_tomorrow_count + overdue_count
    }


def is_invoice_overdue(invoice, today: date = None):
    """
    Check if an invoice is overdue.
    
    Args:
        invoice: PurchaseInvoice instance
        today: Date to use as reference (defaults to date.today())
    
    Returns:
        bool: True if invoice is overdue
    """
    if today is None:
        today = date.today()
    
    return (
        invoice.status == InvoiceStatus.PENDING and
        invoice.due_date is not None and
        invoice.due_date < today
    )


def is_invoice_due_tomorrow(invoice, today: date = None):
    """
    Check if an invoice is due tomorrow.
    
    Args:
        invoice: PurchaseInvoice instance
        today: Date to use as reference (defaults to date.today())
    
    Returns:
        bool: True if invoice is due tomorrow
    """
    if today is None:
        today = date.today()
    
    tomorrow = today + timedelta(days=1)
    
    return (
        invoice.status == InvoiceStatus.PENDING and
        invoice.due_date == tomorrow
    )
