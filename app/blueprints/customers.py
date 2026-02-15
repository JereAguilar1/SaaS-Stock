from flask import Blueprint, render_template, request, redirect, url_for, flash, g, abort, Response, current_app
from app.exceptions import BusinessLogicError, NotFoundError
from typing import List, Dict, Optional, Union, Any, Tuple
from sqlalchemy import or_, func
from sqlalchemy.exc import IntegrityError
from app.database import get_session
from app.models import Customer
from app.middleware import require_login, require_tenant

customers_bp = Blueprint('customers', __name__, url_prefix='/customers')


def _get_customer_data_from_form() -> Dict[str, Any]:
    """Extract and sanitize customer data from request.form."""
    return {
        'name': request.form.get('name', '').strip(),
        'tax_id': request.form.get('tax_id', '').strip() or None,
        'phone': request.form.get('phone', '').strip() or None,
        'email': request.form.get('email', '').strip() or None,
        'address': request.form.get('address', '').strip() or None,
        'notes': request.form.get('notes', '').strip() or None
    }


def _validate_customer_name(session, tenant_id: int, name: str, exclude_id: Optional[int] = None) -> Optional[str]:
    """Centralized customer name validation (required, unique per tenant)."""
    if not name:
        return "El nombre del cliente es obligatorio"
        
    query = session.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        func.lower(Customer.name) == name.lower()
    )
    if exclude_id:
        query = query.filter(Customer.id != exclude_id)
        
    if query.first():
        return f"Ya existe un cliente con el nombre '{name}'"
    return None

@customers_bp.route('/check-name', methods=['POST'])
@require_login
@require_tenant
def check_name() -> str:
    """Check if customer name already exists in the tenant."""
    session = get_session()
    name = request.form.get('name', '').strip()
    cust_id_str = request.form.get('customer_id', '').strip()
    
    if not name:
        return render_template('customers/_check_name.html', error=None)
        
    cust_id = int(cust_id_str) if cust_id_str and cust_id_str.isdigit() else None
    error = _validate_customer_name(session, g.tenant_id, name, cust_id)
    
    return render_template('customers/_check_name.html', error=error)


@customers_bp.route('/search', methods=['GET'])
@require_login
@require_tenant
def search_customers() -> Dict[str, Any]:
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
        current_app.logger.error(f"Error searching customers: {e}")
        return {'results': [], 'error': 'Error en la búsqueda'}


@customers_bp.route('/quick-create', methods=['POST'])
@require_login
@require_tenant
def quick_create() -> Tuple[Union[str, Response], int]:
    """Quick create customer from POS (HTMX endpoint)."""
    session = get_session()
    data = _get_customer_data_from_form()
    
    error = _validate_customer_name(session, g.tenant_id, data['name'])
    if error:
        raise BusinessLogicError(error)
        
    try:
        customer = Customer(tenant_id=g.tenant_id, **data)
        session.add(customer)
        session.commit()
        
        from app.services.customer_service import get_or_create_default_customer_id
        customers = session.query(Customer).filter(Customer.tenant_id == g.tenant_id).order_by(Customer.name).all()
        default_customer_id = get_or_create_default_customer_id(session, g.tenant_id)
        
        return render_template(
            'sales/_customer_selector.html',
            customers=customers,
            default_customer_id=default_customer_id,
            selected_customer_id=customer.id,
            success_message=f'Cliente "{customer.name}" creado exitosamente'
        ), 200
        
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error in quick_create customer: {e}")
        raise BusinessLogicError(f'Error al crear cliente: {str(e)}')



@customers_bp.route('/list')
@require_login
@require_tenant
def list_customers_alt() -> Union[str, Response]:
    """List all customers (alias)."""
    return list_customers()


