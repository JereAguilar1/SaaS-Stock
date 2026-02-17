"""Sale Draft Service - Persistent cart operations (multi-tenant)."""

from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models import SaleDraft, SaleDraftLine, Product
from app.exceptions import BusinessLogicError, NotFoundError, InsufficientStockError


def get_or_create_draft(session: Session, tenant_id: int, user_id: int) -> SaleDraft:
    """
    Get existing draft or create new one for user.
    One draft per user per tenant.
    """
    draft = session.query(SaleDraft).filter(
        SaleDraft.tenant_id == tenant_id,
        SaleDraft.user_id == user_id
    ).first()
    
    if not draft:
        draft = SaleDraft(
            tenant_id=tenant_id,
            user_id=user_id,
            discount_type=None,
            discount_value=Decimal('0')
        )
        session.add(draft)
        # ROBUSTEZ: Solo flush() para asegurar ID sin comprometer el resto de la sesión externa
        session.flush()
    
    return draft


def add_product_to_draft(
    session: Session,
    draft_id: int,
    product_id: int,
    qty: Decimal,
    tenant_id: int
) -> SaleDraftLine:
    """Add product to draft or update quantity if already exists."""
    draft = session.query(SaleDraft).filter(
        SaleDraft.id == draft_id,
        SaleDraft.tenant_id == tenant_id
    ).first()
    
    if not draft:
        raise NotFoundError('Borrador no encontrado.')
    
    product = session.query(Product).filter(
        Product.id == product_id,
        Product.tenant_id == tenant_id
    ).first()
    
    if not product:
        raise NotFoundError('Producto no encontrado.')
    if not product.active:
        raise BusinessLogicError(f'El producto "{product.name}" no está activo.')
    
    if product.on_hand_qty <= 0:
        raise InsufficientStockError(product.name, qty, product.on_hand_qty)
    
    line = session.query(SaleDraftLine).filter(
        SaleDraftLine.draft_id == draft_id,
        SaleDraftLine.product_id == product_id
    ).first()
    
    if line:
        new_qty = line.qty + qty
        if new_qty > product.on_hand_qty:
            raise InsufficientStockError(product.name, new_qty, product.on_hand_qty)
        line.qty = new_qty
    else:
        if qty > product.on_hand_qty:
            raise InsufficientStockError(product.name, qty, product.on_hand_qty)
        line = SaleDraftLine(draft_id=draft_id, product_id=product_id, qty=qty)
        session.add(line)
        
    draft.updated_at = datetime.now()
    session.flush()
    return line


def update_draft_line(
    session: Session,
    draft_id: int,
    product_id: int,
    qty: Optional[Decimal] = None,
    discount_type: Optional[str] = None,
    discount_value: Optional[Decimal] = Decimal('0'),
    tenant_id: int = None
) -> SaleDraftLine:
    """Update draft line quantity or discount."""
    draft = session.query(SaleDraft).filter(SaleDraft.id == draft_id, SaleDraft.tenant_id == tenant_id).first()
    if not draft:
        raise NotFoundError('Borrador no encontrado.')
    
    line = session.query(SaleDraftLine).filter(SaleDraftLine.draft_id == draft_id, SaleDraftLine.product_id == product_id).first()
    if not line:
        raise NotFoundError('El producto no está en el carrito.')
    
    if qty is not None:
        if qty <= 0:
            raise BusinessLogicError('La cantidad debe ser mayor a 0.')
        if qty > line.product.on_hand_qty:
            raise InsufficientStockError(line.product.name, qty, line.product.on_hand_qty)
        line.qty = qty
    
    # Update discount fields
    line.discount_type = discount_type
    line.discount_value = discount_value if discount_value is not None else Decimal('0')
    
    draft.updated_at = datetime.now()
    session.flush()
    return line


def remove_draft_line(session: Session, draft_id: int, product_id: int, tenant_id: int) -> None:
    """Remove line from draft."""
    draft = session.query(SaleDraft).filter(SaleDraft.id == draft_id, SaleDraft.tenant_id == tenant_id).first()
    if draft:
        line = session.query(SaleDraftLine).filter(SaleDraftLine.draft_id == draft_id, SaleDraftLine.product_id == product_id).first()
        if line:
            session.delete(line)
            draft.updated_at = datetime.now()
            session.flush()


def clear_draft(session: Session, draft_id: int, tenant_id: int) -> None:
    """Clear all lines from draft."""
    try:
        draft = session.query(SaleDraft).filter(SaleDraft.id == draft_id, SaleDraft.tenant_id == tenant_id).first()
        if not draft: return
        
        session.query(SaleDraftLine).filter(SaleDraftLine.draft_id == draft_id).delete()
        draft.discount_type = None
        draft.discount_value = Decimal('0')
        draft.updated_at = datetime.now()
        session.flush()
    except Exception:
        pass


def calculate_draft_totals(draft: SaleDraft) -> Dict[str, Any]:
    """Calculate totals for draft (Discounts are currently disabled)."""
    lines_details = []
    subtotal = Decimal('0')
    
    for line in draft.lines:
        unit_price = line.product.sale_price
        line_subtotal = (line.qty * unit_price).quantize(Decimal('0.01'))
        
        lines_details.append({
            'product_id': line.product.id,
            'product_name': line.product.name,
            'product_uom_name': line.product.uom.name if line.product.uom else '',
            'qty': line.qty,
            'unit_price': unit_price,
            'line_subtotal': line_subtotal,
            'line_total': line_subtotal
        })
        subtotal += line_subtotal
    
    return {
        'subtotal': subtotal.quantize(Decimal('0.01')),
        'total': subtotal.quantize(Decimal('0.01')),
        'lines': lines_details
    }


def get_draft_with_totals(session: Session, tenant_id: int, user_id: int) -> Tuple[Optional[SaleDraft], Dict[str, Any]]:
    """Get draft with totals dictionary."""
    draft = session.query(SaleDraft).filter(SaleDraft.tenant_id == tenant_id, SaleDraft.user_id == user_id).first()
    if not draft:
        return None, {'subtotal': Decimal('0'), 'total': Decimal('0'), 'lines': []}
    
    return draft, calculate_draft_totals(draft)
