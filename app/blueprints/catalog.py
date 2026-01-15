"""Catalog blueprint for products management - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, g, abort
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import os
from app.database import get_session
from app.models import Product, ProductStock, UOM, Category
from app.middleware import require_login, require_tenant

catalog_bp = Blueprint('catalog', __name__, url_prefix='/products')

# Allowed image extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}
MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB


def allowed_file(filename):
    """Check if file has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_product_image(file):
    """
    Save product image and return the filename.
    Returns None if no file or invalid file.
    """
    if not file or file.filename == '':
        return None
    
    if not allowed_file(file.filename):
        flash('Formato de imagen no permitido. Use JPG, JPEG o PNG', 'danger')
        return None
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_size > MAX_FILE_SIZE:
        flash('La imagen es demasiado grande. Máximo 2MB', 'danger')
        return None
    
    # Generate secure filename
    filename = secure_filename(file.filename)
    # Add timestamp to avoid collisions
    import time
    filename = f"{int(time.time())}_{filename}"
    
    # Save file
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'products')
    os.makedirs(upload_folder, exist_ok=True)
    filepath = os.path.join(upload_folder, filename)
    file.save(filepath)
    
    return filename


@catalog_bp.route('/')
@require_login
@require_tenant
def list_products():
    """List all products with stock information (tenant-scoped)."""
    session = get_session()
    
    try:
        # Get search and filter parameters
        search_query = request.args.get('q', '').strip()
        category_id = request.args.get('category_id', '').strip()
        stock_filter = request.args.get('stock_filter', '').strip()
        
        # Get all categories for the filter dropdown (tenant-scoped)
        categories = session.query(Category).filter(
            Category.tenant_id == g.tenant_id
        ).order_by(Category.name).all()
        
        # Build query with left join to product_stock (tenant-scoped)
        query = session.query(Product).outerjoin(ProductStock).filter(
            Product.tenant_id == g.tenant_id
        )
        
        # Apply category filter if provided
        category_filter_applied = False
        if category_id:
            try:
                category_id_int = int(category_id)
                # Verify category exists in current tenant
                category_exists = session.query(Category).filter(
                    Category.id == category_id_int,
                    Category.tenant_id == g.tenant_id
                ).first()
                if category_exists:
                    query = query.filter(Product.category_id == category_id_int)
                    category_filter_applied = True
                else:
                    flash('La categoría seleccionada no existe. Mostrando todos los productos.', 'warning')
                    category_id = ''
            except ValueError:
                flash('ID de categoría inválido. Mostrando todos los productos.', 'warning')
                category_id = ''
        
        # Apply search filter if provided
        if search_query:
            search_filter = or_(
                func.lower(Product.name).like(f'%{search_query.lower()}%'),
                func.lower(Product.sku).like(f'%{search_query.lower()}%'),
                func.lower(Product.barcode).like(f'%{search_query.lower()}%')
            )
            query = query.filter(search_filter)
        
        # Apply stock filter if provided
        if stock_filter:
            if stock_filter == 'out':
                query = query.filter(
                    func.coalesce(ProductStock.on_hand_qty, 0) <= 0
                )
            elif stock_filter == 'low':
                query = query.filter(
                    func.coalesce(ProductStock.on_hand_qty, 0) > 0,
                    func.coalesce(Product.min_stock_qty, 0) > 0,
                    func.coalesce(ProductStock.on_hand_qty, 0) <= func.coalesce(Product.min_stock_qty, 0)
                )
            elif stock_filter not in ['', 'out', 'low']:
                flash('Filtro de stock inválido. Mostrando todos los productos.', 'info')
                stock_filter = ''
        
        # Order by name
        products = query.order_by(Product.name).all()
        
        # Check if request is from HTMX (live search)
        is_htmx = request.headers.get('HX-Request') == 'true'
        
        template = 'products/_list_table.html' if is_htmx else 'products/list.html'
        
        return render_template(template, 
                             products=products, 
                             search_query=search_query,
                             categories=categories,
                             selected_category_id=category_id,
                             selected_stock_filter=stock_filter)
        
    except Exception as e:
        session.rollback()
        flash(f'Error al cargar productos: {str(e)}', 'danger')
        
        try:
            categories = session.query(Category).filter(
                Category.tenant_id == g.tenant_id
            ).order_by(Category.name).all()
        except Exception:
            session.rollback()
            categories = []
        
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'products/_list_table.html' if is_htmx else 'products/list.html'
        
        return render_template(template, 
                             products=[], 
                             search_query='',
                             categories=categories,
                             selected_category_id='',
                             selected_stock_filter='')


