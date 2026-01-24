# 📧 SMTP Debugging - Solución Implementada

## 🎯 Problema Resuelto

**Antes:** Endpoint `/test-email` retornaba HTTP 200 pero no enviaba emails, sin logs ni errores visibles.

**Ahora:** Sistema completo de debugging SMTP con:
- ✅ Logs detallados en cada paso
- ✅ Tráfico SMTP visible (`set_debuglevel(1)`)
- ✅ HTTP 200 solo si el email se envió realmente
- ✅ HTTP 500 con mensaje claro si falló
- ✅ Validación de variables de entorno
- ✅ Compatible con Docker + Gunicorn

---

## ⚡ Quick Start (5 minutos)

### 1. Configurar Gmail App Password

```bash
# 1. Ir a: https://myaccount.google.com/apppasswords
# 2. Crear password para "Mail"
# 3. Copiar el código de 16 caracteres (sin espacios)
```

### 2. Configurar Variables

Editar `.env` o `docker-compose.yml`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop  # ← App Password (16 chars, sin espacios)
SMTP_FROM=tu-email@gmail.com
```

### 3. Reiniciar

```bash
docker compose down
docker compose up -d
```

### 4. Probar

```bash
# Opción 1: Script automático
chmod +x test_smtp.sh
./test_smtp.sh

# Opción 2: Manual
curl http://localhost:5000/test-email-config  # Verificar config
curl http://localhost:5000/test-email         # Enviar test
docker compose logs -f web                     # Ver logs
```

---

## 🔍 Endpoints Disponibles

### 1. `GET /test-email-config`

Verifica configuración **sin enviar email**.

**Response (OK):**
```json
{
  "configured": true,
  "config": {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USERNAME": "user@gmail.com",
    "MAIL_PASSWORD": "***"
  }
}
```

**Response (Error):**
```json
{
  "configured": false,
  "missing": ["MAIL_USERNAME", "MAIL_PASSWORD"],
  "hint": "Agregar variables SMTP_USER, SMTP_PASSWORD"
}
```

---

### 2. `GET /test-email`

Envía email de prueba a `tandilaitech@gmail.com` con **debugging completo**.

**Response (Exitosa):**
```json
{
  "success": true,
  "message": "Email enviado exitosamente",
  "smtp_host": "smtp.gmail.com",
  "smtp_to": "tandilaitech@gmail.com"
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "❌ Error de autenticación SMTP: ...",
  "stage": "authentication",
  "hints": [
    "Verificar SMTP_USER y SMTP_PASSWORD",
    "Si usas Gmail, habilitar App Passwords"
  ]
}
```

**Logs en `docker compose logs -f web`:**
```
INFO - ============================================================
INFO - INICIO TEST EMAIL - Verificando configuración SMTP
INFO - ============================================================
INFO - SMTP_HOST: smtp.gmail.com
INFO - Conectando a smtp.gmail.com:587...
send: 'ehlo ...'                         ← Diálogo SMTP
reply: b'250-smtp.gmail.com ...'
INFO - ✓ Conexión SMTP establecida
INFO - Iniciando TLS...
send: 'STARTTLS\r\n'
reply: b'220 Ready to start TLS\r\n'
INFO - ✓ TLS iniciado exitosamente
INFO - Autenticando como user@gmail.com...
send: 'AUTH PLAIN ...'
reply: b'235 Accepted\r\n'
INFO - ✓ Autenticación exitosa
INFO - Enviando email...
send: 'MAIL FROM:<user@gmail.com>'
reply: b'250 OK'
send: 'DATA\r\n'
data: (email content)
reply: b'250 Message accepted'
INFO - ✓ Email enviado exitosamente
INFO - ✅ TEST EMAIL COMPLETADO EXITOSAMENTE
```

---

## 🛠️ Debugging Commands

### Ver logs en tiempo real

```bash
# Todos los logs
docker compose logs -f web

# Solo SMTP/EMAIL
docker compose logs -f web | grep -E "SMTP|EMAIL|send:|reply:"

# Últimas 100 líneas
docker compose logs --tail=100 web
```

### Verificar variables en container

```bash
# Entrar al container
docker compose exec web bash

# Ver variables SMTP
env | grep SMTP
```

### Probar conectividad SMTP

```bash
# Desde el container
docker compose exec web bash
apt-get update && apt-get install -y telnet
telnet smtp.gmail.com 587

# Respuesta esperada:
# 220 smtp.gmail.com ESMTP ...
```

---

## ❌ Errores Comunes

### 1. "Variables faltantes"

**Causa:** Variables SMTP no configuradas en `.env` o `docker-compose.yml`.

**Solución:**
```bash
# 1. Agregar variables al .env
# 2. Reiniciar: docker compose down && docker compose up -d
# 3. Verificar: docker compose exec web env | grep SMTP
```

---

### 2. "Authentication failed (535)"

**Causa:** Password incorrecto o no es App Password.

**Solución:**
1. **NO uses tu password normal de Gmail**
2. Ir a: https://myaccount.google.com/apppasswords
3. Crear nueva App Password (requiere 2FA activado)
4. Copiar 16 caracteres **sin espacios**
5. Actualizar `SMTP_PASSWORD` en `.env`
6. Reiniciar: `docker compose down && docker compose up -d`

---

### 3. "Connection timeout"

**Causa:** Red bloqueada o firewall.

**Solución:**
```bash
# Probar conectividad
docker compose exec web telnet smtp.gmail.com 587

