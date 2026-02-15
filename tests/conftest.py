import pytest
from datetime import datetime
import os
import uuid

# Force test configuration to use localhost ONLY if not already set (e.g. by Docker)
if 'DB_HOST' not in os.environ:
    os.environ['DB_HOST'] = 'localhost'

from app import create_app
from app.database import db_session, get_session
from app.models import (
    Tenant, AppUser, UserTenant, Product, Category, UOM,
    Sale, SaleLine, FinanceLedger, ProductStock
)


@pytest.fixture(scope='session')
def app():
    """Create application instance for testing."""
    app = create_app('config.Config')
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture(scope='function')
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture(scope='function')
def session():
    """Create database session for testing."""
    session = get_session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope='function')
def tenant1(session):
    """Create first test tenant."""
    suffix = str(uuid.uuid4())[:8]
    tenant = Tenant(
        slug=f'test-tenant-1-{suffix}',
        name=f'Test Tenant 1 {suffix}',
        active=True
    )
    session.add(tenant)
    session.commit()
    return tenant


@pytest.fixture(scope='function')
def tenant2(session):
    """Create second test tenant for isolation tests."""
    suffix = str(uuid.uuid4())[:8]
    tenant = Tenant(
        slug=f'test-tenant-2-{suffix}',
        name=f'Test Tenant 2 {suffix}',
        active=True
    )
    session.add(tenant)
    session.commit()
    return tenant


@pytest.fixture(scope='function')
def user1(session, tenant1):
    """Create test user for tenant1."""
    suffix = str(uuid.uuid4())[:8]
    user = AppUser(
        email=f'user1-{suffix}@test.com',
        full_name='User One',
        active=True
    )
    user.set_password('password123')
    session.add(user)
    session.flush()
    
    # Associate user with tenant
    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=tenant1.id,
        role='OWNER',
        active=True
    )
    session.add(user_tenant)
    session.commit()
    return user


@pytest.fixture(scope='function')
def user2(session, tenant2):
    """Create test user for tenant2."""
    suffix = str(uuid.uuid4())[:8]
    user = AppUser(
        email=f'user2-{suffix}@test.com',
        full_name='User Two',
        active=True
    )
    user.set_password('password123')
    session.add(user)
    session.flush()
    
    # Associate user with tenant
    user_tenant = UserTenant(
        user_id=user.id,
        tenant_id=tenant2.id,
        role='OWNER',
        active=True
    )
    session.add(user_tenant)
    session.commit()
    return user


@pytest.fixture(scope='function')
def uom(session, tenant1):
    """Create test UOM for tenant1."""
    uom = UOM(name='Unidad', symbol='un', tenant_id=tenant1.id)
    session.add(uom)
    session.commit()
    return uom


@pytest.fixture(scope='function')
def uom2(session, tenant2):
    """Create test UOM for tenant2."""
    uom = UOM(name='Unidad', symbol='un', tenant_id=tenant2.id)
    session.add(uom)
    session.commit()
    return uom


@pytest.fixture(scope='function')
def category_tenant1(session, tenant1):
    """Create test category for tenant1."""
    category = Category(
        tenant_id=tenant1.id,
        name='Test Category T1'
    )
    session.add(category)
    session.commit()
    return category


@pytest.fixture(scope='function')
def product_tenant1(session, tenant1, category_tenant1, uom):
    """Create test product for tenant1."""
    product = Product(
        tenant_id=tenant1.id,
        name='Product T1',
        sku='SKU-T1-001',
        category_id=category_tenant1.id,
        uom_id=uom.id,
        sale_price=100.00,
        min_stock_qty=10,
        active=True
    )
    session.add(product)
    session.flush()
    
    # Create product_stock
    stock = ProductStock(
        product_id=product.id,
        on_hand_qty=50
    )
    session.add(stock)
    session.commit()
    return product


@pytest.fixture(scope='function')
def product_tenant2(session, tenant2, uom2):
    """Create test product for tenant2."""
    category = Category(
        tenant_id=tenant2.id,
        name='Test Category T2'
    )
    session.add(category)
    session.flush()
    
    product = Product(
        tenant_id=tenant2.id,
        name='Product T2',
        sku='SKU-T2-001',
        category_id=category.id,
        uom_id=uom2.id,
        sale_price=200.00,
        min_stock_qty=5,
        active=True
    )
    session.add(product)
    session.flush()
    
    # Create product_stock
    stock = ProductStock(
        product_id=product.id,
        on_hand_qty=20
    )
    session.add(stock)
    session.commit()
    return product


@pytest.fixture(scope='function')
def authenticated_client(client, user1, tenant1):
    """Create authenticated client for tenant1."""
    with client.session_transaction() as sess:
        sess['user_id'] = user1.id
        sess['tenant_id'] = tenant1.id
    return client