@catalog_bp.route('/new', methods=['GET'])
@require_login
@require_tenant
def new_product():
    """Show form to create a new product (tenant-scoped)."""
    session = get_session()
    
    try:
        # Check if UOM table has data for this tenant
        uom_count = session.query(UOM).filter(
            UOM.tenant_id == g.tenant_id
        ).count()
        if uom_count == 0:
            flash('No hay unidades de medida registradas. Debe crear al menos una unidad de medida antes de poder crear productos.', 'warning')
            return redirect(url_for('settings.list_uoms'))
        
        # Get UOMs and categories for this tenant
        uoms = session.query(UOM).filter(
            UOM.tenant_id == g.tenant_id
        ).order_by(UOM.name).all()
        
        categories = session.query(Category).filter(
            Category.tenant_id == g.tenant_id
        ).order_by(Category.name).all()
        
        return render_template('products/form.html', 
                             product=None, 
                             uoms=uoms, 
                             categories=categories,
                             action='new')
        
    except Exception as e:
        flash(f'Error al cargar formulario: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@catalog_bp.route('/new', methods=['POST'])
@require_login
@require_tenant
def create_product():
    """Create a new product (tenant-scoped)."""
    session = get_session()
    
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        sku = request.form.get('sku', '').strip() or None
        barcode = request.form.get('barcode', '').strip() or None
        category_id = request.form.get('category_id', '').strip() or None
        uom_id = request.form.get('uom_id', '').strip()
        sale_price = request.form.get('sale_price', '0').strip()
        min_stock_qty = request.form.get('min_stock_qty', '0').strip()
        active = request.form.get('active') == 'on'
        
        # Server-side validations
        errors = []
        
        if not name:
            errors.append('El nombre es requerido')
        
        if not uom_id:
            errors.append('La unidad de medida es requerida')
        else:
            # Verify UOM exists in current tenant
            uom = session.query(UOM).filter(
                UOM.id == int(uom_id),
                UOM.tenant_id == g.tenant_id
            ).first()
            if not uom:
                errors.append('La unidad de medida seleccionada no existe o no pertenece a su negocio')
        
        # Verify category belongs to tenant if provided
        if category_id:
            category = session.query(Category).filter(
                Category.id == int(category_id),
                Category.tenant_id == g.tenant_id
            ).first()
            if not category:
                errors.append('La categoría seleccionada no existe o no pertenece a su negocio')
        
        try:
            sale_price_decimal = float(sale_price)
            if sale_price_decimal < 0:
                errors.append('El precio de venta debe ser mayor o igual a 0')
        except ValueError:
            errors.append('El precio de venta debe ser un número válido')
        
        try:
            min_stock_qty_decimal = float(min_stock_qty) if min_stock_qty else 0
            if min_stock_qty_decimal < 0:
                errors.append('El stock mínimo debe ser mayor o igual a 0')
        except ValueError:
            errors.append('El stock mínimo debe ser un número válido')
            min_stock_qty_decimal = 0
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            uoms = session.query(UOM).filter(UOM.tenant_id == g.tenant_id).order_by(UOM.name).all()
            categories = session.query(Category).filter(Category.tenant_id == g.tenant_id).order_by(Category.name).all()
            return render_template('products/form.html',
                                 product=None,
                                 uoms=uoms,
                                 categories=categories,
                                 action='new')
        
        # Handle image upload
        image_filename = None
        if 'image' in request.files:
            image_file = request.files['image']
            image_filename = save_product_image(image_file)
        
        # Create product with tenant_id
        product = Product(
            tenant_id=g.tenant_id,  # Critical: assign tenant
            name=name,
            sku=sku,
            barcode=barcode,
            category_id=int(category_id) if category_id else None,
            uom_id=int(uom_id),
            sale_price=sale_price_decimal,
            active=active,
            image_path=image_filename,
            min_stock_qty=min_stock_qty_decimal
        )
        
        session.add(product)
        session.commit()
        
        flash(f'Producto "{product.name}" creado exitosamente', 'success')
        return redirect(url_for('catalog.list_products'))
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        
        if 'unique' in error_msg.lower():
            if 'sku' in error_msg.lower():
                flash(f'El SKU "{sku}" ya está en uso en su negocio. Por favor, use otro SKU.', 'danger')
            elif 'barcode' in error_msg.lower():
                flash(f'El código de barras "{barcode}" ya está en uso en su negocio. Por favor, use otro código.', 'danger')
            else:
                flash('Ya existe un producto con estos datos únicos en su negocio.', 'danger')
        else:
            flash(f'Error de integridad al crear producto: {error_msg}', 'danger')
        
        uoms = session.query(UOM).filter(UOM.tenant_id == g.tenant_id).order_by(UOM.name).all()
        categories = session.query(Category).filter(Category.tenant_id == g.tenant_id).order_by(Category.name).all()
        return render_template('products/form.html',
                             product=None,
                             uoms=uoms,
                             categories=categories,
                             action='new')
        
    except Exception as e:
        session.rollback()
        flash(f'Error al crear producto: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@catalog_bp.route('/<int:product_id>/edit', methods=['GET'])
@require_login
@require_tenant
def edit_product(product_id):
    """Show form to edit a product (tenant-scoped)."""
    session = get_session()
    
    try:
        # Get product and verify it belongs to current tenant
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            abort(404)
        
        uoms = session.query(UOM).filter(
            UOM.tenant_id == g.tenant_id
        ).order_by(UOM.name).all()
        
        categories = session.query(Category).filter(
            Category.tenant_id == g.tenant_id
        ).order_by(Category.name).all()
        
        return render_template('products/form.html',
                             product=product,
                             uoms=uoms,
                             categories=categories,
                             action='edit')
        
    except Exception as e:
        flash(f'Error al cargar producto: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@catalog_bp.route('/<int:product_id>/edit', methods=['POST'])
@require_login
@require_tenant
def update_product(product_id):
    """Update a product (tenant-scoped)."""
    session = get_session()
    
    try:
        # Get product and verify tenant
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            abort(404)
        
        # Get form data
        name = request.form.get('name', '').strip()
        sku = request.form.get('sku', '').strip() or None
        barcode = request.form.get('barcode', '').strip() or None
        category_id = request.form.get('category_id', '').strip() or None
        uom_id = request.form.get('uom_id', '').strip()
        sale_price = request.form.get('sale_price', '0').strip()
        min_stock_qty = request.form.get('min_stock_qty', '0').strip()
        active = request.form.get('active') == 'on'
        
        # Server-side validations
        errors = []
        
        if not name:
            errors.append('El nombre es requerido')
        
        if not uom_id:
            errors.append('La unidad de medida es requerida')
        else:
            uom = session.query(UOM).filter(
                UOM.id == int(uom_id),
                UOM.tenant_id == g.tenant_id
            ).first()
            if not uom:
                errors.append('La unidad de medida seleccionada no existe o no pertenece a su negocio')
        
        if category_id:
            category = session.query(Category).filter(
                Category.id == int(category_id),
                Category.tenant_id == g.tenant_id
            ).first()
            if not category:
                errors.append('La categoría seleccionada no existe o no pertenece a su negocio')
        
        try:
            sale_price_decimal = float(sale_price)
            if sale_price_decimal < 0:
                errors.append('El precio de venta debe ser mayor o igual a 0')
        except ValueError:
            errors.append('El precio de venta debe ser un número válido')
        
        try:
            min_stock_qty_decimal = float(min_stock_qty) if min_stock_qty else 0
            if min_stock_qty_decimal < 0:
                errors.append('El stock mínimo debe ser mayor o igual a 0')
        except ValueError:
            errors.append('El stock mínimo debe ser un número válido')
            min_stock_qty_decimal = 0
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            uoms = session.query(UOM).filter(UOM.tenant_id == g.tenant_id).order_by(UOM.name).all()
            categories = session.query(Category).filter(Category.tenant_id == g.tenant_id).order_by(Category.name).all()
            return render_template('products/form.html',
                                 product=product,
                                 uoms=uoms,
                                 categories=categories,
                                 action='edit')
        
        # Handle image upload
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename != '':
                # Delete old image if exists
                if product.image_path:
                    old_image_path = os.path.join(current_app.root_path, 'static', 'uploads', 'products', product.image_path)
                    if os.path.exists(old_image_path):
                        try:
                            os.remove(old_image_path)
                        except Exception:
                            pass
                
                # Save new image
                image_filename = save_product_image(image_file)
                if image_filename:
                    product.image_path = image_filename
        
        # Update product
        product.name = name
        product.sku = sku
        product.barcode = barcode
        product.category_id = int(category_id) if category_id else None
        product.uom_id = int(uom_id)
        product.sale_price = sale_price_decimal
        product.min_stock_qty = min_stock_qty_decimal
        product.active = active
        
        session.commit()
        
        flash(f'Producto "{product.name}" actualizado exitosamente', 'success')
        return redirect(url_for('catalog.list_products'))
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig)
        
        if 'unique' in error_msg.lower():
            if 'sku' in error_msg.lower():
                flash(f'El SKU "{sku}" ya está en uso en su negocio. Por favor, use otro SKU.', 'danger')
            elif 'barcode' in error_msg.lower():
                flash(f'El código de barras "{barcode}" ya está en uso en su negocio. Por favor, use otro código.', 'danger')
            else:
                flash('Ya existe un producto con estos datos únicos en su negocio.', 'danger')
        else:
            flash(f'Error de integridad al actualizar producto: {error_msg}', 'danger')
        
        uoms = session.query(UOM).filter(UOM.tenant_id == g.tenant_id).order_by(UOM.name).all()
        categories = session.query(Category).filter(Category.tenant_id == g.tenant_id).order_by(Category.name).all()
        return render_template('products/form.html',
                             product=product,
                             uoms=uoms,
                             categories=categories,
                             action='edit')
        
    except Exception as e:
        session.rollback()
        flash(f'Error al actualizar producto: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@catalog_bp.route('/<int:product_id>/toggle-active', methods=['POST'])
@require_login
@require_tenant
def toggle_active(product_id):
    """Toggle product active status (tenant-scoped)."""
    session = get_session()
    
    try:
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            abort(404)
        
        product.active = not product.active
        session.commit()
        
        status = 'activado' if product.active else 'desactivado'
        flash(f'Producto "{product.name}" {status} exitosamente', 'success')
        
        return redirect(url_for('catalog.list_products'))
        
    except Exception as e:
        session.rollback()
        flash(f'Error al cambiar estado: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@catalog_bp.route('/<int:product_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_product(product_id):
    """
    Delete a product permanently (tenant-scoped).
    
    This operation will fail if the product has associated lines.
    In those cases, the user should deactivate instead.
    """
    session = get_session()
    
    try:
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            abort(404)
        
        product_name = product.name
        image_path = product.image_path
        
        try:
            session.delete(product)
            session.commit()
            
            # Delete image file if exists
            if image_path:
                try:
                    image_full_path = os.path.join(
                        current_app.root_path, 
                        'static', 
                        'uploads', 
                        'products', 
                        image_path
                    )
                    if os.path.exists(image_full_path):
                        os.remove(image_full_path)
                except Exception as img_err:
                    current_app.logger.warning(f"Failed to delete image {image_path}: {img_err}")
            
            flash(f'Producto "{product_name}" eliminado exitosamente', 'success')
            return redirect(url_for('catalog.list_products'))
            
        except IntegrityError:
            session.rollback()
            flash(
                f'No se puede eliminar el producto "{product_name}" porque tiene '
                'movimientos, ventas o compras asociadas. '
                'Use la opción "Desactivar" en su lugar.',
                'warning'
            )
            return redirect(url_for('catalog.list_products'))
        
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error deleting product {product_id}: {e}")
        flash(f'Error al eliminar producto: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))
