"""Balance service for financial reporting - Multi-Tenant."""
from datetime import datetime, date, timedelta
from decimal import Decimal
from sqlalchemy import func, case, extract
from app.models import FinanceLedger, LedgerType
import logging

logger = logging.getLogger(__name__)


def _build_balance_cache_key(view: str, start: date, end: date, method: str) -> str:
    """Build cache key for balance queries (PASO 8)."""
    return f"series:{view}:{start.isoformat()}:{end.isoformat()}:{method}"


def get_balance_series(view: str, start: date, end: date, session, tenant_id: int, method: str = 'all'):
    """
    Get balance series (income, expense, net) grouped by period (tenant-scoped).
    
    Uses Redis cache (PASO 8) with TTL from config.
    Cache key includes tenant_id to prevent data leaks.
    
    Args:
        view: 'daily', 'monthly', or 'yearly'
        start: Start date (inclusive)
        end: End date (inclusive)
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant filtering)
        method: 'all', 'cash', or 'transfer' - filter by payment method
        
    Returns:
        List of dicts with keys:
        - period: date/string of the period
        - period_label: formatted string for display
        - income: Decimal
        - expense: Decimal
        - net: Decimal
    """
    
    # PASO 8: Try cache first
    try:
        from flask import current_app
        from app.services.cache_service import get_cache
        
        cache = get_cache()
        cache_key = _build_balance_cache_key(view, start, end, method)
        cached_result = cache.get(tenant_id, 'balance', cache_key)
        
        if cached_result is not None:
            logger.debug(f"[CACHE] Balance HIT: tenant={tenant_id}, key={cache_key}")
            return cached_result
        
        logger.debug(f"[CACHE] Balance MISS: tenant={tenant_id}, key={cache_key}")
        
    except Exception as e:
        logger.debug(f"[CACHE] Balance error (continuing without cache): {e}")
    
    # Map view to date_trunc granularity
    granularity_map = {
        'daily': 'day',
        'monthly': 'month',
        'yearly': 'year'
    }
    
    granularity = granularity_map.get(view, 'month')
    
    # Convert dates to datetime for comparison
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    
    # Build query with date_trunc and aggregation
    period_col = func.date_trunc(granularity, FinanceLedger.datetime).label('period')
    
    income_sum = func.sum(
        case(
            (FinanceLedger.type == LedgerType.INCOME, FinanceLedger.amount),
            else_=0
        )
    ).label('income')
    
    expense_sum = func.sum(
        case(
            (FinanceLedger.type == LedgerType.EXPENSE, FinanceLedger.amount),
            else_=0
        )
    ).label('expense')
    
    query = (
        session.query(
            period_col,
            income_sum,
            expense_sum
        )
        .filter(FinanceLedger.tenant_id == tenant_id)  # CRITICAL: tenant filter FIRST
        .filter(FinanceLedger.datetime >= start_dt)
        .filter(FinanceLedger.datetime <= end_dt)
    )
    
    # Apply payment method filter
    if method == 'cash':
        query = query.filter(FinanceLedger.payment_method == 'CASH')
    elif method == 'transfer':
        query = query.filter(FinanceLedger.payment_method == 'TRANSFER')
    
    query = query.group_by(period_col).order_by(period_col.asc())
    
    results = query.all()
    
    # Format results
    series = []
    for row in results:
        period = row.period
        income = Decimal(str(row.income)) if row.income else Decimal('0.00')
        expense = Decimal(str(row.expense)) if row.expense else Decimal('0.00')
        net = income - expense
        
        # Format period label based on granularity
        if granularity == 'day':
            period_label = period.strftime('%Y-%m-%d')
        elif granularity == 'month':
            period_label = period.strftime('%Y-%m')
        else:  # year
            period_label = period.strftime('%Y')
        
        series.append({
            'period': period,
            'period_label': period_label,
            'income': income,
            'expense': expense,
            'net': net
        })
    
    # PASO 8: Cache the result
    try:
        from flask import current_app
        from app.services.cache_service import get_cache
        
        cache = get_cache()
        ttl = current_app.config.get('CACHE_BALANCE_TTL', 60)
        cache.set(tenant_id, 'balance', cache_key, series, ttl=ttl)
        logger.debug(f"[CACHE] Balance CACHED: tenant={tenant_id}, key={cache_key}, ttl={ttl}s")
        
    except Exception as e:
        logger.debug(f"[CACHE] Balance cache set error (continuing): {e}")
    
    return series


def get_default_date_range(view: str):
    """
    Get default date range based on view.
    
    Args:
        view: 'daily', 'monthly', or 'yearly'
        
    Returns:
        Tuple of (start_date, end_date)
    """
    today = date.today()
    
    if view == 'daily':
        # Last 30 days
        start = today - timedelta(days=30)
        end = today
    elif view == 'monthly':
        # Last 12 months
        start = today - timedelta(days=365)
        end = today
    else:  # yearly
        # Last 5 years
        start = today.replace(year=today.year - 5)
        end = today
    
    return start, end


def get_totals(series):
    """
    Calculate totals from a balance series.
    
    Args:
        series: List returned by get_balance_series
        
    Returns:
        Dict with keys: total_income, total_expense, total_net
    """
    total_income = Decimal('0.00')
    total_expense = Decimal('0.00')
    
    for item in series:
        total_income += item['income']
        total_expense += item['expense']
    
    total_net = total_income - total_expense
    
    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'total_net': total_net
    }


def get_available_years(session, tenant_id: int):
    """
    Get list of years with finance_ledger data (tenant-scoped).
    
    Args:
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant filtering)
        
    Returns:
        List of integers (years) in descending order
    """
    query = (
        session.query(extract('year', FinanceLedger.datetime).label('year'))
        .filter(FinanceLedger.tenant_id == tenant_id)  # CRITICAL
        .distinct()
        .order_by(extract('year', FinanceLedger.datetime).desc())
    )
    
    results = query.all()
    return [int(row.year) for row in results]


def get_available_months(year: int, session, tenant_id: int):
    """
    Get list of months with finance_ledger data for a specific year (tenant-scoped).
    
    Args:
        year: Year (int)
        session: SQLAlchemy session
        tenant_id: Tenant ID (REQUIRED for multi-tenant filtering)
        
    Returns:
        List of integers (1-12) in ascending order
    """
    query = (
        session.query(extract('month', FinanceLedger.datetime).label('month'))
        .filter(FinanceLedger.tenant_id == tenant_id)  # CRITICAL
        .filter(extract('year', FinanceLedger.datetime) == year)
        .distinct()
        .order_by(extract('month', FinanceLedger.datetime).asc())
    )
    
    results = query.all()
    return [int(row.month) for row in results]


def get_month_date_range(year: int, month: int):
    """
    Get start and end dates for a specific month.
    
    Args:
        year: Year (int)
        month: Month (1-12)
        
    Returns:
        Tuple of (start_date, end_date)
        start_date: First day of month
        end_date: Last day of month
    """
    from calendar import monthrange
    
    start = date(year, month, 1)
    last_day = monthrange(year, month)[1]
    end = date(year, month, last_day)
    
    return start, end


def get_year_date_range(year: int):
    """
    Get start and end dates for a specific year.
    
    Args:
        year: Year (int)
        
    Returns:
        Tuple of (start_date, end_date)
        start_date: First day of year (Jan 1)
        end_date: Last day of year (Dec 31)
    """
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    
    return start, end
