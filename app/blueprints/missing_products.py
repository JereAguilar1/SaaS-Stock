"""Missing Products blueprint for tracking customer requests - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, g, abort
from sqlalchemy import or_, func
from datetime import datetime
from app.database import get_session
from app.models import MissingProductRequest, normalize_missing_product_name, Product
from app.middleware import require_login, require_tenant

missing_products_bp = Blueprint('missing_products', __name__, url_prefix='/missing-products')


@missing_products_bp.route('/')
@require_login
@require_tenant
def list_missing_products():
    """List missing product requests with filters and search (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get filter parameters
        q = request.args.get('q', '').strip()
        status = request.args.get('status', 'all')
        
        # Base query - filter by tenant
        query = db_session.query(MissingProductRequest).filter(
            MissingProductRequest.tenant_id == g.tenant_id
        )
        
        # Apply status filter
        if status == 'OPEN':
            query = query.filter(MissingProductRequest.status == 'OPEN')
        elif status == 'RESOLVED':
            query = query.filter(MissingProductRequest.status == 'RESOLVED')
        
        # Search filter
        if q:
            search_pattern = f'%{q}%'
            query = query.filter(or_(
                MissingProductRequest.name.ilike(search_pattern),
                MissingProductRequest.normalized_name.like(f'%{normalize_missing_product_name(q)}%')
            ))
        
        # Order by request_count DESC, then last_requested_at DESC
        requests = query.order_by(
            MissingProductRequest.request_count.desc(),
            MissingProductRequest.last_requested_at.desc()
        ).all()
        
        return render_template('missing_products/list.html',
                             requests=requests,
                             selected_status=status,
                             search_query=q)
        
    except Exception as e:
        current_app.logger.error(f"Error loading missing products: {e}")
        flash(f'Error al cargar productos faltantes: {str(e)}', 'danger')
        return redirect(url_for('catalog.list_products'))


@missing_products_bp.route('/request', methods=['POST'])
@require_login
@require_tenant
def register_request():
    """Register a new missing product request or increment existing one (tenant-scoped)."""
    db_session = get_session()
    
    try:
        name = request.form.get('name', '').strip()
        
        if not name:
            flash('El nombre del producto es requerido', 'danger')
            return redirect(url_for('missing_products.list_missing_products'))
        
        # Normalize name for deduplication
        normalized = normalize_missing_product_name(name)
        
        if not normalized:
            flash('El nombre del producto no puede estar vacío', 'danger')
            return redirect(url_for('missing_products.list_missing_products'))
        
        # Check if product already exists in catalog (in current tenant)
        existing_product = db_session.query(Product).filter(
            Product.tenant_id == g.tenant_id,
            func.lower(Product.name) == normalized
        ).first()
        
        if existing_product:
            flash(
                f'⚠️ Advertencia: El producto "{existing_product.name}" ya existe en su catálogo (ID: {existing_product.id}). '
                f'Considera usar el producto existente en vez de registrarlo como faltante.',
                'warning'
            )
        
        # Check if already exists in missing products (for this tenant)
        existing_req = db_session.query(MissingProductRequest).filter(
            MissingProductRequest.tenant_id == g.tenant_id,
            MissingProductRequest.normalized_name == normalized
        ).first()
        
        if existing_req:
            # Increment count and update timestamp
            existing_req.request_count += 1
            existing_req.last_requested_at = datetime.now()
            db_session.commit()
            
            flash(f'Registrado pedido: "{existing_req.name}" (ahora {existing_req.request_count} pedidos)', 'success')
        else:
            # Create new with tenant_id
            new_request = MissingProductRequest(
                tenant_id=g.tenant_id,
                name=name.strip(),
                normalized_name=normalized,
                request_count=1,
                status='OPEN',
                last_requested_at=datetime.now()
            )
            db_session.add(new_request)
            db_session.commit()
            
            flash(f'Registrado pedido: "{name}" (1 pedido)', 'success')
        
        return redirect(url_for('missing_products.list_missing_products'))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error registering missing product request: {e}")
        flash(f'Error al registrar pedido: {str(e)}', 'danger')
        return redirect(url_for('missing_products.list_missing_products'))


@missing_products_bp.route('/<int:request_id>/resolve', methods=['POST'])
@require_login
@require_tenant
def resolve_request(request_id):
    """Mark a missing product request as RESOLVED (tenant-scoped)."""
    db_session = get_session()
    
    try:
        missing_req = db_session.query(MissingProductRequest).filter(
            MissingProductRequest.id == request_id,
            MissingProductRequest.tenant_id == g.tenant_id
        ).first()
        
        if not missing_req:
            abort(404)
        
        if missing_req.status == 'RESOLVED':
            flash(f'"{missing_req.name}" ya está marcado como resuelto', 'info')
        else:
            missing_req.status = 'RESOLVED'
            db_session.commit()
            flash(f'✓ "{missing_req.name}" marcado como resuelto', 'success')
        
        return redirect(url_for('missing_products.list_missing_products'))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error resolving missing product request: {e}")
        flash(f'Error al resolver: {str(e)}', 'danger')
        return redirect(url_for('missing_products.list_missing_products'))


@missing_products_bp.route('/<int:request_id>/reopen', methods=['POST'])
@require_login
@require_tenant
def reopen_request(request_id):
    """Reopen a resolved missing product request (tenant-scoped)."""
    db_session = get_session()
    
    try:
        missing_req = db_session.query(MissingProductRequest).filter(
            MissingProductRequest.id == request_id,
            MissingProductRequest.tenant_id == g.tenant_id
        ).first()
        
        if not missing_req:
            abort(404)
        
        if missing_req.status == 'OPEN':
            flash(f'"{missing_req.name}" ya está abierto', 'info')
        else:
            missing_req.status = 'OPEN'
            db_session.commit()
            flash(f'"{missing_req.name}" reabierto correctamente', 'success')
        
        return redirect(url_for('missing_products.list_missing_products'))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error reopening missing product request: {e}")
        flash(f'Error al reabrir solicitud: {str(e)}', 'danger')
        return redirect(url_for('missing_products.list_missing_products'))


@missing_products_bp.route('/<int:request_id>/update-notes', methods=['POST'])
@require_login
@require_tenant
def update_notes(request_id):
    """Update notes for a missing product request (tenant-scoped)."""
    db_session = get_session()
    
    try:
        missing_req = db_session.query(MissingProductRequest).filter(
            MissingProductRequest.id == request_id,
            MissingProductRequest.tenant_id == g.tenant_id
        ).first()
        
        if not missing_req:
            abort(404)
        
        notes = request.form.get('notes', '').strip()
        missing_req.notes = notes if notes else None
        
        db_session.commit()
        flash(f'Notas actualizadas para "{missing_req.name}"', 'success')
        return redirect(url_for('missing_products.list_missing_products'))
        
    except Exception as e:
        db_session.rollback()
        current_app.logger.error(f"Error updating notes: {e}")
        flash(f'Error al actualizar notas: {str(e)}', 'danger')
        return redirect(url_for('missing_products.list_missing_products'))
