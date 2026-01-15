"""Quote service for generating PDF quotes and managing persisted quotes."""
from datetime import datetime, date, timedelta
from decimal import Decimal
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from sqlalchemy.exc import IntegrityError
from app.models import (
    Quote, QuoteLine, Product, ProductStock,
    Sale, SaleLine, StockMove, StockMoveLine, FinanceLedger,
    SaleStatus, StockMoveType, StockReferenceType,
    LedgerType, LedgerReferenceType, PaymentMethod
)


def generate_quote_pdf(cart: dict, business_info: dict) -> BytesIO:
    """
    Generate a PDF quote from cart data.
    
    Args:
        cart: Cart dictionary with 'items' dict {product_id: {'name', 'price', 'qty', 'uom'}}
        business_info: Dictionary with business details:
            - name: Business name
            - address: Business address (optional)
            - phone: Business phone (optional)
            - email: Business email (optional)
            - valid_days: Quote validity in days
            - payment_method: Payment method selected (optional, from MEJORA 12)
    
    Returns:
        BytesIO: PDF file in memory
    """
    
    # Create PDF in memory
    buffer = BytesIO()
    
    # Create document (A4 size)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#7F8C8D'),
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    normal_style = styles['Normal']
    
    # -------------------
    # HEADER
    # -------------------
    
    # Title
    title = Paragraph("PRESUPUESTO", title_style)
    elements.append(title)
    
    # Business info
    if business_info.get('name'):
        business_name = Paragraph(f"<b>{business_info['name']}</b>", header_style)
        elements.append(business_name)
    
    if business_info.get('address'):
        address = Paragraph(business_info['address'], header_style)
        elements.append(address)
    
    contact_parts = []
    if business_info.get('phone'):
        contact_parts.append(f"Tel: {business_info['phone']}")
    if business_info.get('email'):
        contact_parts.append(f"Email: {business_info['email']}")
    
    if contact_parts:
        contact = Paragraph(" | ".join(contact_parts), header_style)
        elements.append(contact)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Quote number and date
    quote_number = f"PRES-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    current_date = datetime.now().strftime('%d/%m/%Y')
    
    quote_info_data = [
        ['Presupuesto N°:', quote_number],
        ['Fecha:', current_date],
    ]
    
    # Add payment method if provided (MEJORA 12)
    if business_info.get('payment_method'):
        method_label = 'Efectivo' if business_info['payment_method'] == 'CASH' else 'Transferencia'
        quote_info_data.append(['Método de Pago:', method_label])
    
    quote_info_table = Table(quote_info_data, colWidths=[2*inch, 3*inch])
    quote_info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#34495E')),
    ]))
    
    elements.append(quote_info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # -------------------
    # ITEMS TABLE
    # -------------------
    
    # Table header
    table_data = [
        ['Producto', 'Unidad', 'Cantidad', 'Precio Unit.', 'Subtotal']
    ]
    
    # Calculate total
    total = Decimal('0.00')
    
    # Add items
    for item in cart['items'].values():
        product_name = item['name']
        uom = item.get('uom', '—')
        qty = item['qty']
        price = Decimal(str(item['price']))
        subtotal = qty * price
        total += subtotal
        
        # Format quantity (remove unnecessary decimals)
        if qty % 1 == 0:
            qty_str = str(int(qty))
        else:
            qty_str = f"{qty:.2f}"
        
        table_data.append([
            product_name,
            uom,
            qty_str,
            f"${price:.2f}",
            f"${subtotal:.2f}"
        ])
    
    # Create table
    items_table = Table(
        table_data,
        colWidths=[3.2*inch, 0.7*inch, 0.8*inch, 1*inch, 1*inch]
    )
    
    # Style the table
    items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Body
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),  # UOM
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Quantity
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),   # Price
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),   # Subtotal
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2C3E50')),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        
        # Zebra stripes
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        
        # Padding
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # -------------------
    # TOTAL
    # -------------------
    
    total_data = [
        ['TOTAL:', f"${total:.2f}"]
    ]
    
    total_table = Table(total_data, colWidths=[5.7*inch, 1*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#27AE60')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8F8F5')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#27AE60')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(total_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # -------------------
    # FOOTER / LEGAL TEXT
    # -------------------
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#95A5A6'),
        alignment=TA_CENTER,
        leading=12
    )
    
    valid_days = business_info.get('valid_days', 7)
    footer_text = f"""
    <b>IMPORTANTE:</b><br/>
    Precios sujetos a modificación sin previo aviso.<br/>
    Validez del presupuesto: {valid_days} días desde la fecha de emisión.<br/>
    <i>Este presupuesto no constituye una factura ni comprobante de venta.</i>
    """
    
    footer = Paragraph(footer_text, footer_style)
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF from buffer
    buffer.seek(0)
    return buffer


# ============================================================================
# MEJORA 13: Persisted Quotes Functions
# ============================================================================

def generate_quote_number(session, tenant_id: int) -> str:
    """
    Generate a unique quote number (tenant-scoped).
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant ID for scoping
    
    Returns:
        str: Unique quote number
    """
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    
    # Get count of quotes created today for this tenant
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = session.query(Quote).filter(
        Quote.tenant_id == tenant_id,
        Quote.created_at >= today_start
    ).count()
    
    sequence = str(count + 1).zfill(4)
    quote_number = f"PRES-{timestamp}-{sequence}"
    
    return quote_number


def create_quote_from_cart(cart: dict, session, tenant_id: int, customer_name: str, customer_phone: str = None, payment_method: str = None, notes: str = None, valid_days: int = 7) -> int:
    """
    Create a persisted quote from cart data (tenant-scoped).
    
    Args:
        cart: Cart dictionary with 'items' dict {product_id_str: {'qty': Decimal}}
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant)
        customer_name: Customer name (required)
        customer_phone: Customer phone (optional)
        payment_method: 'CASH' or 'TRANSFER' (optional)
        notes: Additional notes for the quote (optional)
        valid_days: Number of days the quote is valid (default 7)
    
    Returns:
        int: Quote ID
    
    Raises:
        ValueError: If cart is empty or validation fails
        Exception: For other errors
    """
    
    try:
        # Begin nested transaction
        session.begin_nested()
        
        # Validate cart not empty
        if not cart.get('items'):
            raise ValueError('El carrito está vacío. Agregue productos para crear un presupuesto.')
        
        # Validate customer_name
        if not customer_name or not customer_name.strip():
            raise ValueError('El nombre del cliente es obligatorio.')
        
        # Generate unique quote number (tenant-scoped)
        quote_number = generate_quote_number(session, tenant_id)
        
        # Calculate valid_until date
        issued_at = datetime.now()
        valid_until = (issued_at.date() + timedelta(days=valid_days))
        
        # Ensure payment_method is None if empty string
        if payment_method == '':
            payment_method = None
        
        # Create quote with tenant_id
        quote = Quote(
            tenant_id=tenant_id,  # CRITICAL
            quote_number=quote_number,
            status='DRAFT',
            issued_at=issued_at,
            valid_until=valid_until,
            notes=notes,
            payment_method=payment_method,
            customer_name=customer_name.strip(),
            customer_phone=customer_phone.strip() if customer_phone else None,
            total_amount=Decimal('0.00')
        )
        
        session.add(quote)
        session.flush()  # Get quote.id
        
        # Create quote lines with snapshot (validate products belong to tenant)
        total = Decimal('0.00')
        
        for product_id_str, item in cart['items'].items():
            product_id = int(product_id_str)
            product = session.query(Product).filter(
                Product.id == product_id,
                Product.tenant_id == tenant_id
            ).first()
            
            if not product:
                raise ValueError(f'Producto con ID {product_id} no encontrado o no pertenece a su negocio.')
            
            qty = Decimal(str(item['qty']))
            unit_price = product.sale_price
            line_total = qty * unit_price
            
            quote_line = QuoteLine(
                quote_id=quote.id,
                product_id=product.id,
                product_name_snapshot=product.name,
                uom_snapshot=product.uom.symbol if product.uom else None,
                qty=qty,
                unit_price=unit_price,
                line_total=line_total
            )
            
            session.add(quote_line)
            total += line_total
        
        # Update quote total
        quote.total_amount = total
        
        # Commit transaction
        session.commit()
        
        return quote.id
        
    except ValueError:
        session.rollback()
        raise
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        raise Exception(f'Error de integridad al crear presupuesto: {error_msg}')
        
    except Exception as e:
        session.rollback()
        raise Exception(f'Error al crear presupuesto: {str(e)}')


def generate_quote_pdf_from_db(quote_id: int, session, business_info: dict, tenant_id: int) -> BytesIO:
    """
    Generate PDF from a persisted quote in database (tenant-scoped).
    
    Args:
        quote_id: Quote ID
        session: SQLAlchemy session
        business_info: Business information dictionary
        tenant_id: Tenant ID for validation
    
    Returns:
        BytesIO: PDF file in memory
    
    Raises:
        ValueError: If quote not found or doesn't belong to tenant
    """
    
    # Get quote from DB (validate tenant)
    quote = session.query(Quote).filter(
        Quote.id == quote_id,
        Quote.tenant_id == tenant_id
    ).first()
    
    if not quote:
        raise ValueError(f'Presupuesto con ID {quote_id} no encontrado o no pertenece a su negocio.')
    
    # Build cart-like structure for PDF generation
    cart_data = {'items': {}}
    
    for line in quote.lines:
        cart_data['items'][str(line.product_id)] = {
            'name': line.product_name_snapshot,
            'qty': line.qty,
            'price': line.unit_price,
            'uom': line.uom_snapshot or '—'
        }
    
    # Update business_info with quote-specific data
    business_info_copy = business_info.copy()
    business_info_copy['quote_number'] = quote.quote_number
    business_info_copy['issued_at'] = quote.issued_at
    business_info_copy['valid_until'] = quote.valid_until
    business_info_copy['status'] = quote.status
    business_info_copy['payment_method'] = quote.payment_method
    business_info_copy['notes'] = quote.notes
    business_info_copy['customer_name'] = quote.customer_name  # MEJORA 14
    business_info_copy['customer_phone'] = quote.customer_phone  # MEJORA 14
    
    # Generate PDF using existing function (with modifications)
    return generate_quote_pdf_persisted(cart_data, business_info_copy)


def generate_quote_pdf_persisted(cart: dict, business_info: dict) -> BytesIO:
    """
    Generate PDF for a persisted quote (with quote_number from DB).
    Similar to generate_quote_pdf but uses quote_number from business_info.
    """
    
    # Create PDF in memory
    buffer = BytesIO()
    
    # Create document (A4 size)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for elements
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=12,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#7F8C8D'),
        alignment=TA_CENTER,
        spaceAfter=6
    )
    
    # -------------------
    # HEADER
    # -------------------
    
    # Title
    title = Paragraph("PRESUPUESTO", title_style)
    elements.append(title)
    
    # Business info
    if business_info.get('name'):
        business_name = Paragraph(f"<b>{business_info['name']}</b>", header_style)
        elements.append(business_name)
    
    if business_info.get('address'):
        address = Paragraph(business_info['address'], header_style)
        elements.append(address)
    
    contact_parts = []
    if business_info.get('phone'):
        contact_parts.append(f"Tel: {business_info['phone']}")
    if business_info.get('email'):
        contact_parts.append(f"Email: {business_info['email']}")
    
    if contact_parts:
        contact = Paragraph(" | ".join(contact_parts), header_style)
        elements.append(contact)
    
    elements.append(Spacer(1, 0.3*inch))
    
    # Quote info from DB
    quote_number = business_info.get('quote_number', f"PRES-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
    
    if business_info.get('issued_at'):
        issued_date = business_info['issued_at'].strftime('%d/%m/%Y')
    else:
        issued_date = datetime.now().strftime('%d/%m/%Y')
    
    quote_info_data = [
        ['Presupuesto N°:', quote_number],
        ['Fecha Emisión:', issued_date],
    ]
    
    if business_info.get('valid_until'):
        valid_until_str = business_info['valid_until'].strftime('%d/%m/%Y')
        quote_info_data.append(['Válido Hasta:', valid_until_str])
    
    if business_info.get('payment_method'):
        method_label = 'Efectivo' if business_info['payment_method'] == 'CASH' else 'Transferencia'
        quote_info_data.append(['Método de Pago:', method_label])
    
    # MEJORA 14: Add customer info
    if business_info.get('customer_name'):
        quote_info_data.append(['Cliente:', business_info['customer_name']])
    
    if business_info.get('customer_phone'):
        quote_info_data.append(['Teléfono:', business_info['customer_phone']])
    
    quote_info_table = Table(quote_info_data, colWidths=[2*inch, 3*inch])
    quote_info_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#34495E')),
    ]))
    
    elements.append(quote_info_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # -------------------
    # ITEMS TABLE
    # -------------------
    
    # Table header
    table_data = [
        ['Producto', 'Unidad', 'Cantidad', 'Precio Unit.', 'Subtotal']
    ]
    
    # Calculate total
    total = Decimal('0.00')
    
    # Add items
    for item in cart['items'].values():
        product_name = item['name']
        uom = item.get('uom', '—')
        qty = item['qty']
        price = Decimal(str(item['price']))
        subtotal = qty * price
        total += subtotal
        
        # Format quantity
        if qty % 1 == 0:
            qty_str = str(int(qty))
        else:
            qty_str = f"{qty:.2f}"
        
        table_data.append([
            product_name,
            uom,
            qty_str,
            f"${price:.2f}",
            f"${subtotal:.2f}"
        ])
    
    # Create table
    items_table = Table(
        table_data,
        colWidths=[3.2*inch, 0.7*inch, 0.8*inch, 1*inch, 1*inch]
    )
    
    # Style the table
    items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        # Body
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2C3E50')),
        
        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        
        # Zebra stripes
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        
        # Padding
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # -------------------
    # TOTAL
    # -------------------
    
    total_data = [
        ['TOTAL:', f"${total:.2f}"]
    ]
    
    total_table = Table(total_data, colWidths=[5.7*inch, 1*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#27AE60')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8F8F5')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#27AE60')),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(total_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # -------------------
    # FOOTER / NOTES
    # -------------------
    
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#95A5A6'),
        alignment=TA_CENTER,
        leading=12
    )
    
    footer_text = """
    <b>IMPORTANTE:</b><br/>
    Precios sujetos a modificación sin previo aviso.<br/>
    <i>Este presupuesto no constituye una factura ni comprobante de venta.</i>
    """
    
    if business_info.get('notes'):
        footer_text += f"<br/><br/><b>Notas:</b> {business_info['notes']}"
    
    footer = Paragraph(footer_text, footer_style)
    elements.append(footer)
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF from buffer
    buffer.seek(0)
    return buffer


def convert_quote_to_sale(quote_id: int, session, tenant_id: int) -> int:
    """
    Convert a quote to a sale with full transactional processing (tenant-scoped).
    
    Steps:
    1. Lock quote row (FOR UPDATE) and validate tenant
    2. Validate quote status and conditions
    3. For each line:
       - Lock product_stock (FOR UPDATE) with tenant validation
       - Validate stock availability
    4. Create sale + sale_lines (with tenant_id)
    5. Create stock_move OUT + stock_move_lines (with tenant_id)
    6. Create finance_ledger INCOME (with tenant_id)
    7. Mark quote as ACCEPTED and link to sale
    8. Commit
    
    Args:
        quote_id: Quote ID to convert
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant enforcement)
    
    Returns:
        int: Sale ID created
    
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    
    try:
        # Begin nested transaction
        session.begin_nested()
        
        # Step 1: Lock quote row and validate tenant
        quote = (
            session.query(Quote)
            .filter(Quote.id == quote_id, Quote.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        
        if not quote:
            raise ValueError(f'Presupuesto con ID {quote_id} no encontrado o no pertenece a su negocio.')
        
        # Step 2: Validate quote conditions
        if quote.status not in ['DRAFT', 'SENT']:
            raise ValueError(
                f'El presupuesto está en estado {quote.status}. '
                f'Solo se pueden convertir presupuestos en estado DRAFT o SENT.'
            )
        
        if quote.sale_id is not None:
            raise ValueError('Este presupuesto ya fue convertido a una venta.')
        
        # Check if expired
        if quote.is_expired:
            raise ValueError(
                f'Este presupuesto está vencido (válido hasta {quote.valid_until.strftime("%d/%m/%Y")}). '
                f'No se puede convertir a venta.'
            )
        
        # Validate quote has lines
        if not quote.lines or len(quote.lines) == 0:
            raise ValueError('El presupuesto no tiene líneas.')
        
        # Step 3: Validate stock availability for all lines (tenant-scoped via product)
        for line in quote.lines:
            # Lock product_stock via join with Product for tenant validation
            product_stock = (
                session.query(ProductStock)
                .join(Product, Product.id == ProductStock.product_id)
                .filter(
                    ProductStock.product_id == line.product_id,
                    Product.tenant_id == tenant_id
                )
                .with_for_update()
                .first()
            )
            
            current_stock = product_stock.on_hand_qty if product_stock else Decimal('0')
            
            if current_stock < line.qty:
                product = session.query(Product).filter(
                    Product.id == line.product_id,
                    Product.tenant_id == tenant_id
                ).first()
                product_name = product.name if product else f"ID {line.product_id}"
                raise ValueError(
                    f'Stock insuficiente para {product_name}. '
                    f'Requerido: {line.qty}, Disponible: {current_stock}'
                )
        
        # Step 4: Create sale with tenant_id
        sale_datetime = datetime.now()
        
        sale = Sale(
            tenant_id=tenant_id,  # CRITICAL
            datetime=sale_datetime,
            total=quote.total_amount,
            status=SaleStatus.CONFIRMED
        )
        
        session.add(sale)
        session.flush()  # Get sale.id
        
        # Step 5: Create sale_lines from quote_lines (no tenant_id, inherited)
        for line in quote.lines:
            sale_line = SaleLine(
                sale_id=sale.id,
                product_id=line.product_id,
                qty=line.qty,
                unit_price=line.unit_price,
                line_total=line.line_total
            )
            session.add(sale_line)
        
        # Step 6: Create stock_move OUT with tenant_id
        stock_move = StockMove(
            tenant_id=tenant_id,  # CRITICAL
            date=sale_datetime,
            type=StockMoveType.OUT,
            reference_type=StockReferenceType.SALE,
            reference_id=sale.id,
            notes=f'Salida por venta #{sale.id} (convertida desde presupuesto #{quote.quote_number})'
        )
        
        session.add(stock_move)
        session.flush()  # Get stock_move.id
        
        # Step 7: Create stock_move_lines (no tenant_id, inherited)
        for line in quote.lines:
            product = session.query(Product).filter(
                Product.id == line.product_id,
                Product.tenant_id == tenant_id
            ).first()
            
            stock_move_line = StockMoveLine(
                stock_move_id=stock_move.id,
                product_id=line.product_id,
                qty=line.qty,
                uom_id=product.uom_id,
                unit_cost=None  # OUT moves don't need cost
            )
            session.add(stock_move_line)
        
        # Step 8: Create finance_ledger INCOME with tenant_id
        from app.models import normalize_payment_method
        payment_method_normalized = normalize_payment_method(quote.payment_method)
        
        ledger_entry = FinanceLedger(
            tenant_id=tenant_id,  # CRITICAL
            datetime=sale_datetime,
            type=LedgerType.INCOME,
            amount=quote.total_amount,
            category='Ventas',
            reference_type=LedgerReferenceType.SALE,
            reference_id=sale.id,
            notes=f'Ingreso por venta #{sale.id} (desde presupuesto #{quote.quote_number})',
            payment_method=payment_method_normalized
        )
        session.add(ledger_entry)
        
        # Step 9: Mark quote as ACCEPTED and link to sale
        quote.status = 'ACCEPTED'
        quote.sale_id = sale.id
        
        # Commit transaction
        session.commit()
        
        return sale.id
        
    except ValueError:
        session.rollback()
        raise
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        raise Exception(f'Error de integridad al convertir presupuesto: {error_msg}')
        
    except Exception as e:
        session.rollback()
        raise Exception(f'Error al convertir presupuesto: {str(e)}')


def update_quote(quote_id: int, session, tenant_id: int, lines_data: list, payment_method: str = None, 
                 valid_until: date = None, notes: str = None) -> None:
    """
    Update a quote with new lines and metadata (tenant-scoped, transactional).
    
    Rules:
    - Only DRAFT or SENT quotes can be edited
    - Cannot edit ACCEPTED, CANCELED, or expired quotes
    - Prices are "frozen": existing lines keep their unit_price
    - New lines use current product.sale_price
    - Replaces all lines (delete old, insert new)
    - Recalculates total_amount server-side
    
    Args:
        quote_id: Quote ID to update
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant enforcement)
        lines_data: List of dicts with keys:
            - product_id: int
            - qty: Decimal or float
        payment_method: 'CASH' or 'TRANSFER' (optional)
        valid_until: Date (optional)
        notes: Text (optional)
    
    Raises:
        ValueError: For business logic errors
        Exception: For other errors
    """
    from sqlalchemy import and_
    
    try:
        # Begin nested transaction
        session.begin_nested()
        
        # Step 1: Lock quote row and validate tenant
        quote = (
            session.query(Quote)
            .filter(Quote.id == quote_id, Quote.tenant_id == tenant_id)
            .with_for_update()
            .first()
        )
        
        if not quote:
            raise ValueError(f'Presupuesto con ID {quote_id} no encontrado o no pertenece a su negocio.')
        
        # Step 2: Validate quote is editable
        if quote.status not in ['DRAFT', 'SENT']:
            raise ValueError(
                f'El presupuesto está en estado {quote.status}. '
                f'Solo se pueden editar presupuestos en estado DRAFT o SENT.'
            )
        
        # Check if expired (calculated)
        today = date.today()
        if quote.valid_until and quote.valid_until < today:
            raise ValueError(
                f'Este presupuesto está vencido (válido hasta {quote.valid_until.strftime("%d/%m/%Y")}). '
                f'No se puede editar.'
            )
        
        # Step 3: Validate lines_data
        if not lines_data or len(lines_data) == 0:
            raise ValueError('El presupuesto debe tener al menos una línea.')
        
        # Build dict of old unit_prices and product_name_snapshots by product_id
        old_lines_by_product = {}
        for old_line in quote.lines:
            old_lines_by_product[old_line.product_id] = {
                'unit_price': old_line.unit_price,
                'product_name_snapshot': old_line.product_name_snapshot,
                'uom_snapshot': old_line.uom_snapshot
            }
        
        # Step 4: Validate and prepare new lines (tenant-scoped products)
        new_lines = []
        product_ids_seen = set()
        total_amount = Decimal('0.00')
        
        for line_data in lines_data:
            product_id = int(line_data['product_id'])
            qty = Decimal(str(line_data['qty']))
            
            # Validate qty
            if qty <= 0:
                raise ValueError(f'La cantidad debe ser mayor a 0 para el producto ID {product_id}.')
            
            # Check for duplicates
            if product_id in product_ids_seen:
                raise ValueError(f'El producto ID {product_id} está duplicado en las líneas.')
            product_ids_seen.add(product_id)
            
            # Get product and validate tenant
            product = session.query(Product).filter(
                Product.id == product_id,
                Product.tenant_id == tenant_id
            ).first()
            
            if not product:
                raise ValueError(f'Producto con ID {product_id} no encontrado o no pertenece a su negocio.')
            
            if not product.active:
                raise ValueError(f'El producto "{product.name}" está inactivo y no puede agregarse.')
            
            # Determine unit_price
            if product_id in old_lines_by_product:
                unit_price = old_lines_by_product[product_id]['unit_price']
                product_name_snapshot = old_lines_by_product[product_id]['product_name_snapshot']
                uom_snapshot = old_lines_by_product[product_id].get('uom_snapshot')
            else:
                unit_price = Decimal(str(product.sale_price))
                product_name_snapshot = product.name
                uom_snapshot = product.uom.symbol if product.uom else None
            
            # Validate unit_price
            if unit_price < 0:
                raise ValueError(f'El precio unitario debe ser mayor o igual a 0.')
            
            # Calculate line_total
            line_total = (qty * unit_price).quantize(Decimal('0.01'))
            total_amount += line_total
            
            new_lines.append({
                'product_id': product_id,
                'product_name_snapshot': product_name_snapshot,
                'uom_snapshot': uom_snapshot,
                'qty': qty,
                'unit_price': unit_price,
                'line_total': line_total
            })
        
        # Step 5: Delete old lines
        session.query(QuoteLine).filter(QuoteLine.quote_id == quote_id).delete()
        
        # Step 6: Create new lines
        for line_data in new_lines:
            quote_line = QuoteLine(
                quote_id=quote_id,
                product_id=line_data['product_id'],
                product_name_snapshot=line_data['product_name_snapshot'],
                uom_snapshot=line_data['uom_snapshot'],
                qty=line_data['qty'],
                unit_price=line_data['unit_price'],
                line_total=line_data['line_total']
            )
            session.add(quote_line)
        
        # Step 7: Update quote metadata
        if payment_method is not None:
            if payment_method not in ['CASH', 'TRANSFER', '']:
                raise ValueError(f'Método de pago inválido: {payment_method}')
            quote.payment_method = payment_method if payment_method else None
        
        if valid_until is not None:
            if valid_until < quote.issued_at.date():
                raise ValueError(
                    f'La fecha de validez ({valid_until.strftime("%d/%m/%Y")}) '
                    f'no puede ser anterior a la fecha de emisión ({quote.issued_at.date().strftime("%d/%m/%Y")}).'
                )
            quote.valid_until = valid_until
        
        if notes is not None:
            quote.notes = notes.strip() if notes.strip() else None
        
        # Update total_amount
        quote.total_amount = total_amount.quantize(Decimal('0.01'))
        
        # Commit transaction
        session.commit()
        
    except ValueError:
        session.rollback()
        raise
    
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        raise Exception(f'Error de integridad al actualizar presupuesto: {error_msg}')
    
    except Exception as e:
        session.rollback()
        raise Exception(f'Error al actualizar presupuesto: {str(e)}')
