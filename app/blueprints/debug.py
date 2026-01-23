"""Debug blueprint with testing endpoints."""
import logging
import smtplib
import sys
from flask import Blueprint, jsonify, current_app
from email.message import EmailMessage  # ← Usar EmailMessage en lugar de MIME*

debug_bp = Blueprint('debug', __name__)
logger = logging.getLogger(__name__)

# Force stdout/stderr to be unbuffered for Docker logs
sys.stdout = sys.stdout
sys.stderr = sys.stderr


@debug_bp.route('/test-email')
def test_email():
    """
    Test endpoint para envío SMTP directo con debugging completo.
    
    Returns:
        200 OK: Email enviado exitosamente
        500 ERROR: Fallo con mensaje detallado
    """
    # ===============================================
    # 1. VERIFICAR VARIABLES DE ENTORNO
    # ===============================================
    logger.info("=" * 60)
    logger.info("INICIO TEST EMAIL - Verificando configuración SMTP")
    logger.info("=" * 60)
    
    smtp_host = current_app.config.get('MAIL_SERVER')
    smtp_port = current_app.config.get('MAIL_PORT')
    smtp_user = current_app.config.get('MAIL_USERNAME')
    smtp_pass = current_app.config.get('MAIL_PASSWORD')
    smtp_from = current_app.config.get('MAIL_DEFAULT_SENDER')
    smtp_to = "tandilaitech@gmail.com"
    
    logger.info(f"SMTP_HOST: {smtp_host or '❌ NO CONFIGURADO'}")
    logger.info(f"SMTP_PORT: {smtp_port or '❌ NO CONFIGURADO'}")
    logger.info(f"SMTP_USER: {smtp_user or '❌ NO CONFIGURADO'}")
    logger.info(f"SMTP_PASSWORD: {'***' if smtp_pass else '❌ NO CONFIGURADO'}")
    logger.info(f"SMTP_FROM: {smtp_from or '❌ NO CONFIGURADO'}")
    logger.info(f"SMTP_TO: {smtp_to}")
    
    # Validar que todas las variables estén presentes
    missing = []
    if not smtp_host:
        missing.append("SMTP_HOST")
    if not smtp_port:
        missing.append("SMTP_PORT")
    if not smtp_user:
        missing.append("SMTP_USER")
    if not smtp_pass:
        missing.append("SMTP_PASSWORD")
    if not smtp_from:
        missing.append("SMTP_FROM")
    
    if missing:
        error_msg = f"❌ Variables de entorno faltantes: {', '.join(missing)}"
        logger.error(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'missing_vars': missing,
            'hint': 'Verificar .env o docker-compose.yml'
        }), 500
    
    # ===============================================
    # 2. PREPARAR MENSAJE CON UTF-8
    # ===============================================
    logger.info("-" * 60)
    logger.info("Preparando mensaje de prueba con soporte UTF-8...")
    
    try:
        # Crear EmailMessage (soporta UTF-8 nativamente)
        msg = EmailMessage()
        
        # Headers con UTF-8 explícito
        msg['Subject'] = 'SMTP Test SaaS-Stock - Debugging con áéíóú ñ 🚀'
        msg['From'] = smtp_from
        msg['To'] = smtp_to
        
        # Contenido texto plano (fallback)
        text_body = """
Este es un email de prueba del sistema SaaS Stock.

Prueba de caracteres especiales:
- Acentos: áéíóúñ ÁÉÍÓÚÑ
- Emojis: 🚀 ✅ ❌ 📧
- Símbolos: © ® ™ € £

Si recibes este mensaje, el SMTP está funcionando correctamente con UTF-8.
        """
        
        # Contenido HTML (principal)
        html_body = f"""
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Arial, sans-serif;">
            <h1 style="color: #28a745;">✅ SMTP Funcionando con UTF-8</h1>
            
            <p>Este es un email de prueba del sistema <strong>SaaS Stock</strong>.</p>
            
            <h2>Prueba de caracteres especiales:</h2>
            <ul>
                <li><strong>Acentos:</strong> áéíóúñ ÁÉÍÓÚÑ ¡Hola! ¿Qué tal?</li>
                <li><strong>Emojis:</strong> 🚀 ✅ ❌ 📧 💾 🔒 🎉</li>
                <li><strong>Símbolos:</strong> © ® ™ € £ ¥</li>
            </ul>
            
            <p>Si recibes este mensaje correctamente, el SMTP está configurado para UTF-8.</p>
            
            <hr>
            <p style="color: #666; font-size: 12px;">
                Enviado desde: {smtp_from}<br>
                Servidor: {smtp_host}:{smtp_port}<br>
                Encoding: UTF-8
            </p>
        </body>
        </html>
        """
        
        # Establecer contenido con UTF-8 explícito
        msg.set_content(text_body, charset='utf-8')
        msg.add_alternative(html_body, subtype='html', charset='utf-8')
        
        logger.info(f"✓ Mensaje preparado con UTF-8: From={smtp_from}, To={smtp_to}")
        logger.info(f"✓ Subject con acentos y emojis: {msg['Subject']}")
        
    except Exception as e:
        error_msg = f"❌ Error al preparar mensaje: {str(e)}"
        logger.exception(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stage': 'message_preparation'
        }), 500
    
    # ===============================================
    # 3. CONECTAR A SMTP CON DEBUG COMPLETO
    # ===============================================
    logger.info("-" * 60)
    logger.info(f"Conectando a {smtp_host}:{smtp_port}...")
    
    smtp_connection = None
    
    try:
        # Crear conexión SMTP con debug level 1 (muestra todo en logs)
        smtp_connection = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
        smtp_connection.set_debuglevel(1)  # ← ESTO MUESTRA TODO EN LOGS
        
        logger.info("✓ Conexión SMTP establecida")
        
        # ===============================================
        # 4. INICIAR TLS
        # ===============================================
        logger.info("-" * 60)
        logger.info("Iniciando TLS...")
        smtp_connection.starttls()
        logger.info("✓ TLS iniciado exitosamente")
        
        # ===============================================
        # 5. AUTENTICACIÓN
        # ===============================================
        logger.info("-" * 60)
        logger.info(f"Autenticando como {smtp_user}...")
        smtp_connection.login(smtp_user, smtp_pass)
        logger.info("✓ Autenticación exitosa")
        
        # ===============================================
        # 6. ENVIAR EMAIL CON UTF-8
        # ===============================================
        logger.info("-" * 60)
        logger.info(f"Enviando email a {smtp_to} con encoding UTF-8...")
        
        # Usar send_message() en lugar de sendmail() para soporte UTF-8
        smtp_connection.send_message(msg)
        
        logger.info("✓ Email enviado exitosamente (UTF-8)")
        
        # ===============================================
        # 7. CERRAR CONEXIÓN
        # ===============================================
        smtp_connection.quit()
        logger.info("✓ Conexión SMTP cerrada")
        
        logger.info("=" * 60)
        logger.info("✅ TEST EMAIL COMPLETADO EXITOSAMENTE")
        logger.info("=" * 60)
        
        return jsonify({
            'success': True,
            'message': 'Email enviado exitosamente',
            'smtp_host': smtp_host,
            'smtp_port': smtp_port,
            'smtp_from': smtp_from,
            'smtp_to': smtp_to,
            'hint': 'Revisa la bandeja de entrada (o spam) de ' + smtp_to
        }), 200
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"❌ Error de autenticación SMTP: {str(e)}"
        logger.exception(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stage': 'authentication',
            'hints': [
                'Verificar SMTP_USER y SMTP_PASSWORD',
                'Si usas Gmail, habilitar "App Passwords" en https://myaccount.google.com/apppasswords',
                'Si usas Gmail, verificar que la cuenta tenga 2FA activado',
                'Verificar que el usuario tenga permisos SMTP'
            ]
        }), 500
        
    except smtplib.SMTPConnectError as e:
        error_msg = f"❌ Error de conexión SMTP: {str(e)}"
        logger.exception(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stage': 'connection',
            'hints': [
                f'Verificar que {smtp_host}:{smtp_port} sea accesible desde el container',
                'Verificar reglas de firewall',
                'Probar con telnet desde el container: telnet smtp.gmail.com 587'
            ]
        }), 500
        
    except UnicodeEncodeError as e:
        error_msg = f"❌ Error de encoding Unicode: {str(e)}"
        logger.exception(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stage': 'unicode_encoding',
            'hints': [
                'Este error ya NO debería ocurrir con EmailMessage y send_message()',
                'Verificar que se esté usando EmailMessage (no MIMEMultipart)',
                'Verificar charset="utf-8" en set_content() y add_alternative()'
            ]
        }), 500
        
    except smtplib.SMTPException as e:
        error_msg = f"❌ Error SMTP general: {str(e)}"
        logger.exception(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stage': 'smtp_general'
        }), 500
        
    except Exception as e:
        error_msg = f"❌ Error inesperado: {str(e)}"
        logger.exception(error_msg)
        return jsonify({
            'success': False,
            'error': error_msg,
            'stage': 'unknown',
            'type': type(e).__name__
        }), 500
        
    finally:
        # Asegurar que la conexión se cierre siempre
        if smtp_connection:
            try:
                smtp_connection.quit()
            except:
                pass


