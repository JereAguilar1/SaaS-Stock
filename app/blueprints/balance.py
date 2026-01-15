"""Balance blueprint for financial reporting - Multi-Tenant."""
from flask import Blueprint, render_template, request, flash, redirect, url_for, g, abort
from datetime import datetime, date
from decimal import Decimal
import decimal
from app.database import get_session
from app.models import FinanceLedger, LedgerType, LedgerReferenceType, PaymentMethod
from app.services.balance_service import (
    get_balance_series, get_default_date_range, get_totals,
    get_available_years, get_available_months, get_month_date_range,
    get_year_date_range
)
from app.middleware import require_login, require_tenant

balance_bp = Blueprint('balance', __name__, url_prefix='/balance')


@balance_bp.route('/')
@require_login
@require_tenant
def index():
    """Show balance page with tabs and filters (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get query params
        view = request.args.get('view', 'monthly')  # daily, monthly, yearly
        start_str = request.args.get('start', '').strip()
        end_str = request.args.get('end', '').strip()
        
        # Get year and month params for daily view
        year_str = request.args.get('year', '').strip()
        month_str = request.args.get('month', '').strip()
        
        # Get payment method filter
        method = request.args.get('method', 'all').lower().strip()
        
        # Validate view
        if view not in ['daily', 'monthly', 'yearly']:
            view = 'monthly'
        
        # Validate method
        if method not in ['all', 'cash', 'transfer']:
            flash('Método de pago inválido. Mostrando todos.', 'info')
            method = 'all'
        
        # Get available years for filters (tenant-scoped)
        available_years = get_available_years(db_session, g.tenant_id)
        
        # Handle year/month filters for daily view
        selected_year = None
        selected_month = None
        available_months = []
        
        if view == 'daily':
            if year_str and month_str:
                try:
                    selected_year = int(year_str)
                    selected_month = int(month_str)
                    
                    if selected_month < 1 or selected_month > 12:
                        flash('Mes inválido. Debe estar entre 1 y 12.', 'warning')
                        selected_year = None
                        selected_month = None
                    
                    if selected_year and (selected_year < 1900 or selected_year > 2100):
                        flash('Año inválido.', 'warning')
                        selected_year = None
                        selected_month = None
                    
                    if selected_year and selected_month:
                        start, end = get_month_date_range(selected_year, selected_month)
                        available_months = get_available_months(selected_year, db_session, g.tenant_id)
                        
                except (ValueError, TypeError):
                    flash('Año o mes inválido.', 'warning')
                    selected_year = None
                    selected_month = None
            
            if not (selected_year and selected_month):
                if start_str and end_str:
                    try:
                        start = datetime.strptime(start_str, '%Y-%m-%d').date()
                        end = datetime.strptime(end_str, '%Y-%m-%d').date()
                        
                        if start > end:
                            flash('La fecha de inicio debe ser menor o igual a la fecha de fin', 'warning')
                            start, end = get_default_date_range(view)
                    except ValueError:
                        flash('Formato de fecha inválido. Use YYYY-MM-DD', 'warning')
                        start, end = get_default_date_range(view)
                else:
                    today = date.today()
                    if available_years:
                        current_year = today.year
                        current_month = today.month
                        
                        if current_year in available_years:
                            available_months = get_available_months(current_year, db_session, g.tenant_id)
                            if current_month in available_months:
                                selected_year = current_year
                                selected_month = current_month
                            elif available_months:
                                selected_year = current_year
                                selected_month = available_months[-1]
                            else:
                                selected_year = available_years[0]
                                available_months = get_available_months(selected_year, db_session, g.tenant_id)
                                selected_month = available_months[-1] if available_months else 12
                        else:
                            selected_year = available_years[0]
                            available_months = get_available_months(selected_year, db_session, g.tenant_id)
                            selected_month = available_months[-1] if available_months else 12
                        
                        start, end = get_month_date_range(selected_year, selected_month)
                    else:
                        selected_year = today.year
                        selected_month = today.month
                        start, end = get_month_date_range(selected_year, selected_month)
        
        elif view == 'monthly':
            if year_str:
                try:
                    selected_year = int(year_str)
                    
                    if selected_year < 1900 or selected_year > 2100:
                        flash('Año inválido.', 'warning')
                        selected_year = None
                    
                    if selected_year:
                        start, end = get_year_date_range(selected_year)
                        
                except (ValueError, TypeError):
                    flash('Año inválido.', 'warning')
                    selected_year = None
            
            if not selected_year:
                if start_str and end_str:
                    try:
                        start = datetime.strptime(start_str, '%Y-%m-%d').date()
                        end = datetime.strptime(end_str, '%Y-%m-%d').date()
                        
                        if start > end:
                            flash('La fecha de inicio debe ser menor o igual a la fecha de fin', 'warning')
                            start, end = get_default_date_range(view)
                    except ValueError:
                        flash('Formato de fecha inválido. Use YYYY-MM-DD', 'warning')
                        start, end = get_default_date_range(view)
                else:
                    today = date.today()
                    if available_years:
                        current_year = today.year
                        
                        if current_year in available_years:
                            selected_year = current_year
                        else:
                            selected_year = available_years[0]
                        
                        start, end = get_year_date_range(selected_year)
                    else:
                        selected_year = today.year
                        start, end = get_year_date_range(selected_year)
        
        else:
            if start_str and end_str:
                try:
                    start = datetime.strptime(start_str, '%Y-%m-%d').date()
                    end = datetime.strptime(end_str, '%Y-%m-%d').date()
                    
                    if start > end:
                        flash('La fecha de inicio debe ser menor o igual a la fecha de fin', 'warning')
                        start, end = get_default_date_range(view)
                except ValueError:
                    flash('Formato de fecha inválido. Use YYYY-MM-DD', 'warning')
                    start, end = get_default_date_range(view)
            else:
                start, end = get_default_date_range(view)
        
        # Get balance series (tenant-scoped)
        series = get_balance_series(view, start, end, db_session, g.tenant_id, method=method)
        
        # Calculate totals
        totals = get_totals(series)
        
        # Format dates for input fields
        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        
        return render_template(
            'balance/index.html',
            view=view,
            series=series,
            totals=totals,
            start=start_str,
            end=end_str,
            available_years=available_years,
            selected_year=selected_year,
            selected_month=selected_month,
            available_months=available_months,
            selected_method=method
        )
        
    except Exception as e:
        flash(f'Error al cargar balance: {str(e)}', 'danger')
        
        start, end = get_default_date_range('monthly')
        return render_template(
            'balance/index.html',
            view='monthly',
            series=[],
            totals={'total_income': 0, 'total_expense': 0, 'total_net': 0},
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            available_years=[],
            selected_year=None,
            selected_month=None,
            available_months=[]
        )


@balance_bp.route('/ledger')
@require_login
@require_tenant
def list_ledger():
    """List all finance ledger entries (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get query params
        entry_type = request.args.get('type', '').upper()
        start_str = request.args.get('start', '').strip()
        end_str = request.args.get('end', '').strip()
        method = request.args.get('method', 'all').lower().strip()
        
        # Validate method
        if method not in ['all', 'cash', 'transfer']:
            flash('Método de pago inválido. Mostrando todos.', 'info')
            method = 'all'
        
        # Build query - filter by tenant FIRST
        query = db_session.query(FinanceLedger).filter(
            FinanceLedger.tenant_id == g.tenant_id
        )
        
        # Filter by type
        if entry_type and entry_type in ['INCOME', 'EXPENSE']:
            query = query.filter(FinanceLedger.type == LedgerType[entry_type])
        
        # Filter by payment method
        if method == 'cash':
            query = query.filter(FinanceLedger.payment_method == 'CASH')
        elif method == 'transfer':
            query = query.filter(FinanceLedger.payment_method == 'TRANSFER')
        
        # Filter by date range
        if start_str:
            try:
                start_dt = datetime.strptime(start_str, '%Y-%m-%d')
                query = query.filter(FinanceLedger.datetime >= start_dt)
            except ValueError:
                pass
        
        if end_str:
            try:
                end_dt = datetime.strptime(end_str, '%Y-%m-%d')
                end_dt = end_dt.replace(hour=23, minute=59, second=59)
                query = query.filter(FinanceLedger.datetime <= end_dt)
            except ValueError:
                pass
        
        # Order by datetime desc
        entries = query.order_by(FinanceLedger.datetime.desc()).all()
        
        return render_template(
            'balance/ledger_list.html',
            entries=entries,
            entry_type=entry_type,
            selected_method=method,
            start=start_str,
            end=end_str
        )
        
    except Exception as e:
        flash(f'Error al cargar libro mayor: {str(e)}', 'danger')
        return render_template('balance/ledger_list.html', entries=[], entry_type='', start='', end='')


@balance_bp.route('/ledger/new', methods=['GET'])
@require_login
@require_tenant
def new_ledger():
    """Show form to create manual ledger entry."""
    today = date.today().strftime('%Y-%m-%d')
    return render_template('balance/ledger_form.html', today=today)


@balance_bp.route('/ledger/new', methods=['POST'])
@require_login
@require_tenant
def create_ledger():
    """Create manual ledger entry (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get form data
        entry_type = request.form.get('type', '').upper()
        amount_str = request.form.get('amount', '').strip()
        datetime_str = request.form.get('datetime', '').strip()
        category = request.form.get('category', '').strip() or None
        notes = request.form.get('notes', '').strip() or None
        payment_method = request.form.get('payment_method', 'CASH').upper()
        
        # Validations
        if entry_type not in ['INCOME', 'EXPENSE']:
            flash('Tipo de movimiento inválido', 'danger')
            return redirect(url_for('balance.new_ledger'))
        
        if payment_method not in ['CASH', 'TRANSFER']:
            flash('Método de pago inválido', 'danger')
            return redirect(url_for('balance.new_ledger'))
        
        if not amount_str:
            flash('El monto es requerido', 'danger')
            return redirect(url_for('balance.new_ledger'))
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                flash('El monto debe ser mayor a 0', 'danger')
                return redirect(url_for('balance.new_ledger'))
        except (ValueError, decimal.InvalidOperation):
            flash('Monto inválido', 'danger')
            return redirect(url_for('balance.new_ledger'))
        
        # Parse datetime
        if datetime_str:
            try:
                entry_datetime = datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M')
            except ValueError:
                flash('Formato de fecha/hora inválido', 'danger')
                return redirect(url_for('balance.new_ledger'))
        else:
            entry_datetime = datetime.now()
        
        # Create ledger entry with tenant_id
        from app.models import normalize_payment_method
        payment_method_normalized = normalize_payment_method(payment_method)
        
        ledger = FinanceLedger(
            tenant_id=g.tenant_id,  # CRITICAL
            datetime=entry_datetime,
            type=LedgerType[entry_type],
            amount=amount,
            reference_type=LedgerReferenceType.MANUAL,
            reference_id=None,
            category=category,
            notes=notes,
            payment_method=payment_method_normalized
        )
        
        db_session.add(ledger)
        db_session.commit()
        
        payment_label = 'Efectivo' if payment_method == 'CASH' else 'Transferencia'
        flash(f'Movimiento manual de tipo {entry_type} por ${amount} ({payment_label}) registrado exitosamente', 'success')
        return redirect(url_for('balance.list_ledger'))
        
    except Exception as e:
        db_session.rollback()
        flash(f'Error al crear movimiento: {str(e)}', 'danger')
        return redirect(url_for('balance.new_ledger'))
