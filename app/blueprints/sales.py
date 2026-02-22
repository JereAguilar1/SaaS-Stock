"""Sales blueprint for POS and cart management - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file, current_app, g, abort, Response
from sqlalchemy import or_, func, and_, desc
from sqlalchemy.orm import joinedload
from decimal import Decimal, InvalidOperation
import decimal
from datetime import datetime
from app.database import get_session
from app.models import Product, ProductStock, Sale, SaleLine, SaleStatus, SaleDraft, Category, Customer
from app.services.sales_service import confirm_sale, confirm_sale_from_draft
from app.services import sale_draft_service
from app.services.top_products_service import get_top_selling_products
from app.services.quote_service import generate_quote_pdf
from app.middleware import require_login, require_tenant
from app.exceptions import BusinessLogicError, NotFoundError, InsufficientStockError

from typing import Optional, Tuple, Union
sales_bp = Blueprint('sales', __name__, url_prefix='/sales')

IVA_RATE = Decimal('1.21')

# Helper removed: using global exception handlers

def _calculate_tax_breakdown(total: Decimal) -> Tuple[Decimal, Decimal]:
    """Calculate subtotal and IVA from total with tax included."""
    if total is None:
        return Decimal('0.00'), Decimal('0.00')
    subtotal = (total / IVA_RATE).quantize(Decimal('0.01'))
    iva = total - subtotal
    return subtotal, iva

def _get_product_or_error(db_session, product_id: int, tenant_id: int) -> Optional[Product]:
    """Get product by ID with tenant validation.
    
    Returns None if product not found or doesn't belong to tenant.
    """
    return db_session.query(Product).filter(
        Product.id == product_id,
        Product.tenant_id == tenant_id
    ).first()

def _validate_product_for_cart(product: Optional[Product], qty: Decimal) -> Optional[str]:
    """Validate if product can be added to cart with given quantity."""
    if not product:
        return 'Producto no encontrado o no pertenece a su negocio'
    if not product.active:
        return f'El producto "{product.name}" no está activo'
    if product.on_hand_qty <= 0:
        return f'El producto "{product.name}" no tiene stock disponible'
    if qty <= 0:
        return 'La cantidad debe ser mayor a 0'
    return None

def _search_products_internal(db_session, tenant_id: int, search_query: str = '', category_id: str = '') -> Tuple[list, Optional[int]]:
    """Internal helper to build and execute the product search query."""
    # Build base query
    query = db_session.query(Product).filter(
        Product.tenant_id == tenant_id,
        Product.active == True
    )

    # Apply Category Filter if present
    if category_id:
        try:
            cat_id = int(category_id)
            query = query.filter(Product.category_id == cat_id)
        except ValueError:
            pass
    
    products = []
    exact_barcode_match = None
    
    if search_query:
        # Sanitize input (limit length)
        search_query = search_query[:100]
        
        # Check for exact barcode match first
        exact_match_query = db_session.query(Product).filter(
            Product.tenant_id == tenant_id,
            Product.active == True,
            Product.barcode.isnot(None),
            func.lower(Product.barcode) == search_query.lower()
        )
        
        if category_id:
            try:
                exact_match_query = exact_match_query.filter(Product.category_id == int(category_id))
            except ValueError:
                pass

        exact_match = exact_match_query.first()
        
        if exact_match:
            exact_barcode_match = exact_match.id
            products = [exact_match]
        else:
            # Fuzzy search filter
            search_filter = or_(
                func.lower(Product.name).like(f'%{search_query.lower()}%'),
                and_(Product.sku.isnot(None), func.lower(Product.sku).like(f'%{search_query.lower()}%')),
                and_(Product.barcode.isnot(None), func.lower(Product.barcode).like(f'%{search_query.lower()}%'))
            )
            
            # Popularity Sort Query
            pop_query = (db_session.query(Product)
                       .outerjoin(ProductStock)
                       .outerjoin(SaleLine, SaleLine.product_id == Product.id)
                       .outerjoin(Sale, and_(
                           Sale.id == SaleLine.sale_id, 
                           Sale.status == SaleStatus.CONFIRMED,
                           Sale.tenant_id == tenant_id
                       ))
                       .filter(
                           Product.tenant_id == tenant_id,
                           Product.active == True
                       ))
            
            if category_id:
                try:
                    pop_query = pop_query.filter(Product.category_id == int(category_id))
                except ValueError:
                    pass

            products = (pop_query.filter(search_filter)
                       .group_by(Product.id)
                       .order_by(
                           desc(func.sum(func.coalesce(SaleLine.qty, 0))),
                           Product.name
                       )
                       .limit(20)
                       .all())
    else:
        # No text search, list items with optional category
        products = (query
                   .outerjoin(ProductStock)
                   .order_by(Product.name)
                   .limit(20)
                   .all())
                   
    return products, exact_barcode_match





def get_cart() -> dict:
    """Get cart from session for current tenant."""
    if 'cart_by_tenant' not in session:
        session['cart_by_tenant'] = {}
    
    tenant_id = str(g.tenant_id)
    if tenant_id not in session['cart_by_tenant']:
        session['cart_by_tenant'][tenant_id] = {'items': {}}
        session.modified = True
        
    return session['cart_by_tenant'][tenant_id]


def _serialize_value(val) -> Union[str, dict, any]:
    """Helper to ensure values are JSON serializable for session."""
    if isinstance(val, Decimal):
        return str(val)
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    return val

def save_cart(cart: dict) -> None:
    """Save cart to session for current tenant."""
    if 'cart_by_tenant' not in session:
        session['cart_by_tenant'] = {}
        
    tenant_id = str(g.tenant_id)
    
    # Deep copy and serialize to avoid storing Decimals in session
    serialized_cart = {
        'items': {
            k: _serialize_value(v) 
            for k, v in cart['items'].items()
        }
    }
    
    session['cart_by_tenant'][tenant_id] = serialized_cart
    session.modified = True


def get_cart_with_products(db_session, tenant_id: int) -> Tuple[list, Decimal]:
    """Get cart with product details from database (tenant-scoped)."""
    cart = get_cart()
    cart_items = []
    total = Decimal('0.00')
    
    for product_id_str, item in cart['items'].items():
        product_id = int(product_id_str)
        product = _get_product_or_error(db_session, product_id, tenant_id)
        
        if product:
            qty = Decimal(str(item['qty']))
            subtotal = qty * product.sale_price
            
            cart_items.append({
                'product_id': product.id,
                'product': product,
                'qty': qty,
                'unit_price': product.sale_price,
                'subtotal': subtotal
            })
            total += subtotal
    
    return cart_items, total


def _render_cart_content(db_session, tenant_id: int) -> str:
    """Render cart content template (used for HTMX updates)."""
    cart_items, cart_total = get_cart_with_products(db_session, tenant_id)
    subtotal, iva_total = _calculate_tax_breakdown(cart_total)
    return render_template('sales/_cart_content.html',
                         cart_items=cart_items,
                         cart_total=cart_total,
                         subtotal=subtotal,
                         iva_total=iva_total)



@sales_bp.route('/new')
@require_login
@require_tenant
def new_sale() -> Union[str, Response]:
    """POS screen for new sale (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get search query if any
        search_query = request.args.get('q', '').strip()
        
        # 1. Execute search/catalog via helper
        products, _ = _search_products_internal(db_session, g.tenant_id, search_query)
        
        # Get persisted draft for this user (rehydration)
        try:
             draft, totals = sale_draft_service.get_draft_with_totals(
                 db_session, g.tenant_id, g.user_id
             )
        except Exception as e:
             current_app.logger.warning(f"Error loading draft in new_sale: {e}")
             draft, totals = None, None

        # Reset cash override state on page load
        session['cash_overridden'] = False
        
        # Get top selling products (tenant-scoped)
        top_products, top_products_error = get_top_selling_products(db_session, g.tenant_id, limit=10)
        
        # is_fallback removed as we now show catalog below
        is_fallback = False
        
        # Get categories for filter (tenant-scoped)
        categories = db_session.query(Category).filter(
            Category.tenant_id == g.tenant_id
        ).order_by(Category.name).all()
        
        # NEW: Load customers for selector
        from app.models import Customer
        from app.services.customer_service import get_or_create_default_customer_id
        
        customers = db_session.query(Customer).filter(
            Customer.tenant_id == g.tenant_id
        ).order_by(Customer.name).all()
        
        # Get default customer ID
        default_customer_id = get_or_create_default_customer_id(db_session, g.tenant_id)
        
        return render_template('sales/new.html',
                             products=products,
                             search_query=search_query,
                             draft=draft,
                             totals=totals,
                             top_products=top_products,
                             top_products_error=top_products_error,
                             categories=categories,
                             customers=customers,
                             default_customer_id=default_customer_id)
        
    except Exception as e:
        flash(f'Error al cargar POS: {str(e)}', 'danger')
        return render_template('sales/new.html',
                             products=[],
                             search_query='',
                             draft=None,
                             totals=None,
                             top_products=[],
                             top_products_error=False)


@sales_bp.route('/products/search', methods=['GET'])
@require_login
@require_tenant
def product_search() -> Union[str, Response]:
    """Search products for POS (HTMX endpoint, tenant-scoped)."""
    db_session = get_session()
    
    try:
        search_query = request.args.get('q', '').strip()
        category_id = request.args.get('category_id', '').strip()
        
        # 1. Get draft for highlighting selected products
        try:
            draft, totals = sale_draft_service.get_draft_with_totals(db_session, g.tenant_id, g.user_id)
        except Exception as e:
            current_app.logger.warning(f"Could not load draft in product_search: {e}")
            draft, totals = None, None
        
        # 2. Execute search via helper
        products, exact_barcode_match = _search_products_internal(db_session, g.tenant_id, search_query, category_id)

        
        return render_template('sales/_product_results.html',
                             products=products,
                             search_query=search_query,
                             totals=totals,
                             exact_barcode_match=exact_barcode_match,
                             top_products=products if not search_query else [])
        
    except Exception as e:
        current_app.logger.error(
            f"Error in product_search for tenant {g.tenant_id}, user {g.user_id}, query='{request.args.get('q', '')}': {str(e)}", 
            exc_info=True
        )
        # Return 200 with error HTML (HTMX-friendly, doesn't break UI)
        return render_template('sales/_search_error.html', error_message="Error al buscar productos"), 200


@sales_bp.route('/cart/add', methods=['POST'])
@require_login
@require_tenant
def cart_add() -> Union[str, Response]:
    """Add product to cart (HTMX endpoint, tenant-scoped)."""
    db_session = get_session()
    
    try:
        # 1. Determinar content type y extraer payload
        is_htmx = request.headers.get('HX-Request') == 'true'
        
        # Intentar leer payload de múltiples fuentes
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict()
        
        # Log para debugging
        current_app.logger.info(
            f"[cart_add] tenant_id={g.tenant_id}, "
            f"is_htmx={is_htmx}, content_type={request.content_type}, "
            f"payload_keys={list(payload.keys())}"
        )
        
        # 2. Validar payload
        product_id_str = payload.get('product_id')
        qty_str = payload.get('qty', '1')
        
        if not product_id_str:
            raise BusinessLogicError('Falta el ID del producto')
        
        # 3. Convertir con manejo de errores
        try:
            product_id = int(product_id_str)
            qty = Decimal(str(qty_str))
        except (ValueError, TypeError):
            raise BusinessLogicError('Datos inválidos: product_id o qty no son numéricos')
        
        if qty <= 0:
            raise BusinessLogicError('La cantidad debe ser mayor a 0')
        
        # 4. Get and validate product
        product = _get_product_or_error(db_session, product_id, g.tenant_id)
        error_msg = _validate_product_for_cart(product, qty)
        if error_msg:
            if 'encontrado' in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessLogicError(error_msg)
        
        # 6. Process cart update
        cart = get_cart()
        product_id_str = str(product_id)
        current_qty = Decimal(str(cart['items'].get(product_id_str, {}).get('qty', 0)))
        new_qty = current_qty + qty
        
        if new_qty > product.on_hand_qty:
            raise BusinessLogicError(f'Stock insuficiente para "{product.name}". Disponible: {product.on_hand_qty}')
            
        cart['items'][product_id_str] = {'qty': float(new_qty)}
        save_cart(cart)
        
        flash(f'"{product.name}" agregado al carrito', 'success')
        
        # 8. If HTMX request, return partial content
        if is_htmx:
            current_app.logger.info(
                f"[HTMX] cart_add SUCCESS: product_id={product_id}, "
                f"qty={qty}, cart_size={len(cart['items'])}"
            )
            return _render_cart_content(db_session, g.tenant_id)
        
        return redirect(url_for('sales.new_sale'))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error in cart_add: {str(e)}", exc_info=True)
        
        # Si es HTMX, retornar error parcial
        return _handle_error(f'Error al agregar producto: {str(e)}', 'danger', 500)


@sales_bp.route('/cart/update', methods=['POST'])
@require_login
@require_tenant
def cart_update() -> Union[str, Response]:
    """Update cart item quantity (HTMX endpoint, tenant-scoped)."""
    db_session = get_session()
    
    try:
        product_id = int(request.form.get('product_id'))
        qty_str = request.form.get('qty', '').strip()
        
        # Handle empty qty
        if not qty_str:
            return _render_cart_content(db_session, g.tenant_id)
        
        try:
            qty = Decimal(qty_str)
        except:
            flash('Cantidad inválida', 'warning')
            return _render_cart_content(db_session, g.tenant_id)
        
        # If qty <= 0, remove item automatically
        if qty <= 0:
            cart = session.get('cart', {'items': {}})
            if str(product_id) in cart['items']:
                del cart['items'][str(product_id)]
                session['cart'] = cart
                session.modified = True
                flash('Producto eliminado del carrito', 'info')
            return _render_cart_content(db_session, g.tenant_id)
        
        product = _get_product_or_error(db_session, product_id, g.tenant_id)
        
        if not product:
            flash('Producto no encontrado o no pertenece a su negocio', 'danger')
            return redirect(url_for('sales.new_sale'))
        
        # Check stock
        if qty > product.on_hand_qty:
            flash(f'Stock insuficiente para "{product.name}". Disponible: {product.on_hand_qty}', 'warning')
            return _render_cart_content(db_session, g.tenant_id)
        
        # Update cart
        cart = get_cart()
        product_id_str = str(product_id)
        
        if product_id_str in cart['items']:
            cart['items'][product_id_str]['qty'] = float(qty)
            save_cart(cart)
        
        # Return updated cart partial
        current_app.logger.info(
            f"[HTMX] cart_update: tenant_id={g.tenant_id}, "
            f"product_id={product_id}, qty={qty}"
        )
        return _render_cart_content(db_session, g.tenant_id)
        
    except Exception as e:
        current_app.logger.error(f"Error in cart_update: {str(e)}", exc_info=True)
        flash(f'Error al actualizar carrito: {str(e)}', 'danger')
        return _render_cart_content(db_session, g.tenant_id)


@sales_bp.route('/cart/remove', methods=['POST'])
@require_login
@require_tenant
def cart_remove() -> Union[str, Response]:
    """Remove item from cart (HTMX endpoint)."""
    db_session = get_session()
    
    try:
        product_id = int(request.form.get('product_id'))
        
        # Remove from cart
        cart = get_cart()
        product_id_str = str(product_id)
        
        if product_id_str in cart['items']:
            del cart['items'][product_id_str]
            save_cart(cart)
            flash('Producto removido del carrito', 'info')
        
        # Return updated cart partial
        current_app.logger.info(
            f"[HTMX] cart_remove: tenant_id={g.tenant_id}, "
            f"product_id={product_id}"
        )
        return _render_cart_content(db_session, g.tenant_id)
        
    except Exception as e:
        current_app.logger.error(f"Error in cart_remove: {str(e)}", exc_info=True)
        flash(f'Error al remover producto: {str(e)}', 'danger')
        return _render_cart_content(db_session, g.tenant_id)


@sales_bp.route('/confirm/preview', methods=['GET'])
@require_login
@require_tenant
def confirm_preview() -> Union[str, Response]:
    """Preview sale before confirmation (HTMX modal, tenant-scoped)."""
    db_session = get_session()
    
    cart = get_cart()
    
    # Validate cart not empty
    if not cart.get('items'):
        raise BusinessLogicError('El carrito está vacío. Agregue productos para continuar.')
    
    # Get cart items with products (tenant-scoped)
    cart_items, cart_total = get_cart_with_products(db_session, g.tenant_id)
    
    # Get payment method from form (if selected)
    payment_method = request.args.get('payment_method', 'CASH')
    
    return render_template('sales/_confirm_modal.html',
                         cart_items=cart_items,
                         cart_total=cart_total,
                         payment_method=payment_method)


@sales_bp.route('/confirm', methods=['POST'])
@require_login
@require_tenant
def confirm() -> Union[str, Response]:
    """Confirm sale and process transaction (tenant-scoped)."""
    db_session = get_session()
    
    try:
        cart = get_cart()
        
        # Validate cart not empty
        if not cart['items']:
            raise BusinessLogicError('El carrito está vacío. Agregue productos antes de confirmar.')
        
        # Get payment method from form
        payment_method = request.form.get('payment_method', 'CASH').upper()
        customer_id_raw = request.form.get('customer_id', '').strip()
        
        # NEW: Handle customer_id with fallback to default
        from app.models import Customer
        from app.services.customer_service import get_or_create_default_customer_id
        
        if not customer_id_raw or customer_id_raw == '':
            # No customer selected -> use default
            customer_id = get_or_create_default_customer_id(db_session, g.tenant_id)
        else:
            try:
                customer_id = int(customer_id_raw)
                
                # Verify customer belongs to tenant
                customer = db_session.query(Customer).filter(
                    Customer.id == customer_id,
                    Customer.tenant_id == g.tenant_id
                ).first()
                
                if not customer:
                    raise NotFoundError('Cliente inválido o no pertenece a su negocio')
                    
            except ValueError:
                # Invalid ID format -> use default
                customer_id = get_or_create_default_customer_id(db_session, g.tenant_id)
        
        # Validate payment method
        if payment_method not in ['CASH', 'TRANSFER']:
            raise BusinessLogicError('Método de pago inválido.')
        
        # Call service to confirm sale with tenant_id
        sale_id = confirm_sale(cart, db_session, payment_method, g.tenant_id, customer_id)
        
        # Clear cart
        session['cart'] = {'items': {}}
        session.modified = True
        
        payment_label = 'Efectivo' if payment_method == 'CASH' else 'Transferencia'
        flash(f'Venta #{sale_id} confirmada exitosamente ({payment_label}). Stock actualizado.', 'success')
        return redirect(url_for('sales.new_sale'))
        
    except (ValueError, BusinessLogicError) as e:
        db_session.rollback()
        raise BusinessLogicError(str(e))


@sales_bp.route('/quote.pdf')
@require_login
@require_tenant
def quote_pdf() -> Union[str, Response]:
    """Generate PDF quote from cart (tenant-scoped, no sale creation)."""
    db_session = get_session()
    
    try:
        cart = get_cart()
        
        # Validate cart not empty
        if not cart['items']:
            flash('El carrito está vacío. Agregue productos para generar un presupuesto.', 'warning')
            return redirect(url_for('sales.new_sale'))
        
        # Build cart with product details (tenant-scoped)
        cart_with_details = {'items': {}}
        
        for product_id_str, item in cart['items'].items():
            product_id = int(product_id_str)
            product = _get_product_or_error(db_session, product_id, g.tenant_id)
            
            if not product:
                continue
            
            cart_with_details['items'][product_id_str] = {
                'name': product.name,
                'qty': Decimal(str(item['qty'])),
                'price': product.sale_price,
                'uom': product.uom.symbol if product.uom else '—'
            }
        
        # Get payment method from session if available
        payment_method = session.get('quote_payment_method', None)
        
        # Business info from config
        business_info = {
            'name': current_app.config.get('BUSINESS_NAME', 'Mi Negocio'),
            'address': current_app.config.get('BUSINESS_ADDRESS', ''),
            'phone': current_app.config.get('BUSINESS_PHONE', ''),
            'email': current_app.config.get('BUSINESS_EMAIL', ''),
            'valid_days': current_app.config.get('QUOTE_VALID_DAYS', 7),
            'payment_method': payment_method
        }
        
        # Generate PDF
        pdf_buffer = generate_quote_pdf(cart_with_details, business_info)
        
        # Generate filename with timestamp
        filename = f"presupuesto_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        # Return PDF as download
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f'Error al generar presupuesto: {str(e)}', 'danger')
        return redirect(url_for('sales.new_sale'))


