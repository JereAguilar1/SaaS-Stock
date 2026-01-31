"""
Dashboard service for multi-tenant SaaS.
Provides aggregated metrics and data for the dashboard view.
"""

from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func, case, and_, or_
from app.models import (
    FinanceLedger, Sale, Product, ProductStock, 
    Category, UOM, LedgerType, SaleStatus
)


def get_dashboard_data(session, tenant_id: int, start_dt: datetime, end_dt: datetime) -> dict:
    """
    Get all dashboard data for a tenant for a specific date range.
    
    Args:
        session: SQLAlchemy session
        tenant_id: Current tenant ID
        start_dt: Start datetime (inclusive)
        end_dt: End datetime (exclusive)
    
    Returns:
        dict with keys:
            - income_today: Decimal
            - expense_today: Decimal
            - balance_today: Decimal
            - product_count: int
            - low_stock_products: list of dicts
            - recent_sales: list of Sale objects
    """
    
    # 1. Get Income/Expense/Balance from finance_ledger
    financial_data = session.query(
        func.coalesce(
            func.sum(
                case(
                    (FinanceLedger.type == LedgerType.INCOME, FinanceLedger.amount),
                    else_=0
                )
            ),
            0
        ).label('income_today'),
        func.coalesce(
            func.sum(
                case(
                    (FinanceLedger.type == LedgerType.EXPENSE, FinanceLedger.amount),
                    else_=0
                )
            ),
            0
        ).label('expense_today')
    ).filter(
        FinanceLedger.tenant_id == tenant_id,
        FinanceLedger.datetime >= start_dt,
        FinanceLedger.datetime < end_dt
    ).first()
    
    # Safe conversion to Decimal (handle None)
    income_today = Decimal(str(financial_data.income_today)) if financial_data and financial_data.income_today else Decimal('0')
    expense_today = Decimal(str(financial_data.expense_today)) if financial_data and financial_data.expense_today else Decimal('0')
    balance_today = income_today - expense_today
    
    # 2. Get Product Count (only active products)
    product_count = session.query(func.count(Product.id)).filter(
        Product.tenant_id == tenant_id,
        Product.active == True
    ).scalar() or 0
    
    # 3. Get Low Stock Products
    # Join product with product_stock, filter by tenant and stock conditions
    low_stock_products = session.query(
        Product.id,
        Product.name,
        Product.min_stock_qty,
        ProductStock.on_hand_qty,
        Category.name.label('category_name'),
        UOM.symbol.label('uom_symbol')
    ).join(
        ProductStock, Product.id == ProductStock.product_id
    ).outerjoin(
        Category, Product.category_id == Category.id
    ).outerjoin(
        UOM, Product.uom_id == UOM.id
    ).filter(
        Product.tenant_id == tenant_id,
        Product.active == True,
        Product.min_stock_qty > 0,
        ProductStock.on_hand_qty <= Product.min_stock_qty
    ).order_by(
        # Order by criticality: (current / min) ratio, then by absolute quantity
        (ProductStock.on_hand_qty / func.nullif(Product.min_stock_qty, 0)).asc(),
        ProductStock.on_hand_qty.asc()
    ).limit(10).all()
    
    # Convert to list of dicts
    # Convert to list of dicts with safe type conversion
    low_stock_list = []
    for row in low_stock_products:
        try:
            current = float(row.on_hand_qty or 0)
            minimum = float(row.min_stock_qty or 0)
            percentage = (current / minimum * 100) if minimum > 0 else 0
            
            low_stock_list.append({
                'id': row.id,
                'name': row.name,
                'on_hand_qty': current,
                'min_stock_qty': minimum,
                'category_name': row.category_name or 'Sin categoría',
                'uom_symbol': row.uom_symbol or 'un',
                'percentage': percentage
            })
        except Exception:
            continue
    
    # 4. Get Recent Sales (last 5 confirmed sales)
    recent_sales = session.query(Sale).filter(
        Sale.tenant_id == tenant_id,
        Sale.status == SaleStatus.CONFIRMED
    ).order_by(
        Sale.datetime.desc()
    ).limit(5).all()
    
    return {
        'income_today': income_today,
        'expense_today': expense_today,
        'balance_today': balance_today,
        'product_count': product_count,
        'low_stock_products': low_stock_list,
        'recent_sales': recent_sales
    }


def get_today_datetime_range():
    """
    Get datetime range for today (local server time).
    
    Returns:
        tuple: (start_dt, end_dt) where start is 00:00:00 and end is 23:59:59.999999
    """
    today = date.today()
    start_dt = datetime.combine(today, time.min)
    end_dt = start_dt + timedelta(days=1)
    
    return start_dt, end_dt
