"""Payment service for purchase invoice payment processing - Multi-Tenant."""
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from app.models import (
    PurchaseInvoice, InvoiceStatus, PurchaseInvoicePayment,
    FinanceLedger, LedgerType, LedgerReferenceType, PaymentMethod
)


def register_invoice_payment(
    tenant_id: int,
    invoice_id: int,
    amount: Decimal,
    payment_method: str,
    paid_at: datetime,
    notes: str = None,
    user_id: int = None,
    session=None
) -> object:
    """
    Register a payment for a purchase invoice (partial or full).
    
    Args:
        tenant_id: Tenant ID
        invoice_id: Invoice ID
        amount: Payment amount
        payment_method: 'CASH', 'TRANSFER', 'CARD'
        paid_at: Payment date/time
        notes: Optional notes
        user_id: User ID registering the payment
        session: SQLAlchemy session
        
    Returns:
        PurchaseInvoicePayment object
    """
    try:
        # Step 1: Lock invoice row and validate tenant
        invoice = (
            session.query(PurchaseInvoice)
            .filter(
                PurchaseInvoice.id == invoice_id,
                PurchaseInvoice.tenant_id == tenant_id
            )
            .with_for_update()
            .first()
        )
        
        if not invoice:
            raise ValueError(f'Boleta con ID {invoice_id} no encontrada o no pertenece a su negocio')
        
        # Step 2: Validate status
        if invoice.status == InvoiceStatus.PAID:
            raise ValueError('La boleta ya está totalmente pagada.')
            
        # Step 3: validate amount
        if amount <= 0:
            raise ValueError('El monto a pagar debe ser mayor a 0.')
            
        pending_amount = invoice.total_amount - invoice.paid_amount
        # Allow a small epsilon for float precision issues if needed, but Decimal handles this well.
        # Check if amount > pending_amount
        if amount > pending_amount:
            # Format amounts in Argentine format for error message
            from app.utils.formatters import money_ar_2
            amount_formatted = money_ar_2(amount)
            pending_formatted = money_ar_2(pending_amount)
            raise ValueError(
                f'El monto a pagar (${amount_formatted}) no puede ser mayor al saldo pendiente (${pending_formatted}).'
            )
            
        # Step 4: Create payment record
        from app.models import normalize_payment_method
        payment_method_normalized = normalize_payment_method(payment_method)
        
        payment = PurchaseInvoicePayment(
            tenant_id=tenant_id,
            invoice_id=invoice_id,
            payment_method=payment_method_normalized,
            amount=amount,
            paid_at=paid_at,
            notes=notes,
            created_by=user_id
        )
        session.add(payment)
        
        # Step 5: Update invoice
        invoice.paid_amount += amount
        
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
            # If strictly equal, fine. If greater (should be caught by check above), clamp?
            # Ideally paid_amount matches total_amount exactly.
            if invoice.paid_at is None:
                invoice.paid_at = paid_at.date() if isinstance(paid_at, datetime) else paid_at
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
            
        session.flush()
        
        # Step 6: Create finance ledger entry
        # Sanitize notes
        supplier_name_safe = str(invoice.supplier.name).replace('\\', '/').replace('\n', ' ').replace('\r', '')
        invoice_number_safe = str(invoice.invoice_number).replace('\\', '/').replace('\n', ' ').replace('\r', '')
        
        ledger_notes = f'Pago parcial boleta #{invoice_number_safe} - {supplier_name_safe}'
        if notes:
            ledger_notes += f' ({notes})'
            
        ledger_entry = FinanceLedger(
            tenant_id=tenant_id,
            datetime=paid_at,
            type=LedgerType.EXPENSE,
            amount=amount,
            category="Pago Boleta",
            reference_type=LedgerReferenceType.INVOICE_PAYMENT,
            reference_id=invoice.id,
            notes=ledger_notes[:500],
            payment_method=payment_method_normalized
        )
        session.add(ledger_entry)
        
        # NOTE: Commit is handled by the caller (route)
        
        # Invalidate cache
        try:
            from app.services.cache_service import get_cache
            cache = get_cache()
            cache.invalidate_module(tenant_id, 'balance')
        except Exception:
            pass
            
        return payment

    except ValueError:
        raise
    except IntegrityError as e:
        raise Exception(f'Error de integridad: {str(e.orig)}')
    except Exception as e:
        raise Exception(f'Error al registrar pago: {str(e)}')


def pay_invoice(invoice_id: int, paid_at: date, session, payment_method: str = 'CASH', tenant_id: int = None) -> None:
    """
    Legacy wrapper for full payment.
    """
    # Fetch invoice to get total amount
    invoice = session.query(PurchaseInvoice).get(invoice_id)
    if not invoice:
        raise ValueError('Boleta no encontrada')
        
    amount = invoice.total_amount - invoice.paid_amount
    if amount <= 0:
        raise ValueError('La boleta ya está pagada')
        
    register_invoice_payment(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        amount=amount,
        payment_method=payment_method,
        paid_at=datetime.combine(paid_at, datetime.min.time()),
        session=session
    )
