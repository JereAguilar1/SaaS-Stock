"""
Settings blueprint for managing master data (UOM and Categories) - Multi-Tenant.
MEJORA 9: Allows users to create/edit/delete UOMs and Categories from UI.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from sqlalchemy import func
from app.database import get_session
from app.models import UOM, Category, Product
from app.middleware import require_login, require_tenant


settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def invalidate_categories_cache(tenant_id: int):
    """Invalidate categories cache for a tenant (PASO 8)."""
    try:
        from app.services.cache_service import get_cache
        cache = get_cache()
        cache.invalidate_module(tenant_id, 'categories')
    except Exception:
        pass


def invalidate_uom_cache(tenant_id: int):
    """Invalidate UOM cache for a tenant (PASO 8)."""
    try:
        from app.services.cache_service import get_cache
        cache = get_cache()
        cache.invalidate_module(tenant_id, 'uom')
    except Exception:
        pass


def invalidate_products_cache(tenant_id: int):
    """Invalidate products cache for a tenant (PASO 8)."""
    try:
        from app.services.cache_service import get_cache
        cache = get_cache()
        cache.invalidate_module(tenant_id, 'products')
    except Exception:
        pass


# ============================================================================
# UOM (Unidades de Medida) Routes - TENANT-SCOPED
# ============================================================================

@settings_bp.route('/uoms/check-name', methods=['POST'])
@require_login
@require_tenant
def check_uom_name():
    """Check if UOM name already exists in the tenant."""
    session = get_session()
    name = request.form.get('name', '').strip()
    uom_id = request.form.get('uom_id', '').strip()
    
    if not name:
        return render_template('settings/_check_uom_name.html', error=None)
        
    query = session.query(UOM).filter(
        UOM.tenant_id == g.tenant_id,
        func.lower(UOM.name) == func.lower(name)
    )
    
    # If editing, exclude current uom
    if uom_id:
        try:
            query = query.filter(UOM.id != int(uom_id))
        except ValueError:
            pass
            
    exists = query.first()
    
    if exists:
        return render_template('settings/_check_uom_name.html', error=f"Ya existe una UOM con este nombre")
    
    return render_template('settings/_check_uom_name.html', error=None)


@settings_bp.route('/uoms')
@require_login
@require_tenant
def list_uoms():
    """List all UOMs with product count (tenant-scoped)."""
    session = get_session()
    
    # Get all UOMs with product count for current tenant
    uoms_with_count = session.query(
        UOM,
        func.count(Product.id).label('product_count')
    ).outerjoin(Product, Product.uom_id == UOM.id)\
     .filter(UOM.tenant_id == g.tenant_id)\
     .group_by(UOM.id)\
     .order_by(UOM.name)\
     .all()
    
    return render_template('settings/uoms_list.html', uoms_with_count=uoms_with_count)


@settings_bp.route('/uoms/new', methods=['GET', 'POST'])
@require_login
@require_tenant
def new_uom():
    """Create new UOM (tenant-scoped)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        symbol = request.form.get('symbol', '').strip()
        
        # Validations
        if not name:
            flash('El nombre es obligatorio.', 'danger')
            return render_template('settings/uoms_form.html', uom=None)
        
        if len(name) > 80:
            flash('El nombre debe tener máximo 80 caracteres.', 'danger')
            return render_template('settings/uoms_form.html', uom={'name': name, 'symbol': symbol})
        
        if not symbol:
            flash('El símbolo es obligatorio.', 'danger')
            return render_template('settings/uoms_form.html', uom={'name': name, 'symbol': symbol})
        
        if len(symbol) > 16:
            flash('El símbolo debe tener máximo 16 caracteres.', 'danger')
            return render_template('settings/uoms_form.html', uom={'name': name, 'symbol': symbol})
        
        session = get_session()
        
        # Check if name already exists in current tenant (case-insensitive)
        existing_name = session.query(UOM).filter(
            UOM.tenant_id == g.tenant_id,
            func.lower(UOM.name) == func.lower(name)
        ).first()
        
        if existing_name:
            flash(f'Ya existe una unidad de medida con el nombre "{name}" en su negocio.', 'danger')
            return render_template('settings/uoms_form.html', uom={'name': name, 'symbol': symbol})
        
        # Create UOM with tenant_id
        try:
            uom = UOM(
                tenant_id=g.tenant_id,
                name=name,
                symbol=symbol
            )
            session.add(uom)
            session.commit()
            
            # PASO 8: Invalidate UOM cache
            invalidate_uom_cache(g.tenant_id)
            
            flash(f'Unidad de medida "{name}" creada exitosamente.', 'success')
            return redirect(url_for('settings.list_uoms'))
        except Exception as e:
            session.rollback()
            flash(f'Error al crear unidad de medida: {str(e)}', 'danger')
            return render_template('settings/uoms_form.html', uom={'name': name, 'symbol': symbol})
    
    # GET request
    return render_template('settings/uoms_form.html', uom=None)