@customers_bp.route('/')
@require_login
@require_tenant
def list_customers() -> str:
    """List all customers (tenant-scoped)."""
    session = get_session()
    
    try:
        search_query = request.args.get('q', '').strip()
        query = session.query(Customer).filter(Customer.tenant_id == g.tenant_id)
        
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
        current_app.logger.error(f"Error loading customers: {e}")
        raise BusinessLogicError(f'Error al cargar clientes: {str(e)}')


@customers_bp.route('/new', methods=['GET'])
@require_login
@require_tenant
def new_customer() -> str:
    """Show form to create a new customer."""
    return render_template('customers/form.html', customer=None, action='new')


@customers_bp.route('/new', methods=['POST'])
@require_login
@require_tenant
def create_customer() -> Union[str, Response]:
    """Create a new customer (tenant-scoped)."""
    session = get_session()
    data = _get_customer_data_from_form()
    
    error = _validate_customer_name(session, g.tenant_id, data['name'])
    if error:
        raise BusinessLogicError(error)
    
    try:
        customer = Customer(tenant_id=g.tenant_id, **data)
        session.add(customer)
        session.commit()
        flash(f'Cliente "{customer.name}" creado exitosamente', 'success')
        return redirect(url_for('customers.list_customers'))
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error creating customer: {e}")
        raise BusinessLogicError(f'Error al crear cliente: {str(e)}')


@customers_bp.route('/<int:customer_id>/edit', methods=['GET'])
@require_login
@require_tenant
def edit_customer(customer_id: int) -> Union[str, Response]:
    """Show form to edit a customer (tenant-scoped)."""
    session = get_session()
    customer = session.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == g.tenant_id).first()
    if not customer:
        abort(404)
    return render_template('customers/form.html', customer=customer, action='edit')


@customers_bp.route('/<int:customer_id>/edit', methods=['POST'])
@require_login
@require_tenant
def update_customer(customer_id: int) -> Union[str, Response]:
    """Update a customer (tenant-scoped)."""
    session = get_session()
    customer = session.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == g.tenant_id).first()
    if not customer:
        raise NotFoundError('Cliente no encontrado')
        
    data = _get_customer_data_from_form()
    error = _validate_customer_name(session, g.tenant_id, data['name'], customer_id)
    if error:
        raise BusinessLogicError(error)
    
    try:
        for key, value in data.items():
            setattr(customer, key, value)
        session.commit()
        flash(f'Cliente "{customer.name}" actualizado exitosamente', 'success')
        return redirect(url_for('customers.list_customers'))
    except (BusinessLogicError, NotFoundError) as e:
        session.rollback()
        raise e
    except Exception as e:
        session.rollback()
        current_app.logger.error(f"Error updating customer {customer_id}: {e}")
        raise BusinessLogicError(f'Error al actualizar cliente: {str(e)}')


@customers_bp.route('/<int:customer_id>')
@require_login
@require_tenant
def view_customer(customer_id: int) -> Union[str, Response]:
    """View customer detail (tenant-scoped)."""
    session = get_session()
    customer = session.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == g.tenant_id).first()
    if not customer:
        abort(404)
    return render_template('customers/detail.html', customer=customer)


@customers_bp.route('/<int:customer_id>/delete', methods=['POST'])
@require_login
@require_tenant
def delete_customer(customer_id: int) -> Response:
    """Delete a customer (tenant-scoped)."""
    session = get_session()
    customer = session.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == g.tenant_id).first()
    
    if not customer:
        raise NotFoundError('Cliente no encontrado')
    
    customer_name = customer.name
    try:
        session.delete(customer)
        session.commit()
        flash(f'Cliente "{customer_name}" eliminado exitosamente', 'success')
        return redirect(url_for('customers.list_customers'))
    except IntegrityError:
        session.rollback()
        raise BusinessLogicError(f'No se puede eliminar el cliente "{customer_name}" porque tiene ventas o registros asociados.')
    except Exception as e:
        session.rollback()
        raise BusinessLogicError(f'Error al eliminar cliente: {str(e)}')
