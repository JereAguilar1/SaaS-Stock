"""
Authentication blueprint for multi-tenant SaaS.
Handles user registration, login, logout, and tenant selection.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from sqlalchemy.exc import IntegrityError
from app.database import db_session
from app.models import AppUser, Tenant, UserTenant
import re


auth_bp = Blueprint('auth', __name__)


def is_valid_email(email):
    """Validate email format."""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def generate_slug(name):
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


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Registration page - creates user + tenant + user_tenant relationship.
    
    Flow:
    1. User provides: email, password, full_name, business_name
    2. Create Tenant (business)
    3. Create AppUser
    4. Create UserTenant with role=OWNER
    5. Auto-login (set session)
    6. Redirect to dashboard
    """
    # If already authenticated, redirect to dashboard
    if g.user:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        full_name = request.form.get('full_name', '').strip()
        business_name = request.form.get('business_name', '').strip()
        
        # Validations
        errors = []
        
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
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return render_template('auth/register.html'), 400
        
        try:
            # 1. Create Tenant
            slug = generate_slug(business_name)
            
            # Ensure slug is unique
            base_slug = slug
            counter = 1
            while db_session.query(Tenant).filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            tenant = Tenant(
                slug=slug,
                name=business_name,
                active=True
            )
            db_session.add(tenant)
            db_session.flush()  # Get tenant.id
            
            # 2. Create AppUser
            user = AppUser(
                email=email,
                full_name=full_name,
                active=True
            )
            user.set_password(password)
            db_session.add(user)
            db_session.flush()  # Get user.id
            
            # 3. Create UserTenant (OWNER role)
            user_tenant = UserTenant(
                user_id=user.id,
                tenant_id=tenant.id,
                role='OWNER',
                active=True
            )
            db_session.add(user_tenant)
            
            db_session.commit()
            
            # 4. Auto-login
            session.clear()
            session['user_id'] = user.id
            session['tenant_id'] = tenant.id
            session.permanent = True
            
            flash(f'¡Bienvenido {full_name}! Tu negocio "{business_name}" ha sido creado.', 'success')
            return redirect(url_for('dashboard.index'))
            
        except IntegrityError as e:
            db_session.rollback()
            if 'app_user_email_key' in str(e):
                flash('Este email ya está registrado. Usa otro o inicia sesión.', 'danger')
            else:
                flash('Error al crear la cuenta. Intenta nuevamente.', 'danger')
            return render_template('auth/register.html'), 400
        except Exception as e:
            db_session.rollback()
            flash(f'Error inesperado: {str(e)}', 'danger')
            return render_template('auth/register.html'), 500
    
    # GET request - show registration form
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page - validates email + password.
    
    Flow:
    1. Validate credentials
    2. Set session['user_id']
    3. If user has only 1 tenant -> auto-select tenant_id
    4. If user has multiple tenants -> redirect to /select-tenant
    5. If user has 0 tenants -> error (shouldn't happen)
    6. Redirect to dashboard or 'next' param
    """
    # If already authenticated, redirect to dashboard
    if g.user:
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        next_url = request.args.get('next')
        
        if not email or not password:
            flash('Email y contraseña son requeridos.', 'danger')
            return render_template('auth/login.html'), 400
        
        # Find user
        user = db_session.query(AppUser).filter_by(email=email).first()
        
        if not user or not user.active:
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('auth/login.html'), 401
        
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
        
        # Authentication successful - set user_id in session
        session.clear()
        session['user_id'] = user.id
        session.permanent = True
        
        # Get user's tenants
        user_tenants = db_session.query(UserTenant).filter_by(
            user_id=user.id,
            active=True
        ).all()
        
        if len(user_tenants) == 0:
            # User has no tenants (shouldn't happen in normal flow)
            flash('Tu cuenta no tiene negocios asociados. Contacta soporte.', 'danger')
            session.clear()
            return render_template('auth/login.html'), 403
        
        elif len(user_tenants) == 1:
            # Auto-select the only tenant
            session['tenant_id'] = user_tenants[0].tenant_id
            flash(f'Bienvenido, {user.full_name or user.email}!', 'success')
            
            # Redirect to 'next' or dashboard
            if next_url:
                return redirect(next_url)
            return redirect(url_for('dashboard.index'))
        
        else:
            # User has multiple tenants -> let them choose
            flash('Selecciona un negocio para continuar.', 'info')
            return redirect(url_for('auth.select_tenant'))
    
    # GET request - show login form
    return render_template('auth/login.html')


@auth_bp.route('/select-tenant', methods=['GET', 'POST'])
def select_tenant():
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
def logout():
    """Logout endpoint - clear session and redirect to login with query param."""
    session.clear()
    # Use query parameter instead of flash to avoid persistence issues
    return redirect(url_for('auth.login', logged_out='1'))


@auth_bp.route('/create-business', methods=['GET', 'POST'])
def create_business():
    """
    Create first business page for logged-in users.
    
    Only accessible if user is logged in.
    Replaces the need to go to register for new OAuth users.
    """
    if not g.user:
        flash('Debes iniciar sesión primero.', 'warning')
        return redirect(url_for('auth.login'))
        
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip()
        
        if not business_name:
            flash('El nombre del negocio es requerido.', 'danger')
            return render_template('auth/create_business.html'), 400
            
        try:
            # Create Tenant
            slug = generate_slug(business_name)
            
            # Ensure slug is unique
            base_slug = slug
            counter = 1
            while db_session.query(Tenant).filter_by(slug=slug).first():
                slug = f"{base_slug}-{counter}"
                counter += 1
            
            tenant = Tenant(
                slug=slug,
                name=business_name,
                active=True
            )
            db_session.add(tenant)
            db_session.flush()
            
            # Create UserTenant
            user_tenant = UserTenant(
                user_id=g.user.id,
                tenant_id=tenant.id,
                role='OWNER',
                active=True
            )
            db_session.add(user_tenant)
            db_session.commit()
            
            # Set tenant in session
            session['tenant_id'] = tenant.id
            session.permanent = True
            
            flash(f'¡Negocio "{business_name}" creado exitosamente!', 'success')
            return redirect(url_for('dashboard.index'))
            
        except IntegrityError:
            db_session.rollback()
            flash('Error al crear el negocio. Intenta nuevamente.', 'danger')
            return render_template('auth/create_business.html'), 400
        except Exception as e:
            db_session.rollback()
            flash(f'Error inesperado: {str(e)}', 'danger')
            return render_template('auth/create_business.html'), 500

    return render_template('auth/create_business.html')


@auth_bp.route('/')
def root():
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
