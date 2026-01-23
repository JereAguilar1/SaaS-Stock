"""
User management blueprint for multi-tenant SaaS.
Allows OWNER to invite, manage, and remove users from their tenant.
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from app.database import get_session
from app.middleware import require_login, require_tenant
from app.decorators.permissions import owner_only
from app.models import AppUser, UserTenant, Tenant
from sqlalchemy.exc import IntegrityError
import secrets
import jwt
import os
from datetime import datetime, timedelta


users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/')
@require_login
@require_tenant
@owner_only
def list_users():
    """
    List all users in the current tenant.
    Only accessible by OWNER.
    """
    session = get_session()
    tenant_id = g.tenant_id
    
    # Get all user-tenant relationships for this tenant
    user_tenants = session.query(UserTenant, AppUser).join(
        AppUser, AppUser.id == UserTenant.user_id
    ).filter(
        UserTenant.tenant_id == tenant_id,
        UserTenant.active == True
    ).order_by(
        UserTenant.role.desc(),  # OWNER first, then ADMIN, then STAFF
        UserTenant.created_at.asc()
    ).all()
    
    return render_template('users/list.html', user_tenants=user_tenants)


@users_bp.route('/invite', methods=['GET', 'POST'])
@require_login
@require_tenant
@owner_only
def invite():
    """
    Generate invitation link for new user.
    Only accessible by OWNER.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'STAFF')
        
        # Validations
        if not email or '@' not in email:
            flash('Email inválido.', 'danger')
            return render_template('users/invite.html')
        
        if not full_name:
            flash('El nombre completo es requerido.', 'danger')
            return render_template('users/invite.html')
        
        if role not in ['ADMIN', 'STAFF']:
            flash('Rol inválido. Solo puedes invitar ADMIN o STAFF.', 'danger')
            return render_template('users/invite.html')
        
        session = get_session()
        
        # Check if email already in tenant
        existing_user = session.query(AppUser).filter_by(email=email).first()
        if existing_user:
            user_tenant = session.query(UserTenant).filter_by(
                user_id=existing_user.id,
                tenant_id=g.tenant_id,
                active=True
            ).first()
            
            if user_tenant:
                flash(f'El usuario {email} ya pertenece a este negocio.', 'warning')
                return redirect(url_for('users.list_users'))
        
        # Generate invitation token (JWT)
        secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
        payload = {
            'email': email,
            'full_name': full_name,
            'role': role,
            'tenant_id': g.tenant_id,
            'invited_by': g.user.id,
            'exp': datetime.utcnow() + timedelta(days=7)  # Expires in 7 days
        }
        
        token = jwt.encode(payload, secret_key, algorithm='HS256')
        
        # Create invitation link
        invitation_link = url_for('users.accept_invite', token=token, _external=True)
        
        # Send invitation email
        try:
            from app.services.email_service import send_invitation_email
            tenant = session.query(Tenant).filter_by(id=g.tenant_id).first()
            tenant_name = tenant.name if tenant else "Sistema Ferretería"
            
            email_sent = send_invitation_email(
                to_email=email,
                full_name=full_name,
                invite_link=invitation_link,
                role=role,
                tenant_name=tenant_name
            )
            
            if email_sent:
                flash(f'Invitación enviada a {email}.', 'success')
            else:
                # If email fails, show link
                flash(f'No se pudo enviar el email. Envía este link manualmente:', 'warning')
                flash(invitation_link, 'info')
        except Exception as e:
            # Fallback: show link if email service is not configured
            flash(f'Invitación generada. Envía este link a {email}:', 'success')
            flash(invitation_link, 'info')
        
        return redirect(url_for('users.list_users'))
    
    # GET request
    return render_template('users/invite.html')


