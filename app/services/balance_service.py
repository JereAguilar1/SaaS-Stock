"""Balance service - Financial reporting."""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Tuple, Optional
from calendar import monthrange

from flask import current_app
from sqlalchemy import func, case, extract
from sqlalchemy.orm import Session

from app.models import FinanceLedger, LedgerType, Product, ProductStock
from app.services.cache_service import get_cache

logger = logging.getLogger(__name__)


def _build_balance_cache_key(view: str, start: date, end: date, method: str) -> str:
    """Build cache key for balance queries."""
    return f"series:{view}:{start.isoformat()}:{end.isoformat()}:{method}"


def get_balance_series(
    view: str, 
    start: date, 
    end: date, 
    session: Session, 
    tenant_id: int, 
    method: str = 'all'
) -> List[Dict[str, Any]]:
    """
    Get balance series (income, expense, net) grouped by period (tenant-scoped).
    """
    cache_key = _build_balance_cache_key(view, start, end, method)
    
    # Try cache
    try:
        cache = get_cache()
        cached_result = cache.get(tenant_id, 'balance', cache_key)
        if cached_result is not None:
            return cached_result
    except Exception as e:
        logger.debug(f"[CACHE] Balance error (continuing): {e}")
    
    granularity = {'daily': 'day', 'monthly': 'month', 'yearly': 'year'}.get(view, 'month')
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(end, datetime.max.time())
    
    period_col = func.date_trunc(granularity, FinanceLedger.datetime).label('period')
    income_sum = func.sum(case((FinanceLedger.type == LedgerType.INCOME, FinanceLedger.amount), else_=0)).label('income')
    expense_sum = func.sum(case((FinanceLedger.type == LedgerType.EXPENSE, FinanceLedger.amount), else_=0)).label('expense')
    
    query = session.query(period_col, income_sum, expense_sum).filter(
        FinanceLedger.tenant_id == tenant_id,
        FinanceLedger.datetime >= start_dt,
        FinanceLedger.datetime <= end_dt
    )
    
    if method == 'cash':
        query = query.filter(FinanceLedger.payment_method == 'CASH')
    elif method == 'transfer':
        query = query.filter(FinanceLedger.payment_method == 'TRANSFER')
    
    results = query.group_by(period_col).order_by(period_col.asc()).all()
    
    series = []
    for row in results:
        inc = Decimal(str(row.income or 0))
        exp = Decimal(str(row.expense or 0))
        
        label_fmt = '%Y-%m-%d' if granularity == 'day' else '%Y-%m' if granularity == 'month' else '%Y'
        
        series.append({
            'period': row.period,
            'period_label': row.period.strftime(label_fmt),
            'income': inc,
            'expense': exp,
            'net': inc - exp
        })
    
    # Save to cache
    try:
        ttl = current_app.config.get('CACHE_BALANCE_TTL', 60)
        get_cache().set(tenant_id, 'balance', cache_key, series, ttl=ttl)
    except Exception as e:
        logger.debug(f"[CACHE] Balance save error: {e}")
    
    return series


def get_default_date_range(view: str) -> Tuple[date, date]:
    """Get default date range based on view."""
    today = date.today()
    if view == 'daily':
        return today - timedelta(days=30), today
    elif view == 'monthly':
        return today - timedelta(days=365), today
    return today.replace(year=today.year - 5), today


def get_totals(series: List[Dict[str, Any]]) -> Dict[str, Decimal]:
    """Calculate totals from a balance series."""
    total_income = Decimal('0.00')
    total_expense = Decimal('0.00')
    
    for item in series:
        inc = item['income']
        exp = item['expense']
        total_income += inc if isinstance(inc, Decimal) else Decimal(str(inc or 0))
        total_expense += exp if isinstance(exp, Decimal) else Decimal(str(exp or 0))
    
    return {
        'total_income': total_income,
        'total_expense': total_expense,
        'total_net': total_income - total_expense
    }


def get_available_years(session: Session, tenant_id: int) -> List[int]:
    """Get list of years with finance data (tenant-scoped)."""
    yr_col = extract('year', FinanceLedger.datetime)
    results = session.query(yr_col).filter(FinanceLedger.tenant_id == tenant_id).distinct().order_by(yr_col.desc()).all()
    return [int(row[0]) for row in results]


def get_available_months(year: int, session: Session, tenant_id: int) -> List[int]:
    """Get list of months with finance data (tenant-scoped)."""
    mo_col = extract('month', FinanceLedger.datetime)
    results = session.query(mo_col).filter(
        FinanceLedger.tenant_id == tenant_id,
        extract('year', FinanceLedger.datetime) == year
    ).distinct().order_by(mo_col.asc()).all()
    return [int(row[0]) for row in results]


def get_month_date_range(year: int, month: int) -> Tuple[date, date]:
    """Get start and end dates for a specific month."""
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def get_year_date_range(year: int) -> Tuple[date, date]:
    """Get start and end dates for a specific year."""
    return date(year, 1, 1), date(year, 12, 31)


def get_total_stock_value(session: Session, tenant_id: int) -> Decimal:
    """Calcula el valor total del inventario (Fondo de Comercio)."""
    try:
        val = session.query(func.sum(ProductStock.on_hand_qty * Product.cost)).join(
            Product, ProductStock.product_id == Product.id
        ).filter(
            Product.tenant_id == tenant_id,
            Product.active == True
        ).scalar()
        return Decimal(str(val or 0)).quantize(Decimal('0.01'))
    except Exception as e:
        logger.error(f"Error stock value tenant {tenant_id}: {e}")
        return Decimal('0.00')
