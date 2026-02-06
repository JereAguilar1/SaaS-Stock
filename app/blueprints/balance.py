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
    get_year_date_range, get_total_stock_value
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
        
        # Get year, month, and day params
        year_str = request.args.get('year', '').strip()
        month_str = request.args.get('month', '').strip()
        day_str = request.args.get('day', '').strip()
        
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
        
        # Initialize filter variables
        selected_year = None
        selected_month = None
        selected_day = None
        available_months = []
        days_in_month = 31  # Por defecto
        
        if view == 'daily':
            # Procesar año y mes primero
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
                        available_months = get_available_months(selected_year, db_session, g.tenant_id)
                        # Calcular días en el mes
                        import calendar
                        days_in_month = calendar.monthrange(selected_year, selected_month)[1]
                        
                except (ValueError, TypeError):
                    flash('Año o mes inválido.', 'warning')
                    selected_year = None
                    selected_month = None
            
            # Procesar selector de día
            if day_str:
                if day_str.lower() == 'all':
                    # Opción "Todos": Mostrar todos los días del mes
                    if selected_year and selected_month:
                        start, end = get_month_date_range(selected_year, selected_month)
                        selected_day = None  # Indica "Todos"
                    else:
                        # Si no hay año/mes, usar mes actual
                        today = date.today()
                        selected_year = today.year
                        selected_month = today.month
                        start, end = get_month_date_range(selected_year, selected_month)
                        available_months = get_available_months(selected_year, db_session, g.tenant_id)
                        import calendar
                        days_in_month = calendar.monthrange(selected_year, selected_month)[1]
                        selected_day = None
                else:
                    # Día específico (puede ser número o fecha completa)
                    try:
                        # Intentar parsear como fecha completa primero
                        selected_day = datetime.strptime(day_str, '%Y-%m-%d').date()
                        start = selected_day
                        end = selected_day
                        # Extraer año y mes del día seleccionado
                        selected_year = selected_day.year
                        selected_month = selected_day.month
                        available_months = get_available_months(selected_year, db_session, g.tenant_id)
                        import calendar
                        days_in_month = calendar.monthrange(selected_year, selected_month)[1]
                    except ValueError:
                        # Intentar como número de día
                        try:
                            day_num = int(day_str)
                            if selected_year and selected_month:
                                import calendar
                                days_in_month = calendar.monthrange(selected_year, selected_month)[1]
                                if 1 <= day_num <= days_in_month:
                                    selected_day = date(selected_year, selected_month, day_num)
                                    start = selected_day
                                    end = selected_day
                                else:
                                    flash(f'Día inválido para el mes seleccionado (1-{days_in_month}).', 'warning')
                                    selected_day = None
                            else:
                                flash('Debe seleccionar año y mes primero.', 'warning')
                                selected_day = None
                        except (ValueError, TypeError):
                            flash('Formato de día inválido.', 'warning')
                            selected_day = None
            
            # Valor por defecto: TODOS los días del mes actual
            if not day_str or (not selected_day and day_str.lower() != 'all'):
                if not (selected_year and selected_month):
                    today = date.today()
                    selected_year = today.year
                    selected_month = today.month
                    available_months = get_available_months(selected_year, db_session, g.tenant_id)
                    import calendar
                    days_in_month = calendar.monthrange(selected_year, selected_month)[1]
                start, end = get_month_date_range(selected_year, selected_month)
                selected_day = None  # Por defecto muestra Todos
        
        elif view == 'monthly':
            # Procesar año primero
            if year_str:
                try:
                    selected_year = int(year_str)
                    
                    if selected_year < 1900 or selected_year > 2100:
                        flash('Año inválido.', 'warning')
                        selected_year = None
                    
                    if selected_year:
                        available_months = get_available_months(selected_year, db_session, g.tenant_id)
                        
                except (ValueError, TypeError):
                    flash('Año inválido.', 'warning')
                    selected_year = None
            
            # Procesar selector de mes
            if month_str:
                if month_str.lower() == 'all':
                    # Opción "TODOS": Mostrar todos los meses del año
                    if selected_year:
                        start, end = get_year_date_range(selected_year)
                        selected_month = None  # Indica "TODOS"
                    else:
                        # Si no hay año, usar año actual
                        today = date.today()
                        selected_year = today.year
                        start, end = get_year_date_range(selected_year)
                        available_months = get_available_months(selected_year, db_session, g.tenant_id)
                        selected_month = None
                else:
                    # Mes específico
                    try:
                        selected_month = int(month_str)
                        
                        if selected_month < 1 or selected_month > 12:
                            flash('Mes inválido. Debe estar entre 1 y 12.', 'warning')
                            selected_month = None
                        
                        if selected_month:
                            if not selected_year:
                                selected_year = date.today().year
                                available_months = get_available_months(selected_year, db_session, g.tenant_id)
                            start, end = get_month_date_range(selected_year, selected_month)
                            
                    except (ValueError, TypeError):
                        flash('Mes inválido.', 'warning')
                        selected_month = None
            
            # Valor por defecto: TODOS los meses del año actual
            if not month_str or (not selected_month and month_str.lower() != 'all'):
                if not selected_year:
                    today = date.today()
                    selected_year = today.year
                    available_months = get_available_months(selected_year, db_session, g.tenant_id)
                start, end = get_year_date_range(selected_year)
                selected_month = None  # Por defecto muestra TODOS
        
        else:  # yearly
            # Procesar selector de año
            if year_str:
                if year_str.lower() == 'all':
                    # Opción "TODOS": Mostrar todos los años disponibles
                    if available_years:
                        start = date(min(available_years), 1, 1)
                        end = date(max(available_years), 12, 31)
                        selected_year = None  # Indica "TODOS"
                    else:
                        # Fallback: año actual si no hay datos
                        today = date.today()
                        selected_year = today.year
                        start, end = get_year_date_range(selected_year)
                else:
                    # Año específico
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
            
            # Valor por defecto: año actual (NO todos los años)
            if not year_str or (not selected_year and year_str.lower() != 'all'):
                today = date.today()
                selected_year = today.year
                start, end = get_year_date_range(selected_year)
        
        # Get balance series (tenant-scoped)
        series = get_balance_series(view, start, end, db_session, g.tenant_id, method=method)
        
        # Calculate totals
        totals = get_totals(series)
        
        # Calculate Fondo de Comercio (stock value)
        stock_value = get_total_stock_value(db_session, g.tenant_id)
        
        # Format dates for input fields
        start_str = start.strftime('%Y-%m-%d')
        end_str = end.strftime('%Y-%m-%d')
        
        return render_template(
            'balance/index.html',
            view=view,
            series=series,
            totals=totals,
            stock_value=stock_value,
            start=start_str,
            end=end_str,
            available_years=available_years,
            selected_year=selected_year,
            selected_month=selected_month,
            selected_day=selected_day,  # Pasar el objeto date completo
            available_months=available_months,
            selected_method=method,
            days_in_month=days_in_month
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

