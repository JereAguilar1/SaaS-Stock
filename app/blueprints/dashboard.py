"""
Dashboard blueprint for multi-tenant SaaS.
Shows key metrics, alerts, and recent activity for the current tenant.
"""

from flask import Blueprint, render_template, g
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
        
        return render_template(
            'dashboard/index.html',
            income_today=data['income_today'],
            expense_today=data['expense_today'],
            balance_today=data['balance_today'],
            product_count=data['product_count'],
            low_stock_products=data['low_stock_products'],
            recent_sales=data['recent_sales']
        )
        
    except Exception as e:
        # Log error but don't crash - show empty dashboard
        print(f"Error loading dashboard for tenant {tenant_id}: {e}")
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
