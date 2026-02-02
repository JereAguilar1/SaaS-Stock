"""
Flask CLI commands for admin panel management.

Commands:
- flask create-admin: Create a new admin user
"""

import click
import re
from flask import current_app
from app.database import db_session
from app.models import AdminUser


def init_cli_commands(app):
    """Register CLI commands with Flask app."""
    
    @app.cli.command('create-admin')
    @click.option('--email', prompt=True, help='Admin email address')
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Admin password')
    def create_admin(email, password):
        """Create a new admin user for the backoffice panel."""
        
        # Validate email format
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            click.echo(click.style('❌ Email inválido. Use formato: user@example.com', fg='red'))
            return
        
        # Validate password length
        if len(password) < 6:
            click.echo(click.style('❌ La contraseña debe tener al menos 6 caracteres.', fg='red'))
            return
        
        # Check if admin already exists
        existing_admin = db_session.query(AdminUser).filter_by(email=email).first()
        if existing_admin:
            click.echo(click.style(f'❌ Ya existe un administrador con el email: {email}', fg='red'))
            return
        
        # Create admin user
        try:
            admin = AdminUser(email=email)
            admin.set_password(password)
            
            db_session.add(admin)
            db_session.commit()
            
            click.echo(click.style(f'\n✅ Administrador creado exitosamente!', fg='green', bold=True))
            click.echo(f'   Email: {email}')
            click.echo(f'   ID: {admin.id}')
            click.echo(f'\n💡 Accede al panel admin en: /admin/login')
            
        except Exception as e:
            db_session.rollback()
            click.echo(click.style(f'❌ Error al crear administrador: {str(e)}', fg='red'))
