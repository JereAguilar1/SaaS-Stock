"""
Admin Dashboard Service - Global KPI aggregation across all tenants.

This service provides data for the admin panel dashboard, including
aggregate metrics and tenant management information.
"""

from datetime import datetime, timedelta
from sqlalchemy import func, case, and_, desc
from sqlalchemy.sql import text


def get_global_kpis(db_session):
    """
    Get global KPIs for admin dashboard.
    
    Returns dict with:
    - total_tenants: Total number of tenants
    - active_tenants_30d: Tenants with activity in last 30 days
    - total_sales: Total sales count (CONFIRMED status)
    - total_revenue: Total revenue from all sales
    """
    from app.models import Tenant, Sale
    
    # Total tenants
    total_tenants = db_session.query(func.count(Tenant.id)).scalar() or 0
    
    # Active tenants (30 days) - tenants with at least one sale in last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    active_tenants_30d = db_session.query(
        func.count(func.distinct(Sale.tenant_id))
    ).filter(
        Sale.datetime >= thirty_days_ago,
        Sale.status == 'CONFIRMED'
    ).scalar() or 0
    
    # Total sales (CONFIRMED only)
    total_sales = db_session.query(func.count(Sale.id)).filter(
        Sale.status == 'CONFIRMED'
    ).scalar() or 0
    
    # Total revenue (sum of all confirmed sales)
    total_revenue = db_session.query(func.sum(Sale.total)).filter(
        Sale.status == 'CONFIRMED'
    ).scalar() or 0
    
    # Calculate active tenants (not suspended)
    active_tenants = db_session.query(Tenant).filter_by(is_suspended=False).count()
    
    # Subscription status counts
    from app.models import Subscription
    past_due_tenants = db_session.query(Subscription).filter_by(status='past_due').count()
    trial_tenants = db_session.query(Subscription).filter_by(status='trial').count()
    
    return {
        'total_tenants': total_tenants,
        'active_tenants_30d': active_tenants_30d,
        'total_sales': total_sales,
        'total_revenue': float(total_revenue),
        'active_tenants': active_tenants,
        'past_due_tenants': past_due_tenants,
        'trial_tenants': trial_tenants,
    }


def get_sales_trend_30d(db_session):
    """
    Get daily sales trend for last 30 days (for chart).
    
    Returns list of dicts: [{date, count, revenue}]
    """
    from app.models import Sale
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    # Query for daily aggregates
    results = db_session.query(
        func.date(Sale.datetime).label('date'),
        func.count(Sale.id).label('count'),
        func.sum(Sale.total).label('revenue')
    ).filter(
        Sale.datetime >= thirty_days_ago,
        Sale.status == 'CONFIRMED'
    ).group_by(
        func.date(Sale.datetime)
    ).order_by(
        func.date(Sale.datetime)
    ).all()
    
    # Convert to list of dicts
    trend_data = []
    for row in results:
        trend_data.append({
            'date': row.date.strftime('%Y-%m-%d') if row.date else None,
            'count': row.count or 0,
            'revenue': float(row.revenue) if row.revenue else 0.0
        })
    
    return trend_data


