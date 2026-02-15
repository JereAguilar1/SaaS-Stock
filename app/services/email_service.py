"""
Email service for sending invitations, alerts, and reports.
Uses Flask-Mail for SMTP integration with UTF-8 support.
"""

import logging
from typing import List, Optional, Union, Dict, Any
from flask import Flask, current_app
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)

# Singleton instance
mail = Mail()


def init_mail(app: Flask) -> None:
    """Initialize Flask-Mail with app."""
    mail.init_app(app)


def _mail_enabled() -> bool:
    """Check if mail is properly configured and enabled."""
    cfg = current_app.config
    return (
        not cfg.get("MAIL_SUPPRESS_SEND", False)
        and bool(cfg.get("MAIL_SERVER"))
        and bool(cfg.get("MAIL_USERNAME"))
    )


def send_invitation_email(
    to_email: str,
    full_name: str,
    invite_link: str,
    role: str,
    tenant_name: str
) -> bool:
    """Send invitation email with UTF-8 support."""
    try:
        if not _mail_enabled():
            logger.warning(f"[MAIL DISABLED] Invitation skipped for {to_email}")
            return True

        subject = f"🎉 Invitación a {tenant_name} - Sistema de Gestión"
        bg = "#ffc107" if role == "ADMIN" else "#6c757d"
        color = "#000" if role == "ADMIN" else "#fff"

        perms = (
            "<li>Gestionar productos y categorías</li><li>Registrar y gestionar ventas</li>"
            "<li>Crear y convertir presupuestos</li><li>Gestionar proveedores y facturas</li>"
            "<li>Ver finanzas y balance</li>" if role == "ADMIN" else
            "<li>Ver catálogo de productos</li><li>Registrar ventas en POS</li>"
            "<li>Crear presupuestos</li><li>Ver productos faltantes</li>"
        )

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee;">
                <div style="background: #007bff; color: #fff; padding: 20px; text-align: center;">
                    <h1>🎉 ¡Has sido invitado!</h1>
                </div>
                <div style="padding: 30px;">
                    <p>Hola <strong>{full_name}</strong>, te invitaron a <strong>{tenant_name}</strong>.</p>
                    <p>Rol: <span style="background:{bg};color:{color};padding:5px 10px;border-radius:3px;">{role}</span></p>
                    <h3>Permisos:</h3><ul>{perms}</ul>
                    <div style="text-align:center;margin:30px 0;">
                        <a href="{invite_link}" style="padding:12px 30px;background:#28a745;color:#fff;text-decoration:none;border-radius:5px;">✅ Aceptar Invitación</a>
                    </div>
                    <p style="font-size:12px;color:#666;">⏰ Expira en 7 días.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg = Message(subject=subject, recipients=[to_email], body=f"Invitación a {tenant_name}: {invite_link}", html=html)
        mail.send(msg)
        return True
    except Exception as e:
        logger.exception(f"[EMAIL] Error invitation to {to_email}: {e}")
        return False


def send_alert_email(to_email: str, subject: str, message: str) -> bool:
    """Send a simple text alert email."""
    try:
        if not _mail_enabled(): return True
        mail.send(Message(subject=subject, recipients=[to_email], body=message))
        return True
    except Exception:
        logger.exception("Error sending alert email")
        return False


def send_low_stock_alert(to_emails: List[str], products: List[Dict[str, Any]], tenant_name: str) -> bool:
    """Send low stock alert report."""
    try:
        if not _mail_enabled(): return True
        rows = "".join(f"<tr><td>{p['name']}</td><td>{p['current']}</td><td>{p['minimum']}</td></tr>" for p in products)
        html = f"<h2>⚠️ Stock Bajo - {tenant_name}</h2><table border='1'>{rows}</table>"
        mail.send(Message(subject=f"⚠️ Stock Bajo - {tenant_name}", recipients=to_emails, html=html))
        return True
    except Exception:
        logger.exception("Error stock alert")
        return False


def send_email(to: str, subject: str, template: str, text: Optional[str] = None) -> bool:
    """Send a generic email."""
    try:
        if not _mail_enabled(): return True
        mail.send(Message(subject=subject, recipients=[to], body=text or "Email", html=template))
        return True
    except Exception as e:
        logger.exception(f"Error to {to}: {e}")
        return False


def send_password_reset_email(to_email: str, reset_link: str) -> bool:
    """Send password reset instructions."""
    try:
        if not _mail_enabled():
            logger.info(f"RESET LINK (Mail Disabled): {reset_link}")
            return True
        
        html = f"""
        <div style="font-family:Arial;max-width:600px;margin:auto;padding:20px;border:1px solid #ddd;">
            <div style="background:#dc3545;color:#fff;padding:20px;text-align:center;"><h1>Recuperación</h1></div>
            <div style="padding:30px;">
                <p>Hola, haz clic abajo para restablecer tu contraseña:</p>
                <div style="text-align:center;"><a href="{reset_link}" style="padding:12px 30px;background:#dc3545;color:#fff;text-decoration:none;border-radius:5px;">Restablecer</a></div>
                <p style="font-size:12px;color:#666;margin-top:20px;">Link: {reset_link}</p>
            </div>
        </div>
        """
        mail.send(Message(subject="🔑 Restablecer contraseña", recipients=[to_email], html=html))
        return True
    except Exception as e:
        logger.exception(f"Reset error to {to_email}: {e}")
        return False


def send_oauth_login_email(to_email: str, provider: str) -> bool:
    """Send OAuth reminder email."""
    try:
        if not _mail_enabled(): return True
        name = "Google" if provider == 'google' else provider.title()
        html = f"<h3>Tu cuenta usa {name}</h3><p>No necesitas contraseña, usa el botón de {name} para entrar.</p>"
        mail.send(Message(subject="ℹ️ Inicio de sesión", recipients=[to_email], html=html))
        return True
    except Exception as e:
        logger.exception(f"OAuth error to {to_email}: {e}")
        return False
