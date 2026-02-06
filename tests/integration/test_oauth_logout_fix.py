"""
Additional tests for Google OAuth logout message bug fix.
"""
import pytest
from flask import session as flask_session
import uuid


class TestGoogleOAuthLogoutMessage:
    """Test that Google OAuth flow doesn't show logout message."""
    
    def test_logout_shows_message_with_query_param(self, client):
        """Test that logout redirects with query parameter."""
        # First login
        from app.models import AppUser, Tenant, UserTenant
        from app.database import db_session
        
        # Create test user and tenant
        suffix = str(uuid.uuid4())[:8]
        email = f'test_{suffix}@example.com'
        user = AppUser(email=email, full_name='Test User', active=True)
        user.set_password('password123')
        db_session.add(user)
        db_session.flush()
        
        tenant = Tenant(slug=f'test-tenant-{suffix}', name=f'Test Tenant {suffix}', active=True)
        db_session.add(tenant)
        db_session.flush()
        
        user_tenant = UserTenant(user_id=user.id, tenant_id=tenant.id, role='OWNER', active=True)
        db_session.add(user_tenant)
        db_session.commit()
        
        # Login
        client.post('/login', data={
            'email': email,
            'password': 'password123'
        })
        
        # Logout
        response = client.post('/logout', follow_redirects=False)
        
        # Should redirect to login with query parameter
        assert response.status_code == 302
        assert '/login' in response.location
        assert 'logged_out=1' in response.location
    
    def test_login_page_shows_logout_message_with_param(self, client):
        """Test that login page shows logout message when query param is present."""
        response = client.get('/login?logged_out=1')
        
        assert response.status_code == 200
        assert 'Sesión cerrada correctamente' in response.data.decode('utf-8')
    
    def test_login_page_no_logout_message_without_param(self, client):
        """Test that login page doesn't show logout message without query param."""
        response = client.get('/login')
        
        assert response.status_code == 200
        # Should not contain the logout message
        assert 'Sesión cerrada correctamente' not in response.data.decode('utf-8')
    
    def test_oauth_callback_clears_flash_messages(self, client, mocker):
        """Test that OAuth callback clears any lingering flash messages."""
        # This is a unit test to verify the session.pop('_flashes', None) call
        # We can't easily test the full OAuth flow without mocking Google's API
        
        # Mock the OAuth service
        mock_oauth_service = mocker.MagicMock()
        mock_oauth_service.exchange_code_for_tokens.return_value = {
            'id_token': 'mock_token'
        }
        mock_oauth_service.validate_and_decode_id_token.return_value = {
            'sub': 'google_123',
            'email': 'oauth@example.com',
            'name': 'OAuth User',
            'email_verified': True
        }
        
        mocker.patch(
            'app.blueprints.auth_google.get_google_oauth_service',
            return_value=mock_oauth_service
        )
        
        # Mock get_or_create_user_from_google
        from app.models import AppUser, Tenant, UserTenant
        from app.database import db_session
        
        suffix = str(uuid.uuid4())[:8]
        email = f'oauth_{suffix}@example.com'
        suffix = str(uuid.uuid4())[:8]
        email = f'oauth_cb_{suffix}@example.com'
        user = AppUser(email=email, full_name='OAuth User', active=True)
        db_session.add(user)
        db_session.flush()
        
        tenant = Tenant(slug=f'oauth-tenant-{suffix}', name=f'OAuth Tenant {suffix}', active=True)
        db_session.add(tenant)
        db_session.flush()
        
        user_tenant = UserTenant(user_id=user.id, tenant_id=tenant.id, role='OWNER', active=True)
        db_session.add(user_tenant)
        db_session.commit()
        
        mocker.patch(
            'app.blueprints.auth_google.get_or_create_user_from_google',
            return_value=user
        )
        mocker.patch(
            'app.blueprints.auth_google.get_user_tenants',
            return_value=[user_tenant]
        )
        
        # Set up OAuth state in session
        with client.session_transaction() as sess:
            sess['oauth_state'] = 'test_state'
            sess['oauth_provider'] = 'google'
            # Add a flash message to simulate lingering logout message
            sess.setdefault('_flashes', []).append(('info', 'Sesión cerrada correctamente.'))
        
        # Call callback
        response = client.get('/auth/google/callback?code=test_code&state=test_state', follow_redirects=False)
        
        # Should redirect successfully
        assert response.status_code == 302
        
        # Session should have user_id but no flashes
        with client.session_transaction() as sess:
            assert 'user_id' in sess
            assert sess['user_id'] == user.id
            # Flashes should be cleared
            assert '_flashes' not in sess or len(sess.get('_flashes', [])) == 0
