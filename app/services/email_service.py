"""
Email service for sending invitations, alerts, and reports.
Uses Flask-Mail for SMTP integration with UTF-8 support.
"""
import logging
from flask import current_app
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)

mail = Mail()

# Nota: Flask-Mail ya maneja UTF-8 correctamente con Message()
# Para emails directos con smtplib, usar EmailMessage (ver debug.py)


def init_mail(app):
    """Initialize Flask-Mail with app."""
    mail.init_app(app)


def _mail_enabled() -> bool:
    """
    Check if mail is properly configured and enabled.
    Prevents 500 errors in dev or misconfigured environments.
    """
    cfg = current_app.config
    return (
        not cfg.get("MAIL_SUPPRESS_SEND", False)
        and cfg.get("MAIL_SERVER")
        and cfg.get("MAIL_USERNAME")
    )


def send_invitation_email(
    to_email: str,
    full_name: str,
    invite_link: str,
    role: str,
    tenant_name: str
) -> bool:
    """
    Send invitation email with UTF-8 support for accents and emojis.
    
    Args:
        to_email: Recipient email
        full_name: Full name (may contain accents: José, María)
        invite_link: Invitation URL
        role: ADMIN or STAFF
        tenant_name: Tenant name (may contain accents: Ferretería López)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        logger.info(f"[EMAIL] Preparando invitación para {to_email} con rol {role}")
        
        if not _mail_enabled():
            logger.warning(f"[MAIL DISABLED] Invitation email skipped for {to_email}")
            return True  # NO romper el flujo de la app

        # Subject con acentos y emojis (Flask-Mail maneja UTF-8)
        subject = f"🎉 Invitación a {tenant_name} - Sistema de Gestión"

        badge_bg = "#ffc107" if role == "ADMIN" else "#6c757d"
        badge_color = "#000" if role == "ADMIN" else "#fff"

        permissions = (
            """
            <li>Gestionar productos y categorías</li>
            <li>Registrar y gestionar ventas</li>
            <li>Crear y convertir presupuestos</li>
            <li>Gestionar proveedores y facturas</li>
            <li>Ver finanzas y balance</li>
            """
            if role == "ADMIN"
            else
            """
            <li>Ver catálogo de productos</li>
            <li>Registrar ventas en POS</li>
            <li>Crear presupuestos</li>
            <li>Ver productos faltantes</li>
            """
        )

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; }}
                .container {{ max-width: 600px; margin: auto; padding: 20px; }}
                .header {{ background: #007bff; color: #fff; padding: 20px; text-align: center; }}
                .content {{ background: #fff; padding: 30px; }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #28a745;
                    color: #fff !important;
                    text-decoration: none;
                    border-radius: 5px;
                }}
                .role-badge {{
                    background: {badge_bg};
                    color: {badge_color};
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🎉 ¡Has sido invitado!</h1>
                </div>
                <div class="content">
                    <p>Hola <strong>{full_name}</strong>,</p>
                    <p>Te invitaron a <strong>{tenant_name}</strong>.</p>
                    <p>Rol asignado: <span class="role-badge">{role}</span></p>
                    <h3>Tus permisos:</h3>
                    <ul>{permissions}</ul>

                    <div style="text-align:center;margin:30px 0;">
                        <a href="{invite_link}" class="button">✅ Aceptar Invitación</a>
                    </div>

                    <p style="font-size: 13px; color: #666;">
                        ⏰ El enlace expira en 7 días.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
¡Hola {full_name}!

Has sido invitado a {tenant_name}.
Rol asignado: {role}

Aceptá la invitación acá:
{invite_link}

⏰ Este enlace expira en 7 días.
"""

        # Flask-Mail maneja UTF-8 automáticamente con Message()
        msg = Message(
            subject=subject,
            recipients=[to_email],
            body=text_body,
            html=html_body,
        )
    
        logger.info(f"[EMAIL] Enviando invitación via Flask-Mail (UTF-8)...")
        mail.send(msg)
        logger.info(f"[EMAIL] ✓ Invitation email sent to {to_email}")
        return True

    except UnicodeEncodeError as e:
        logger.exception(f"[EMAIL] ✗ Unicode encoding error: {e}")
        logger.error("[EMAIL] HINT: Flask-Mail debería manejar UTF-8 automáticamente")
        return False
    
    except Exception as e:
        logger.exception(f"[EMAIL] ✗ Error sending invitation email: {e}")
        return False


def send_alert_email(to_email: str, subject: str, message: str) -> bool:
    try:
        if not _mail_enabled():
            logger.info(f"[MAIL DISABLED] Alert email skipped for {to_email}")
            return True

        msg = Message(subject=subject, recipients=[to_email], body=message)
        mail.send(msg)
        return True

    except Exception:
        logger.exception("Error sending alert email")
        return False


def send_low_stock_alert(to_emails: list, products: list, tenant_name: str) -> bool:
    try:
        if not _mail_enabled():
            logger.info("[MAIL DISABLED] Low stock alert skipped")
            return True

        rows = "".join(
            f"""
            <tr>
                <td>{p['name']}</td>
                <td align="center">{p['current']}</td>
                <td align="center">{p['minimum']}</td>
            </tr>
            """
            for p in products
        )

        html_body = f"""
        <h2>⚠️ Alerta de Stock Bajo - {tenant_name}</h2>
        <table border="1" cellpadding="8" cellspacing="0" width="100%">
            <tr>
                <th>Producto</th>
                <th>Stock Actual</th>
                <th>Stock Mínimo</th>
            </tr>
            {rows}
        </table>
        """

        msg = Message(
            subject=f"⚠️ Stock Bajo - {tenant_name}",
            recipients=to_emails,
            html=html_body,
        )

        mail.send(msg)
        return True

    except Exception:
        logger.exception("Error sending low stock alert")
        return False