# ============================================================================
# Sales Management (List, Detail, Edit/Adjust) - TENANT-SCOPED
# ============================================================================

@sales_bp.route('/')
@require_login
@require_tenant
def list_sales() -> Union[str, Response]:
    """List all confirmed sales (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Capturar término de búsqueda
        q = request.args.get('q', '').strip()
        
        # Build query (tenant-scoped)
        query = db_session.query(Sale).options(joinedload(Sale.customer)).filter(
            Sale.tenant_id == g.tenant_id,
            Sale.status == SaleStatus.CONFIRMED
        )
        
        if q:
            if q.isdigit():
                # Si el usuario escribió números, buscamos por ID de la venta
                query = query.filter(Sale.id == int(q))
            else:
                # Si escribió texto, buscamos por nombre del cliente
                # Hacemos un JOIN con Customer para poder filtrar por su nombre
                query = query.join(Customer).filter(Customer.name.ilike(f'%{q}%'))
        
        # Order by most recent first
        sales = query.order_by(Sale.datetime.desc()).all()
        
        return render_template('sales/list.html', 
                             sales=sales,
                             search_query=q)
        
    except Exception as e:
        flash(f'Error al cargar ventas: {str(e)}', 'danger')
        return redirect(url_for('sales.new_sale'))


@sales_bp.route('/<int:sale_id>')
@require_login
@require_tenant
def detail_sale(sale_id: int) -> Union[str, Response]:
    """Show sale detail (tenant-scoped)."""
    db_session = get_session()
    
    try:
        sale = db_session.query(Sale).filter(
            Sale.id == sale_id,
            Sale.tenant_id == g.tenant_id
        ).first()
        
        if not sale:
            abort(404)
        
        return render_template('sales/detail.html', sale=sale)
        
    except Exception as e:
        flash(f'Error al cargar venta: {str(e)}', 'danger')
        return redirect(url_for('sales.list_sales'))


@sales_bp.route('/<int:sale_id>/edit', methods=['GET'])
@require_login
@require_tenant
def edit_sale_form(sale_id: int) -> Union[str, Response]:
    """Show form to edit/adjust a sale (tenant-scoped)."""
    db_session = get_session()
    
    try:
        from app.services.sale_adjustment_service import get_sale_summary
        
        sale_summary = get_sale_summary(sale_id, db_session, g.tenant_id)
        
        # Get active products for search (tenant-scoped)
        products = db_session.query(Product).filter(
            Product.tenant_id == g.tenant_id,
            Product.active == True
        ).order_by(Product.name).all()
        
        return render_template('sales/edit.html', 
                             sale=sale_summary,
                             products=products)
        
    except ValueError as e:
        flash(str(e), 'danger')
        return redirect(url_for('sales.list_sales'))
    except Exception as e:
        flash(f'Error al cargar formulario de edición: {str(e)}', 'danger')
        return redirect(url_for('sales.list_sales'))


@sales_bp.route('/<int:sale_id>/edit/preview', methods=['POST'])
@require_login
@require_tenant
def edit_sale_preview(sale_id: int) -> Union[str, Response]:
    """Preview sale adjustments before applying (HTMX modal, tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Parse lines from form
        lines = []
        line_index = 0
        
        while True:
            product_id_key = f'lines[{line_index}][product_id]'
            qty_key = f'lines[{line_index}][qty]'
            
            if product_id_key not in request.form:
                break
            
            product_id = request.form.get(product_id_key)
            qty = request.form.get(qty_key)
            
            if product_id and qty:
                lines.append({
                    'product_id': int(product_id),
                    'qty': Decimal(qty)
                })
            
            line_index += 1
        
        if not lines:
            return '<div class="alert alert-warning">Debe haber al menos una línea en la venta.</div>'
        
        # Get current sale and validate tenant
        sale = db_session.query(Sale).filter(
            Sale.id == sale_id,
            Sale.tenant_id == g.tenant_id
        ).first()
        
        if not sale:
            return '<div class="alert alert-danger">Venta no encontrada.</div>'
        
        # Build old_lines
        old_lines = []
        old_total = Decimal('0.00')
        for line in sale.lines:
            old_lines.append({
                'product_id': line.product_id,
                'product_name': line.product.name,
                'product_sku': line.product.sku or '-',
                'product_uom': line.product.uom.symbol if line.product.uom else '-',
                'qty': line.qty,
                'unit_price': line.unit_price,
                'subtotal': line.line_total
            })
            old_total += line.line_total
        
        # Build new_lines with product info (tenant-scoped)
        new_lines = []
        new_total = Decimal('0.00')
        products_cache = {}
        
        for line_data in lines:
            product_id = line_data['product_id']
            qty = line_data['qty']
            
            # Get product and validate tenant
            if product_id not in products_cache:
                product = _get_product_or_error(db_session, product_id, g.tenant_id)
                if not product:
                    continue
                products_cache[product_id] = product
            else:
                product = products_cache[product_id]
            
            # Use original unit_price if product was in old sale, else current price
            old_line = next((ol for ol in old_lines if ol['product_id'] == product_id), None)
            unit_price = old_line['unit_price'] if old_line else product.sale_price
            
            subtotal = qty * unit_price
            new_lines.append({
                'product_id': product_id,
                'product_name': product.name,
                'product_sku': product.sku or '-',
                'product_uom': product.uom.symbol if product.uom else '-',
                'qty': qty,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'current_stock': product.on_hand_qty
            })
            new_total += subtotal
        
        # Calculate deltas
        changes = {
            'added': [],
            'removed': [],
            'modified': [],
            'stock_issues': []
        }
        
        # Check for removed
        for old_line in old_lines:
            if not any(nl['product_id'] == old_line['product_id'] for nl in new_lines):
                changes['removed'].append(old_line)
        
        # Check for added and modified
        for new_line in new_lines:
            old_line = next((ol for ol in old_lines if ol['product_id'] == new_line['product_id']), None)
            
            if not old_line:
                # Added
                changes['added'].append(new_line)
                
                # Check stock
                if new_line['qty'] > new_line['current_stock']:
                    changes['stock_issues'].append({
                        'product_name': new_line['product_name'],
                        'needed': new_line['qty'],
                        'available': new_line['current_stock']
                    })
            else:
                # Modified?
                if new_line['qty'] != old_line['qty']:
                    delta_qty = new_line['qty'] - old_line['qty']
                    changes['modified'].append({
                        'product_name': new_line['product_name'],
                        'old_qty': old_line['qty'],
                        'new_qty': new_line['qty'],
                        'delta_qty': delta_qty
                    })
                    
                    # Check stock if increasing
                    if delta_qty > 0:
                        if delta_qty > new_line['current_stock']:
                            changes['stock_issues'].append({
                                'product_name': new_line['product_name'],
                                'needed': delta_qty,
                                'available': new_line['current_stock']
                            })
        
        # Check if no changes
        if not changes['added'] and not changes['removed'] and not changes['modified']:
            return '<div class="alert alert-info">No hay cambios para aplicar.</div>'
        
        # Calculate diff
        diff = new_total - old_total
        
        return render_template('sales/_edit_confirm_modal.html',
                             sale_id=sale_id,
                             old_lines=old_lines,
                             new_lines=new_lines,
                             old_total=old_total,
                             new_total=new_total,
                             diff=diff,
                             changes=changes)
        
    except (ValueError, BusinessLogicError) as e:
        raise BusinessLogicError(f"Error al generar vista previa: {str(e)}")


@sales_bp.route('/<int:sale_id>/edit', methods=['POST'])
@require_login
@require_tenant
def edit_sale_save(sale_id: int) -> Union[str, Response]:
    """Save sale adjustments (tenant-scoped)."""
    db_session = get_session()
    
    try:
        from app.services.sale_adjustment_service import adjust_sale
        
        # Parse lines from form
        lines = []
        line_index = 0
        
        while True:
            product_id_key = f'lines[{line_index}][product_id]'
            qty_key = f'lines[{line_index}][qty]'
            
            if product_id_key not in request.form:
                break
            
            product_id = request.form.get(product_id_key)
            qty = request.form.get(qty_key)
            
            if product_id and qty:
                lines.append({
                    'product_id': int(product_id),
                    'qty': Decimal(qty)
                })
            
            line_index += 1
        
        if not lines:
            flash('Debe haber al menos una línea en la venta', 'warning')
            return redirect(url_for('sales.edit_sale_form', sale_id=sale_id))
        
        # Apply adjustment with tenant_id
        adjust_sale(sale_id, lines, db_session, g.tenant_id)
        
        flash(f'Venta #{sale_id} ajustada exitosamente', 'success')
        return redirect(url_for('sales.detail_sale', sale_id=sale_id))
        
    except (ValueError, BusinessLogicError) as e:
        db_session.rollback()
        raise BusinessLogicError(str(e))
from app.services import sale_draft_service
from app.services.sales_service import confirm_sale_from_draft
from app.middleware import require_login, require_tenant
import uuid


# ============================================================================
# DRAFT CART ENDPOINTS (Persistent Cart)
# ============================================================================

@sales_bp.route('/draft/add', methods=['POST'])
@require_login
@require_tenant
def draft_add() -> Union[str, Response]:
    """Add product to persistent draft cart (HTMX endpoint)."""
    db_session = get_session()
    
    try:
        is_htmx = request.headers.get('HX-Request') == 'true'
        
        # Get payload
        if request.is_json:
            payload = request.get_json(silent=True) or {}
        else:
            payload = request.form.to_dict()
        
        # Validate product_id
        if not payload.get('product_id'):
             raise ValueError("Falta ID de producto")
             
        try:
            product_id = int(payload.get('product_id'))
        except (ValueError, TypeError):
             raise ValueError("ID de producto inválido")

        # Parse quantity
        qty_val = payload.get('qty', '1')
        try:
            qty = Decimal(str(qty_val))
        except:
            qty = Decimal('1')

        if qty <= 0:
            raise ValueError('La cantidad debe ser mayor a 0')
        
        # Validate user_id availability
        if not hasattr(g, 'user_id') or not g.user_id:
            current_app.logger.error("draft_add called without g.user_id")
            raise Exception("Error de sesión de usuario")

        # Get or create draft
        draft = sale_draft_service.get_or_create_draft(
            db_session, g.tenant_id, g.user_id
        )
        
        # Add product to draft
        # This service method handles availability checks and raises ValueError if needed
        sale_draft_service.add_product_to_draft(
            db_session, draft.id, product_id, qty, g.tenant_id
        )
        
        db_session.commit()
        
        # Get updated draft with totals
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        
        if is_htmx:
            return render_template('sales/_cart_content_draft.html',
                                 draft=draft,
                                 totals=totals)
        
        flash('Producto agregado al carrito', 'success')
        return redirect(url_for('sales.new_sale'))
        
    except InsufficientStockError as e:
        db_session.rollback()
        current_app.logger.warning(f"Stock error in draft_add: {str(e)}")
        if is_htmx:
            try:
                 draft, totals = sale_draft_service.get_draft_with_totals(db_session, g.tenant_id, g.user_id)
            except:
                 draft, totals = None, None
            
            return render_template('sales/_cart_content_draft.html', 
                                 draft=draft, 
                                 totals=totals, 
                                 error_message=str(e)) # Show friendly error
        
        flash(str(e), 'warning')
        return redirect(url_for('sales.new_sale'))

    except ValueError as e:
        db_session.rollback()
        current_app.logger.warning(f"Validation error in draft_add: {str(e)}")
        if is_htmx:
            # Return current cart with error message at top (or as alert)
            # Fetch current state to not leave cart empty
            try:
                 draft, totals = sale_draft_service.get_draft_with_totals(db_session, g.tenant_id, g.user_id)
            except:
                 draft, totals = None, None
            
            # We can use a custom header to trigger a toast, but simplest is to return valid HTML with an alert
            # Using 200 status so HTMX swaps content normally
            return render_template('sales/_cart_content_draft.html', 
                                 draft=draft, 
                                 totals=totals, 
                                 error_message=str(e)) # Pass error to template
            
            # Alternative: return alert only if target handles it, but here we swap #cart-container
        
        flash(str(e), 'warning')
        return redirect(url_for('sales.new_sale'))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error in draft_add: {str(e)}", exc_info=True)
        
        if is_htmx:
             try:
                 draft, totals = sale_draft_service.get_draft_with_totals(db_session, g.tenant_id, g.user_id)
             except:
                 draft, totals = None, None
                 
             return render_template('sales/_cart_content_draft.html', 
                                  draft=draft, 
                                  totals=totals, 
                                  error_message=f"Error: {str(e)}") # Exposing error for diagnosis

        flash('Error al agregar producto', 'danger')
        return redirect(url_for('sales.new_sale'))


@sales_bp.route('/draft/update', methods=['POST'])
@require_login
@require_tenant
def draft_update() -> Union[str, Response]:
    """Update draft line quantity or discount (HTMX endpoint)."""
    db_session = get_session()
    
    try:
        product_id = int(request.form.get('product_id'))
        qty_str = request.form.get('qty', '').strip()
        discount_type = request.form.get('discount_type')
        discount_value_str = request.form.get('discount_value', '0').strip()
        
        # Get draft
        draft = sale_draft_service.get_or_create_draft(
            db_session, g.tenant_id, g.user_id
        )
        
        # Parse values safely
        try:
            qty = Decimal(qty_str) if qty_str and qty_str.strip() else None
            # If qty is None, treat as no change or invalid? Service handles None as 'no change', 
            # but for mandatory update we might want to check.
            # If user sends empty string, we should probably raise ValueError or revert.
            if qty_str is not None and not qty_str.strip():
                 raise ValueError("La cantidad no puede estar vacía")
        except decimal.InvalidOperation:
            raise ValueError("Cantidad inválida")
            
        discount_value = Decimal(discount_value_str) if discount_value_str else Decimal('0')
        
        # Validation strict based on UOM
        # 1. Get product to check UOM
        product = _get_product_or_error(db_session, product_id, g.tenant_id)
        if not product:
            raise NotFoundError('Producto no encontrado')
            
        # 2. Check if UOM allows decimals
        uom_name = product.uom.name.lower() if product.uom else ''
        divisible_keywords = ['kg', 'kilo', 'gram', 'mt', 'metro', 'longitud']
        is_divisible = any(kw in uom_name for kw in divisible_keywords)
        
        # 3. Sanitize Qty
        if qty is not None:
            if not is_divisible:
                # If not divisible, round to nearest integer
                # Example: 1.2 -> 1, 1.8 -> 2
                qty = qty.quantize(Decimal('1'), rounding=decimal.ROUND_HALF_UP)
        
        # Update line
        sale_draft_service.update_draft_line(
            db_session, draft.id, product_id,
            qty=qty,
            discount_type=discount_type if discount_type else None,
            discount_value=discount_value,
            tenant_id=g.tenant_id
        )
        
        db_session.commit()
        
        # Get updated totals
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        
        # Find the specific line that was updated to pass to the template
        # Note: product_id is an INT, line.product_id might be INT or STR depending on dict construction
        updated_line = next((l for l in totals['lines'] if l['product_id'] == product_id), None)
        
        if updated_line:
             return render_template('sales/_cart_update_response.html',
                                  line=updated_line,
                                  totals=totals)
        else:
             # Fallback if line disappeared (shouldn't happen on update unless qty=0, which might trigger remove)
             return render_template('sales/_cart_content_draft.html',
                                  draft=draft,
                                  totals=totals)
        
    except InsufficientStockError as e:
        db_session.rollback()
        # Re-render the row with the error message
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        
        # Locate the line
        error_line = next((l for l in totals['lines'] if l['product_id'] == product_id), None)
        
        if error_line:
             return render_template('sales/_cart_line.html',
                                  line=error_line,
                                  error_message=str(e),
                                  error_line_id=str(product_id))
        else:
             return render_template('sales/_cart_content_draft.html',
                                  draft=draft,
                                  totals=totals,
                                  error_message=str(e))

    except ValueError as e:
        db_session.rollback()
        # On error, we re-render the row with the error message
        # We need the current state of the draft to re-render the row properly
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        
        # Locate the line
        error_line = next((l for l in totals['lines'] if l['product_id'] == product_id), None)
        
        if error_line:
             # We assume product_id is available in scope (from try block)
             return render_template('sales/_cart_line.html',
                                  line=error_line,
                                  error_message=str(e),
                                  error_line_id=str(product_id))
        else:
             return render_template('sales/_cart_content_draft.html',
                                  draft=draft,
                                  totals=totals,
                                  error_message=str(e))

    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error in draft_update: {str(e)}", exc_info=True)
        # For generic errors, better to refresh the whole cart
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        return render_template('sales/_cart_content_draft.html',
                             draft=draft,
                             totals=totals,
                             error_message=f"Error al actualizar: {str(e)}")


@sales_bp.route('/draft/payment/update_cash', methods=['POST'])
@require_login
@require_tenant
def draft_payment_update_cash() -> Union[str, Response]:
    """Update cash amount manually and set override flag."""
    db_session = get_session()
    
    amount_str = request.form.get('amount_received_display')
    try:
        amount = Decimal(amount_str) if amount_str else Decimal('0')
    except InvalidOperation:
        amount = Decimal('0')
        
    session['cash_overridden'] = True
    session['cash_amount'] = str(amount) # Store as string for JSON serialization
    
    # Get current totals for calculation
    draft, totals = sale_draft_service.get_draft_with_totals(
        db_session, g.tenant_id, g.user_id
    )
    
    return render_template('sales/_cart_payment_updates.html', totals=totals)

@sales_bp.route('/draft/payment/reset_cash', methods=['POST'])
@require_login
@require_tenant
def draft_payment_reset_cash() -> Union[str, Response]:
    """Reset cash amount to match total and clear override flag."""
    db_session = get_session()
    
    session['cash_overridden'] = False
    session.pop('cash_amount', None)
    
    # Get current totals to re-sync
    draft, totals = sale_draft_service.get_draft_with_totals(
        db_session, g.tenant_id, g.user_id
    )
    
    return render_template('sales/_cart_content_draft.html',
                         draft=draft,
                         totals=totals)


@sales_bp.route('/draft/remove', methods=['POST'])
@require_login
@require_tenant
def draft_remove() -> Union[str, Response]:
    """Remove line from draft (HTMX endpoint)."""
    db_session = get_session()
    
    try:
        product_id = int(request.form.get('product_id'))
        
        # Get draft
        draft = sale_draft_service.get_or_create_draft(
            db_session, g.tenant_id, g.user_id
        )
        
        # Remove line
        sale_draft_service.remove_draft_line(
            db_session, draft.id, product_id, g.tenant_id
        )
        
        db_session.commit()
        flash('Producto eliminado del carrito', 'info')
        
        # Get updated totals
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        
        return render_template('sales/_cart_content_draft.html',
                             draft=draft,
                             totals=totals)
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error in draft_remove: {str(e)}", exc_info=True)
        flash('Error al eliminar producto', 'danger')
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        return render_template('sales/_cart_content_draft.html',
                             draft=draft,
                             totals=totals)


@sales_bp.route('/draft/clear', methods=['POST'])
@require_login
@require_tenant
def draft_clear() -> Union[str, Response]:
    """Clear all lines from draft (HTMX endpoint)."""
    db_session = get_session()
    
    try:
        # Get draft
        draft = sale_draft_service.get_or_create_draft(
            db_session, g.tenant_id, g.user_id
        )
        
        # Clear draft
        sale_draft_service.clear_draft(
            db_session, draft.id, g.tenant_id
        )
        
        db_session.commit()
        flash('Carrito vaciado', 'info')
        
        # Get updated totals (should be empty)
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        
        return render_template('sales/_cart_content_draft.html',
                             draft=draft,
                             totals=totals)
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error in draft_clear: {str(e)}", exc_info=True)
        flash('Error al vaciar carrito', 'danger')
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        return render_template('sales/_cart_content_draft.html',
                             draft=draft,
                             totals=totals)



        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error in draft_apply_discount: {str(e)}", exc_info=True)
        flash('Error al aplicar descuento', 'danger')
        draft, totals = sale_draft_service.get_draft_with_totals(
            db_session, g.tenant_id, g.user_id
        )
        return render_template('sales/_cart_content_draft.html',
                             draft=draft,
                             totals=totals)


# ============================================================================
# CONFIRM SALE WITH IDEMPOTENCY AND MIXED PAYMENTS
# ============================================================================

@sales_bp.route('/confirm_draft', methods=['POST'])
@require_login
@require_tenant
def confirm_draft() -> Union[str, Response]:
    """Confirm sale from draft with idempotency and mixed payments."""
    db_session = get_session()
    
    try:
        # Get idempotency key
        idempotency_key = request.form.get('idempotency_key', '').strip()
        
        if not idempotency_key:
            raise BusinessLogicError('Clave de idempotencia requerida')
        
        # ROBUSTEZ: Obtener draft con manejo de errores
        try:
            draft = sale_draft_service.get_or_create_draft(
                db_session, g.tenant_id, g.user_id
            )
        except Exception as draft_error:
            current_app.logger.error(f"Error getting draft in confirm_draft: {draft_error}", exc_info=True)
            raise BusinessLogicError('Error: Carrito no válido. Por favor, intente nuevamente.')
        
        if not draft or not draft.lines:
            raise BusinessLogicError('Error: El carrito está vacío')
        
        # Parse payments from form
        # Expected format: payments[0][method], payments[0][amount], etc.
        payments = []
        payment_index = 0
        
        while True:
            method_key = f'payments[{payment_index}][method]'
            amount_key = f'payments[{payment_index}][amount]'
            
            if method_key not in request.form:
                break
            
            method = request.form.get(method_key)
            amount = request.form.get(amount_key)
            
            if method and amount:
                payment = {
                    'method': method.upper(),
                    'amount': Decimal(str(amount))
                }
                
                # For CASH, get received amount and change
                if method.upper() == 'CASH':
                    received_key = f'payments[{payment_index}][amount_received]'
                    change_key = f'payments[{payment_index}][change_amount]'
                    
                    payment['amount_received'] = Decimal(str(request.form.get(received_key, amount)))
                    payment['change_amount'] = Decimal(str(request.form.get(change_key, '0')))
                
                payments.append(payment)
            
            payment_index += 1
        
        if not payments:
            raise BusinessLogicError('Debe especificar al menos un método de pago')
        
        # Get customer_id (optional)
        customer_id = request.form.get('customer_id')
        if customer_id:
            try:
                customer_id = int(customer_id)
            except ValueError:
                customer_id = None
        
        # Confirm sale
        sale_id = confirm_sale_from_draft(
            draft_id=draft.id,
            payments=payments,
            idempotency_key=idempotency_key,
            session=db_session,
            tenant_id=g.tenant_id,
            user_id=g.user_id,
            customer_id=customer_id
        )
        
        # ROBUSTEZ: Clear draft con manejo de errores (no crítico)
        try:
            sale_draft_service.clear_draft(
                session=db_session,
                draft_id=draft.id,
                tenant_id=g.tenant_id
            )
        except Exception as clear_error:
            current_app.logger.warning(f"Error clearing draft after confirmation: {clear_error}")
            # No propagar error, la venta ya fue confirmada
        
        db_session.commit()
        
        flash(f'Venta #{sale_id} confirmada exitosamente', 'success')
        
        # Redirect back to New Sale (POS) with clean slate
        # Logic: User wants to continue selling
        return redirect(url_for('sales.new_sale'))
        
    except (ValueError, BusinessLogicError) as e:
        db_session.rollback()
        raise BusinessLogicError(str(e))


# ============================================================================
# Delete Sale with Stock Reversal - TENANT-SCOPED
# ============================================================================

@sales_bp.route('/<int:sale_id>/delete/confirm', methods=['GET'])
@require_login
@require_tenant
def delete_sale_confirm_modal(sale_id: int) -> Union[str, Response]:
    """Load delete confirmation modal (HTMX endpoint, tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Validate sale exists and belongs to tenant
        sale = db_session.query(Sale).options(joinedload(Sale.lines)).filter(
            Sale.id == sale_id,
            Sale.tenant_id == g.tenant_id
        ).first()
        
        if not sale:
            raise NotFoundError('Venta no encontrada o no pertenece a su negocio')
        
        # Calculate total units to be restored
        total_units = sum(line.qty for line in sale.lines)
        
        # Get sale details
        sale_data = {
            'id': sale.id,
            'total': sale.total,
            'total_units': total_units,
            'line_count': len(sale.lines)
        }
        
        return render_template('sales/_delete_confirm_modal.html', sale=sale_data)
        
    except Exception as e:
        raise BusinessLogicError(f"No se pudo cargar el modal de confirmación: {str(e)}")



@sales_bp.route('/<int:sale_id>/delete', methods=['POST', 'DELETE'])
@require_login
@require_tenant
def delete_sale(sale_id: int) -> Union[str, Response]:
    """Delete sale and reverse stock (tenant-scoped, HTMX-compatible)."""
    db_session = get_session()
    
    try:
        from app.services.sale_delete_service import delete_sale_with_reversal
        
        # Delete sale with stock reversal
        result = delete_sale_with_reversal(sale_id, db_session, g.tenant_id)
        
        # Check if HTMX request
        is_htmx = request.headers.get('HX-Request') == 'true'
        
        if is_htmx:
            # Return success message for HTMX to display
            return f'''
                <div class="alert-custom alert-success">
                    <i class="alert-custom-icon bi bi-check-circle"></i>
                    <div class="alert-custom-content">
                        <strong>Éxito:</strong> {result['message']}
                    </div>
                </div>
            ''', 200
        else:
            flash(result['message'], 'success')
            return redirect(url_for('sales.list_sales'))
        
    except (ValueError, BusinessLogicError) as e:
        db_session.rollback()
        raise BusinessLogicError(str(e))
