"""Payment service for purchase invoice payment processing - Multi-Tenant."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models import (
    PurchaseInvoice, InvoiceStatus, PurchaseInvoicePayment,
    FinanceLedger, LedgerType, LedgerReferenceType, 
    normalize_payment_method
)
from app.utils.formatters import money_ar_2
from app.services.cache_service import get_cache
from app.exceptions import BusinessLogicError, NotFoundError


def register_invoice_payment(
    tenant_id: int,
    invoice_id: int,
    amount: Decimal,
    payment_method: str,
    paid_at: datetime,
    notes: Optional[str] = None,
    user_id: Optional[int] = None,
    session: Session = None
) -> PurchaseInvoicePayment:
    """
    Register a payment for a purchase invoice (partial or full).
    """
    try:
        # 1. Lock invoice and validate tenant
        invoice = session.query(PurchaseInvoice).filter(
            PurchaseInvoice.id == invoice_id,
            PurchaseInvoice.tenant_id == tenant_id
        ).with_for_update().first()
        
        if not invoice:
            raise NotFoundError(f'Factura #{invoice_id} no encontrada.')
        
        if invoice.status == InvoiceStatus.PAID:
            raise BusinessLogicError('La factura ya está totalmente pagada.')
            
        if amount <= 0:
            raise BusinessLogicError('El monto debe ser mayor a 0.')
            
        pending = invoice.total_amount - invoice.paid_amount
        if amount > pending:
            raise BusinessLogicError(
                f'Monto ({money_ar_2(amount)}) excede el saldo pendiente ({money_ar_2(pending)}).'
            )
            
        # 2. Register Payment
        method_norm = normalize_payment_method(payment_method)
        payment = PurchaseInvoicePayment(
            tenant_id=tenant_id, invoice_id=invoice_id,
            payment_method=method_norm, amount=amount,
            paid_at=paid_at, notes=notes, created_by=user_id
        )
        session.add(payment)
        
        # 3. Update Invoice Status
        invoice.paid_amount += amount
        if invoice.paid_amount >= invoice.total_amount:
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = paid_at.date() if isinstance(paid_at, datetime) else paid_at
        else:
            invoice.status = InvoiceStatus.PARTIALLY_PAID
            
        session.flush()
        
        # 4. Create Ledger Entry
        # Simple sanitization
        supp_name = str(invoice.supplier.name).strip().replace('\n', ' ')[:100]
        inv_no = str(invoice.invoice_number).strip()
        ledger_notes = f'Pago boleta #{inv_no} - {supp_name}'
        if notes: ledger_notes += f' ({notes.strip()})'
            
        session.add(FinanceLedger(
            tenant_id=tenant_id, datetime=paid_at, type=LedgerType.EXPENSE,
            amount=amount.quantize(Decimal('0.01')), category="Pago Boleta",
            reference_type=LedgerReferenceType.INVOICE_PAYMENT,
            reference_id=invoice.id, notes=ledger_notes[:500],
            payment_method=method_norm
        ))
        
        # 5. Cache Invalidation
        try:
            cache = get_cache()
            cache.invalidate_module(tenant_id, 'balance')
        except Exception:
            pass
            
        return payment

    except (BusinessLogicError, NotFoundError) as e:
        raise e
    except Exception:
        raise


def pay_invoice(invoice_id: int, paid_at: date, session: Session, payment_method: str = 'CASH', tenant_id: int = None) -> None:
    """Legacy wrapper for full payment."""
    invoice = session.query(PurchaseInvoice).filter(
        PurchaseInvoice.id == invoice_id,
        PurchaseInvoice.tenant_id == tenant_id
    ).first()
    
    if not invoice: 
        raise NotFoundError('Factura no encontrada.')
        
    amount = invoice.total_amount - invoice.paid_amount
    if amount <= 0: 
        raise BusinessLogicError('La factura ya está pagada.')
        
    register_invoice_payment(
        tenant_id=tenant_id,
        invoice_id=invoice_id,
        amount=amount,
        payment_method=payment_method,
        paid_at=datetime.combine(paid_at, datetime.min.time()),
        session=session
    )
