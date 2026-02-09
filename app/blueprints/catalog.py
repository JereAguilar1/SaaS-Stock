"""Catalog blueprint for products management - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, g, abort
from sqlalchemy import or_, func, select
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
import time
from io import BytesIO
from PIL import Image
import requests
from app.database import get_session
from app.models import Product, ProductStock, UOM, Category, ProductFeature, StockMove, StockMoveLine, StockMoveType, StockReferenceType
from app.middleware import require_login, require_tenant
from app.services.storage_service import get_storage_service
from app.services.cache_service import get_cache

catalog_bp = Blueprint('catalog', __name__, url_prefix='/products')


def invalidate_products_cache(tenant_id: int):
    """Invalidate all products cache for a tenant (PASO 8)."""
    try:
        cache = get_cache()
        cache.invalidate_module(tenant_id, 'products')
    except Exception:
        pass  # Graceful degradation


def invalidate_categories_cache(tenant_id: int):
    """Invalidate categories cache for a tenant (PASO 8)."""
    try:
        cache = get_cache()
        cache.invalidate_module(tenant_id, 'categories')
    except Exception:
        pass


def save_product_image(file, tenant_id: int):
    """
    Upload product image to S3-compatible storage (MinIO/S3).
    
    Args:
        file: Werkzeug FileStorage object
        tenant_id: Tenant ID for organizing uploads
    
    Returns:
        Full public URL if successful, None if failed
    
    Note:
        This function is now stateless - no local filesystem dependencies.
        Compatible with horizontal scaling and multiple Flask instances.
    """
    if not file or file.filename == '':
        return None
    
    try:
        # Generate secure object name (S3 key)
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        object_name = f"products/tenant_{tenant_id}/{timestamp}_{filename}"
        
        # Upload to S3-compatible storage
        storage = get_storage_service()
        url = storage.upload_file(
            file=file,
            object_name=object_name,
            content_type=file.content_type
        )
        
        return url
        
    except ValueError as e:
        # Validation errors (size, type)
        flash(str(e), 'danger')
        return None
    except Exception as e:
        flash(f'Error al subir imagen: {str(e)}', 'danger')
        return None


def delete_product_image(image_url: str):
    """
    Delete product image from S3-compatible storage.
    
    Args:
        image_url: Full public URL or object name
    
    Returns:
        True if deleted successfully, False otherwise
    """
    if not image_url:
        return False
    
    try:
        # Extract object name from URL
        # URL format: http://localhost:9000/uploads/products/tenant_1/123_image.jpg
        # Object name: products/tenant_1/123_image.jpg
        storage = get_storage_service()
        bucket = current_app.config['S3_BUCKET']
        
        if f"/{bucket}/" in image_url:
            object_name = image_url.split(f"/{bucket}/", 1)[1]
        else:
            object_name = image_url  # Assume it's already an object name
        
        return storage.delete_file(object_name)
        
    except Exception:
        return False


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


@catalog_bp.route('/<int:product_id>/detalle', methods=['GET'])
@require_login
@require_tenant
def product_detail(product_id):
    """Show product detail page (tenant-scoped)."""
    session = get_session()
    
    try:
        # Get product and verify it belongs to current tenant
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            abort(404)
        
        return render_template('products/detail.html', product=product)
        
    except Exception as e:
        flash(f'Error al cargar detalle del producto: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))



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
        
        # NORMALIZACIÓN SKU: Convertir "none" o vacío a NULL
        sku_raw = request.form.get('sku', '').strip()
        if sku_raw.lower() == 'none' or sku_raw == '':
            sku = None
        else:
            sku = sku_raw
        
        # NORMALIZACIÓN BARCODE: Convertir "none" o vacío a NULL
        barcode_raw = request.form.get('barcode', '').strip()
        if barcode_raw.lower() == 'none' or barcode_raw == '':
            barcode = None
        else:
            barcode = barcode_raw
        
        category_id = request.form.get('category_id', '').strip() or None
        uom_id = request.form.get('uom_id', '').strip()
        
        # SANITIZER: Limpiar precio de formato local (1.000,00 -> 1000.00)
        # Algoritmo estricto:
        # 1. Obtener valor como string
        # 2. Eliminar TODOS los puntos (separadores de miles)
        # 3. Reemplazar coma por punto (separador decimal)
        raw_price = request.form.get('sale_price', '0')
        # Forzar a string por seguridad
        raw_price = str(raw_price).strip()
        # Paso 1: Eliminar puntos de miles (20.000 -> 20000)
        clean_price = raw_price.replace('.', '')
        # Paso 2: Normalizar decimal (20000,50 -> 20000.50)
        clean_price = clean_price.replace(',', '.')
        sale_price = clean_price
        
        # SANITIZER: Limpiar costo de formato local
        raw_cost = request.form.get('cost', '0')
        raw_cost = str(raw_cost).strip()
        clean_cost = raw_cost.replace('.', '').replace(',', '.')
        cost = clean_cost
        
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
        
        # Validación de precio
        try:
            sale_price_decimal = float(sale_price)
            if sale_price_decimal < 0:
                errors.append('El precio de venta debe ser mayor o igual a 0')
        except (ValueError, TypeError):
            errors.append(f'El precio de venta debe ser un número válido. Valor recibido: "{raw_price}"')
        
        # Validación de costo
        try:
            cost_decimal = float(cost)
            if cost_decimal < 0:
                errors.append('El costo debe ser mayor o igual a 0')
        except (ValueError, TypeError):
            errors.append(f'El costo debe ser un número válido. Valor recibido: "{raw_cost}"')
        
        try:
            # Parse as integer (floor if decimal provided)
            min_stock_qty_val = float(min_stock_qty) if min_stock_qty else 0
            min_stock_qty_int = int(min_stock_qty_val)
            if min_stock_qty_int < 0:
                errors.append('El stock mínimo debe ser mayor o igual a 0')
        except ValueError:
            errors.append('El stock mínimo debe ser un número válido')
            min_stock_qty_int = 0
        
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
        
        # Handle image upload (S3/MinIO)
        image_url = None
        if 'image' in request.files:
            image_file = request.files['image']
            image_url = save_product_image(image_file, g.tenant_id)
        
        # Create product with tenant_id
        product = Product(
            tenant_id=g.tenant_id,  # Critical: assign tenant
            name=name,
            sku=sku,
            barcode=barcode,
            category_id=int(category_id) if category_id else None,
            uom_id=int(uom_id),
            sale_price=sale_price_decimal,
            cost=cost_decimal,
            active=active,
            image_path=image_url,
            image_original_path=image_url,  # Save original reference
            min_stock_qty=min_stock_qty_int
        )
        
        session.add(product)
        session.flush()  # To get product.id
        
        # PERSIST FEATURES
        for feat in request.form:
            if feat.startswith('features[') and feat.endswith('][title]'):
                idx = feat.split('[')[1].split(']')[0]
                title = request.form.get(f'features[{idx}][title]', '').strip()
                description = request.form.get(f'features[{idx}][description]', '').strip()
                if title and description:
                    new_feature = ProductFeature(
                        tenant_id=g.tenant_id,
                        product_id=product.id,
                        title=title,
                        description=description
                    )
                    session.add(new_feature)

        session.commit()
        
        # PASO 8: Invalidate products cache
        invalidate_products_cache(g.tenant_id)
        
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
        
        # NORMALIZACIÓN SKU: Convertir "none" o vacío a NULL
        sku_raw = request.form.get('sku', '').strip()
        if sku_raw.lower() == 'none' or sku_raw == '':
            sku = None
        else:
            sku = sku_raw
        
        # NORMALIZACIÓN BARCODE: Convertir "none" o vacío a NULL
        barcode_raw = request.form.get('barcode', '').strip()
        if barcode_raw.lower() == 'none' or barcode_raw == '':
            barcode = None
        else:
            barcode = barcode_raw
        
        category_id = request.form.get('category_id', '').strip() or None
        uom_id = request.form.get('uom_id', '').strip()
        
        # SANITIZER: Limpiar precio de formato local (1.000,00 -> 1000.00)
        # Algoritmo estricto:
        # 1. Obtener valor como string
        # 2. Eliminar TODOS los puntos (separadores de miles)
        # 3. Reemplazar coma por punto (separador decimal)
        raw_price = request.form.get('sale_price', '0')
        # Forzar a string por seguridad
        raw_price = str(raw_price).strip()
        # Paso 1: Eliminar puntos de miles (20.000 -> 20000)
        clean_price = raw_price.replace('.', '')
        # Paso 2: Normalizar decimal (20000,50 -> 20000.50)
        clean_price = clean_price.replace(',', '.')
        sale_price = clean_price
        
        # SANITIZER: Limpiar costo de formato local
        raw_cost = request.form.get('cost', '0')
        raw_cost = str(raw_cost).strip()
        clean_cost = raw_cost.replace('.', '').replace(',', '.')
        cost = clean_cost
        
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
        
        # Validación de precio
        try:
            sale_price_decimal = float(sale_price)
            if sale_price_decimal < 0:
                errors.append('El precio de venta debe ser mayor o igual a 0')
        except (ValueError, TypeError):
            errors.append(f'El precio de venta debe ser un número válido. Valor recibido: "{raw_price}"')
        
        # Validación de costo
        try:
            cost_decimal = float(cost)
            if cost_decimal < 0:
                errors.append('El costo debe ser mayor o igual a 0')
        except (ValueError, TypeError):
            errors.append(f'El costo debe ser un número válido. Valor recibido: "{raw_cost}"')
        
        try:
            min_stock_qty_val = float(min_stock_qty) if min_stock_qty else 0
            min_stock_qty_int = int(min_stock_qty_val)
            if min_stock_qty_int < 0:
                errors.append('El stock mínimo debe ser mayor o igual a 0')
        except ValueError:
            errors.append('El stock mínimo debe ser un número válido')
            min_stock_qty_int = 0
        
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
        
        # Handle image upload (S3/MinIO)
        if 'image' in request.files:
            image_file = request.files['image']
            if image_file and image_file.filename != '':
                # Delete old image from S3 if exists
                if product.image_path:
                    delete_product_image(product.image_path)
                
                # Also delete original if it's different
                if product.image_original_path and product.image_original_path != product.image_path:
                    delete_product_image(product.image_original_path)
                
                # Upload new image to S3
                image_url = save_product_image(image_file, g.tenant_id)
                if image_url:
                    product.image_path = image_url
                    product.image_original_path = image_url # Update original as well
        
        # Update product
        product.name = name
        product.sku = sku
        product.barcode = barcode
        product.category_id = int(category_id) if category_id else None
        product.uom_id = int(uom_id)
        product.sale_price = sale_price_decimal
        product.cost = cost_decimal
        product.min_stock_qty = min_stock_qty_int
        product.active = active

        # STOCK ADJUSTMENT (Refactored)
        # Check if stock changed
        new_on_hand_qty_str = request.form.get('on_hand_qty', '').strip()
        if new_on_hand_qty_str:
            try:
                # SANITIZER: Clean stock format (1.000,00 -> 1000.00)
                clean_qty = new_on_hand_qty_str.replace('.', '').replace(',', '.')
                new_on_hand_qty = float(clean_qty)

                if new_on_hand_qty >= 0:
                    current_qty = product.on_hand_qty
                    delta = new_on_hand_qty - float(current_qty)
                    
                    if abs(delta) > 0.001:
                        # Create Stock Move
                        stock_move = StockMove(
                            tenant_id=g.tenant_id,
                            type=StockMoveType.ADJUST,
                            reference_type=StockReferenceType.MANUAL,
                            notes=f"Edición directa desde formulario de producto (Usuario: {g.user.email if g.user else 'Unknown'})"
                        )
                        session.add(stock_move)
                        session.flush()
                        
                        # Create Move Line
                        move_line = StockMoveLine(
                            stock_move_id=stock_move.id,
                            product_id=product.id,
                            qty=delta,
                            uom_id=product.uom_id
                        )
                        session.add(move_line)
                        
                        # Update ProductStock (if exists) or Product field logic
                        # Checking if ProductStock entity is used or if we need to update it
                        product_stock = session.query(ProductStock).filter(ProductStock.product_id == product.id).first()
                        if not product_stock:
                            product_stock = ProductStock(product_id=product.id, on_hand_qty=0)
                            session.add(product_stock)
                        
                        product_stock.on_hand_qty = new_on_hand_qty
                        # Note: product.on_hand_qty is a proxy/property usually, but if it's not we might need to refresh
                else:
                    flash('El stock no puede ser negativo. Se ignoró el cambio de stock.', 'warning')
            except ValueError:
                flash('Valor de stock inválido. Se ignoró el cambio de stock.', 'warning')
        
        # PERSIST FEATURES (Clear and Recreate)
        product.features = [] # Cascade delete-orphan will handle deletions
        for feat in request.form:
            if feat.startswith('features[') and feat.endswith('][title]'):
                idx = feat.split('[')[1].split(']')[0]
                title = request.form.get(f'features[{idx}][title]', '').strip()
                description = request.form.get(f'features[{idx}][description]', '').strip()
                if title and description:
                    new_feature = ProductFeature(
                        tenant_id=g.tenant_id,
                        product_id=product.id,
                        title=title,
                        description=description
                    )
                    session.add(new_feature)

        session.commit()
        
        # PASO 8: Invalidate products cache
        invalidate_products_cache(g.tenant_id)
        
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
            # FIX: Check for StockMoveLine dependencies
            # If exists, check if they are all from MANUAL/ADJUST stock moves
            # If so, we can safely delete the lines first.
            # If any is from SALE/INVOICE, we block.
            
            stmt = select(StockMoveLine).filter(StockMoveLine.product_id == product_id)
            lines = session.execute(stmt).scalars().all()
            
            if lines:
                # Check parents
                for line in lines:
                    # Lazy loading might trigger here, better to join if performance critical
                    # but for deletion of single product it's fine.
                    move = line.stock_move
                    if move.reference_type not in (StockReferenceType.MANUAL,): 
                        # If we had other safe types like 'INITIAL', add them here.
                        # Block if SALE or INVOICE
                        raise IntegrityError("Has commercial history", params=None, orig=None)
                
                # All lines are safe to delete (Manual adjustments)
                # We delete the lines. The StockMove parent might be left empty or deleted?
                # Usually StockMove is the header. If we delete the line, the header 
                # might stay if it has other lines, or become empty.
                # For this fix, we just delete the lines associated with this product.
                for line in lines:
                    session.delete(line)
                
                session.flush()

            session.delete(product)
            session.commit()
            
            # Delete image file from storage if exists
            if image_path:
                try:
                    # Use the helper function which handles S3/MinIO deletion
                    delete_product_image(image_path)
                except Exception as img_err:
                    current_app.logger.warning(f"Failed to delete image {image_path}: {img_err}")
            
            # PASO 8: Invalidate products cache
            invalidate_products_cache(g.tenant_id)
            
            flash(f'Producto "{product_name}" eliminado exitosamente', 'success')
            return redirect(url_for('catalog.list_products'))
            
        except IntegrityError:
            session.rollback()
            flash(
                f'No se puede eliminar el producto "{product_name}" porque tiene '
                'ventas o compras asociadas. '
                'Use la opción "Desactivar" en su lugar.',
                'warning'
            )
            return redirect(url_for('catalog.list_products'))
        
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error deleting product {product_id}: {e}")
        flash(f'Error al eliminar producto: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@catalog_bp.route('/check-sku', methods=['POST'])
@require_login
@require_tenant
def check_sku():
    """Check if SKU is unique (HTMX endpoint, tenant-scoped)."""
    session = get_session()
    
    try:
        sku = request.form.get('sku', '').strip()
        product_id_str = request.form.get('product_id', '').strip()
        
        if not sku:
            return '<div id="sku-error-container"></div>'
            
        # Check uniqueness
        query = session.query(Product).filter(
            Product.tenant_id == g.tenant_id,
            Product.sku == sku
        )
        
        # If editing, exclude current product
        if product_id_str:
            try:
                product_id = int(product_id_str)
                query = query.filter(Product.id != product_id)
            except ValueError:
                pass
                
        existing_product = query.first()
        
        if existing_product:
            return f'''
            <div id="sku-error-container" class="text-danger small mt-1">
                <i class="bi bi-exclamation-circle"></i> El SKU "{sku}" ya está en uso por "{existing_product.name}".
            </div>
            '''
        
        return '<div id="sku-error-container" class="text-success small mt-1"><i class="bi bi-check-circle"></i> SKU disponible</div>'
        
    except Exception as e:
        current_app.logger.error(f"Error checking SKU: {e}")
        return '<div id="sku-error-container"></div>'


@catalog_bp.route('/<int:product_id>/crop', methods=['POST'])
@require_login
@require_tenant
def crop_product_image(product_id):
    """
    Crop product image using server-side processing (Pillow).
    Always crops from the ORIGINAL image to preserve quality/context.
    """
    session = get_session()
    storage = get_storage_service()
    
    try:
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            return {'error': 'Producto no encontrado'}, 404
            
        # 1. Resolve source image (ORIGINAL)
        source_key = product.image_original_path
        if not source_key:
            # Fallback for legacy data: use current image as original
            source_key = product.image_path
            if source_key:
                product.image_original_path = source_key # Backfill
                session.commit()
            else:
                return {'error': 'El producto no tiene imagen para recortar'}, 400
                
        # 2. Get crop parameters
        try:
            x = float(request.form.get('x'))
            y = float(request.form.get('y'))
            width = float(request.form.get('width'))
            height = float(request.form.get('height'))
        except (TypeError, ValueError):
            return {'error': 'Parámetros de recorte inválidos'}, 400

        # 3. Download original image from S3
        try:
            # We need to get the file content. 
            # StorageService uses boto3 client. Let's use get_object.
            s3_response = storage.client.get_object(Bucket=storage.bucket, Key=source_key)
            file_stream = BytesIO(s3_response['Body'].read())
        except Exception as e:
            current_app.logger.error(f"Error downloading original image: {e}")
            return {'error': 'No se pudo acceder a la imagen original'}, 500

        # 4. Process with Pillow
        try:
            img = Image.open(file_stream)
            
            # Crop
            # The coordinates from frontend (Cropper.js) are relative to natural dimensions 
            # if we configured it correctly, otherwise we might need to scale.
            # Assuming frontend sends natural dimensions or we trust the values.
            box = (x, y, x + width, y + height)
            cropped_img = img.crop(box)
            
            # Save to buffer
            output_buffer = BytesIO()
            # Preserve format if possible, default to JPEG
            format = img.format or 'JPEG'
            if format == 'PNG':
                 cropped_img.save(output_buffer, format='PNG')
                 content_type = 'image/png'
                 extension = '.png'
            else:
                 cropped_img = cropped_img.convert('RGB')
                 cropped_img.save(output_buffer, format='JPEG', quality=90)
                 content_type = 'image/jpeg'
                 extension = '.jpg'
                 
            output_buffer.seek(0)
            
            # Create a FileStorage-like object or modify StorageService to accept stream
            # StorageService expects FileStorage. Let's wrap it.
            from werkzeug.datastructures import FileStorage
            timestamp = int(time.time())
            filename = f"crop_{timestamp}{extension}"
            
            new_file = FileStorage(
                stream=output_buffer,
                filename=filename,
                content_type=content_type,
            )
            
        except Exception as e:
            current_app.logger.error(f"Error processing image with Pillow: {e}")
            return {'error': 'Error al procesar el recorte de imagen'}, 500

        # 5. Upload new cropped image
        # We don't overwrite the original! We create a new file.
        # If there was a previous *cropped* image (different from original), we should delete it?
        # Yes, to avoid orphans.
        old_cropped_key = product.image_path
        if old_cropped_key and old_cropped_key != product.image_original_path:
             delete_product_image(old_cropped_key)

        new_image_key = save_product_image(new_file, g.tenant_id)
        
        if not new_image_key:
             return {'error': 'Error al guardar la imagen recortada'}, 500
             
        # 6. Update Product
        product.image_path = new_image_key
        session.commit()
        
        # 7. Invalidate cache
        invalidate_products_cache(g.tenant_id)
        
        return {
            'success': True, 
            'image_url': product.image_url,
            'message': 'Imagen recortada exitosamente'
        }
        
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error in crop_product_image: {e}")
        return {'error': str(e)}, 500


@catalog_bp.route('/<int:product_id>/restore-image', methods=['POST'])
@require_login
@require_tenant
def restore_product_image(product_id):
    """Restore the product image to its original uploaded version."""
    session = get_session()
    
    try:
        product = session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == g.tenant_id
        ).first()
        
        if not product:
            return {'error': 'Producto no encontrado'}, 404
            
        if not product.image_original_path:
            return {'error': 'No existe una imagen original para restaurar'}, 400
            
        # If current image is strictly different from original, delete it (it's a crop)
        current_key = product.image_path
        original_key = product.image_original_path
        
        if current_key and current_key != original_key:
            delete_product_image(current_key)
            
        # Restore reference
        product.image_path = original_key
        session.commit()
        
        invalidate_products_cache(g.tenant_id)
        
        return {
            'success': True,
            'image_url': product.image_url,
            'message': 'Imagen original restaurada'
        }

    except Exception as e:
        session.rollback()
        return {'error': str(e)}, 500
    # ... existing implementation ...

