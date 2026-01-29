"""
Integration test for the Create Business flow.
Verifies that users with 0 tenants are redirected to create-business instead of logout,
and that they can successfully create a business.
"""
import pytest
from flask import session, url_for

def test_redirect_to_create_business_if_no_tenants(client, app):
    """
    Test that a logged-in user with 0 tenants is redirected to /auth/create-business
    when accessing the root or dashboard, instead of being logged out.
    """
    # 1. Create a user with NO tenants
    from app.models import AppUser
    from app.database import db_session
    
    user = AppUser(email='new_oauth_user@example.com', full_name='New User', active=True)
    db_session.add(user)
    db_session.commit()
    
    # 2. Simulate Login (session set)
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
        sess['_fresh'] = True
    
    # 3. Access Root URL
    response = client.get('/', follow_redirects=False)
    
    # Should redirect to create-business, NOT select-tenant or login
    assert response.status_code == 302
    assert response.location.endswith(url_for('auth.create_business'))
    
    # 4. Access Dashboard URL
    response = client.get('/dashboard/', follow_redirects=False)
    
    # Dashboard requires tenant, so it redirects to select_tenant
    # But select_tenant should redirect to create_business for 0-tenant users
    assert response.status_code == 302
    assert response.location.endswith(url_for('auth.select_tenant'))
    
    # Follow redirect to check select_tenant logic
    response = client.get('/auth/select-tenant', follow_redirects=False)
    assert response.status_code == 302
    assert response.location.endswith(url_for('auth.create_business'))

def test_create_business_flow(client, app):
    """
    Test that the user can successfully create a business via the new route.
    """
    # 1. Create user with NO tenants
    from app.models import AppUser, Tenant, UserTenant
    from app.database import db_session
    
    user = AppUser(email='creator@example.com', full_name='Creator', active=True)
    db_session.add(user)
    db_session.commit()
    
    # 2. Simulate Login
    with client.session_transaction() as sess:
        sess['user_id'] = user.id
    
    # 3. Post to create-business
    response = client.post('/auth/create-business', data={
        'business_name': 'My First Shop'
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert 'My First Shop' in response.data.decode('utf-8')
    assert '¡Negocio "My First Shop" creado exitosamente!' in response.data.decode('utf-8')
    
    # 4. Verify DB state
    tenant = db_session.query(Tenant).filter_by(name='My First Shop').first()
    assert tenant is not None
    assert tenant.slug == 'my-first-shop'
    
    user_tenant = db_session.query(UserTenant).filter_by(user_id=user.id, tenant_id=tenant.id).first()
    assert user_tenant is not None
    assert user_tenant.role == 'OWNER'
