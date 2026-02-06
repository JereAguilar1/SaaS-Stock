"""Quotes blueprint for presupuesto management - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app, g, abort
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import or_, func
from app.database import get_session
from app.models import Quote, QuoteLine, Product
from app.services.quote_service import (
    create_quote_from_cart,
    generate_quote_pdf_from_db,
    convert_quote_to_sale,
    update_quote
)
from app.middleware import require_login, require_tenant

quotes_bp = Blueprint('quotes', __name__, url_prefix='/quotes')


def get_cart():
    """Get cart from session."""
    if 'cart' not in session:
        session['cart'] = {'items': {}}
    return session['cart']


@quotes_bp.route('/')
@require_login
@require_tenant
def list_quotes():
    """List all quotes with filters (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get query params
        status_filter = request.args.get('status', '').upper()
        search = request.args.get('q', '').strip()
        
        # Build query - filter by tenant
        query = db_session.query(Quote).filter(
            Quote.tenant_id == g.tenant_id
        )
        
        # Filter by status
        if status_filter and status_filter in ['DRAFT', 'SENT', 'ACCEPTED', 'CANCELED']:
            query = query.filter(Quote.status == status_filter)
        
        # Search by quote_number, customer_name, customer_phone, etc.
        if search:
            from sqlalchemy import cast, String
            query = query.filter(
                or_(
                    Quote.quote_number.ilike(f'%{search}%'),
                    Quote.customer_name.ilike(f'%{search}%'),
                    Quote.customer_phone.ilike(f'%{search}%'),
                    Quote.notes.ilike(f'%{search}%'),
                    cast(Quote.id, String).like(f'%{search}%'),
                    cast(Quote.total_amount, String).like(f'%{search}%'),
                    cast(Quote.issued_at, String).like(f'%{search}%'),
                    cast(Quote.valid_until, String).like(f'%{search}%')
                )
            )
        
        # Order by most recent first
        quotes = query.order_by(Quote.issued_at.desc()).all()
        
        # Calculate "expired" status for display
        today = date.today()
        for quote in quotes:
            if quote.status in ['DRAFT', 'SENT'] and quote.valid_until and today > quote.valid_until:
                quote.display_expired = True
            else:
                quote.display_expired = False
        
        # Check if HTMX request
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'quotes/_list_table.html' if is_htmx else 'quotes/list.html'
        
        return render_template(
            template,
            quotes=quotes,
            status_filter=status_filter,
            search=search
        )
        
    except Exception as e:
        flash(f'Error al cargar presupuestos: {str(e)}', 'danger')
        
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'quotes/_list_table.html' if is_htmx else 'quotes/list.html'
        
        return render_template(template, quotes=[], status_filter='', search='')


@quotes_bp.route('/<int:quote_id>')
@require_login
@require_tenant
def view_quote(quote_id):
    """View quote detail (tenant-scoped)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            abort(404)
        
        return render_template('quotes/detail.html', quote=quote)
        
    except Exception as e:
        flash(f'Error al cargar presupuesto: {str(e)}', 'danger')
        return redirect(url_for('quotes.list_quotes'))


@quotes_bp.route('/from-cart', methods=['POST'])
@require_login
@require_tenant
def create_from_cart():
    """Create a new quote from current cart (tenant-scoped)."""
    db_session = get_session()
    
    try:
        cart = get_cart()
        
        # Validate cart not empty
        if not cart.get('items'):
            flash('El carrito está vacío. Agregue productos para crear un presupuesto.', 'warning')
            return redirect(url_for('sales.new_sale'))
        
        # Get customer data from form
        customer_name = request.form.get('customer_name', '').strip()
        customer_phone = request.form.get('customer_phone', '').strip() or None
        
        # Validate customer_name
        if not customer_name:
            flash('El nombre del cliente es obligatorio para crear un presupuesto.', 'danger')
            return redirect(url_for('sales.new_sale'))
        
        # Get payment method from form (optional)
        payment_method = request.form.get('payment_method', '').strip().upper()
        if not payment_method or payment_method not in ['CASH', 'TRANSFER']:
            payment_method = None
        
        # Get notes (optional)
        notes = request.form.get('notes', '').strip() or None
        
        # Get valid_days from config
        valid_days = current_app.config.get('QUOTE_VALID_DAYS', 7)
        
        # Create quote with tenant_id
        quote_id = create_quote_from_cart(
            cart=cart,
            session=db_session,
            tenant_id=g.tenant_id,  # CRITICAL
            customer_name=customer_name,
            customer_phone=customer_phone,
            payment_method=payment_method,
            notes=notes,
            valid_days=valid_days
        )
        
        # Clear cart
        session['cart'] = {'items': {}}
        session.modified = True
        
        flash(f'Presupuesto creado exitosamente.', 'success')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
    except ValueError as e:
        db_session.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('sales.new_sale'))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al crear presupuesto: {str(e)}', 'danger')
        return redirect(url_for('sales.new_sale'))


@quotes_bp.route('/<int:quote_id>/pdf')
@require_login
@require_tenant
def download_pdf(quote_id):
    """Generate and download PDF for a quote (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Verify quote exists and belongs to tenant
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            abort(404)
        
        # Business info from config
        business_info = {
            'name': current_app.config.get('BUSINESS_NAME', 'Ferretería'),
            'address': current_app.config.get('BUSINESS_ADDRESS', ''),
            'phone': current_app.config.get('BUSINESS_PHONE', ''),
            'email': current_app.config.get('BUSINESS_EMAIL', ''),
            'valid_days': current_app.config.get('QUOTE_VALID_DAYS', 7)
        }
        
        # Generate PDF (service validates tenant internally)
        pdf_buffer = generate_quote_pdf_from_db(quote_id, db_session, business_info, g.tenant_id)
        
        # Generate filename
        filename = f"presupuesto_{quote.quote_number}.pdf"
        
        # Return PDF as download
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'Error al generar PDF: {str(e)}', 'danger')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))