@settings_bp.route('/uoms/<int:uom_id>/edit', methods=['GET', 'POST'])
@require_login
@require_tenant
def edit_uom(uom_id):
    """Edit existing UOM (tenant-scoped)."""
    session = get_session()
    uom = session.query(UOM).filter(
        UOM.id == uom_id,
        UOM.tenant_id == g.tenant_id
    ).first()
    
    if not uom:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        symbol = request.form.get('symbol', '').strip()
        
        # Validations
        if not name:
            flash('El nombre es obligatorio.', 'danger')
            return render_template('settings/uoms_form.html', uom=uom)
        
        if len(name) > 80:
            flash('El nombre debe tener máximo 80 caracteres.', 'danger')
            return render_template('settings/uoms_form.html', uom={'id': uom.id, 'name': name, 'symbol': symbol})
        
        if not symbol:
            flash('El símbolo es obligatorio.', 'danger')
            return render_template('settings/uoms_form.html', uom={'id': uom.id, 'name': name, 'symbol': symbol})
        
        if len(symbol) > 16:
            flash('El símbolo debe tener máximo 16 caracteres.', 'danger')
            return render_template('settings/uoms_form.html', uom={'id': uom.id, 'name': name, 'symbol': symbol})
        
        # Check if name already exists in tenant (excluding current UOM)
        existing_name = session.query(UOM).filter(
            UOM.tenant_id == g.tenant_id,
            func.lower(UOM.name) == func.lower(name),
            UOM.id != uom_id
        ).first()
        
        if existing_name:
            flash(f'Ya existe otra unidad de medida con el nombre "{name}" en su negocio.', 'danger')
            return render_template('settings/uoms_form.html', uom={'id': uom.id, 'name': name, 'symbol': symbol})
        
        # Update UOM
        try:
            uom.name = name
            uom.symbol = symbol
            session.commit()
            
            # PASO 8: Invalidate UOM cache
            invalidate_uom_cache(g.tenant_id)
            
            flash(f'Unidad de medida "{name}" actualizada exitosamente.', 'success')
            return redirect(url_for('settings.list_uoms'))
        except Exception as e:
            session.rollback()
            flash(f'Error al actualizar unidad de medida: {str(e)}', 'danger')
            return render_template('settings/uoms_form.html', uom={'id': uom.id, 'name': name, 'symbol': symbol})
    
    # GET request
    return render_template('settings/uoms_form.html', uom=uom)


