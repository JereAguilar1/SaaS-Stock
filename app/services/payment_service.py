"""Payment service for purchase invoice payment processing - Multi-Tenant."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.models import (
    PurchaseInvoice, InvoiceStatus,
    FinanceLedger, LedgerType, LedgerReferenceType, PaymentMethod
)


def pay_invoice(invoice_id: int, paid_at: date, session, payment_method: str = 'CASH', tenant_id: int = None) -> None:
    """
    Mark a purchase invoice as PAID and register EXPENSE (tenant-scoped).
    
    Steps (in a single transaction):
    1. Lock invoice row (SELECT FOR UPDATE) - validate tenant
    2. Validate invoice exists and is PENDING
    3. Validate paid_at is provided
    4. Update invoice: status=PAID, paid_at=paid_at
    5. Insert finance_ledger: type=EXPENSE, amount=total_amount, reference=INVOICE_PAYMENT, tenant_id
    6. Commit or rollback
    
    Args:
        invoice_id: ID of the invoice to pay
        paid_at: Payment date
        session: SQLAlchemy session
        payment_method: 'CASH' or 'TRANSFER'
        tenant_id: Tenant ID (REQUIRED for multi-tenant validation)
        
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    
    try:
        # Validate tenant_id is provided
        if not tenant_id:
            raise ValueError('tenant_id es requerido')
        
        # Start nested transaction
        session.begin_nested()
        
        # Step 1: Lock invoice row and validate tenant
        invoice = (
            session.query(PurchaseInvoice)
            .filter(
                PurchaseInvoice.id == invoice_id,
                PurchaseInvoice.tenant_id == tenant_id  # CRITICAL
            )
            .with_for_update()
            .first()
        )
        
        if not invoice:
            raise ValueError(f'Boleta con ID {invoice_id} no encontrada o no pertenece a su negocio')
        
        # Step 2: Validate invoice is PENDING
        if invoice.status != InvoiceStatus.PENDING:
            raise ValueError(
                f'La boleta ya está {invoice.status.value}. '
                f'Solo se pueden pagar boletas PENDING.'
            )
        
        # Step 3: Validate paid_at
        if not paid_at:
            raise ValueError('La fecha de pago es requerida')
        
        # Defensive: validate total_amount
        if invoice.total_amount < 0:
            raise ValueError(
                f'El monto total de la boleta es inválido: {invoice.total_amount}'
            )
        
        # Defensive: validate invoice has lines
        if not invoice.lines or len(invoice.lines) == 0:
            raise ValueError('La boleta no tiene ítems. No se puede pagar.')
        
        # Step 4: Update invoice
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = paid_at
        
        session.flush()  # Ensure invoice is updated before creating ledger entry
        
        # Step 5: Create finance_ledger entry (EXPENSE) with tenant_id
        from app.models import normalize_payment_method
        payment_method_normalized = normalize_payment_method(payment_method)
        
        # Sanitize notes to prevent issues with special characters
        supplier_name_safe = str(invoice.supplier.name).replace('\\', '/').replace('\n', ' ').replace('\r', '')
        invoice_number_safe = str(invoice.invoice_number).replace('\\', '/').replace('\n', ' ').replace('\r', '')
        notes_text = f'Pago boleta #{invoice_number_safe} - {supplier_name_safe}'
        
        ledger_entry = FinanceLedger(
            tenant_id=tenant_id,  # CRITICAL
            datetime=datetime.now(),
            type=LedgerType.EXPENSE,
            amount=invoice.total_amount,
            reference_type=LedgerReferenceType.INVOICE_PAYMENT,
            reference_id=invoice.id,
            notes=notes_text[:500],
            payment_method=payment_method_normalized
        )
        
        session.add(ledger_entry)
        
        # Step 6: Commit transaction
        session.commit()
        
    except ValueError:
        # Business logic errors - rollback and re-raise
        session.rollback()
        raise
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        raise Exception(f'Error de integridad al registrar pago: {error_msg}')
        
    except Exception as e:
        # Other errors - rollback and re-raise
        session.rollback()
        raise Exception(f'Error al procesar pago: {str(e)}')
