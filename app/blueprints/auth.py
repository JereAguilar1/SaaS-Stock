"""
Authentication blueprint for multi-tenant SaaS.
Handles user registration, login, logout, and tenant selection.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from typing import Union, Optional, Tuple, List
from app.database import db_session
from app.models import AppUser, Tenant, UserTenant
import re
import logging
from app.exceptions import BusinessLogicError, UnauthorizedError

logger = logging.getLogger(__name__)


auth_bp = Blueprint('auth', __name__)


def is_valid_email(email: str) -> bool:
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generate_slug(name: str) -> str:
    """Generate URL-safe slug from business name."""
    import unicodedata
    
    # Normalize unicode characters
    slug = unicodedata.normalize('NFKD', name)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    
    # Convert to lowercase and replace spaces/special chars with hyphens
    slug = slug.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = slug.strip('-')
    
    # Limit length
    slug = slug[:80]
    
    return slug


def _generate_unique_tenant_slug(db_session, business_name: str) -> str:
    """Generate a unique slug for a new tenant."""
    slug = generate_slug(business_name)
    base_slug = slug
    counter = 1
    while db_session.query(Tenant).filter_by(slug=slug).first():
        slug = f"{base_slug}-{counter}"
        counter += 1
    return slug


def _validate_registration_form(form: dict) -> List[str]:
    """Validate registration form fields and return list of errors."""
    errors = []
    email = form.get('email', '').strip()
    password = form.get('password', '')
    password_confirm = form.get('password_confirm', '')
    full_name = form.get('full_name', '').strip()
    business_name = form.get('business_name', '').strip()

    if not email or not is_valid_email(email):
        errors.append('Email inválido.')
    
    if not password or len(password) < 6:
        errors.append('La contraseña debe tener al menos 6 caracteres.')
    
    if password != password_confirm:
        errors.append('Las contraseñas no coinciden.')
    
    if not full_name:
        errors.append('El nombre es requerido.')
    
    if not business_name:
        errors.append('El nombre del negocio es requerido.')
    
    return errors


@auth_bp.route('/check-email', methods=['POST'])
def check_email() -> Union[str, Response]:
    """Check if email already exists."""
    email = request.form.get('email', '').strip()
    
    if not email or not is_valid_email(email):
        return render_template('auth/_check_email.html', error=None)
        
    user = db_session.query(AppUser).filter(
        func.lower(AppUser.email) == email.lower()
    ).first()
    
    if user:
        return render_template('auth/_check_email.html', error="Este email ya está registrado")
    
    return render_template('auth/_check_email.html', error=None)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register() -> Union[str, Response]:
    """Registration page - creates user + tenant + user_tenant relationship."""
    # If already authenticated, redirect to dashboard
    if g.user:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        business_name = request.form.get('business_name', '').strip()
        password = request.form.get('password', '')
        
        # 1. Validations
        errors = _validate_registration_form(request.form)
        if errors:
            raise BusinessLogicError(", ".join(errors))
        
        try:
            # 2. Create Tenant
            slug = _generate_unique_tenant_slug(db_session, business_name)
            tenant = Tenant(slug=slug, name=business_name, active=True)
            db_session.add(tenant)
            db_session.flush()
            
            # 3. Create AppUser
            user = AppUser(email=email, full_name=full_name, active=True)
            user.set_password(password)
            db_session.add(user)
            db_session.flush()
            
            # 4. Create UserTenant (OWNER role)
            user_tenant = UserTenant(
                user_id=user.id,
                tenant_id=tenant.id,
                role='OWNER',
                active=True
            )
            db_session.add(user_tenant)
            db_session.commit()
            
            # 5. Auto-login
            session.clear()
            session['user_id'] = user.id
            session['tenant_id'] = tenant.id
            session.permanent = True
            
            flash(f'¡Bienvenido {full_name}! Tu negocio "{business_name}" ha sido creado.', 'success')
            return redirect(url_for('dashboard.index'))
            
        except IntegrityError as e:
            db_session.rollback()
            if 'app_user_email_key' in str(e):
                raise BusinessLogicError('Este email ya está registrado. Usa otro o inicia sesión.')
            raise BusinessLogicError('Error al crear la cuenta. Intenta nuevamente.')
        except Exception as e:
            db_session.rollback()
            logger.error(f"Unexpected error in register: {str(e)}", exc_info=True)
            raise e
    
    return render_template('auth/register.html', email='', full_name='', business_name='')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login() -> Union[str, Response]:
    """Login page - validates email + password."""
    # If already authenticated, redirect to dashboard
    if g.user:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        next_url = request.args.get('next')
        
        if not email or not password:
            raise BusinessLogicError('Email y contraseña son requeridos.')
        
        # Find user
        user = db_session.query(AppUser).filter_by(email=email).first()
        
        if not user or not user.active:
            raise UnauthorizedError('Email o contraseña incorrectos.')
        
        # Check if user is OAuth-only (no password)
        if not user.password_hash:
            flash(
                'Esta cuenta usa inicio de sesión con Google. '
                'Usa el botón "Continuar con Google" a continuación.',
                'info'
            )
            return render_template('auth/login.html'), 401
        
        # Verify password
        if not user.check_password(password):
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('auth/login.html'), 401
        
        # Authentication successful
        session.clear()
        session['user_id'] = user.id
        session.permanent = True
        
        # Get user's tenants
        user_tenants = db_session.query(UserTenant).filter_by(
            user_id=user.id,
            active=True
        ).all()
        
        if not user_tenants:
            flash('Tu cuenta no tiene negocios asociados. Contacta soporte.', 'danger')
            session.clear()
            return render_template('auth/login.html'), 403
        
        if len(user_tenants) == 1:
            session['tenant_id'] = user_tenants[0].tenant_id
            flash(f'Bienvenido, {user.full_name or user.email}!', 'success')
            return redirect(next_url or url_for('dashboard.index'))
        
        flash('Selecciona un negocio para continuar.', 'info')
        return redirect(url_for('auth.select_tenant'))
    
    return render_template('auth/login.html')


@auth_bp.route('/select-tenant', methods=['GET', 'POST'])
def select_tenant() -> Union[str, Response]:
    """
    Tenant selection page for users with multiple tenants.
    
    Only accessible if user is logged in but no tenant selected.
    """
    if not g.user:
        flash('Debes iniciar sesión primero.', 'warning')
        return redirect(url_for('auth.login'))
    
    # Get user's tenants
    user_tenants = db_session.query(UserTenant, Tenant).join(
        Tenant, Tenant.id == UserTenant.tenant_id
    ).filter(
        UserTenant.user_id == g.user.id,
        UserTenant.active == True,
        Tenant.active == True
    ).all()
    
    if len(user_tenants) == 0:
        # Redirect new users to create business instead of logout
        logger = __import__('logging').getLogger(__name__)
        logger.info(f"User {g.user.id} has no tenants, redirecting to create_business")
        return redirect(url_for('auth.create_business'))
    
    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id', type=int)
        
        # Verify user has access to this tenant
        valid_tenant = any(ut.UserTenant.tenant_id == tenant_id for ut in user_tenants)
        
        if not valid_tenant:
            flash('Negocio inválido.', 'danger')
            return render_template('auth/select_tenant.html', user_tenants=user_tenants), 403
        
        # Set tenant in session
        session['tenant_id'] = tenant_id
        
        # Get tenant name for flash message
        tenant_name = next(ut.Tenant.name for ut in user_tenants if ut.UserTenant.tenant_id == tenant_id)
        flash(f'Trabajando en: {tenant_name}', 'success')
        
        return redirect(url_for('dashboard.index'))
    
    # GET request - show tenant selection
    return render_template('auth/select_tenant.html', user_tenants=user_tenants)


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout() -> Union[str, Response]:
    """Logout endpoint - clear session and redirect to login with query param."""
    session.clear()
    # Use query parameter instead of flash to avoid persistence issues
    return redirect(url_for('auth.login', logged_out='1'))


@auth_bp.route('/create-business', methods=['GET', 'POST'])
def create_business() -> Union[str, Response]:
    """Create first business page for logged-in users."""
    if not g.user:
        flash('Debes iniciar sesión primero.', 'warning')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        
        if not business_name:
            flash('El nombre del negocio es requerido.', 'danger')
            return render_template('auth/create_business.html', business_name=business_name), 400
            
        try:
            # 1. Create Tenant
            slug = _generate_unique_tenant_slug(db_session, business_name)
            tenant = Tenant(slug=slug, name=business_name, active=True)
            db_session.add(tenant)
            db_session.flush()
            
            # 2. Create UserTenant (OWNER)
            user_tenant = UserTenant(
                user_id=g.user.id,
                tenant_id=tenant.id,
                role='OWNER',
                active=True
            )
            db_session.add(user_tenant)
            db_session.commit()
            
            # 3. Set tenant in session
            session['tenant_id'] = tenant.id
            session.permanent = True
            
            flash(f'¡Negocio {business_name} creado exitosamente!', 'success')
            return redirect(url_for('dashboard.index'))
            
        except IntegrityError:
            db_session.rollback()
            flash('Error al crear el negocio. Intenta nuevamente.', 'danger')
            return render_template('auth/create_business.html', business_name=business_name), 400
        except Exception as e:
            db_session.rollback()
            logger.error(f"Error in create_business: {str(e)}", exc_info=True)
            flash(f'Error inesperado: {str(e)}', 'danger')
            return render_template('auth/create_business.html', business_name=business_name), 500

    return render_template('auth/create_business.html', business_name='')


@auth_bp.route('/')
def root() -> Union[str, Response]:
    """Root route - redirect based on authentication status."""
    if g.user:
        if g.tenant_id:
            return redirect(url_for('dashboard.index'))
        else:
            # Check if user has any tenants
            user_tenants_count = db_session.query(UserTenant).filter_by(
                user_id=g.user.id,
                active=True
            ).count()
            
            if user_tenants_count == 0:
                return redirect(url_for('auth.create_business'))
            
            return redirect(url_for('auth.select_tenant'))
    else:
        return redirect(url_for('auth.login'))


# =====================================================
# IMPERSONATION - STOP (EXIT SUPPORT MODE)
# =====================================================


# =====================================================
# IMPERSONATION - STOP (EXIT SUPPORT MODE)
# =====================================================

@auth_bp.route('/stop-impersonation', methods=['POST'])
def stop_impersonation() -> Union[str, Response]:
    """
    Stop impersonating a tenant and return to admin session.
    
    This route is accessible from the impersonation banner that appears
    on all pages when an admin is in support mode.
    """
    from app.services.impersonation_service import stop_impersonation as stop_imp_service
    
    # Get client IP
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    
    # Stop impersonation
    success, message, redirect_url = stop_imp_service(ip_address=ip_address)
    
    flash(message, 'success' if success else 'danger')
    
    if redirect_url:
        return redirect(redirect_url)
    else:
        # Fallback to admin login if no redirect URL
        return redirect(url_for('admin.login'))


# =====================================================
# PASSWORD RESET FLOW
# =====================================================


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password() -> Union[str, Response]:
    """
    Request password reset link.
    
    Flow:
    1. User enters email
    2. Check if user exists
    3. If OAuth user -> Send email reminding to use Google
    4. If Local user -> Generate token and send reset link
    5. Always show success message (security)
    """
    if g.user:
        return redirect(url_for('dashboard.index'))
        
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Por favor ingresa tu email.', 'danger')
            return render_template('auth/forgot_password.html')
            
        user = db_session.query(AppUser).filter(
            func.lower(AppUser.email) == email.lower()
        ).first()
        
        if user:
            from app.services.email_service import send_password_reset_email, send_oauth_login_email
            
            if user.is_oauth_user():
                # Notify OAuth user they should login with Google
                send_oauth_login_email(user.email, user.auth_provider)
            else:
                # Local user: standard reset flow
                import secrets
                from datetime import datetime, timedelta, timezone
                
                # Generate secure token
                token = secrets.token_urlsafe(32)
                # Use UTC for expiration to match timezone=True column
                expires = datetime.now(timezone.utc) + timedelta(hours=1)
                
                # Save to DB
                user.reset_password_token = token
                user.reset_password_expires = expires
                db_session.commit()
                
                # Send email
                reset_link = url_for('auth.reset_password', token=token, _external=True)
                send_password_reset_email(user.email, reset_link)
            
        # Security: Always show same message
        flash('Si el correo está registrado, recibirás instrucciones para acceder a tu cuenta.', 'info')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token: str) -> Union[str, Response]:
    """
    Reset password using token.
    
    Flow:
    1. Validate token (exists and not expired)
    2. Show password form
    3. Update password
    4. Clear token
    """
    if g.user:
        return redirect(url_for('dashboard.index'))
        
    from datetime import datetime, timezone
    
    # Find user by token
    user = db_session.query(AppUser).filter_by(reset_password_token=token).first()
    
    # Validate token
    # Comparison must be timezone aware
    if not user or not user.reset_password_expires or user.reset_password_expires < datetime.now(timezone.utc):
        flash('El enlace de recuperación es inválido o ha expirado.', 'danger')
        return redirect(url_for('auth.forgot_password'))

        
    if request.method == 'POST':
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        if not password or len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return render_template('auth/reset_password.html', token=token)
            
        if password != password_confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('auth/reset_password.html', token=token)
            
        # Update password
        user.set_password(password)
        user.reset_password_token = None
        user.reset_password_expires = None
        db_session.commit()
        
        flash('Tu contraseña ha sido restablecida exitosamente. Inicia sesión.', 'success')
        return redirect(url_for('auth.login'))
        
    return render_template('auth/reset_password.html', token=token)

