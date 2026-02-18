"""
Dashboard blueprint for multi-tenant SaaS.
Shows key metrics, alerts, and recent activity for the current tenant.
"""

from flask import Blueprint, render_template, g, current_app
from app.database import get_session
from app.middleware import require_login, require_tenant
from app.services.dashboard_service import get_dashboard_data, get_today_datetime_range


dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/dashboard')


@dashboard_bp.route('/')
@require_login
@require_tenant
def index():
    """
    Dashboard home page.
    
    Shows for the current tenant and today:
    - Balance del día (Income - Expense)
    - Ingresos Hoy
    - Egresos Hoy
    - Productos (Cantidad)
    - Aviso de productos bajos en stock
    - Últimas ventas
    """
    db_session = get_session()
    tenant_id = g.tenant_id
    
    try:
        # Get today's datetime range
        start_dt, end_dt = get_today_datetime_range()
        
        # Get all dashboard data
        data = get_dashboard_data(db_session, tenant_id, start_dt, end_dt)
        
        # --- CASH FLOW LOGIC ---
        from sqlalchemy import func
        from datetime import date
        from app.models import Sale, SalePayment
        from app.models.payment_log import PaymentLog
        
        today = date.today()
        
        # A. Cash Sales Today (SalePayment joined with Sale)
        # Filter: Sale date is today AND SalePayment method is NOT Cuenta Corriente (redundant but safe)
        cash_today = db_session.query(func.coalesce(func.sum(SalePayment.amount), 0)).join(Sale).filter(
            func.date(Sale.datetime) == today,
            Sale.tenant_id == tenant_id,
            SalePayment.payment_method != 'CUENTA_CORRIENTE'
        ).scalar()
        
        # B. Debt Payments Today (PaymentLog)
        debt_today = db_session.query(func.coalesce(func.sum(PaymentLog.amount), 0)).join(Sale).filter(
            func.date(PaymentLog.date) == today,
            Sale.tenant_id == tenant_id
        ).scalar()
        
        # Total Real Cash Flow
        daily_total = (cash_today or 0) + (debt_today or 0)
        
        # Calculate Balance based on Real Cash Flow
        daily_balance = daily_total - (data['expense_today'] or 0)
        
        return render_template(
            'dashboard/index.html',
            daily_total=daily_total,
            debt_today=debt_today,
            income_today=data['income_today'],
            expense_today=data['expense_today'],
            balance_today=daily_balance,
            product_count=data['product_count'],
            low_stock_products=data['low_stock_products'],
            recent_sales=data['recent_sales']
        )
        
    except Exception as e:
        # Log error with stack trace for debugging
        current_app.logger.error(f"Error loading dashboard for tenant {tenant_id}: {e}", exc_info=True)
        return render_template(
            'dashboard/index.html',
            income_today=0,
            expense_today=0,
            balance_today=0,
            product_count=0,
            low_stock_products=[],
            recent_sales=[],
            error="Error al cargar el dashboard. Por favor, intente nuevamente."
        )
