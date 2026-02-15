"""Quote service for managing and converting sales quotes."""

from datetime import datetime, date, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Dict, Any, List, Optional, Union

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import (
    Quote, QuoteLine, Product, ProductStock,
    Sale, SaleLine, StockMove, StockMoveLine, FinanceLedger,
    SaleStatus, StockMoveType, StockReferenceType,
    LedgerType, LedgerReferenceType, PaymentMethod, normalize_payment_method
)
from app.exceptions import BusinessLogicError, NotFoundError, InsufficientStockError


def _render_quote_pdf(cart_data: Dict[str, Any], business_info: Dict[str, Any]) -> BytesIO:
    """
    Internal PDF rendering engine for quotes.
    Shared by both transient and persisted quote generation.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    elements = []
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
    
    # 1. Title and Business Header
    elements.append(Paragraph("PRESUPUESTO", title_style))
    
    if business_info.get('name'):
        elements.append(Paragraph(f"<b>{business_info['name']}</b>", header_style))
    
    if business_info.get('address'):
        elements.append(Paragraph(business_info['address'], header_style))
    
    contact_parts = []
    if business_info.get('phone'):
        contact_parts.append(f"Tel: {business_info['phone']}")
    if business_info.get('email'):
        contact_parts.append(f"Email: {business_info['email']}")
    
    if contact_parts:
        elements.append(Paragraph(" | ".join(contact_parts), header_style))
    
    elements.append(Spacer(1, 0.3*inch))
    
    # 2. Quote Metadata Table
    quote_number = business_info.get('quote_number', f"PRES-TEMP-{datetime.now().strftime('%Y%m%d')}")
    issued_date = business_info.get('issued_at', datetime.now())
    if isinstance(issued_date, datetime):
        issued_date = issued_date.strftime('%d/%m/%Y')
    
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
    
    # 3. Items Table
    table_data = [['Producto', 'Unidad', 'Cantidad', 'Precio Unit.', 'Subtotal']]
    total = Decimal('0.00')
    
    for item in cart_data['items'].values():
        price = Decimal(str(item['price']))
        subtotal = Decimal(str(item['qty'])) * price
        total += subtotal
        
        qty = item['qty']
        qty_str = str(int(qty)) if qty % 1 == 0 else f"{qty:.2f}"
        
        table_data.append([
            item['name'],
            item.get('uom', '—'),
            qty_str,
            f"${price:.2f}",
            f"${subtotal:.2f}"
        ])
    
    items_table = Table(table_data, colWidths=[3.2*inch, 0.7*inch, 0.8*inch, 1*inch, 1*inch])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498DB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('ALIGN', (1, 1), (1, -1), 'CENTER'),
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),
        ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
        ('ALIGN', (4, 1), (4, -1), 'RIGHT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
    ]))
    
    elements.append(items_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # 4. Total and Footer
    total_table = Table([['TOTAL:', f"${total:.2f}"]], colWidths=[5.7*inch, 1*inch])
    total_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'RIGHT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#27AE60')),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#E8F8F5')),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#27AE60')),
    ]))
    
    elements.append(total_table)
    elements.append(Spacer(1, 0.4*inch))
    
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, textColor=colors.HexColor('#95A5A6'), alignment=TA_CENTER)
    valid_days = business_info.get('valid_days', 7)
    footer_text = f"<b>IMPORTANTE:</b><br/>Precios sujetos a modificación sin previo aviso.<br/>Validez: {valid_days} días.<br/><i>No constituye factura.</i>"
    
    if business_info.get('notes'):
        footer_text += f"<br/><br/><b>Notas:</b> {business_info['notes']}"
    
    elements.append(Paragraph(footer_text, footer_style))
    
    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_quote_pdf(cart: dict, business_info: dict) -> BytesIO:
    """Generate a PDF from transient cart data."""
    return _render_quote_pdf(cart, business_info)


def generate_quote_pdf_from_db(quote_id: int, session: Session, business_info: dict, tenant_id: int) -> BytesIO:
    """Generate PDF from a persisted quote in DB."""
    quote = session.query(Quote).filter(Quote.id == quote_id, Quote.tenant_id == tenant_id).first()
    if not quote:
        raise NotFoundError(f'Presupuesto {quote_id} no encontrado.')
    
    cart_data = {'items': {}}
    for line in quote.lines:
        cart_data['items'][str(line.product_id)] = {
            'name': line.product_name_snapshot,
            'qty': line.qty,
            'price': line.unit_price,
            'uom': line.uom_snapshot or '—'
        }
    
    info = business_info.copy()
    info.update({
        'quote_number': quote.quote_number,
        'issued_at': quote.issued_at,
        'valid_until': quote.valid_until,
        'payment_method': quote.payment_method,
        'notes': quote.notes,
        'customer_name': quote.customer_name,
        'customer_phone': quote.customer_phone
    })
    
    return _render_quote_pdf(cart_data, info)


def generate_quote_number(session: Session, tenant_id: int) -> str:
    """Generate a unique quote number."""
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = session.query(Quote).filter(Quote.tenant_id == tenant_id, Quote.created_at >= today_start).count()
    return f"PRES-{timestamp}-{str(count + 1).zfill(4)}"


def create_quote_from_cart(cart: dict, session: Session, tenant_id: int, customer_name: str, **kwargs) -> int:
    """Create a persisted quote from cart data."""
    if not cart.get('items'):
        raise BusinessLogicError('Carrito vacío.')
    if not customer_name or not customer_name.strip():
        raise BusinessLogicError('Nombre de cliente requerido.')

    try:
        session.begin_nested()
        
        # Batch fetch products
        product_ids = [int(pid) for pid in cart['items'].keys()]
        products = session.query(Product).filter(Product.id.in_(product_ids), Product.tenant_id == tenant_id).all()
        products_dict = {p.id: p for p in products}

        if len(products) != len(product_ids):
            raise NotFoundError('Uno o más productos no encontrados.')

        quote = Quote(
            tenant_id=tenant_id,
            quote_number=generate_quote_number(session, tenant_id),
            status='DRAFT',
            issued_at=datetime.now(),
            valid_until=datetime.now().date() + timedelta(days=kwargs.get('valid_days', 7)),
            notes=kwargs.get('notes'),
            payment_method=kwargs.get('payment_method') or None,
            customer_name=customer_name.strip(),
            customer_phone=kwargs.get('customer_phone', '').strip() or None,
            total_amount=Decimal('0.00')
        )
        session.add(quote)
        session.flush()

        total = Decimal('0.00')
        for pid_str, item in cart['items'].items():
            product = products_dict[int(pid_str)]
            qty = Decimal(str(item['qty']))
            line_total = qty * product.sale_price
            
            line = QuoteLine(
                quote_id=quote.id,
                product_id=product.id,
                product_name_snapshot=product.name,
                uom_snapshot=product.uom.symbol if product.uom else None,
                qty=qty,
                unit_price=product.sale_price,
                line_total=line_total
            )
            session.add(line)
            total += line_total

        quote.total_amount = total
        session.commit()
        return quote.id
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception:
        session.rollback()
        raise


def convert_quote_to_sale(quote_id: int, session: Session, tenant_id: int) -> int:
    """Convert a quote to a confirmed sale."""
    try:
        session.begin_nested()
        quote = session.query(Quote).filter(Quote.id == quote_id, Quote.tenant_id == tenant_id).with_for_update().first()
        
        if not quote or quote.status not in ['DRAFT', 'SENT'] or quote.sale_id:
            raise BusinessLogicError('Presupuesto no válido para conversión.')
        if quote.is_expired:
            raise BusinessLogicError('Presupuesto vencido.')

        # 1. Product validation and stock locking
        product_ids = [line.product_id for line in quote.lines]
        stocks = session.query(ProductStock).join(Product).filter(
            ProductStock.product_id.in_(product_ids), Product.tenant_id == tenant_id
        ).with_for_update().all()
        stocks_dict = {s.product_id: s for s in stocks}

        # 2. Create Sale
        sale = Sale(tenant_id=tenant_id, datetime=datetime.now(), total=quote.total_amount, status=SaleStatus.CONFIRMED)
        session.add(sale)
        session.flush()

        # 3. Process lines
        for line in quote.lines:
            stock = stocks_dict.get(line.product_id)
            if not stock or stock.on_hand_qty < line.qty:
                product = session.query(Product).get(line.product_id)
                raise InsufficientStockError(f'Stock insuficiente para {product.name if product else "producto"}')

            session.add(SaleLine(sale_id=sale.id, product_id=line.product_id, qty=line.qty, unit_price=line.unit_price, line_total=line.line_total))

        # 4. Stock Movement
        move = StockMove(tenant_id=tenant_id, date=sale.datetime, type=StockMoveType.OUT, reference_type=StockReferenceType.SALE, reference_id=sale.id)
        session.add(move)
        session.flush()

        for line in quote.lines:
            p = session.query(Product).get(line.product_id)
            session.add(StockMoveLine(stock_move_id=move.id, product_id=line.product_id, qty=line.qty, uom_id=p.uom_id))

        # 5. Finance
        session.add(FinanceLedger(
            tenant_id=tenant_id, datetime=sale.datetime, type=LedgerType.INCOME, amount=quote.total_amount,
            category='Ventas', reference_type=LedgerReferenceType.SALE, reference_id=sale.id,
            payment_method=normalize_payment_method(quote.payment_method)
        ))

        # 6. Finalize Quote
        quote.status = 'ACCEPTED'
        quote.sale_id = sale.id
        
        session.commit()
        return sale.id
    except (BusinessLogicError, NotFoundError, InsufficientStockError) as e:
        session.rollback()
        raise e
    except Exception:
        session.rollback()
        raise


def update_quote(quote_id: int, session: Session, tenant_id: int, lines_data: List[Dict[str, Any]], **kwargs) -> None:
    """Update an existing quote (tenant-scoped)."""
    try:
        session.begin_nested()
        quote = session.query(Quote).filter(Quote.id == quote_id, Quote.tenant_id == tenant_id).with_for_update().first()

        if not quote or quote.status not in ['DRAFT', 'SENT'] or (quote.valid_until and quote.valid_until < date.today()):
            raise BusinessLogicError('No se puede editar este presupuesto.')

        # Batch fetch products
        pids = [int(l['product_id']) for l in lines_data]
        products = {p.id: p for p in session.query(Product).filter(Product.id.in_(pids), Product.tenant_id == tenant_id).all()}
        
        old_prices = {line.product_id: line.unit_price for line in quote.lines}
        session.query(QuoteLine).filter(QuoteLine.quote_id == quote_id).delete()

        total = Decimal('0.00')
        for line in lines_data:
            pid = int(line['product_id'])
            product = products.get(pid)
            if not product or not product.active:
                raise BusinessLogicError(f'Producto {pid} no válido o inactivo.')

            qty = Decimal(str(line['qty']))
            price = old_prices.get(pid, product.sale_price)
            subtotal = qty * price
            
            session.add(QuoteLine(
                quote_id=quote_id, product_id=pid, product_name_snapshot=product.name,
                uom_snapshot=product.uom.symbol if product.uom else None,
                qty=qty, unit_price=price, line_total=subtotal
            ))
            total += subtotal

        if 'payment_method' in kwargs: 
            quote.payment_method = kwargs['payment_method'] or None
        if 'valid_until' in kwargs: 
            quote.valid_until = kwargs['valid_until']
        if 'notes' in kwargs: 
            quote.notes = kwargs['notes'].strip() if kwargs['notes'] else None
            
        quote.total_amount = total
        session.commit()
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception:
        session.rollback()
        raise
