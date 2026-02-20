"""
Settings blueprint for managing master data (UOM and Categories) - Multi-Tenant.
MEJORA 9: Allows users to create/edit/delete UOMs and Categories from UI.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, make_response, Response, jsonify, current_app
from app.exceptions import BusinessLogicError, NotFoundError
from typing import List, Dict, Optional, Union, Any, Tuple
from sqlalchemy import func
from app.database import get_session
from app.models import UOM, Category, Product, Tenant
from app.middleware import require_login, require_tenant
from app.services.cache_service import get_cache


settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


def invalidate_settings_cache(tenant_id: int, modules: List[str]) -> None:
    """Invalidate specified caches for a tenant (PASO 8)."""
    try:
        cache = get_cache()
        for module in modules:
            cache.invalidate_module(tenant_id, module)
    except Exception:
        pass


def _validate_uom(session, tenant_id: int, name: str, symbol: str, uom_id: Optional[int] = None) -> Optional[str]:
    """Validate UOM name and symbol. Returns error message or None."""
    if not name:
        return 'El nombre es obligatorio.'
    if len(name) > 80:
        return 'El nombre debe tener máximo 80 caracteres.'
    if not symbol:
        return 'El símbolo es obligatorio.'
    if len(symbol) > 16:
        return 'El símbolo debe tener máximo 16 caracteres.'
        
    query = session.query(UOM).filter(
        UOM.tenant_id == tenant_id,
        func.lower(UOM.name) == func.lower(name)
    )
    if uom_id:
        query = query.filter(UOM.id != uom_id)
        
    if query.first():
        return f'Ya existe una unidad de medida con el nombre "{name}".'
    return None


def _validate_category(session, tenant_id: int, name: str, category_id: Optional[int] = None) -> Optional[str]:
    """Validate Category name. Returns error message or None."""
    if not name:
        return 'El nombre es obligatorio.'
    if len(name) > 120:
        return 'El nombre debe tener máximo 120 caracteres.'
        
    query = session.query(Category).filter(
        Category.tenant_id == tenant_id,
        func.lower(Category.name) == func.lower(name)
    )
    if category_id:
        query = query.filter(Category.id != category_id)
        
    if query.first():
        return f'Ya existe una categoría con el nombre "{name}".'
    return None


# ============================================================================
# UOM (Unidades de Medida) Routes - TENANT-SCOPED
# ============================================================================

@settings_bp.route('/uoms/check-name', methods=['POST'])
@require_login
@require_tenant
def check_uom_name() -> str:
    """Check if UOM name already exists in the tenant."""
    session = get_session()
    name = request.form.get('name', '').strip()
    uom_id_str = request.form.get('uom_id', '').strip()
    
    if not name:
        return render_template('settings/_check_uom_name.html', error=None)
        
    uom_id = int(uom_id_str) if uom_id_str and uom_id_str.isdigit() else None
    error = _validate_uom(session, g.tenant_id, name, 'TEMP', uom_id)
    
    # We only care about the name existence for this check, so we ignore 'TEMP' errors
    if error and 'nombre' not in error.lower() and 'existe' not in error.lower():
        error = None
            
    return render_template('settings/_check_uom_name.html', error=error)


@settings_bp.route('/uoms')
@require_login
@require_tenant
def list_uoms() -> str:
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
def new_uom() -> Union[str, Response]:
    """Create new UOM (tenant-scoped)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        symbol = request.form.get('symbol', '').strip()
        session = get_session()
        
        error = _validate_uom(session, g.tenant_id, name, symbol)
        if error:
            raise BusinessLogicError(error)
        
        try:
            uom = UOM(tenant_id=g.tenant_id, name=name, symbol=symbol)
            session.add(uom)
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['uom'])
            flash(f'Unidad de medida "{name}" creada exitosamente.', 'success')
            return redirect(url_for('settings.list_uoms'))
        except (BusinessLogicError, NotFoundError) as e:
            session.rollback()
            raise e
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error creating UOM: {e}")
            raise BusinessLogicError(f'Error al crear unidad de medida: {str(e)}')
    
    return render_template('settings/uoms_form.html', uom=None)