# Si falla, verificar:
# - Firewall del host
# - Reglas de Docker network
# - DNS resolution
```

---

## 📁 Archivos Modificados

### Nuevos archivos:
- `app/blueprints/debug.py` ← Endpoints de testing
- `test_smtp.sh` ← Script bash automatizado
- `SMTP_DEBUGGING_GUIDE.md` ← Guía completa (600+ líneas)
- `SMTP_QUICKSTART.md` ← Guía rápida (5 min)
- `SMTP_IMPLEMENTATION_SUMMARY.md` ← Resumen técnico
- `README_SMTP_DEBUG.md` ← Este archivo

### Archivos modificados:
- `app/services/email_service.py` ← Mejor logging en `send_email()`

---

## 🎯 Características Implementadas

### 1. Validación de Variables
```python
# Verifica que todas las variables estén configuradas
missing = []
if not smtp_host: missing.append("SMTP_HOST")
if not smtp_user: missing.append("SMTP_USER")
# ...

if missing:
    return jsonify({
        'error': f"Variables faltantes: {', '.join(missing)}",
        'hint': 'Verificar .env o docker-compose.yml'
    }), 500
```

### 2. Logging Detallado
```python
logger.info("=" * 60)
logger.info("INICIO TEST EMAIL")
logger.info("=" * 60)
logger.info(f"SMTP_HOST: {smtp_host}")
logger.info(f"SMTP_PORT: {smtp_port}")
# ... cada paso loggeado ...
```

### 3. Debug SMTP
```python
smtp = smtplib.SMTP(smtp_host, smtp_port)
smtp.set_debuglevel(1)  # ← Muestra TODO el tráfico SMTP
```

### 4. Manejo de Excepciones Específicas
```python
except smtplib.SMTPAuthenticationError as e:
    return jsonify({
        'error': f"Error de autenticación: {e}",
        'hints': ['Verificar App Password', '...']
    }), 500

except smtplib.SMTPConnectError as e:
    return jsonify({
        'error': f"Error de conexión: {e}",
        'hints': ['Verificar firewall', '...']
    }), 500
```

### 5. Respuestas HTTP Correctas
```python
# 200 solo si se envió realmente
return jsonify({'success': True, ...}), 200

# 500 si falló
return jsonify({'success': False, 'error': ...}), 500
```

---

## 🎉 Resultado Final

### Al ejecutar `/test-email`:

**Terminal:**
```bash
$ curl http://localhost:5000/test-email
{
  "success": true,
  "message": "Email enviado exitosamente"
}
```

**Logs (`docker compose logs -f web`):**
```
INFO - SMTP_HOST: smtp.gmail.com
send: 'ehlo ...'
reply: b'250-smtp.gmail.com'
INFO - ✓ Conexión SMTP establecida
send: 'STARTTLS\r\n'
reply: b'220 Ready to start TLS'
INFO - ✓ TLS iniciado
send: 'AUTH PLAIN ...'
reply: b'235 Accepted'
INFO - ✓ Autenticación exitosa
send: 'MAIL FROM:<...>'
reply: b'250 OK'
INFO - ✓ Email enviado exitosamente
INFO - ✅ TEST COMPLETADO
```

**Gmail:**
- ✅ Email recibido en `tandilaitech@gmail.com`
- Subject: "SMTP Test SaaS-Stock - Debugging"

---

## 📚 Documentación

| Archivo | Descripción | Audiencia |
|---------|-------------|-----------|
| `SMTP_QUICKSTART.md` | Setup en 5 minutos | Usuarios |
| `SMTP_DEBUGGING_GUIDE.md` | Guía completa | Developers |
| `SMTP_IMPLEMENTATION_SUMMARY.md` | Resumen técnico | Tech leads |
| `test_smtp.sh` | Script automatizado | DevOps |
| `README_SMTP_DEBUG.md` | Este archivo | Todos |

---

## ✅ Checklist de Verificación

- [ ] Variables SMTP configuradas en `.env`
- [ ] App Password de Gmail creado (16 chars)
- [ ] Container reiniciado: `docker compose down && docker compose up -d`
- [ ] Variables visibles en container: `docker compose exec web env | grep SMTP`
- [ ] Config verificada: `curl http://localhost:5000/test-email-config`
- [ ] Email enviado: `curl http://localhost:5000/test-email`
- [ ] Logs visibles: `docker compose logs -f web | grep -E "SMTP|EMAIL"`
- [ ] Email recibido en `tandilaitech@gmail.com`

---

## 🆘 Soporte

Si después de seguir esta guía el email aún no se envía:

1. **Ejecutar:**
   ```bash
   ./test_smtp.sh
   ```

2. **Revisar logs completos:**
   ```bash
   docker compose logs --tail=200 web > smtp_logs.txt
   ```

3. **Verificar variables:**
   ```bash
   docker compose exec web env | grep SMTP
   ```

4. **Consultar:**
   - `SMTP_DEBUGGING_GUIDE.md` → Troubleshooting avanzado
   - Gmail SMTP: https://support.google.com/mail/answer/7126229

---

**Fecha:** 2026-01-22  
**Estado:** ✅ IMPLEMENTACIÓN COMPLETA  
**Compatibilidad:** Docker + Gunicorn + Flask + Python 3.x
