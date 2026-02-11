"""Customers blueprint for CRUD operations - Multi-Tenant."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from app.database import get_session
from app.models import Customer
from app.middleware import require_login, require_tenant

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')

@customers_bp.route('/check-name', methods=['POST'])
@require_login
@require_tenant
def check_name():
    """Check if customer name already exists in the tenant."""
    session = get_session()
    name = request.form.get('name', '').strip()
    customer_id = request.form.get('customer_id', '').strip()
    
    if not name:
        return render_template('customers/_check_name.html', error=None)
        
    query = session.query(Customer).filter(
        Customer.tenant_id == g.tenant_id,
        func.lower(Customer.name) == name.lower()
    )
    
    # If editing, exclude current customer
    if customer_id:
        try:
            query = query.filter(Customer.id != int(customer_id))
        except ValueError:
            pass
            
    exists = query.first()
    
    if exists:
        return render_template('customers/_check_name.html', error=f"El cliente '{name}' ya existe")
    
    return render_template('customers/_check_name.html', error=None)


@customers_bp.route('/search', methods=['GET'])
@require_login
@require_tenant
def search_customers():
    """Search customers for autocomplete (JSON)."""
    session = get_session()
    query_str = request.args.get('q', '').strip()
    
    if not query_str:
        return {'results': []}
        
    try:
        query = session.query(Customer).filter(
            Customer.tenant_id == g.tenant_id,
            or_(
                func.lower(Customer.name).like(f'%{query_str.lower()}%'),
                func.lower(Customer.tax_id).like(f'%{query_str.lower()}%'),
                func.lower(Customer.phone).like(f'%{query_str.lower()}%')
            )
        ).limit(10)
        
        results = [
            {
                'id': c.id,
                'name': c.name,
                'tax_id': c.tax_id,
                'phone': c.phone
            }
            for c in query.all()
        ]
        
        return {'results': results}
        
    except Exception as e:
        return {'results': [], 'error': str(e)}


@customers_bp.route('/quick-create', methods=['POST'])
@require_login
@require_tenant
def quick_create():
    """
    Quick create customer from POS (HTMX endpoint).
    
    Returns HTML fragment with updated customer selector.
    """
    session = get_session()
    
    try:
        # Get form data
        name = request.form.get('name', '').strip()
        tax_id = request.form.get('tax_id', '').strip() or None
        phone = request.form.get('phone', '').strip() or None
        email = request.form.get('email', '').strip() or None
        address = request.form.get('address', '').strip() or None
        
        # Validate
        if not name:
            return render_template(
                'sales/_customer_quick_form.html',
                error='El nombre es requerido',
                name=name,
                tax_id=tax_id,
                phone=phone,
                email=email,
                address=address
            ), 400
        
        # Create customer
        customer = Customer(
            tenant_id=g.tenant_id,
            name=name,
            tax_id=tax_id,
            phone=phone,
            email=email,
            address=address
        )
        
        session.add(customer)
        session.commit()
        
        # Return updated selector with new customer selected
        from app.services.customer_service import get_or_create_default_customer_id
        
        customers = session.query(Customer).filter(
            Customer.tenant_id == g.tenant_id
        ).order_by(Customer.name).all()
        
        default_customer_id = get_or_create_default_customer_id(session, g.tenant_id)
        
        # Return selector with newly created customer selected
        return render_template(
            'sales/_customer_selector.html',
            customers=customers,
            default_customer_id=default_customer_id,
            selected_customer_id=customer.id,  # NEW customer selected
            success_message=f'Cliente "{customer.name}" creado exitosamente'
        )
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig).lower() if hasattr(e, 'orig') else str(e).lower()
        if 'unique' in error_msg:
            error = f'El cliente "{name}" ya existe'
        else:
            error = 'Error al crear cliente'
            
        return render_template(
            'sales/_customer_quick_form.html',
            error=error,
            name=name,
            tax_id=tax_id,
            phone=phone,
            email=email,
            address=address
        ), 400
        
    except Exception as e:
        session.rollback()
        return render_template(
            'sales/_customer_quick_form.html',
            error=f'Error: {str(e)}',
            name=name or '',
            tax_id=tax_id or '',
            phone=phone or '',
            email=email or '',
            address=address or ''
        ), 500



@customers_bp.route('/list')
@require_login
@require_tenant
def list_customers_alt():
    """List all customers (alias)."""
    return list_customers()


@customers_bp.route('/')
@require_login
@require_tenant
def list_customers():
    """List all customers (tenant-scoped)."""
    session = get_session()
    
    try:
        search_query = request.args.get('q', '').strip()
        
        query = session.query(Customer).filter(
            Customer.tenant_id == g.tenant_id
        )
        
        if search_query:
            from sqlalchemy import cast, String
            search_filter = or_(
                func.lower(Customer.name).like(f'%{search_query.lower()}%'),
                func.lower(Customer.tax_id).like(f'%{search_query.lower()}%'),
                func.lower(Customer.phone).like(f'%{search_query.lower()}%'),
                func.lower(Customer.email).like(f'%{search_query.lower()}%'),
                func.lower(Customer.notes).like(f'%{search_query.lower()}%'),
                cast(Customer.id, String).like(f'%{search_query}%')
            )
            query = query.filter(search_filter)
            
        customers = query.order_by(Customer.name).all()
        
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'customers/_list_table.html' if is_htmx else 'customers/list.html'
        
        return render_template(template, customers=customers, search_query=search_query)
        
    except Exception as e:
        flash(f'Error al cargar clientes: {str(e)}', 'danger')
        is_htmx = request.headers.get('HX-Request') == 'true'
        template = 'customers/_list_table.html' if is_htmx else 'customers/list.html'
        return render_template(template, customers=[], search_query='')


@customers_bp.route('/new', methods=['GET'])
@require_login
@require_tenant
def new_customer():
    """Show form to create a new customer."""
    return render_template('customers/form.html', customer=None, action='new')


@customers_bp.route('/new', methods=['POST'])
@require_login
@require_tenant
def create_customer():
    """Create a new customer (tenant-scoped)."""
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
            return render_template('customers/form.html', customer=None, action='new')
        
        # Create customer with tenant_id
        customer = Customer(
            tenant_id=g.tenant_id,
            name=name,
            tax_id=tax_id,
            phone=phone,
            email=email,
            notes=notes
        )
        
        session.add(customer)
        session.commit()
        
        flash(f'Cliente "{customer.name}" creado exitosamente', 'success')
        return redirect(url_for('customers.list_customers'))
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig).lower()
        if 'unique' in error_msg and 'name' in error_msg:
            flash(f'El cliente "{name}" ya existe en su negocio. Use otro nombre.', 'danger')
        else:
            flash(f'Error al crear cliente: {str(e)}', 'danger')
            
        # Preserve form data
        form_customer = {
            'name': name,
            'tax_id': tax_id,
            'phone': phone,
            'email': email,
            'notes': notes
        }
        return render_template('customers/form.html', customer=form_customer, action='new')
        
    except Exception as e:
        session.rollback()
        flash(f'Error al crear cliente: {str(e)}', 'danger')
        # Preserve form data on general error too
        form_customer = {
            'name': name,
            'tax_id': tax_id,
            'phone': phone,
            'email': email,
            'notes': notes
        }
        return render_template('customers/form.html', customer=form_customer, action='new')


@customers_bp.route('/<int:customer_id>/edit', methods=['GET'])
@require_login
@require_tenant
def edit_customer(customer_id):
    """Show form to edit a customer (tenant-scoped)."""
    session = get_session()
    
    try:
        customer = session.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == g.tenant_id
        ).first()
        
        if not customer:
            abort(404)
        
        return render_template('customers/form.html', customer=customer, action='edit')
        
    except Exception as e:
        flash(f'Error al cargar cliente: {str(e)}', 'danger')
        return redirect(url_for('customers.list_customers'))


@customers_bp.route('/<int:customer_id>/edit', methods=['POST'])
@require_login
@require_tenant
def update_customer(customer_id):
    """Update a customer (tenant-scoped)."""
    session = get_session()
    
    try:
        customer = session.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == g.tenant_id
        ).first()
        
        if not customer:
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
            return render_template('customers/form.html', customer=customer, action='edit')
        
        # Update customer
        customer.name = name
        customer.tax_id = tax_id
        customer.phone = phone
        customer.email = email
        customer.notes = notes
        
        session.commit()
        
        flash(f'Cliente "{customer.name}" actualizado exitosamente', 'success')
        return redirect(url_for('customers.list_customers'))
        
    except IntegrityError as e:
        session.rollback()
        error_msg = str(e.orig).lower()
        if 'unique' in error_msg and 'name' in error_msg:
            flash(f'El cliente "{name}" ya existe en su negocio. Use otro nombre.', 'danger')
        else:
            flash(f'Error al actualizar cliente: {str(e)}', 'danger')
            
        # Preserve form data
        form_customer = {
            'id': customer_id,
            'name': name,
            'tax_id': tax_id,
            'phone': phone,
            'email': email,
            'notes': notes
        }
        return render_template('customers/form.html', customer=form_customer, action='edit')
        
    except Exception as e:
        session.rollback()
        flash(f'Error al actualizar cliente: {str(e)}', 'danger')
        return redirect(url_for('customers.list_customers'))


@customers_bp.route('/<int:customer_id>')
@require_login
@require_tenant
def view_customer(customer_id):
    """View customer detail (tenant-scoped)."""
    session = get_session()
    
    try:
        customer = session.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == g.tenant_id
        ).first()
        
        if not customer:
            abort(404)
        
        return render_template('customers/detail.html', customer=customer)
        
    except Exception as e:
        flash(f'Error al cargar cliente: {str(e)}', 'danger')
        return redirect(url_for('customers.list_customers'))


@customers_bp.route('/<int:customer_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_customer(customer_id):
    """Delete a customer (tenant-scoped)."""
    session = get_session()
    
    try:
        customer = session.query(Customer).filter(
            Customer.id == customer_id,
            Customer.tenant_id == g.tenant_id
        ).first()
        
        if not customer:
            abort(404)
        
        customer_name = customer.name
        
        try:
            session.delete(customer)
            session.commit()
            
            flash(f'Cliente "{customer_name}" eliminado exitosamente', 'success')
            
        except IntegrityError:
            session.rollback()
            flash(
                f'No se puede eliminar el cliente "{customer_name}" porque tiene '\
                'ventas o registros asociados.',
                'warning'
            )
            
        return redirect(url_for('customers.list_customers'))
        
    except Exception as e:
        session.rollback()
        flash(f'Error al eliminar cliente: {str(e)}', 'danger')
        return redirect(url_for('customers.list_customers'))