@quotes_bp.route('/<int:quote_id>/convert/preview')
@require_login
@require_tenant
def convert_to_sale_preview(quote_id):
    """Preview quote conversion (HTMX modal, tenant-scoped)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            return '<div class="alert alert-danger">Presupuesto no encontrado.</div>'
        
        # Check if convertible
        if quote.status not in ['DRAFT', 'SENT']:
            return f'<div class="alert alert-danger">Solo se pueden convertir presupuestos DRAFT o SENT. Estado actual: {quote.status}</div>'
        
        if quote.sale_id:
            return '<div class="alert alert-danger">Este presupuesto ya fue convertido a venta.</div>'
        
        # Check stock availability for each line (tenant-scoped via product)
        from app.models import ProductStock
        stock_warnings = []
        for line in quote.lines:
            product_stock = db_session.query(ProductStock).join(Product).filter(
                ProductStock.product_id == line.product_id,
                Product.tenant_id == g.tenant_id
            ).first()
            
            if product_stock:
                available = product_stock.on_hand_qty or 0
                if available < line.qty:
                    stock_warnings.append(
                        f"{line.product.name}: necesita {line.qty}, disponible {available}"
                    )
            else:
                stock_warnings.append(
                    f"{line.product.name}: necesita {line.qty}, disponible 0"
                )
        
        return render_template('quotes/_convert_confirm_modal.html',
                             quote=quote,
                             stock_warnings=stock_warnings)
        
    except Exception as e:
        current_app.logger.error(f"Error generating conversion preview for quote {quote_id}: {e}")
        return f'<div class="alert alert-danger">Error al generar vista previa: {str(e)}</div>'


@quotes_bp.route('/<int:quote_id>/convert', methods=['POST'])
@require_login
@require_tenant
def convert_to_sale(quote_id):
    """Convert quote to sale (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Convert quote to sale with tenant_id
        sale_id = convert_quote_to_sale(quote_id, db_session, g.tenant_id)
        
        flash(
            f'Presupuesto convertido a venta #{sale_id} exitosamente. '
            f'Stock descontado y registro financiero creado.',
            'success'
        )
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
    except ValueError as e:
        db_session.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al convertir presupuesto: {str(e)}', 'danger')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))


@quotes_bp.route('/<int:quote_id>/cancel', methods=['POST'])
@require_login
@require_tenant
def cancel_quote(quote_id):
    """Cancel a quote (tenant-scoped)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            abort(404)
        
        # Validate can be canceled
        if quote.status not in ['DRAFT', 'SENT']:
            flash(
                f'No se puede cancelar un presupuesto en estado {quote.status}.',
                'danger'
            )
            return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
        # Cancel quote
        quote.status = 'CANCELED'
        db_session.commit()
        
        flash('Presupuesto cancelado exitosamente.', 'success')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al cancelar presupuesto: {str(e)}', 'danger')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))


@quotes_bp.route('/<int:quote_id>/send', methods=['POST'])
@require_login
@require_tenant
def mark_as_sent(quote_id):
    """Mark quote as sent (tenant-scoped)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            abort(404)
        
        # Validate can be marked as sent
        if quote.status != 'DRAFT':
            flash(
                f'Solo presupuestos en estado DRAFT pueden marcarse como enviados.',
                'warning'
            )
            return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
        # Mark as sent
        quote.status = 'SENT'
        db_session.commit()
        
        flash('Presupuesto marcado como enviado.', 'success')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al actualizar presupuesto: {str(e)}', 'danger')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))


def is_quote_editable(quote):
    """Check if a quote can be edited."""
    if quote.status not in ['DRAFT', 'SENT']:
        return False, f'El presupuesto está en estado {quote.status}. Solo se pueden editar presupuestos en estado DRAFT o SENT.'
    
    # Check if expired
    today = date.today()
    if quote.valid_until and quote.valid_until < today:
        return False, f'Este presupuesto está vencido (válido hasta {quote.valid_until.strftime("%d/%m/%Y")}). No se puede editar.'
    
    return True, None


@quotes_bp.route('/<int:quote_id>/edit', methods=['GET'])
@require_login
@require_tenant
def edit_quote(quote_id):
    """Show form to edit a quote (tenant-scoped)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            abort(404)
        
        # Validate quote is editable
        can_edit, error_msg = is_quote_editable(quote)
        if not can_edit:
            flash(error_msg, 'danger')
            return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
        # Get all active products for the tenant
        products = db_session.query(Product).filter(
            Product.tenant_id == g.tenant_id,
            Product.active == True
        ).order_by(Product.name).all()
        
        return render_template('quotes/edit.html', quote=quote, products=products)
        
    except Exception as e:
        flash(f'Error al cargar formulario de edición: {str(e)}', 'danger')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))


@quotes_bp.route('/<int:quote_id>/edit/preview', methods=['POST'])
@require_login
@require_tenant
def edit_quote_preview(quote_id):
    """Preview quote changes (HTMX modal, tenant-scoped)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            return '<div class="alert alert-danger">Presupuesto no encontrado.</div>'
        
        # Validate quote is editable
        can_edit, error_msg = is_quote_editable(quote)
        if not can_edit:
            return f'<div class="alert alert-danger">{error_msg}</div>'
        
        # Parse form data
        payment_method = request.form.get('payment_method', '').strip().upper() or None
        if payment_method and payment_method not in ['CASH', 'TRANSFER']:
            payment_method = None
        
        valid_until_str = request.form.get('valid_until', '').strip()
        valid_until = None
        if valid_until_str:
            try:
                valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date()
            except ValueError:
                return '<div class="alert alert-danger">Fecha de validez inválida.</div>'
        
        notes = request.form.get('notes', '').strip() or None
        
        # Parse lines from form
        lines_data = []
        line_index = 0
        
        while True:
            product_id_key = f'lines[{line_index}][product_id]'
            qty_key = f'lines[{line_index}][qty]'
            
            if product_id_key not in request.form:
                break
            
            product_id = request.form.get(product_id_key, '').strip()
            qty = request.form.get(qty_key, '').strip()
            
            if not product_id or not qty:
                line_index += 1
                continue
            
            try:
                product_id_int = int(product_id)
                qty_decimal = Decimal(str(qty))
                
                if qty_decimal <= 0:
                    return f'<div class="alert alert-danger">La cantidad debe ser mayor a 0 en la línea {line_index + 1}.</div>'
                
                # Get product and validate tenant
                product = db_session.query(Product).filter(
                    Product.id == product_id_int,
                    Product.tenant_id == g.tenant_id
                ).first()
                
                if not product:
                    return f'<div class="alert alert-danger">Producto con ID {product_id_int} no encontrado o no pertenece a su negocio.</div>'
                
                if not product.active:
                    return f'<div class="alert alert-danger">El producto "{product.name}" está inactivo.</div>'
                
                lines_data.append({
                    'product_id': product_id_int,
                    'qty': qty_decimal,
                    'product': product
                })
                
            except (ValueError, TypeError) as e:
                return f'<div class="alert alert-danger">Error en línea {line_index + 1}: {str(e)}</div>'
            
            line_index += 1
        
        if not lines_data:
            return '<div class="alert alert-danger">Debe agregar al menos una línea.</div>'
        
        # Build comparison (same logic as before)
        old_lines_by_product = {line.product_id: line for line in quote.lines}
        new_lines_by_product = {line['product_id']: line for line in lines_data}
        
        old_total = quote.total_amount
        new_total = Decimal('0.00')
        
        changes = {
            'added': [],
            'removed': [],
            'modified': []
        }
        
        # Check for removed lines
        for old_line in quote.lines:
            if old_line.product_id not in new_lines_by_product:
                changes['removed'].append({
                    'product': old_line.product_name_snapshot,
                    'qty': old_line.qty,
                    'unit_price': old_line.unit_price,
                    'line_total': old_line.line_total
                })
        
        # Check for added/modified lines
        for new_line_data in lines_data:
            product_id = new_line_data['product_id']
            new_qty = new_line_data['qty']
            product = new_line_data['product']
            
            # Determine unit_price
            if product_id in old_lines_by_product:
                old_line = old_lines_by_product[product_id]
                unit_price = old_line.unit_price
                product_name_snapshot = old_line.product_name_snapshot
                is_new = False
            else:
                unit_price = Decimal(str(product.sale_price))
                product_name_snapshot = product.name
                is_new = True
            
            line_total = (new_qty * unit_price).quantize(Decimal('0.01'))
            new_total += line_total
            
            if is_new:
                changes['added'].append({
                    'product': product_name_snapshot,
                    'qty': new_qty,
                    'unit_price': unit_price,
                    'line_total': line_total
                })
            else:
                old_line = old_lines_by_product[product_id]
                if old_line.qty != new_qty or old_line.unit_price != unit_price:
                    changes['modified'].append({
                        'product': product_name_snapshot,
                        'old_qty': old_line.qty,
                        'new_qty': new_qty,
                        'unit_price': unit_price,
                        'old_line_total': old_line.line_total,
                        'new_line_total': line_total
                    })
        
        # Check if there are any changes
        has_changes = (
            len(changes['added']) > 0 or
            len(changes['removed']) > 0 or
            len(changes['modified']) > 0 or
            payment_method != quote.payment_method or
            valid_until != quote.valid_until or
            notes != quote.notes or
            old_total != new_total
        )
        
        if not has_changes:
            return '<div class="alert alert-info">No hay cambios para aplicar.</div>'
        
        return render_template('quotes/_edit_confirm_modal.html',
                             quote=quote,
                             old_total=old_total,
                             new_total=new_total,
                             changes=changes,
                             payment_method=payment_method,
                             valid_until=valid_until,
                             notes=notes)
        
    except Exception as e:
        current_app.logger.error(f"Error generating edit preview for quote {quote_id}: {e}")
        import traceback
        current_app.logger.error(traceback.format_exc())
        return f'<div class="alert alert-danger">Error al generar vista previa: {str(e)}</div>'


@quotes_bp.route('/<int:quote_id>/edit', methods=['POST'])
@require_login
@require_tenant
def save_quote_edit(quote_id):
    """Save quote changes (tenant-scoped, transactional)."""
    db_session = get_session()
    
    try:
        quote = db_session.query(Quote).filter(
            Quote.id == quote_id,
            Quote.tenant_id == g.tenant_id
        ).first()
        
        if not quote:
            abort(404)
        
        # Validate quote is editable
        can_edit, error_msg = is_quote_editable(quote)
        if not can_edit:
            flash(error_msg, 'danger')
            return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
        # Parse form data
        payment_method = request.form.get('payment_method', '').strip().upper() or None
        if payment_method and payment_method not in ['CASH', 'TRANSFER']:
            payment_method = None
        
        valid_until_str = request.form.get('valid_until', '').strip()
        valid_until = None
        if valid_until_str:
            try:
                valid_until = datetime.strptime(valid_until_str, '%Y-%m-%d').date()
            except ValueError:
                flash('Fecha de validez inválida.', 'danger')
                return redirect(url_for('quotes.edit_quote', quote_id=quote_id))
        
        notes = request.form.get('notes', '').strip() or None
        
        # Parse lines from form
        lines_data = []
        line_index = 0
        
        while True:
            product_id_key = f'lines[{line_index}][product_id]'
            qty_key = f'lines[{line_index}][qty]'
            
            if product_id_key not in request.form:
                break
            
            product_id = request.form.get(product_id_key, '').strip()
            qty = request.form.get(qty_key, '').strip()
            
            if not product_id or not qty:
                line_index += 1
                continue
            
            try:
                product_id_int = int(product_id)
                qty_decimal = Decimal(str(qty))
                
                if qty_decimal <= 0:
                    flash(f'La cantidad debe ser mayor a 0 en la línea {line_index + 1}.', 'danger')
                    return redirect(url_for('quotes.edit_quote', quote_id=quote_id))
                
                lines_data.append({
                    'product_id': product_id_int,
                    'qty': qty_decimal
                })
                
            except (ValueError, TypeError) as e:
                flash(f'Error en línea {line_index + 1}: {str(e)}', 'danger')
                return redirect(url_for('quotes.edit_quote', quote_id=quote_id))
            
            line_index += 1
        
        if not lines_data:
            flash('Debe agregar al menos una línea.', 'danger')
            return redirect(url_for('quotes.edit_quote', quote_id=quote_id))
        
        # Call service to update quote (tenant validated)
        update_quote(
            quote_id=quote_id,
            session=db_session,
            tenant_id=g.tenant_id,  # CRITICAL
            lines_data=lines_data,
            payment_method=payment_method,
            valid_until=valid_until,
            notes=notes
        )
        
        flash('Presupuesto actualizado exitosamente.', 'success')
        return redirect(url_for('quotes.view_quote', quote_id=quote_id))
        
    except ValueError as e:
        db_session.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('quotes.edit_quote', quote_id=quote_id))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al actualizar presupuesto: {str(e)}', 'danger')
        return redirect(url_for('quotes.edit_quote', quote_id=quote_id))
