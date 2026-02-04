"""Invoices blueprint for purchase invoice management - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, g, abort, make_response
from decimal import Decimal, InvalidOperation
from datetime import datetime, date, timedelta
from sqlalchemy import and_, or_, func
from app.database import get_session
from app.models import PurchaseInvoice, Supplier, Product, InvoiceStatus, PurchaseInvoicePayment, ProductStock
from app.services.invoice_service import create_invoice_with_lines
from app.services.payment_service import register_invoice_payment
from app.services.invoice_alerts_service import is_invoice_overdue
from app.middleware import require_login, require_tenant
from app.utils.number_format import parse_ar_decimal, parse_ar_number
from flask import jsonify

invoices_bp = Blueprint('invoices', __name__, url_prefix='/invoices')


def get_invoice_draft():
    """Get invoice draft from session."""
    if 'invoice_draft' not in session:
        session['invoice_draft'] = {
            'supplier_id': None,
            'invoice_number': '',
            'invoice_date': '',
            'due_date': '',
            'lines': []
        }
    return session['invoice_draft']


def save_invoice_draft(draft):
    """Save invoice draft to session."""
    session['invoice_draft'] = draft
    session.modified = True


def clear_invoice_draft():
    """Clear invoice draft from session."""
    session['invoice_draft'] = {
        'supplier_id': None,
        'invoice_number': '',
        'invoice_date': '',
        'due_date': '',
        'lines': []
    }
    session.modified = True


@invoices_bp.route('/')
@require_login
@require_tenant
def list_invoices():
    """List all purchase invoices (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Optional filters
        supplier_id = request.args.get('supplier_id', type=int)
        status = request.args.get('status', '').upper()
        search_query = request.args.get('q', '').strip()
        due_soon = request.args.get('due_soon', type=int)
        overdue = request.args.get('overdue', type=int)
        
        # Base query - filter by tenant
        query = db_session.query(PurchaseInvoice).filter(
            PurchaseInvoice.tenant_id == g.tenant_id
        )
        
        # Validate supplier belongs to tenant if provided
        if supplier_id:
            supplier_exists = db_session.query(Supplier).filter(
                Supplier.id == supplier_id,
                Supplier.tenant_id == g.tenant_id
            ).first()
            if supplier_exists:
                query = query.filter(PurchaseInvoice.supplier_id == supplier_id)
            else:
                supplier_id = None  # Reset if invalid
        
        if status and status in ['PENDING', 'PAID', 'PARTIALLY_PAID']:
            query = query.filter(PurchaseInvoice.status == InvoiceStatus[status])
        
        # Filter by due soon (tomorrow)
        if due_soon:
            tomorrow = date.today() + timedelta(days=1)
            query = query.filter(
                and_(
                    PurchaseInvoice.status == InvoiceStatus.PENDING,
                    PurchaseInvoice.due_date == tomorrow
                )
            )
        
        # Filter by overdue
        if overdue:
            today = date.today()
            query = query.filter(
                and_(
                    PurchaseInvoice.status == InvoiceStatus.PENDING,
                    PurchaseInvoice.due_date < today,
                    PurchaseInvoice.due_date.isnot(None)
                )
            )
        
        # Search by invoice number
        if search_query:
            query = query.filter(PurchaseInvoice.invoice_number.ilike(f'%{search_query}%'))
        
        # Order by due_date (ascending, NULLS LAST), then by created_at (descending)
        invoices = query.order_by(
            PurchaseInvoice.due_date.asc().nullslast(),
            PurchaseInvoice.created_at.desc()
        ).all()
        
        # Calculate overdue status
        today = date.today()
        for invoice in invoices:
            invoice.is_overdue = is_invoice_overdue(invoice, today)
        
        # Get suppliers for filter (tenant-scoped)
        suppliers = db_session.query(Supplier).filter(
            Supplier.tenant_id == g.tenant_id
        ).order_by(Supplier.name).all()
        
        # Check if HTMX request
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'invoices/_list_table.html' if is_htmx else 'invoices/list.html'
        
        return render_template(template,
                             invoices=invoices,
                             suppliers=suppliers,
                             selected_supplier=supplier_id,
                             selected_status=status,
                             search_query=search_query,
                             due_soon=due_soon,
                             overdue=overdue)
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al cargar boletas: {str(e)}', 'danger')
        
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'invoices/_list_table.html' if is_htmx else 'invoices/list.html'
        
        return render_template(template,
                             invoices=[],
                             suppliers=[],
                             selected_supplier=None,
                             selected_status='',
                             search_query='',
                             due_soon=None,
                             overdue=None)


@invoices_bp.route('/<int:invoice_id>')
@require_login
@require_tenant
def view_invoice(invoice_id):
    """View invoice detail (tenant-scoped)."""
    db_session = get_session()
    
    try:
        invoice = db_session.query(PurchaseInvoice).filter(
            PurchaseInvoice.id == invoice_id,
            PurchaseInvoice.tenant_id == g.tenant_id
        ).first()
        
        if not invoice:
            abort(404)
        
        # Calculate overdue status
        today_date = date.today()
        invoice.is_overdue = is_invoice_overdue(invoice, today_date)
        
        # Pass today's date for payment form default
        today = today_date.strftime('%Y-%m-%d')
        
        return render_template('invoices/detail.html', invoice=invoice, today=today)
        
    except Exception as e:
        import traceback
        current_app.logger.error(f"Error loading invoice {invoice_id}: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        
        flash(f'Error al cargar boleta: {str(e)}', 'danger')
        return redirect(url_for('invoices.list_invoices'))


@invoices_bp.route('/new', methods=['GET'])
@require_login
@require_tenant
def new_invoice():
    """Show form to create new invoice (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Check if suppliers exist for this tenant
        supplier_count = db_session.query(Supplier).filter(
            Supplier.tenant_id == g.tenant_id
        ).count()
        
        if supplier_count == 0:
            flash('No hay proveedores registrados. Por favor, cree al menos un proveedor primero.', 'warning')
            return redirect(url_for('suppliers.new_supplier'))
        
        # Get suppliers and products for current tenant
        suppliers = db_session.query(Supplier).filter(
            Supplier.tenant_id == g.tenant_id
        ).order_by(Supplier.name).all()
        
        products = db_session.query(Product).filter(
            Product.tenant_id == g.tenant_id,
            Product.active == True
        ).order_by(Product.name).all()
        
        # Get or initialize draft
        draft = get_invoice_draft()
        
        # Calculate totals
        total_amount = Decimal('0.00')
        for line in draft['lines']:
            qty = Decimal(str(line['qty']))
            unit_cost = Decimal(str(line['unit_cost']))
            line_total = (qty * unit_cost).quantize(Decimal('0.01'))
            total_amount += line_total
        
        return render_template('invoices/new.html',
                             suppliers=suppliers,
                             products=products,
                             draft=draft,
                             total_amount=total_amount)
        
    except Exception as e:
        flash(f'Error al cargar formulario: {str(e)}', 'danger')
        return redirect(url_for('invoices.list_invoices'))


@invoices_bp.route('/draft/update-header', methods=['POST'])
@require_login
@require_tenant
def update_draft_header():
    """Update invoice draft header (HTMX endpoint)."""
    try:
        draft = get_invoice_draft()
        
        # Update header fields
        draft['supplier_id'] = request.form.get('supplier_id', type=int)
        draft['invoice_number'] = request.form.get('invoice_number', '').strip()
        draft['invoice_date'] = request.form.get('invoice_date', '').strip()
        draft['due_date'] = request.form.get('due_date', '').strip()
        
        save_invoice_draft(draft)
        
        return '', 204
        
    except Exception as e:
        flash(f'Error al actualizar: {str(e)}', 'danger')
        return '', 500


@invoices_bp.route('/draft/add-line', methods=['POST'])
@require_login
@require_tenant
def add_draft_line():
    """Add line to invoice draft (HTMX endpoint, tenant-scoped)."""
    db_session = get_session()
    
    try:
        product_id = request.form.get('product_id', type=int)
        qty = request.form.get('qty', type=float, default=1)
        unit_cost_str = request.form.get('unit_cost', '').strip()
        
        try:
            unit_cost_decimal = Decimal(unit_cost_str)
            
            # Check if it's an integer
            if unit_cost_decimal % 1 != 0:
                flash('El costo unitario debe ser un número entero (sin decimales).', 'danger')
                return redirect(url_for('invoices.new_invoice'))
            
            unit_cost = int(unit_cost_decimal)
            
        except (ValueError, TypeError, Exception):
            flash('El costo unitario debe ser un número entero válido.', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        # Validations
        if not product_id:
            flash('Debe seleccionar un producto', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        if qty <= 0:
            flash('La cantidad debe ser mayor a 0', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        if unit_cost < 0:
            flash('El costo unitario no puede ser negativo', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        # Verify product exists and belongs to tenant
        product = db_session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            flash('Producto no encontrado o no pertenece a su negocio', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        # Add line to draft
        draft = get_invoice_draft()
        
        # Check if product already exists in lines
        existing_line = next((line for line in draft['lines'] if line['product_id'] == product_id), None)
        
        if existing_line:
            existing_line['qty'] = float(qty)
            existing_line['unit_cost'] = int(unit_cost)
        else:
            draft['lines'].append({
                'product_id': product_id,
                'qty': float(qty),
                'unit_cost': int(unit_cost)
            })
        
        save_invoice_draft(draft)
        
        return redirect(url_for('invoices.new_invoice'))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al agregar línea: {str(e)}', 'danger')
        return redirect(url_for('invoices.new_invoice'))


@invoices_bp.route('/draft/remove-line/<int:product_id>', methods=['POST'])
@require_login
@require_tenant
def remove_draft_line(product_id):
    """Remove line from invoice draft (HTMX endpoint)."""
    try:
        draft = get_invoice_draft()
        
        # Remove line
        draft['lines'] = [line for line in draft['lines'] if line['product_id'] != product_id]
        
        save_invoice_draft(draft)
        
        return redirect(url_for('invoices.new_invoice'))
        
    except Exception as e:
        flash(f'Error al remover línea: {str(e)}', 'danger')
        return redirect(url_for('invoices.new_invoice'))


@invoices_bp.route('/new/confirm-preview', methods=['GET'])
@require_login
@require_tenant
def confirm_create_preview():
    """Preview invoice creation (HTMX modal, tenant-scoped)."""
    db_session = get_session()
    
    try:
        draft = get_invoice_draft()
        
        # Validate draft
        errors = []
        
        if not draft.get('supplier_id'):
            errors.append('Debe seleccionar un proveedor')
        
        if not draft.get('invoice_number'):
            errors.append('El número de boleta es requerido')
        
        if not draft.get('invoice_date'):
            errors.append('La fecha de boleta es requerida')
        
        if not draft.get('lines'):
            errors.append('Debe agregar al menos un ítem a la boleta')
        
        if errors:
            error_html = '<div class="alert alert-danger"><ul class="mb-0">'
            for error in errors:
                error_html += f'<li>{error}</li>'
            error_html += '</ul></div>'
            return error_html
        
        # Validate supplier belongs to tenant
        supplier = db_session.query(Supplier).filter(
            Supplier.id == draft['supplier_id'],
            Supplier.tenant_id == g.tenant_id
        ).first()
        
        if not supplier:
            return '<div class="alert alert-danger">Proveedor no encontrado o no pertenece a su negocio.</div>'
        
        # Get products for lines (tenant-scoped)
        products = db_session.query(Product).filter(
            Product.tenant_id == g.tenant_id,
            Product.active == True
        ).all()
        product_dict = {p.id: p for p in products}
        
        # Prepare lines with product info
        lines_data = []
        total_amount = Decimal('0.00')
        
        for line in draft['lines']:
            product_id = line['product_id']
            product = product_dict.get(product_id)
            
            if not product:
                continue
            
            qty = Decimal(str(line['qty']))
            unit_cost = Decimal(str(line['unit_cost']))
            line_total = qty * unit_cost
            total_amount += line_total
            
            lines_data.append({
                'product': product,
                'qty': qty,
                'unit_cost': unit_cost,
                'line_total': line_total
            })
        
        # Parse dates
        try:
            invoice_date = datetime.strptime(draft['invoice_date'], '%Y-%m-%d').date()
            due_date = datetime.strptime(draft['due_date'], '%Y-%m-%d').date() if draft.get('due_date') else None
        except ValueError:
            return '<div class="alert alert-danger">Fecha inválida en el draft.</div>'
        
        return render_template('invoices/_create_confirm_modal.html',
                             supplier=supplier,
                             invoice_number=draft['invoice_number'],
                             invoice_date=invoice_date,
                             due_date=due_date,
                             lines=lines_data,
                             total_amount=total_amount)
        
    except Exception as e:
        current_app.logger.error(f"Error generating create preview: {e}")
        return f'<div class="alert alert-danger">Error al generar vista previa: {str(e)}</div>'


@invoices_bp.route('/create', methods=['POST'])
@require_login
@require_tenant
def create_invoice():
    """Create invoice with lines and update stock (tenant-scoped)."""
    db_session = get_session()
    
    try:
        draft = get_invoice_draft()
        
        # Validate draft
        if not draft['supplier_id']:
            flash('Debe seleccionar un proveedor', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        if not draft['invoice_number']:
            flash('El número de boleta es requerido', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        if not draft['invoice_date']:
            flash('La fecha de boleta es requerida', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        if not draft['lines']:
            flash('Debe agregar al menos un ítem a la boleta', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        # Parse dates
        try:
            invoice_date = datetime.strptime(draft['invoice_date'], '%Y-%m-%d').date()
            due_date = datetime.strptime(draft['due_date'], '%Y-%m-%d').date() if draft['due_date'] else None
        except ValueError:
            flash('Fecha inválida', 'danger')
            return redirect(url_for('invoices.new_invoice'))
        
        # Prepare payload with tenant_id
        payload = {
            'tenant_id': g.tenant_id,  # CRITICAL
            'supplier_id': draft['supplier_id'],
            'invoice_number': draft['invoice_number'],
            'invoice_date': invoice_date,
            'due_date': due_date,
            'lines': draft['lines']
        }
        
        # Call service to create invoice
        invoice_id = create_invoice_with_lines(payload, db_session)
        
        # Clear draft
        clear_invoice_draft()
        
        flash(f'Boleta #{invoice_id} creada exitosamente. Stock actualizado.', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
        
    except ValueError as e:
        db_session.rollback()
        flash(str(e), 'danger')
        return redirect(url_for('invoices.new_invoice'))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al crear boleta: {str(e)}', 'danger')
        return redirect(url_for('invoices.new_invoice'))


@invoices_bp.route('/<int:invoice_id>/pay/preview', methods=['GET'])
@require_login
@require_tenant
def pay_invoice_preview(invoice_id):
    """Preview invoice payment (HTMX modal, tenant-scoped)."""
    db_session = get_session()
    
    try:
        invoice = db_session.query(PurchaseInvoice).filter(
            PurchaseInvoice.id == invoice_id,
            PurchaseInvoice.tenant_id == g.tenant_id
        ).first()
        
        if not invoice:
            return '<div class="alert alert-danger">Boleta no encontrada.</div>'
        
        if invoice.status == InvoiceStatus.PAID:
             return f'<div class="alert alert-danger">La boleta ya está pagada.</div>'
        
        today = date.today().strftime('%Y-%m-%d')
        pending_amount = invoice.total_amount - invoice.paid_amount
        
        return render_template('invoices/_pay_confirm_modal.html',
                             invoice=invoice,
                             pending_amount=pending_amount,
                             today=today)
        
    except Exception as e:
        current_app.logger.error(f"Error generating payment preview for invoice {invoice_id}: {e}")
        return f'<div class="alert alert-danger">Error al generar vista previa: {str(e)}</div>'


@invoices_bp.route('/<int:invoice_id>/payments', methods=['POST'])
@require_login
@require_tenant
def register_payment_route(invoice_id):
    """Register a payment for an invoice (HTMX, tenant-scoped)."""
    db_session = get_session()
    
    current_app.logger.info(f"[PAYMENT] Starting payment registration for invoice {invoice_id}")
    current_app.logger.info(f"[PAYMENT] Form data: {dict(request.form)}")
    
    try:
        # Get form data
        paid_at_str = request.form.get('paid_at', '').strip()
        payment_method = request.form.get('payment_method', 'CASH').upper()
        amount_str = request.form.get('amount', '').strip()
        notes = request.form.get('notes', '').strip() or None
        
        current_app.logger.info(f"[PAYMENT] Parsed data - amount_str: '{amount_str}', method: {payment_method}, date: {paid_at_str}")
        
        if not paid_at_str:
            raise ValueError('La fecha de pago es requerida')
        
        if payment_method not in ['CASH', 'TRANSFER']:
             raise ValueError('Método de pago inválido. Permitidos: CASH, TRANSFER')
            
        try:
            # Use utility for flexible AR number format parsing
            amount = parse_ar_number(amount_str)
            if amount <= 0:
                raise ValueError("El monto debe ser positivo")
        except ValueError as e:
             raise ValueError(f'Monto inválido: {str(e)}')
        except Exception:
             raise ValueError(f'Monto inválido: {amount_str}')
        
        # Parse date
        try:
            paid_at_date = datetime.strptime(paid_at_str, '%Y-%m-%d')
            # If it's today, use current time. Else use start of day.
            if paid_at_date.date() == date.today():
                 paid_at = datetime.now()
            else:
                 paid_at = datetime.combine(paid_at_date.date(), datetime.min.time())
        except ValueError:
            raise ValueError('Formato de fecha inválido. Use AAAA-MM-DD')
        
        # Call payment service
        register_invoice_payment(
            tenant_id=g.tenant_id,
            invoice_id=invoice_id,
            amount=amount,
            payment_method=payment_method,
            paid_at=paid_at,
            notes=notes,
            user_id=g.user.id,
            session=db_session
        )
        
        # COMMIT THE TRANSACTION
        current_app.logger.info(f"[PAYMENT] Committing transaction for invoice {invoice_id}")
        db_session.commit()
        current_app.logger.info(f"[PAYMENT] Payment registered successfully: ${amount}")
        
        # Check if HTMX request
        if request.headers.get('HX-Request'):
             current_app.logger.info(f"[PAYMENT] HTMX request detected, preparing response")
             
             referer = request.headers.get('Referer', '')
             if f'/invoices/{invoice_id}' in referer:
                 # Detail view: Update via OOB swaps
                 db_session.expire_all()
                 invoice = db_session.query(PurchaseInvoice).get(invoice_id)
                 
                 # Render updated payments section
                 payments_html = render_template('invoices/_payments.html', invoice=invoice)
                 # Inject OOB attribute to replace the section in the background
                 payments_html = payments_html.replace('id="invoice-payments-section"', 'id="invoice-payments-section" hx-swap-oob="true"')
                 
                 # Create success alert with OOB swap
                 alert_html = f'''<div id="payment-alerts" hx-swap-oob="true">
                     <div class="alert-custom alert-success" role="alert">
                         <i class="alert-custom-icon bi bi-check-circle-fill"></i>
                         <div class="alert-custom-content">Pago de ${amount} registrado exitosamente.</div>
                         <button type="button" class="alert-custom-close" onclick="this.parentElement.remove()">
                             <i class="bi bi-x-lg"></i>
                         </button>
                     </div>
                 </div>'''
                 
                 return payments_html + alert_html
             else:
                 # List view: Force full page refresh to update status/badges in table
                 response = make_response('', 200)
                 response.headers['HX-Refresh'] = 'true'
                 return response
             
        flash(f'Pago de ${amount} registrado exitosamente.', 'success')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
        
    except ValueError as e:
        db_session.rollback()
        current_app.logger.warning(f"[PAYMENT] Validation error for invoice {invoice_id}: {str(e)}")
        if request.headers.get('HX-Request'):
             # Return error to the modal using HX-Retarget
             error_html = f'''<div class="alert alert-danger" style="margin: 0; padding: var(--spacing-3); font-size: var(--font-size-sm);">
                 <i class="bi bi-exclamation-circle me-2"></i>{str(e)}
             </div>'''
             response = make_response(error_html)
             response.headers['HX-Retarget'] = '#modal-errors'
             response.headers['HX-Reswap'] = 'innerHTML'
             return response
        flash(str(e), 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"[PAYMENT] CRITICAL ERROR for invoice {invoice_id}: {str(e)}")
        import traceback
        current_app.logger.error(f"[PAYMENT] Traceback:\n{traceback.format_exc()}")
        if request.headers.get('HX-Request'):
             error_html = f'''<div class="alert alert-danger" style="margin: 0; padding: var(--spacing-3); font-size: var(--font-size-sm);">
                 <i class="bi bi-exclamation-octagon me-2"></i>Error interno al procesar pago. Por favor, contacte al administrador.
             </div>'''
             response = make_response(error_html)
             response.headers['HX-Retarget'] = '#modal-errors'
             response.headers['HX-Reswap'] = 'innerHTML'
             return response
        flash(f'Error al procesar pago: {str(e)}', 'danger')
        return redirect(url_for('invoices.view_invoice', invoice_id=invoice_id))


@invoices_bp.route('/<int:invoice_id>/pay', methods=['POST'])
@require_login
@require_tenant
def pay_invoice_route(invoice_id):
    """Legacy route compatibility."""
    return register_payment_route(invoice_id)