@settings_bp.route('/uoms/<int:uom_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_uom(uom_id):
    """Delete UOM if not in use (tenant-scoped)."""
    session = get_session()
    uom = session.query(UOM).filter(
        UOM.id == uom_id,
        UOM.tenant_id == g.tenant_id
    ).first()
    
    if not uom:
        abort(404)
    
    # Check if UOM is used by any product in this tenant
    product_count = session.query(func.count(Product.id)).filter(
        Product.tenant_id == g.tenant_id,
        Product.uom_id == uom_id
    ).scalar()
    
    if product_count > 0:
        flash(
            f'No se puede eliminar la unidad "{uom.name}" porque está asociada a {product_count} producto(s).',
            'danger'
        )
        return redirect(url_for('settings.list_uoms'))
    
    # Delete UOM
    try:
        uom_name = uom.name
        session.delete(uom)
        session.commit()
        
        # PASO 8: Invalidate UOM cache
        invalidate_uom_cache(g.tenant_id)
        
        flash(f'Unidad de medida "{uom_name}" eliminada exitosamente.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error al eliminar unidad de medida: {str(e)}', 'danger')
    
    return redirect(url_for('settings.list_uoms'))


# ============================================================================
# Category Routes - TENANT-SCOPED
# ============================================================================

@settings_bp.route('/categories/check-name', methods=['POST'])
@require_login
@require_tenant
def check_category_name():
    """Check if category name already exists in the tenant."""
    session = get_session()
    name = request.form.get('name', '').strip()
    category_id = request.form.get('category_id', '').strip()
    
    if not name:
        return render_template('settings/_check_category_name.html', error=None)
        
    query = session.query(Category).filter(
        Category.tenant_id == g.tenant_id,
        func.lower(Category.name) == func.lower(name)
    )
    
    # If editing, exclude current category
    if category_id:
        try:
            query = query.filter(Category.id != int(category_id))
        except ValueError:
            pass
            
    exists = query.first()
    
    if exists:
        return render_template('settings/_check_category_name.html', error=f"Ya existe una categoría con este nombre")
    
    return render_template('settings/_check_category_name.html', error=None)


@settings_bp.route('/categories')
@require_login
@require_tenant
def list_categories():
    """List all categories with product count (tenant-scoped)."""
    session = get_session()
    
    # Get all categories with product count for current tenant
    categories_with_count = session.query(
        Category,
        func.count(Product.id).label('product_count')
    ).outerjoin(Product, Product.category_id == Category.id)\
     .filter(Category.tenant_id == g.tenant_id)\
     .group_by(Category.id)\
     .order_by(Category.name)\
     .all()
    
    return render_template('settings/categories_list.html', categories_with_count=categories_with_count)


@settings_bp.route('/categories/new', methods=['GET', 'POST'])
@require_login
@require_tenant
def new_category():
    """Create new category (tenant-scoped)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        # Validations
        if not name:
            flash('El nombre es obligatorio.', 'danger')
            return render_template('settings/categories_form.html', category=None)
        
        if len(name) > 120:
            flash('El nombre debe tener máximo 120 caracteres.', 'danger')
            return render_template('settings/categories_form.html', category={'name': name})
        
        session = get_session()
        
        # Check if name already exists in tenant (case-insensitive)
        existing = session.query(Category).filter(
            Category.tenant_id == g.tenant_id,
            func.lower(Category.name) == func.lower(name)
        ).first()
        
        if existing:
            flash(f'Ya existe una categoría con el nombre "{name}" en su negocio.', 'danger')
            return render_template('settings/categories_form.html', category={'name': name})
        
        # Create category with tenant_id
        try:
            category = Category(
                tenant_id=g.tenant_id,
                name=name
            )
            session.add(category)
            session.commit()
            
            # PASO 8: Invalidate categories & products cache
            invalidate_categories_cache(g.tenant_id)
            invalidate_products_cache(g.tenant_id)  # Products show category
            
            flash(f'Categoría "{name}" creada exitosamente.', 'success')
            return redirect(url_for('settings.list_categories'))
        except Exception as e:
            session.rollback()
            flash(f'Error al crear categoría: {str(e)}', 'danger')
            return render_template('settings/categories_form.html', category={'name': name})
    
    # GET request
    return render_template('settings/categories_form.html', category=None)


@settings_bp.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@require_login
@require_tenant
def edit_category(category_id):
    """Edit existing category (tenant-scoped)."""
    session = get_session()
    category = session.query(Category).filter(
        Category.id == category_id,
        Category.tenant_id == g.tenant_id
    ).first()
    
    if not category:
        abort(404)
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        # Validations
        if not name:
            flash('El nombre es obligatorio.', 'danger')
            return render_template('settings/categories_form.html', category=category)
        
        if len(name) > 120:
            flash('El nombre debe tener máximo 120 caracteres.', 'danger')
            return render_template('settings/categories_form.html', category={'id': category.id, 'name': name})
        
        # Check if name already exists in tenant (excluding current category)
        existing = session.query(Category).filter(
            Category.tenant_id == g.tenant_id,
            func.lower(Category.name) == func.lower(name),
            Category.id != category_id
        ).first()
        
        if existing:
            flash(f'Ya existe otra categoría con el nombre "{name}" en su negocio.', 'danger')
            return render_template('settings/categories_form.html', category={'id': category.id, 'name': name})
        
        # Update category
        try:
            category.name = name
            session.commit()
            
            # PASO 8: Invalidate categories & products cache
            invalidate_categories_cache(g.tenant_id)
            invalidate_products_cache(g.tenant_id)  # Products show category
            
            flash(f'Categoría "{name}" actualizada exitosamente.', 'success')
            return redirect(url_for('settings.list_categories'))
        except Exception as e:
            session.rollback()
            flash(f'Error al actualizar categoría: {str(e)}', 'danger')
            return render_template('settings/categories_form.html', category={'id': category.id, 'name': name})
    
    # GET request
    return render_template('settings/categories_form.html', category=category)


@settings_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_category(category_id):
    """Delete category if not in use (tenant-scoped)."""
    session = get_session()
    category = session.query(Category).filter(
        Category.id == category_id,
        Category.tenant_id == g.tenant_id
    ).first()
    
    if not category:
        abort(404)
    
    # Check if category is used by any product in this tenant
    product_count = session.query(func.count(Product.id)).filter(
        Product.tenant_id == g.tenant_id,
        Product.category_id == category_id
    ).scalar()
    
    if product_count > 0:
        flash(
            f'No se puede eliminar la categoría "{category.name}" porque está asociada a {product_count} producto(s).',
            'danger'
        )
        return redirect(url_for('settings.list_categories'))
    
    # Delete category
    try:
        category_name = category.name
        session.delete(category)
        session.commit()
        
        # PASO 8: Invalidate categories & products cache
        invalidate_categories_cache(g.tenant_id)
        invalidate_products_cache(g.tenant_id)  # Products show category
        
        flash(f'Categoría "{category_name}" eliminada exitosamente.', 'success')
    except Exception as e:
        session.rollback()
        flash(f'Error al eliminar categoría: {str(e)}', 'danger')
    
    return redirect(url_for('settings.list_categories'))
