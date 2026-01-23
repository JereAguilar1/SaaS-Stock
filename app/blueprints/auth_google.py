"""
Google OAuth authentication blueprint.

Handles OAuth2/OpenID Connect flow:
- /auth/google/start: Initiates OAuth flow
- /auth/google/callback: Processes Google callback
"""
from flask import Blueprint, redirect, url_for, session, flash, request, g
from app.services.google_oauth_service import get_google_oauth_service
from app.services.auth_service import get_or_create_user_from_google, get_user_tenants
import secrets
import logging

logger = logging.getLogger(__name__)

auth_google_bp = Blueprint('auth_google', __name__, url_prefix='/auth/google')


@auth_google_bp.route('/start')
def start():
    """
    Initiate Google OAuth flow.
    
    Flow:
    1. Generate CSRF state token
    2. Store state in session
    3. Redirect to Google consent screen
    
    Returns:
        Redirect to Google authorization URL
    """
    # If already authenticated, redirect to dashboard
    if g.user:
        logger.info(f"User {g.user.id} already authenticated, redirecting to dashboard")
        return redirect(url_for('dashboard.index'))
    
    # Generate CSRF state token (32 bytes = 256 bits)
    state = secrets.token_urlsafe(32)
    session['oauth_state'] = state
    session['oauth_provider'] = 'google'
    
    logger.info(f"Starting Google OAuth flow with state: {state[:10]}...")
    
    # Get authorization URL
    try:
        oauth_service = get_google_oauth_service()
        authorization_url = oauth_service.get_authorization_url(state)
        
        logger.info("Redirecting to Google consent screen")
        print("GOOGLE REDIRECT URI:", authorization_url)  # 👈 ACÁ
        return redirect(authorization_url)
        
    except ValueError as e:
        logger.error(f"OAuth configuration error: {str(e)}")
        flash('Error de configuración OAuth. Contacta soporte.', 'danger')
        return redirect(url_for('auth.login'))
    except Exception as e:
        logger.error(f"Unexpected error starting OAuth: {str(e)}", exc_info=True)
        flash('Error inesperado. Intenta nuevamente.', 'danger')
        return redirect(url_for('auth.login'))


@auth_google_bp.route('/callback')
def callback():
    """
    Handle Google OAuth callback.
    
    Flow:
    1. Check for errors from Google
    2. Validate state (CSRF protection)
    3. Exchange code for tokens
    4. Validate ID token
    5. Extract user profile
    6. Create/update user
    7. Start session
    8. Redirect based on tenant count
    
    Returns:
        Redirect to dashboard, tenant selection, or login with error
    """
    # Check for error from Google (user cancelled or other error)
    error = request.args.get('error')
    if error:
        if error == 'access_denied':
            logger.info("User cancelled Google OAuth")
            flash('Cancelaste el inicio de sesión con Google.', 'info')
        else:
            logger.warning(f"Google OAuth error: {error}")
            flash(f'Error de Google: {error}', 'danger')
        return redirect(url_for('auth.login'))
    
    # Validate state (CSRF protection)
    state = request.args.get('state')
    session_state = session.pop('oauth_state', None)
    session_provider = session.pop('oauth_provider', None)
    
    if not state or not session_state or state != session_state:
        logger.warning(
            f"OAuth state mismatch - received: {state[:10] if state else 'None'}..., "
            f"expected: {session_state[:10] if session_state else 'None'}..."
        )
        flash('Error de seguridad (state mismatch). Intenta nuevamente.', 'danger')
        return redirect(url_for('auth.login'))
    
    if session_provider != 'google':
        logger.warning(f"OAuth provider mismatch: {session_provider}")
        flash('Error de proveedor OAuth.', 'danger')
        return redirect(url_for('auth.login'))
    
    # Get authorization code
    code = request.args.get('code')
    if not code:
        logger.warning("No authorization code received from Google")
        flash('No se recibió código de autorización.', 'danger')
        return redirect(url_for('auth.login'))
    
    try:
        # Exchange code for tokens
        logger.info("Exchanging code for tokens")
        oauth_service = get_google_oauth_service()
        token = oauth_service.exchange_code_for_tokens(code)
        
        # Validate and decode ID token
        id_token = token.get('id_token')
        if not id_token:
            logger.error("No ID token in token response")
            raise ValueError("No se recibió ID token de Google")
        
        logger.info("Validating ID token")
        claims = oauth_service.validate_and_decode_id_token(id_token)
        
        # Extract user profile from claims
        google_profile = {
            'sub': claims['sub'],
            'email': claims['email'],
            'name': claims.get('name', ''),
            'email_verified': claims.get('email_verified', False)
        }
        
        logger.info(f"Google profile extracted: email={google_profile['email']}")
        
        # Get or create user
        user = get_or_create_user_from_google(google_profile)
        
        # Start session
        session.clear()
        session['user_id'] = user.id
        session.permanent = True
        
        logger.info(f"Session started for user {user.id}")
        
        # Handle tenant selection based on user's tenants
        user_tenants = get_user_tenants(user.id)
        
        if len(user_tenants) == 0:
            # New user with no tenants - redirect to tenant creation
            logger.info(f"New user {user.id} has no tenants, needs to create one")
            flash(
                f'¡Bienvenido {user.full_name or user.email}! '
                'Ahora crea tu primer negocio para comenzar.',
                'success'
            )
            # Redirect to register page which has tenant creation
            # User is already authenticated, so they'll go through tenant creation
            return redirect(url_for('auth.register'))
        
        elif len(user_tenants) == 1:
            # Auto-select the only tenant
            session['tenant_id'] = user_tenants[0].tenant_id
            logger.info(f"Auto-selected tenant {user_tenants[0].tenant_id} for user {user.id}")
            flash(f'¡Bienvenido {user.full_name or user.email}!', 'success')
            return redirect(url_for('dashboard.index'))
        
        else:
            # Multiple tenants - let user choose
            logger.info(f"User {user.id} has {len(user_tenants)} tenants, redirecting to selection")
            flash('Selecciona un negocio para continuar.', 'info')
            return redirect(url_for('auth.select_tenant'))
    
    except ValueError as e:
        # Expected errors (validation, account linking conflicts, etc.)
        logger.warning(f"OAuth validation error: {str(e)}")
        flash(str(e), 'danger')
        return redirect(url_for('auth.login'))
    
    except Exception as e:
        # Unexpected errors
        logger.error(f"Unexpected OAuth callback error: {str(e)}", exc_info=True)
        flash('Error inesperado al iniciar sesión con Google. Intenta nuevamente.', 'danger')
        return redirect(url_for('auth.login'))