@debug_bp.route('/test-email-config')
def test_email_config():
    """
    Endpoint para verificar configuración SMTP sin enviar email.
    
    Returns:
        200 OK: Configuración válida
        500 ERROR: Configuración incompleta
    """
    smtp_host = current_app.config.get('MAIL_SERVER')
    smtp_port = current_app.config.get('MAIL_PORT')
    smtp_user = current_app.config.get('MAIL_USERNAME')
    smtp_pass = current_app.config.get('MAIL_PASSWORD')
    smtp_from = current_app.config.get('MAIL_DEFAULT_SENDER')
    mail_suppress = current_app.config.get('MAIL_SUPPRESS_SEND')
    
    config = {
        'MAIL_SERVER': smtp_host or None,
        'MAIL_PORT': smtp_port or None,
        'MAIL_USERNAME': smtp_user or None,
        'MAIL_PASSWORD': '***' if smtp_pass else None,
        'MAIL_DEFAULT_SENDER': smtp_from or None,
        'MAIL_SUPPRESS_SEND': mail_suppress
    }
    
    missing = [k for k, v in config.items() if v is None and k != 'MAIL_SUPPRESS_SEND']
    
    if missing:
        return jsonify({
            'configured': False,
            'missing': missing,
            'config': config,
            'hint': 'Agregar variables SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM'
        }), 500
    
    return jsonify({
        'configured': True,
        'config': config,
        'message': 'Configuración SMTP completa. Usar /test-email para probar envío.'
    }), 200