@users_bp.route('/accept-invite/<token>', methods=['GET', 'POST'])
def accept_invite(token):
    """
    Accept invitation and create/associate user with tenant.
    Public endpoint (no authentication required).
    """
    try:
        # Decode token
        secret_key = os.getenv('SECRET_KEY', 'dev-secret-key')
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
        
        email = payload['email']
        full_name = payload['full_name']
        role = payload['role']
        tenant_id = payload['tenant_id']
        
    except jwt.ExpiredSignatureError:
        flash('Este link de invitación ha expirado.', 'danger')
        return redirect(url_for('auth.login'))
    except jwt.InvalidTokenError:
        flash('Link de invitación inválido.', 'danger')
        return redirect(url_for('auth.login'))
    
    session = get_session()
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')
        
        # Validations
        if not password or len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            return render_template('users/accept_invite.html', 
                                   email=email, full_name=full_name, role=role)
        
        if password != password_confirm:
            flash('Las contraseñas no coinciden.', 'danger')
            return render_template('users/accept_invite.html', 
                                   email=email, full_name=full_name, role=role)
        
        try:
            # Check if user already exists
            existing_user = session.query(AppUser).filter_by(email=email).first()
            
            if existing_user:
                # User exists, just associate with tenant
                user = existing_user
            else:
                # Create new user
                user = AppUser(
                    email=email,
                    full_name=full_name,
                    active=True
                )
                user.set_password(password)
                session.add(user)
                session.flush()
            
            # Create user-tenant association
            user_tenant = UserTenant(
                user_id=user.id,
                tenant_id=tenant_id,
                role=role,
                active=True
            )
            session.add(user_tenant)
            session.commit()
            
            flash(f'¡Bienvenido! Tu cuenta ha sido creada con rol de {role}.', 'success')
            return redirect(url_for('auth.login'))
            
        except IntegrityError:
            session.rollback()
            flash('Error al crear la cuenta. Intenta nuevamente.', 'danger')
            return render_template('users/accept_invite.html', 
                                   email=email, full_name=full_name, role=role)
        except Exception as e:
            session.rollback()
            flash(f'Error inesperado: {str(e)}', 'danger')
            return render_template('users/accept_invite.html', 
                                   email=email, full_name=full_name, role=role)
    
    # GET request - show accept form
    return render_template('users/accept_invite.html', 
                           email=email, full_name=full_name, role=role, token=token)


@users_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@require_login
@require_tenant
@owner_only
def edit_user(id):
    """
    Edit user role in tenant.
    Only accessible by OWNER.
    """
    session = get_session()
    tenant_id = g.tenant_id
    
    # Get user-tenant relationship
    user_tenant = session.query(UserTenant, AppUser).join(
        AppUser, AppUser.id == UserTenant.user_id
    ).filter(
        UserTenant.id == id,
        UserTenant.tenant_id == tenant_id
    ).first()
    
    if not user_tenant:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('users.list_users'))
    
    ut, user = user_tenant
    
    # Prevent editing own role
    if user.id == g.user.id:
        flash('No puedes editar tu propio rol.', 'warning')
        return redirect(url_for('users.list_users'))
    
    # Prevent editing other OWNER
    if ut.role == 'OWNER':
        flash('No puedes editar el rol de otro OWNER.', 'warning')
        return redirect(url_for('users.list_users'))
    
    if request.method == 'POST':
        new_role = request.form.get('role')
        
        if new_role not in ['ADMIN', 'STAFF']:
            flash('Rol inválido.', 'danger')
            return render_template('users/edit.html', user_tenant=ut, user=user)
        
        # Update role
        ut.role = new_role
        session.commit()
        
        flash(f'Rol de {user.email} actualizado a {new_role}.', 'success')
        return redirect(url_for('users.list_users'))
    
    # GET request
    return render_template('users/edit.html', user_tenant=ut, user=user)


@users_bp.route('/<int:id>/remove', methods=['POST'])
@require_login
@require_tenant
@owner_only
def remove_user(id):
    """
    Remove user from tenant (deactivate user-tenant relationship).
    Only accessible by OWNER.
    """
    session = get_session()
    tenant_id = g.tenant_id
    
    # Get user-tenant relationship
    user_tenant = session.query(UserTenant, AppUser).join(
        AppUser, AppUser.id == UserTenant.user_id
    ).filter(
        UserTenant.id == id,
        UserTenant.tenant_id == tenant_id,
        UserTenant.active == True
    ).first()
    
    if not user_tenant:
        flash('Usuario no encontrado.', 'danger')
        return redirect(url_for('users.list_users'))
    
    ut, user = user_tenant
    
    # Prevent removing self
    if user.id == g.user.id:
        flash('No puedes removerte a ti mismo.', 'warning')
        return redirect(url_for('users.list_users'))
    
    # Prevent removing other OWNER
    if ut.role == 'OWNER':
        flash('No puedes remover a otro OWNER.', 'warning')
        return redirect(url_for('users.list_users'))
    
    # Deactivate user-tenant relationship
    ut.active = False
    session.commit()
    
    flash(f'Usuario {user.email} removido del negocio.', 'success')
    return redirect(url_for('users.list_users'))