@settings_bp.route('/uoms/quick-create', methods=['GET', 'POST'])
@require_login
@require_tenant
def quick_create_uom() -> Union[str, Response, Tuple[str, int]]:
    """Create new UOM via modal (HTMX)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        symbol = request.form.get('symbol', '').strip()
        session = get_session()
        
        error = _validate_uom(session, g.tenant_id, name, symbol)
        if error:
            raise BusinessLogicError(error)
        
        try:
            uom = UOM(tenant_id=g.tenant_id, name=name, symbol=symbol)
            session.add(uom)
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['uom'])
            
            uoms = session.query(UOM).filter(UOM.tenant_id == g.tenant_id).order_by(UOM.name).all()
            options_html = render_template('products/_uom_selector_options.html', uoms=uoms, selected_uom_id=uom.id)
            
            response_html = f'<select class="form-select-custom" id="uom_id" name="uom_id" required hx-swap-oob="true">{options_html}</select>'
            response = make_response(response_html)
            response.headers['HX-Trigger'] = 'uomCreated'
            return response
            
        except (BusinessLogicError, NotFoundError) as e:
            session.rollback()
            raise e
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error in quick_create_uom: {e}")
            raise BusinessLogicError(f'Error al crear unidad de medida: {str(e)}')
    
    return render_template('settings/_uom_modal_form.html')



@settings_bp.route('/uoms/<int:uom_id>/edit', methods=['GET', 'POST'])
@require_login
@require_tenant
def edit_uom(uom_id: int) -> Union[str, Response]:
    """Edit existing UOM (tenant-scoped)."""
    session = get_session()
    uom = session.query(UOM).filter(UOM.id == uom_id, UOM.tenant_id == g.tenant_id).first()
    
    if not uom:
        raise NotFoundError('No encontrado')
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        symbol = request.form.get('symbol', '').strip()
        
        error = _validate_uom(session, g.tenant_id, name, symbol, uom_id)
        if error:
            raise BusinessLogicError(error)
        
        try:
            uom.name = name
            uom.symbol = symbol
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['uom'])
            flash(f'Unidad de medida "{name}" actualizada exitosamente.', 'success')
            return redirect(url_for('settings.list_uoms'))
        except (BusinessLogicError, NotFoundError) as e:
            session.rollback()
            raise e
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error updating UOM {uom_id}: {e}")
            raise BusinessLogicError(f'Error al actualizar unidad de medida: {str(e)}')
    
    return render_template('settings/uoms_form.html', uom=uom)


@settings_bp.route('/uoms/<int:uom_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_uom(uom_id: int) -> Response:
    """Delete UOM if not in use (tenant-scoped)."""
    session = get_session()
    
    try:
        uom = session.query(UOM).filter(UOM.id == uom_id, UOM.tenant_id == g.tenant_id).first()
        
        if not uom:
            flash('Unidad de medida no encontrada.', 'warning')
            return redirect(url_for('settings.list_uoms'))
        
        product_count = session.query(func.count(Product.id)).filter(
            Product.tenant_id == g.tenant_id,
            Product.uom_id == uom_id
        ).scalar()
        
        if product_count > 0:
            flash(
                f'No se puede eliminar la unidad "{uom.name}" porque está asociada a {product_count} producto(s).',
                'warning'
            )
            return redirect(url_for('settings.list_uoms'))
        
        try:
            uom_name = uom.name
            session.delete(uom)
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['uom'])
            flash(f'Unidad de medida "{uom_name}" eliminada exitosamente.', 'success')
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error deleting UOM {uom_id}: {e}")
            flash(f'Error al eliminar unidad de medida: {str(e)}', 'danger')
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
def check_category_name() -> str:
    """Check if category name already exists in the tenant."""
    session = get_session()
    name = request.form.get('name', '').strip()
    cat_id_str = request.form.get('category_id', '').strip()
    
    if not name:
        return render_template('settings/_check_category_name.html', error=None)
        
    cat_id = int(cat_id_str) if cat_id_str and cat_id_str.isdigit() else None
    error = _validate_category(session, g.tenant_id, name, cat_id)
    
    return render_template('settings/_check_category_name.html', error=error)


@settings_bp.route('/categories')
@require_login
@require_tenant
def list_categories() -> str:
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
def new_category() -> Union[str, Response]:
    """Create new category (tenant-scoped)."""
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        session = get_session()
        
        error = _validate_category(session, g.tenant_id, name)
        if error:
            raise BusinessLogicError(error)
        
        try:
            category = Category(tenant_id=g.tenant_id, name=name)
            session.add(category)
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['categories', 'products'])
            flash(f'Categoría "{name}" creada exitosamente.', 'success')
            return redirect(url_for('settings.list_categories'))
        except (BusinessLogicError, NotFoundError) as e:
            session.rollback()
            raise e
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error creating category: {e}")
            raise BusinessLogicError(f'Error al crear categoría: {str(e)}')
    
    return render_template('settings/categories_form.html', category=None)


@settings_bp.route('/categories/quick-create', methods=['GET', 'POST'])
@require_login
@require_tenant
def quick_create_category() -> Union[str, Response, Tuple[str, int]]:
    """Create new category via modal (HTMX)."""
    session = get_session()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        error = _validate_category(session, g.tenant_id, name)
        if error:
            raise BusinessLogicError(error)
            
        try:
            new_cat = Category(name=name, tenant_id=g.tenant_id)
            session.add(new_cat)
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['categories', 'products'])
            
            categories = session.query(Category).filter(Category.tenant_id == g.tenant_id).order_by(Category.name).all()
            
            response = make_response(render_template('products/_category_selector_options.html', 
                                                  categories=categories, 
                                                  selected_category_id=new_cat.id))
            response.headers['HX-Trigger'] = 'categoryCreated'
            return response
        except (BusinessLogicError, NotFoundError) as e:
            session.rollback()
            raise e
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error in quick_create_category: {e}")
            raise BusinessLogicError(f'Error al crear categoría: {str(e)}')

    return render_template('settings/_category_modal_form.html')


@settings_bp.route('/categories/<int:category_id>/edit', methods=['GET', 'POST'])
@require_login
@require_tenant
def edit_category(category_id: int) -> Union[str, Response]:
    """Edit existing category (tenant-scoped)."""
    session = get_session()
    category = session.query(Category).filter(Category.id == category_id, Category.tenant_id == g.tenant_id).first()
    
    if not category:
        raise NotFoundError('No encontrado')
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        
        error = _validate_category(session, g.tenant_id, name, category_id)
        if error:
            raise BusinessLogicError(error)
        
        try:
            category.name = name
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['categories', 'products'])
            flash(f'Categoría "{name}" actualizada exitosamente.', 'success')
            return redirect(url_for('settings.list_categories'))
        except (BusinessLogicError, NotFoundError) as e:
            session.rollback()
            raise e
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error updating category {category_id}: {e}")
            raise BusinessLogicError(f'Error al actualizar categoría: {str(e)}')
    
    return render_template('settings/categories_form.html', category=category)


@settings_bp.route('/categories/<int:category_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_category(category_id: int) -> Response:
    """Delete category if not in use (tenant-scoped)."""
    session = get_session()
    
    try:
        category = session.query(Category).filter(Category.id == category_id, Category.tenant_id == g.tenant_id).first()
        
        if not category:
            flash('Categoría no encontrada.', 'warning')
            return redirect(url_for('settings.list_categories'))
        
        product_count = session.query(func.count(Product.id)).filter(
            Product.tenant_id == g.tenant_id,
            Product.category_id == category_id
        ).scalar()
        
        if product_count > 0:
            flash(
                f'No se puede eliminar la categoría "{category.name}" porque está asociada a {product_count} producto(s).',
                'warning'
            )
            return redirect(url_for('settings.list_categories'))
        
        try:
            category_name = category.name
            session.delete(category)
            session.commit()
            
            invalidate_settings_cache(g.tenant_id, ['categories', 'products'])
            flash(f'Categoría "{category_name}" eliminada exitosamente.', 'success')
        except Exception as e:
            session.rollback()
            current_app.logger.error(f"Error deleting category {category_id}: {e}")
            flash(f'Error al eliminar categoría: {str(e)}', 'danger')
    except Exception as e:
        session.rollback()
        flash(f'Error al eliminar categoría: {str(e)}', 'danger')
    
    return redirect(url_for('settings.list_categories'))


# ============================================================================
# Business Configuration Routes - TENANT-SCOPED
# ============================================================================

@settings_bp.route('/business', methods=['GET'])
@require_login
@require_tenant
def business_config() -> str:
    """Display business configuration form (tenant-scoped)."""
    session = get_session()
    tenant = session.query(Tenant).filter(Tenant.id == g.tenant_id).first()
    
    if not tenant:
        raise NotFoundError('Tenant no encontrado')
    
    from app.services.storage_service import get_storage_service
    storage = get_storage_service()
    
    logo_public_url = storage.get_public_url(tenant.logo_url) if tenant.logo_url else None
    
    return render_template('settings/business_config.html', tenant=tenant, logo_public_url=logo_public_url)


@settings_bp.route('/business/logo', methods=['POST'])
@require_login
@require_tenant
def upload_logo() -> Union[str, Response]:
    """Upload tenant business logo (HTMX endpoint)."""
    session = get_session()
    from app.services.storage_service import get_storage_service
    
    tenant = session.query(Tenant).filter(Tenant.id == g.tenant_id).first()
    if not tenant:
        raise NotFoundError('No encontrado')
    
    logo_file = request.files.get('logo')
    if not logo_file or not logo_file.filename:
        raise BusinessLogicError('No se proporcionó ningún archivo.')
    
    try:
        storage = get_storage_service()
        if tenant.logo_url:
            storage.delete_tenant_logo(tenant.logo_url)
        
        logo_url = storage.upload_tenant_logo(logo_file, g.tenant_id)
        tenant.logo_url = logo_url
        session.commit()
        
        logo_public_url = storage.get_public_url(logo_url)
        return render_template('settings/_sidebar_logo.html', current_tenant=tenant, logo_public_url=logo_public_url)
    
    except (BusinessLogicError, NotFoundError, ValueError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error uploading logo for tenant {g.tenant_id}: {e}")
        raise BusinessLogicError(f'Error al subir logo: {str(e)}')


@settings_bp.route('/business/logo/delete', methods=['POST'])
@require_login
@require_tenant
def delete_logo() -> Union[str, Response]:
    """Delete tenant business logo (HTMX endpoint)."""
    session = get_session()
    from app.services.storage_service import get_storage_service
    
    tenant = session.query(Tenant).filter(Tenant.id == g.tenant_id).first()
    if not tenant:
        raise NotFoundError('No encontrado')
    
    try:
        storage = get_storage_service()
        if tenant.logo_url:
            storage.delete_tenant_logo(tenant.logo_url)
        
        tenant.logo_url = None
        session.commit()
        
        return render_template('settings/_sidebar_logo.html', current_tenant=tenant, logo_public_url=None)
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error deleting logo for tenant {g.tenant_id}: {e}")
        raise BusinessLogicError(f'Error al eliminar logo: {str(e)}')

