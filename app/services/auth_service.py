"""
Authentication service for user management.

Handles user creation, OAuth account linking, and session management.
"""
from app.database import db_session
from app.models import AppUser, UserTenant
from sqlalchemy.exc import IntegrityError
import logging

logger = logging.getLogger(__name__)


def get_or_create_user_from_google(google_profile):
    """
    Get existing user or create new user from Google profile.
    
    Account linking policy:
    - If google_sub exists: return that user (update email/name)
    - If email exists without google_sub: link Google account
    - If email exists with different google_sub: reject (security)
    - If email doesn't exist: create new user
    
    Args:
        google_profile: Dict with 'sub', 'email', 'name', 'email_verified'
    
    Returns:
        AppUser: User instance
    
    Raises:
        ValueError: If email not verified or account linking conflict
    """
    email = google_profile['email']
    google_sub = google_profile['sub']
    full_name = google_profile.get('name', '')
    email_verified = google_profile.get('email_verified', False)
    
    # Validate email is verified
    if not email_verified:
        logger.warning(f"Attempted login with unverified email: {email}")
        raise ValueError("Email no verificado por Google")
    
    # Check if user exists by google_sub
    user = db_session.query(AppUser).filter_by(google_sub=google_sub).first()
    
    if user:
        # User exists with this google_sub - update and return
        logger.info(f"Existing Google user login: {email}")
        user.email = email  # Update email in case it changed
        user.full_name = full_name or user.full_name
        user.email_verified = True
        user.active = True  # Ensure user is active
        db_session.commit()
        return user
    
    # Check if user exists by email
    user = db_session.query(AppUser).filter_by(email=email).first()
    
    if user:
        # Email exists - check linking policy
        if user.google_sub and user.google_sub != google_sub:
            # Email already linked to different Google account - SECURITY ISSUE
            logger.warning(
                f"Account linking conflict: email={email}, "
                f"existing_sub={user.google_sub}, new_sub={google_sub}"
            )
            raise ValueError(
                "Este email ya está vinculado a otra cuenta de Google. "
                "Si crees que esto es un error, contacta soporte."
            )
        
        # Link Google account to existing local user
        logger.info(f"Linking Google account to existing user: {email}")
        user.google_sub = google_sub
        user.auth_provider = 'google'
        user.email_verified = True
        user.full_name = full_name or user.full_name
        user.active = True
        db_session.commit()
        
        return user
    
    # Create new user from Google profile
    try:
        logger.info(f"Creating new user from Google OAuth: {email}")
        new_user = AppUser(
            email=email,
            google_sub=google_sub,
            auth_provider='google',
            email_verified=True,
            full_name=full_name,
            active=True,
            password_hash=None  # OAuth users don't have password
        )
        db_session.add(new_user)
        db_session.commit()
        
        logger.info(f"Successfully created new Google user: {email}")
        return new_user
        
    except IntegrityError as e:
        db_session.rollback()
        logger.error(f"Error creating user from Google (IntegrityError): {str(e)}")
        
        # Check if it's a duplicate email (race condition)
        if 'app_user_email_key' in str(e) or 'unique constraint' in str(e).lower():
            raise ValueError(
                "Este email ya está registrado. "
                "Intenta iniciar sesión o usa otro email."
            )
        
        raise ValueError("Error al crear la cuenta. Intenta nuevamente.")
    
    except Exception as e:
        db_session.rollback()
        logger.error(f"Unexpected error creating user from Google: {str(e)}", exc_info=True)
        raise ValueError("Error inesperado al crear la cuenta.")


def get_user_tenants(user_id):
    """
    Get active tenants for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        list[UserTenant]: List of active user-tenant relationships
    """
    return db_session.query(UserTenant).filter_by(
        user_id=user_id,
        active=True
    ).all()