def send_email(to: str, subject: str, template: str, text: str | None = None) -> bool:
    """
    Send a generic email (for testing or custom purposes).
    
    Args:
        to: Recipient email
        subject: Email subject
        template: HTML template
        text: Plain text body (optional)
    
    Returns:
        True if sent successfully, False otherwise
    """
    try:
        logger.info(f"[EMAIL] Attempting to send email to {to}")
        logger.info(f"[EMAIL] Subject: {subject}")
        
        if not _mail_enabled():
            logger.warning(f"[MAIL DISABLED] Email skipped for {to}")
            logger.warning(f"[MAIL DISABLED] Reason: MAIL_SUPPRESS_SEND={current_app.config.get('MAIL_SUPPRESS_SEND')}")
            logger.warning(f"[MAIL DISABLED] MAIL_SERVER={current_app.config.get('MAIL_SERVER')}")
            logger.warning(f"[MAIL DISABLED] MAIL_USERNAME={'SET' if current_app.config.get('MAIL_USERNAME') else 'NOT SET'}")
            return True

        logger.info(f"[EMAIL] Creating message object...")
        msg = Message(
            subject=subject,
            recipients=[to],
            body=text or "Email test",
            html=template
        )
        
        logger.info(f"[EMAIL] Sending via Flask-Mail (SMTP: {current_app.config.get('MAIL_SERVER')}:{current_app.config.get('MAIL_PORT')})...")
        mail.send(msg)
        logger.info(f"[EMAIL] ✓ Email sent successfully to {to}")
        return True

    except Exception as e:
        logger.exception(f"[EMAIL] ✗ Failed to send email to {to}: {str(e)}")
        return False


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """
    Send password reset email.
    
    Args:
        to_email: Recipient email
        reset_link: Full URL for password reset (including token)
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        logger.info(f"[EMAIL] Sending password reset email to {to_email}")
        
        if not _mail_enabled():
            logger.warning(f"[EMAIL] Mail disabled, skipping password reset email to {to_email}")
            # En dev, loguear el link para poder probar sin email
            logger.info(f"[EMAIL] RESET LINK: {reset_link}")
            return True

        subject = "🔑 Restablecer tu contraseña - Sistema de Gestión"
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: auto; padding: 20px; }}
                .header {{ background: #dc3545; color: #fff; padding: 20px; text-align: center; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #ddd; }}
                .button {{
                    display: inline-block;
                    padding: 12px 30px;
                    background: #dc3545;
                    color: #fff !important;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                    margin: 20px 0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Recuperación de Contraseña</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta.</p>
                    <p>Si fuiste tú, haz clic en el siguiente botón para continuar:</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_link}" class="button">Restablecer Contraseña</a>
                    </div>
                    
                    <p>Si el botón no funciona, copia y pega este enlace en tu navegador:</p>
                    <p style="font-size: 12px; color: #666; word-break: break-all;">{reset_link}</p>
                    
                    <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
                    
                    <p style="font-size: 13px; color: #999;">
                        Si no solicitaste este cambio, puedes ignorar este correo. Tu contraseña seguirá siendo la misma.
                        Este enlace expirará en 1 hora por seguridad.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(
            subject=subject,
            recipients=[to_email],
            html=html_body
        )
        
        mail.send(msg)
        logger.info(f"[EMAIL] ✓ Password reset email sent to {to_email}")
        return True
        
    except Exception as e:
        logger.exception(f"[EMAIL] ✗ Error sending password reset email: {e}")
        return False

def send_oauth_login_email(to_email: str, provider: str) -> bool:
    """
    Send email informing user they must login via OAuth (Google).
    
    Args:
        to_email: Recipient email
        provider: Auth provider name (e.g. 'google')
        
    Returns:
        bool: True if sent successfully
    """
    try:
        logger.info(f"[EMAIL] Sending OAuth login reminder to {to_email}")
        
        if not _mail_enabled():
            logger.warning(f"[EMAIL] Mail disabled, skipping OAuth reminder to {to_email}")
            return True

        subject = "ℹ️ Inicio de sesión - SaaS Stock"
        
        provider_name = "Google" if provider == 'google' else provider.title()
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; color: #333; line-height: 1.6; }}
                .container {{ max-width: 600px; margin: auto; padding: 20px; }}
                .header {{ background: #0f172a; color: #fff; padding: 20px; text-align: center; }}
                .content {{ background: #fff; padding: 30px; border: 1px solid #ddd; }}
                .box {{
                    background: #f8fafc;
                    border: 1px solid #e2e8f0;
                    padding: 15px;
                    border-radius: 8px;
                    margin: 20px 0;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Información de Cuenta</h1>
                </div>
                <div class="content">
                    <p>Hola,</p>
                    <p>Recibimos una solicitud para restablecer la contraseña de tu cuenta asociada a <strong>{to_email}</strong>.</p>
                    
                    <div class="box">
                        <p>Tu cuenta está registrada mediante <strong>{provider_name}</strong>.</p>
                        <p>No necesitas una contraseña. Simplemente inicia sesión haciendo clic en el botón "Continuar con {provider_name}".</p>
                    </div>
                    
                    <p>Si tienes problemas para acceder, por favor contacta a soporte.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(
            subject=subject,
            recipients=[to_email],
            html=html_body
        )
        
        mail.send(msg)
        logger.info(f"[EMAIL] ✓ OAuth reminder sent to {to_email}")
        return True
        
    except Exception as e:
        logger.exception(f"[EMAIL] ✗ Error sending OAuth reminder: {e}")
        return False
