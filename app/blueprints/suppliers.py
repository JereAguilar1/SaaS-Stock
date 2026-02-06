"""Suppliers blueprint for CRUD operations - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from app.database import get_session
from app.models import Supplier
from app.middleware import require_login, require_tenant

suppliers_bp = Blueprint('suppliers', __name__, url_prefix='/suppliers')

@suppliers_bp.route('/')
@require_login
@require_tenant
def list_suppliers():
    """List all suppliers (tenant-scoped)."""
    session = get_session()
    
    try:
        search_query = request.args.get('q', '').strip()
        
        query = session.query(Supplier).filter(
            Supplier.tenant_id == g.tenant_id
        )
        
        if search_query:
            search_filter = or_(
                func.lower(Supplier.name).like(f'%{search_query.lower()}%'),
                func.lower(Supplier.tax_id).like(f'%{search_query.lower()}%'),
                func.lower(Supplier.phone).like(f'%{search_query.lower()}%'),
                func.lower(Supplier.email).like(f'%{search_query.lower()}%')
            )
            query = query.filter(search_filter)
            
        suppliers = query.order_by(Supplier.name).all()
        
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'suppliers/_list_table.html' if is_htmx else 'suppliers/list.html'
        
        return render_template(template, suppliers=suppliers, search_query=search_query)
        
    except Exception as e:
        flash(f'Error al cargar proveedores: {str(e)}', 'danger')
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'suppliers/_list_table.html' if is_htmx else 'suppliers/list.html'
        return render_template(template, suppliers=[], search_query='')


@suppliers_bp.route('/new', methods=['GET'])
@require_login
@require_tenant
def new_supplier():
    """Show form to create a new supplier."""
    return render_template('suppliers/form.html', supplier=None, action='new')


@suppliers_bp.route('/new', methods=['POST'])
@require_login
@require_tenant
def create_supplier():
    """Create a new supplier (tenant-scoped)."""
    session = get_session()
    
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        tax_id = request.form.get('tax_id', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        email = request.form.get('email', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        
        # Validations
        if not name:
            flash('El nombre es requerido', 'danger')
            return render_template('suppliers/form.html', supplier=None, action='new')
        
        # Create supplier with tenant_id
        supplier = Supplier(
            tenant_id=g.tenant_id,
            name=name,
            tax_id=tax_id,
            phone=phone,
            email=email,
            notes=notes
        )
        
        session.add(supplier)
        session.commit()
        
        flash(f'Proveedor "{supplier.name}" creado exitosamente', 'success')
        return redirect(url_for('suppliers.list_suppliers'))
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig).lower()
        if 'unique' in error_msg and 'name' in error_msg:
            flash(f'El proveedor "{name}" ya existe en su negocio. Use otro nombre.', 'danger')
        else:
            flash(f'Error al crear proveedor: {str(e)}', 'danger')
        return render_template('suppliers/form.html', supplier=None, action='new')
        
    except Exception as e:
        session.rollback()
        flash(f'Error al crear proveedor: {str(e)}', 'danger')
        return redirect(url_for('suppliers.list_suppliers'))


@suppliers_bp.route('/<int:supplier_id>/edit', methods=['GET'])
@require_login
@require_tenant
def edit_supplier(supplier_id):
    """Show form to edit a supplier (tenant-scoped)."""
    session = get_session()
    
    try:
        supplier = session.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.tenant_id == g.tenant_id
        ).first()
        
        if not supplier:
            abort(404)
        
        return render_template('suppliers/form.html', supplier=supplier, action='edit')
        
    except Exception as e:
        flash(f'Error al cargar proveedor: {str(e)}', 'danger')
        return redirect(url_for('suppliers.list_suppliers'))


@suppliers_bp.route('/<int:supplier_id>/edit', methods=['POST'])
@require_login
@require_tenant
def update_supplier(supplier_id):
    """Update a supplier (tenant-scoped)."""
    session = get_session()
    
    try:
        supplier = session.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.tenant_id == g.tenant_id
        ).first()
        
        if not supplier:
            abort(404)
        
        # Get form data
        name = request.form.get('name', '').strip()
        tax_id = request.form.get('tax_id', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        email = request.form.get('email', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        
        # Validations
        if not name:
            flash('El nombre es requerido', 'danger')
            return render_template('suppliers/form.html', supplier=supplier, action='edit')
        
        # Update supplier
        supplier.name = name
        supplier.tax_id = tax_id
        supplier.phone = phone
        supplier.email = email
        supplier.notes = notes
        
        session.commit()
        
        flash(f'Proveedor "{supplier.name}" actualizado exitosamente', 'success')
        return redirect(url_for('suppliers.list_suppliers'))
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig).lower()
        if 'unique' in error_msg and 'name' in error_msg:
            flash(f'El proveedor "{name}" ya existe en su negocio. Use otro nombre.', 'danger')
        else:
            flash(f'Error al actualizar proveedor: {str(e)}', 'danger')
        return render_template('suppliers/form.html', supplier=supplier, action='edit')
        
        flash(f'Error al actualizar proveedor: {str(e)}', 'danger')
        return redirect(url_for('suppliers.list_suppliers'))


@suppliers_bp.route('/<int:supplier_id>')
@require_login
@require_tenant
def view_supplier(supplier_id):
    """View supplier detail (tenant-scoped)."""
    session = get_session()
    
    try:
        supplier = session.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.tenant_id == g.tenant_id
        ).first()
        
        if not supplier:
            abort(404)
        
        return render_template('suppliers/detail.html', supplier=supplier)
        
    except Exception as e:
        flash(f'Error al cargar proveedor: {str(e)}', 'danger')
        return redirect(url_for('suppliers.list_suppliers'))


@suppliers_bp.route('/<int:supplier_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_supplier(supplier_id):
    """Delete a supplier (tenant-scoped)."""
    session = get_session()
    
    try:
        supplier = session.query(Supplier).filter(
            Supplier.id == supplier_id,
            Supplier.tenant_id == g.tenant_id
        ).first()
        
        if not supplier:
            abort(404)
        
        supplier_name = supplier.name
        
        try:
            session.delete(supplier)
            session.commit()
            
            flash(f'Proveedor "{supplier_name}" eliminado exitosamente', 'success')
            
        except IntegrityError:
            session.rollback()
            flash(
                f'No se puede eliminar el proveedor "{supplier_name}" porque tiene '\
                'boletas de compra o productos asociados.',
                'warning'
            )
            
        return redirect(url_for('suppliers.list_suppliers'))
        
    except Exception as e:
        session.rollback()
        flash(f'Error al eliminar proveedor: {str(e)}', 'danger')
        return redirect(url_for('suppliers.list_suppliers'))
