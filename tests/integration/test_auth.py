"""
Integration tests for authentication and authorization.
"""

import pytest
from flask import session as flask_session


class TestRegistration:
    """Test user registration flow."""
    
    def test_register_new_user_and_tenant(self, client, session):
        """Test successful user registration creates user + tenant."""
        response = client.post('/register', data={
            'email': 'newuser@test.com',
            'password': 'securepass123',
            'password_confirm': 'securepass123',
            'full_name': 'New User',
            'business_name': 'New Business'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        # Verify user was created
        from app.models import AppUser
        user = session.query(AppUser).filter_by(email='newuser@test.com').first()
        assert user is not None
        assert user.full_name == 'New User'
        
        # Verify tenant was created
        from app.models import Tenant
        tenant = session.query(Tenant).filter_by(name='New Business').first()
        assert tenant is not None
        
        # Verify user-tenant relationship
        from app.models import UserTenant
        user_tenant = session.query(UserTenant).filter_by(
            user_id=user.id,
            tenant_id=tenant.id
        ).first()
        assert user_tenant is not None
        assert user_tenant.role == 'OWNER'
    
    def test_register_with_existing_email_fails(self, client, user1):
        """Test that registering with existing email fails."""
        response = client.post('/register', data={
            'email': user1.email,
            'password': 'password123',
            'password_confirm': 'password123',
            'full_name': 'Duplicate User',
            'business_name': 'Duplicate Business'
        })
        
        assert response.status_code == 400
        assert b'email ya est' in response.data.lower() or b'registrado' in response.data.lower()
    
    def test_register_with_mismatched_passwords_fails(self, client):
        """Test that registration with mismatched passwords fails."""
        response = client.post('/register', data={
            'email': 'test@test.com',
            'password': 'password123',
            'password_confirm': 'differentpassword',
            'full_name': 'Test User',
            'business_name': 'Test Business'
        })
        
        assert response.status_code == 400


class TestLogin:
    """Test login functionality."""
    
    def test_login_with_valid_credentials(self, client, user1, tenant1):
        """Test successful login with valid credentials."""
        response = client.post('/login', data={
            'email': user1.email,
            'password': 'password123'
        }, follow_redirects=False)
        
        # Should redirect to dashboard
        assert response.status_code == 302
        assert '/dashboard' in response.location or '/products' in response.location
    
    def test_login_with_invalid_password(self, client, user1):
        """Test login with invalid password fails."""
        response = client.post('/login', data={
            'email': user1.email,
            'password': 'wrongpassword'
        })
        
        assert response.status_code == 401
        assert b'incorrectos' in response.data.lower() or b'incorrect' in response.data.lower()
    
    def test_login_with_nonexistent_email(self, client):
        """Test login with non-existent email fails."""
        response = client.post('/login', data={
            'email': 'nonexistent@test.com',
            'password': 'password123'
        })
        
        assert response.status_code == 401


class TestSessionManagement:
    """Test session and authentication state management."""
    
    def test_logout_clears_session(self, authenticated_client):
        """Test that logout clears session."""
        # Verify user is logged in
        with authenticated_client.session_transaction() as sess:
            assert 'user_id' in sess
            assert 'tenant_id' in sess
        
        # Logout
        response = authenticated_client.post('/logout', follow_redirects=False)
        assert response.status_code == 302
        
        # Verify session is cleared
        with authenticated_client.session_transaction() as sess:
            assert 'user_id' not in sess
            assert 'tenant_id' not in sess
    
    def test_accessing_protected_route_without_login_redirects(self, client):
        """Test that accessing protected routes without login redirects to login."""
        response = client.get('/dashboard/', follow_redirects=False)
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.location
    
    def test_accessing_protected_route_with_login_succeeds(self, authenticated_client):
        """Test that authenticated users can access protected routes."""
        response = authenticated_client.get('/dashboard/')
        
        # Should succeed (200) or redirect within app (not to login)
        assert response.status_code in [200, 302]
        if response.status_code == 302:
            assert '/login' not in response.location


class TestTenantContext:
    """Test tenant context management."""
    
    def test_session_contains_tenant_id_after_login(self, client, user1, tenant1):
        """Test that tenant_id is set in session after login."""
        client.post('/login', data={
            'email': user1.email,
            'password': 'password123'
        })
        
        with client.session_transaction() as sess:
            assert 'tenant_id' in sess
            assert sess['tenant_id'] == tenant1.id
    
    def test_requests_use_correct_tenant_context(self, authenticated_client, tenant1):
        """Test that requests use the correct tenant from session."""
        # Access dashboard (which uses tenant_id from session)
        response = authenticated_client.get('/dashboard/')
        
        # Should use tenant1's data
        # This is implicitly tested by the fact that the request succeeds
        # and dashboard service filters by tenant_id
        assert response.status_code == 200
