from flask import Blueprint, render_template, request, flash, redirect, url_for, g, abort, Response, current_app
from app.exceptions import BusinessLogicError, NotFoundError
from typing import List, Dict, Optional, Union, Any, Tuple
from datetime import datetime, date
import calendar
from decimal import Decimal
from app.database import get_session
from app.models import FinanceLedger, LedgerType, LedgerReferenceType, PaymentMethod
from app.services.balance_service import (
    get_balance_series, get_default_date_range, get_totals,
    get_available_years, get_available_months, get_month_date_range,
    get_year_date_range, get_total_stock_value
)
from app.middleware import require_login, require_tenant

balance_bp = Blueprint('balance', __name__, url_prefix='/balance')


def _parse_int(value: Optional[str], default: Optional[int] = None) -> Optional[int]:
    """Safely parse integer from string."""
    if not value:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _resolve_date_range(view: str, db_session, tenant_id: int) -> Tuple[date, date, Dict[str, Any]]:
    """Resolve start/end dates and context variables based on view and request parameters."""
    year = _parse_int(request.args.get('year'))
    month = _parse_int(request.args.get('month'))
    day_param = request.args.get('day', '').strip()
    
    # Default return context
    ctx = {
        'selected_year': year,
        'selected_month': month,
        'selected_day': None,
        'available_months': [],
        'days_in_month': 31
    }

    today = date.today()

    if view == 'daily':
        # year/month defaults to current if missing
        if not year or not month:
            year, month = today.year, today.month
        
        if month < 1 or month > 12: month = today.month
        
        ctx['selected_year'], ctx['selected_month'] = year, month
        ctx['available_months'] = get_available_months(year, db_session, tenant_id)
        ctx['days_in_month'] = calendar.monthrange(year, month)[1]
        
        if day_param and day_param.lower() != 'all':
            try:
                # Try full date first
                d = datetime.strptime(day_param, '%Y-%m-%d').date()
                start = end = d
                ctx['selected_day'] = d
                # Sync year/month with selected date
                ctx['selected_year'], ctx['selected_month'] = d.year, d.month
            except ValueError:
                # Try day number
                day_num = _parse_int(day_param)
                if day_num and 1 <= day_num <= ctx['days_in_month']:
                    selected_date = date(year, month, day_num)
                    start = end = selected_date
                    ctx['selected_day'] = selected_date
                else:
                    start, end = get_month_date_range(year, month)
        else:
            start, end = get_month_date_range(year, month)

    elif view == 'monthly':
        if not year: year = today.year
        ctx['selected_year'] = year
        ctx['available_months'] = get_available_months(year, db_session, tenant_id)
        
        if month and 1 <= month <= 12:
            start, end = get_month_date_range(year, month)
            ctx['selected_month'] = month
        else:
            # "All" or invalid month
            start, end = get_year_date_range(year)
            ctx['selected_month'] = None

    else: # yearly
        if year:
            start, end = get_year_date_range(year)
            ctx['selected_year'] = year
        else:
            available_years = get_available_years(db_session, tenant_id)
            if available_years:
                start = date(min(available_years), 1, 1)
                end = date(max(available_years), 12, 31)
            else:
                start, end = get_year_date_range(today.year)
            ctx['selected_year'] = None

    return start, end, ctx


@balance_bp.route('/')
@require_login
@require_tenant
def index() -> str:
    """Show balance page with tabs and filters (tenant-scoped)."""
    db_session = get_session()
    
    try:
        # Get query params
        view = request.args.get('view', 'monthly')  # daily, monthly, yearly
        if view not in ['daily', 'monthly', 'yearly']:
            view = 'monthly'
            
        method = request.args.get('method', 'all').lower().strip()
        if method not in ['all', 'cash', 'transfer']:
            method = 'all'
            
        # Resolve dates and context
        start, end, ctx = _resolve_date_range(view, db_session, g.tenant_id)
        
        # Get data
        series = get_balance_series(view, start, end, db_session, g.tenant_id, method=method)
        totals = get_totals(series)
        stock_value = get_total_stock_value(db_session, g.tenant_id)
        available_years = get_available_years(db_session, g.tenant_id)
        
        return render_template(
            'balance/index.html',
            view=view,
            series=series,
            totals=totals,
            stock_value=stock_value,
            start=start.strftime('%Y-%m-%d'),
            end=end.strftime('%Y-%m-%d'),
            available_years=available_years,
            selected_method=method,
            **ctx
        )
        
    except Exception as e:
        current_app.logger.error(f"Error loading balance: {e}")
        raise BusinessLogicError(f'Error al cargar balance: {str(e)}')