def get_tenants_with_stats(db_session, search_query=None):
    """
    Get list of tenants with computed statistics.
    
    For each tenant returns:
    - id, name, slug, created_at, is_suspended
    - owner_email: Email of the OWNER user
    - total_sales: Count of confirmed sales
    - total_revenue: Sum of confirmed sales
    
    Args:
        search_query: Optional search string to filter by name or slug
    """
    from app.models import Tenant, UserTenant, AppUser, Sale
    from sqlalchemy.orm import aliased
    
    # Subquery for total sales per tenant
    sales_subq = db_session.query(
        Sale.tenant_id,
        func.count(Sale.id).label('total_sales'),
        func.coalesce(func.sum(Sale.total), 0).label('total_revenue')
    ).filter(
        Sale.status == 'CONFIRMED'
    ).group_by(
        Sale.tenant_id
    ).subquery()
    
    # Subquery for owner email
    owner_subq = db_session.query(
        UserTenant.tenant_id,
        AppUser.email.label('owner_email')
    ).join(
        AppUser, AppUser.id == UserTenant.user_id
    ).filter(
        UserTenant.role == 'OWNER',
        UserTenant.active == True
    ).subquery()
    
    # Main query
    query = db_session.query(
        Tenant.id,
        Tenant.name,
        Tenant.slug,
        Tenant.created_at,
        Tenant.is_suspended,
        owner_subq.c.owner_email,
        func.coalesce(sales_subq.c.total_sales, 0).label('total_sales'),
        func.coalesce(sales_subq.c.total_revenue, 0).label('total_revenue')
    ).outerjoin(
        sales_subq, sales_subq.c.tenant_id == Tenant.id
    ).outerjoin(
        owner_subq, owner_subq.c.tenant_id == Tenant.id
    )
    
    # Apply search filter if provided
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            (Tenant.name.ilike(search_pattern)) |
            (Tenant.slug.ilike(search_pattern))
        )
    
    # Order by created_at descending
    query = query.order_by(desc(Tenant.created_at))
    
    results = query.all()
    
    # Convert to list of dicts
    tenants = []
    for row in results:
        tenants.append({
            'id': row.id,
            'name': row.name,
            'slug': row.slug,
            'created_at': row.created_at,
            'is_suspended': row.is_suspended,
            'owner_email': row.owner_email or 'N/A',
            'total_sales': row.total_sales or 0,
            'total_revenue': float(row.total_revenue) if row.total_revenue else 0.0
        })
    
    return tenants


def get_tenant_detail(db_session, tenant_id):
    """
    Get detailed information for a specific tenant.
    
    Returns dict with:
    - Tenant basic info
    - Owner email
    - Total sales, revenue
    - Monthly sales breakdown (last 12 months)
    - User count
    - Latest 10 sales
    """
    from app.models import Tenant, UserTenant, AppUser, Sale
    
    # Get tenant
    tenant = db_session.query(Tenant).filter_by(id=tenant_id).first()
    if not tenant:
        return None
    
    # Get owner email
    owner = db_session.query(AppUser.email).join(
        UserTenant, UserTenant.user_id == AppUser.id
    ).filter(
        UserTenant.tenant_id == tenant_id,
        UserTenant.role == 'OWNER',
        UserTenant.active == True
    ).first()
    owner_email = owner.email if owner else 'N/A'
    
    # Get total sales and revenue
    sales_stats = db_session.query(
        func.count(Sale.id).label('total_sales'),
        func.coalesce(func.sum(Sale.total), 0).label('total_revenue')
    ).filter(
        Sale.tenant_id == tenant_id,
        Sale.status == 'CONFIRMED'
    ).first()
    
    # Get user count
    user_count = db_session.query(func.count(UserTenant.id)).filter(
        UserTenant.tenant_id == tenant_id,
        UserTenant.active == True
    ).scalar() or 0
    
    # Get latest 10 sales
    latest_sales = db_session.query(Sale).filter(
        Sale.tenant_id == tenant_id,
        Sale.status == 'CONFIRMED'
    ).order_by(
        desc(Sale.datetime)
    ).limit(10).all()
    
    # Convert latest sales to dicts
    sales_list = []
    for sale in latest_sales:
        sales_list.append({
            'id': sale.id,
            'datetime': sale.datetime,
            'total': float(sale.total)
        })
    
    return {
        'id': tenant.id,
        'name': tenant.name,
        'slug': tenant.slug,
        'created_at': tenant.created_at,
        'is_suspended': tenant.is_suspended,
        'owner_email': owner_email,
        'total_sales': sales_stats.total_sales if sales_stats else 0,
        'total_revenue': float(sales_stats.total_revenue) if sales_stats else 0.0,
        'user_count': user_count,
        'latest_sales': sales_list,
        'subscription': {
            'plan_type': tenant.subscription.plan_type if tenant.subscription else 'free',
            'status': tenant.subscription.status if tenant.subscription else 'trial',
            'amount': float(tenant.subscription.amount) if tenant.subscription and tenant.subscription.amount else 0.0,
            'trial_ends_at': tenant.subscription.trial_ends_at,
            'current_period_end': tenant.subscription.current_period_end
        } if tenant.subscription else None
    }
