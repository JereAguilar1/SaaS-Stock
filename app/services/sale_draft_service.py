"""Sale Draft Service - Persistent cart operations (multi-tenant)."""
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from sqlalchemy.orm import Session
from app.models import (
    SaleDraft, SaleDraftLine, Product, ProductStock
)


def get_or_create_draft(session: Session, tenant_id: int, user_id: int) -> SaleDraft:
    """
    Get existing draft or create new one for user.
    
    One draft per user per tenant (enforced by UNIQUE constraint).
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant ID
        user_id: User ID
    
    Returns:
        SaleDraft instance
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
        session.flush()
        # ROBUSTEZ: Commit inmediato para garantizar ID disponible
        session.commit()
    
    return draft


def add_product_to_draft(
    session: Session,
    draft_id: int,
    product_id: int,
    qty: Decimal,
    tenant_id: int
) -> SaleDraftLine:
    """
    Add product to draft or update quantity if already exists.
    
    Args:
        session: SQLAlchemy session
        draft_id: Draft ID
        product_id: Product ID
        qty: Quantity to add (positive)
        tenant_id: Tenant ID (for validation)
    
    Returns:
        SaleDraftLine instance
    
    Raises:
        ValueError: If validation fails
    """
    # Validate draft belongs to tenant
    draft = session.query(SaleDraft).filter(
        SaleDraft.id == draft_id,
        SaleDraft.tenant_id == tenant_id
    ).first()
    
    if not draft:
        raise ValueError('Draft no encontrado o no pertenece a su negocio')
    
    # Validate product belongs to tenant and is active
    product = session.query(Product).filter(
        Product.id == product_id,
        Product.tenant_id == tenant_id
    ).first()
    
    if not product:
        raise ValueError('Producto no encontrado o no pertenece a su negocio')
    
    if not product.active:
        raise ValueError(f'El producto "{product.name}" no está activo')
    
    # Check stock availability
    if product.on_hand_qty <= 0:
        raise ValueError(f'El producto "{product.name}" no tiene stock disponible')
    
    # Check if line already exists
    line = session.query(SaleDraftLine).filter(
        SaleDraftLine.draft_id == draft_id,
        SaleDraftLine.product_id == product_id
    ).first()
    
    if line:
        # Update existing line
        new_qty = line.qty + qty
        
        if new_qty > product.on_hand_qty:
            raise ValueError(
                f'Stock insuficiente para "{product.name}". '
                f'Disponible: {product.on_hand_qty}, Solicitado: {new_qty}'
            )
        
        line.qty = new_qty
        draft.updated_at = datetime.now()
    else:
        # Create new line
        if qty > product.on_hand_qty:
            raise ValueError(
                f'Stock insuficiente para "{product.name}". '
                f'Disponible: {product.on_hand_qty}, Solicitado: {qty}'
            )
        
        line = SaleDraftLine(
            draft_id=draft_id,
            product_id=product_id,
            qty=qty,
            discount_type=None,
            discount_value=Decimal('0')
        )
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
    discount_value: Optional[Decimal] = None,
    tenant_id: int = None
) -> SaleDraftLine:
    """
    Update draft line quantity and/or discount.
    
    Args:
        session: SQLAlchemy session
        draft_id: Draft ID
        product_id: Product ID
        qty: New quantity (if provided)
        discount_type: 'PERCENT' or 'AMOUNT' (if provided)
        discount_value: Discount value (if provided)
        tenant_id: Tenant ID (for validation)
    
    Returns:
        Updated SaleDraftLine
    
    Raises:
        ValueError: If validation fails
    """
    # Validate draft belongs to tenant
    draft = session.query(SaleDraft).filter(
        SaleDraft.id == draft_id,
        SaleDraft.tenant_id == tenant_id
    ).first()
    
    if not draft:
        raise ValueError('Draft no encontrado')
    
    # Get line
    line = session.query(SaleDraftLine).filter(
        SaleDraftLine.draft_id == draft_id,
        SaleDraftLine.product_id == product_id
    ).first()
    
    if not line:
        raise ValueError('Línea no encontrada en el carrito')
    
    # Update quantity if provided
    if qty is not None:
        if qty <= 0:
            raise ValueError('La cantidad debe ser mayor a 0')
        
        # Validate stock
        product = line.product
        if qty > product.on_hand_qty:
            raise ValueError(
                f'Stock insuficiente para "{product.name}". '
                f'Disponible: {product.on_hand_qty}'
            )
        
        line.qty = qty
    
    # Update discount if provided - DISABLED
    # if discount_type is not None:
    #     if discount_type not in ['PERCENT', 'AMOUNT', None]:
    #         raise ValueError('Tipo de descuento inválido')
    #     line.discount_type = discount_type
    
    # if discount_value is not None:
    #     if discount_value < 0:
    #         raise ValueError('El descuento no puede ser negativo')
    #     line.discount_value = discount_value
    
    draft.updated_at = datetime.now()
    session.flush()
    return line


def remove_draft_line(
    session: Session,
    draft_id: int,
    product_id: int,
    tenant_id: int
) -> None:
    """
    Remove line from draft.
    
    Args:
        session: SQLAlchemy session
        draft_id: Draft ID
        product_id: Product ID
        tenant_id: Tenant ID (for validation)
    
    Raises:
        ValueError: If validation fails
    """
    # Validate draft belongs to tenant
    draft = session.query(SaleDraft).filter(
        SaleDraft.id == draft_id,
        SaleDraft.tenant_id == tenant_id
    ).first()
    
    if not draft:
        raise ValueError('Draft no encontrado')
    
    # Get and delete line
    line = session.query(SaleDraftLine).filter(
        SaleDraftLine.draft_id == draft_id,
        SaleDraftLine.product_id == product_id
    ).first()
    
    if line:
        session.delete(line)
        draft.updated_at = datetime.now()
        session.flush()


def clear_draft(session: Session, draft_id: int, tenant_id: int) -> None:
    """
    Clear all lines from draft.
    
    Args:
        session: SQLAlchemy session
        draft_id: Draft ID
        tenant_id: Tenant ID (for validation)
    
    Raises:
        ValueError: If validation fails (non-critical, allows continuation)
    """
    try:
        # Validate draft belongs to tenant
        draft = session.query(SaleDraft).filter(
            SaleDraft.id == draft_id,
            SaleDraft.tenant_id == tenant_id
        ).first()
        
        if not draft:
            # ROBUSTEZ: No romper si draft no existe, solo loguear
            import logging
            logging.warning(f"clear_draft: Draft {draft_id} not found for tenant {tenant_id}")
            return
        
        # Delete all lines (cascade will handle this, but explicit is better)
        session.query(SaleDraftLine).filter(
            SaleDraftLine.draft_id == draft_id
        ).delete()
        
        # Reset global discount
        draft.discount_type = None
        draft.discount_value = Decimal('0')
        draft.updated_at = datetime.now()
        
        session.flush()
    except Exception as e:
        # ROBUSTEZ: No propagar error, solo loguear
        import logging
        logging.error(f"Error in clear_draft: {e}", exc_info=True)


def apply_global_discount(
    session: Session,
    draft_id: int,
    discount_type: Optional[str],
    discount_value: Decimal,
    tenant_id: int
) -> SaleDraft:
    """
    Apply global discount to draft.
    
    Args:
        session: SQLAlchemy session
        draft_id: Draft ID
        discount_type: 'PERCENT' or 'AMOUNT' or None
        discount_value: Discount value
        tenant_id: Tenant ID (for validation)
    
    Returns:
        Updated SaleDraft
    
    Raises:
        ValueError: If validation fails
    """
    # Validate draft belongs to tenant
    draft = session.query(SaleDraft).filter(
        SaleDraft.id == draft_id,
        SaleDraft.tenant_id == tenant_id
    ).first()
    
    if not draft:
        raise ValueError('Draft no encontrado')
    
    if discount_type not in ['PERCENT', 'AMOUNT', None]:
        raise ValueError('Tipo de descuento inválido')
    
    if discount_value < 0:
        raise ValueError('El descuento no puede ser negativo')
    
    draft.discount_type = discount_type
    draft.discount_value = discount_value
    draft.updated_at = datetime.now()
    
    session.flush()
    return draft


def calculate_draft_totals(draft: SaleDraft) -> Dict[str, Decimal]:
    """
    Calculate totals for draft with discounts applied.
    
    Args:
        draft: SaleDraft instance (with lines loaded)
    
    Returns:
        Dict with:
            - subtotal: Sum of all lines before discounts
            - line_discounts: Total line-level discounts
            - subtotal_after_line_discounts: Subtotal after line discounts
            - global_discount: Global discount amount
            - total: Final total after all discounts
            - lines: List of line details with calculations
    """
    lines_details = []
    subtotal = Decimal('0')
    line_discounts_total = Decimal('0') # Always 0
    
    for line in draft.lines:
        product = line.product
        unit_price = product.sale_price
        qty = line.qty
        
        # Calculate line subtotal
        line_subtotal = (qty * unit_price).quantize(Decimal('0.01'))
        
        # Discounts DISABLED (Legacy support: force 0)
        line_discount = Decimal('0')
        # if line.discount_type == 'PERCENT':
        #     line_discount = (line_subtotal * line.discount_value / 100).quantize(Decimal('0.01'))
        # elif line.discount_type == 'AMOUNT':
        #     line_discount = min(line.discount_value, line_subtotal)
        
        line_total = line_subtotal - line_discount
        
        lines_details.append({
            'product_id': product.id,
            'product_name': product.name,
            'qty': qty,
            'unit_price': unit_price,
            'line_subtotal': line_subtotal,
            'discount_type': None,
            'discount_value': Decimal('0'),
            'line_discount': line_discount,
            'line_total': line_total
        })
        
        subtotal += line_subtotal
        line_discounts_total += line_discount
    
    subtotal_after_line_discounts = subtotal - line_discounts_total
    
    # Calculate global discount - DISABLED
    global_discount = Decimal('0')
    # if draft.discount_type == 'PERCENT':
    #     global_discount = (subtotal_after_line_discounts * draft.discount_value / 100).quantize(Decimal('0.01'))
    # elif draft.discount_type == 'AMOUNT':
    #     global_discount = min(draft.discount_value, subtotal_after_line_discounts)
    
    total = subtotal_after_line_discounts - global_discount
    
    return {
        'subtotal': subtotal.quantize(Decimal('0.01')),
        'line_discounts': Decimal('0.00'),
        'subtotal_after_line_discounts': subtotal.quantize(Decimal('0.01')),
        'global_discount': Decimal('0.00'),
        'total': total.quantize(Decimal('0.01')),
        'lines': lines_details
    }


def get_draft_with_totals(
    session: Session,
    tenant_id: int,
    user_id: int
) -> Tuple[Optional[SaleDraft], Dict[str, Decimal]]:
    """
    Get draft with calculated totals.
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant ID
        user_id: User ID
    
    Returns:
        Tuple of (draft, totals_dict)
    """
    draft = session.query(SaleDraft).filter(
        SaleDraft.tenant_id == tenant_id,
        SaleDraft.user_id == user_id
    ).first()
    
    if not draft:
        return None, {
            'subtotal': Decimal('0'),
            'line_discounts': Decimal('0'),
            'subtotal_after_line_discounts': Decimal('0'),
            'global_discount': Decimal('0'),
            'total': Decimal('0'),
            'lines': []
        }
    
    totals = calculate_draft_totals(draft)
    return draft, totals
