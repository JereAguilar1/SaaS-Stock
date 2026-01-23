# 🔍 Guía Completa de Debugging SMTP

## 📋 Índice
1. [Endpoints de Testing](#endpoints-de-testing)
2. [Variables de Entorno](#variables-de-entorno)
3. [Comandos de Debugging](#comandos-de-debugging)
4. [Errores Comunes](#errores-comunes)
5. [Configuración Gmail](#configuración-gmail)
6. [Verificación en Container](#verificación-en-container)

---

## 🎯 Endpoints de Testing

### 1. `/test-email-config` - Verificar Configuración

**Sin enviar email**, solo valida que todas las variables estén configuradas:

```bash
# Desde fuera del container
curl http://localhost:5000/test-email-config

# O con formato
curl -s http://localhost:5000/test-email-config | jq
```

**Respuesta exitosa (200 OK):**
```json
{
  "configured": true,
  "config": {
    "MAIL_SERVER": "smtp.gmail.com",
    "MAIL_PORT": 587,
    "MAIL_USERNAME": "tu-email@gmail.com",
    "MAIL_PASSWORD": "***",
    "MAIL_DEFAULT_SENDER": "tu-email@gmail.com",
    "MAIL_SUPPRESS_SEND": false
  },
  "message": "Configuración SMTP completa. Usar /test-email para probar envío."
}
```

**Respuesta error (500):**
```json
{
  "configured": false,
  "missing": ["MAIL_USERNAME", "MAIL_PASSWORD"],
  "hint": "Agregar variables SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM"
}
```

---

### 2. `/test-email` - Enviar Email Real

**Envía un email de prueba** con debugging completo:

```bash
curl http://localhost:5000/test-email
```

**Logs esperados en `docker compose logs -f web`:**

```
INFO - ============================================================
INFO - INICIO TEST EMAIL - Verificando configuración SMTP
INFO - ============================================================
INFO - SMTP_HOST: smtp.gmail.com
INFO - SMTP_PORT: 587
INFO - SMTP_USER: tu-email@gmail.com
INFO - SMTP_PASSWORD: ***
INFO - SMTP_FROM: tu-email@gmail.com
INFO - SMTP_TO: tandilaitech@gmail.com
INFO - ------------------------------------------------------------
INFO - Preparando mensaje de prueba...
INFO - ✓ Mensaje preparado: From=tu-email@gmail.com, To=tandilaitech@gmail.com
INFO - ------------------------------------------------------------
INFO - Conectando a smtp.gmail.com:587...
send: 'ehlo ...'   # ← Debug SMTP (set_debuglevel(1))
reply: b'250-smtp.gmail.com ...'
INFO - ✓ Conexión SMTP establecida
INFO - ------------------------------------------------------------
INFO - Iniciando TLS...
send: 'STARTTLS\r\n'
reply: b'220 2.0.0 Ready to start TLS\r\n'
INFO - ✓ TLS iniciado exitosamente
INFO - ------------------------------------------------------------
INFO - Autenticando como tu-email@gmail.com...
send: 'AUTH PLAIN ...'
reply: b'235 2.7.0 Accepted\r\n'
INFO - ✓ Autenticación exitosa
INFO - ------------------------------------------------------------
INFO - Enviando email a tandilaitech@gmail.com...
send: 'MAIL FROM:<tu-email@gmail.com> SIZE=...'
reply: b'250 2.1.0 OK ...'
send: 'RCPT TO:<tandilaitech@gmail.com>\r\n'
reply: b'250 2.1.5 OK ...'
send: 'DATA\r\n'
reply: b'354 Go ahead ...'
data: (message content)
reply: b'250 2.0.0 OK Message accepted ...'
INFO - ✓ Email enviado exitosamente
INFO - ✓ Conexión SMTP cerrada
INFO - ============================================================
INFO - ✅ TEST EMAIL COMPLETADO EXITOSAMENTE
INFO - ============================================================
```

**Respuesta exitosa (200 OK):**
```json
{
  "success": true,
  "message": "Email enviado exitosamente",
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_from": "tu-email@gmail.com",
  "smtp_to": "tandilaitech@gmail.com",
  "hint": "Revisa la bandeja de entrada (o spam) de tandilaitech@gmail.com"
}
```

---

## ⚙️ Variables de Entorno

### Archivo `.env` (desarrollo local)

```bash
# SMTP Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password-aqui  # ← App Password de Gmail
SMTP_FROM=tu-email@gmail.com
```

### Docker Compose (`docker-compose.yml`)

```yaml
services:
  web:
    environment:
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=tu-email@gmail.com
      - SMTP_PASSWORD=tu-app-password-aqui
      - SMTP_FROM=tu-email@gmail.com
```

### Verificar variables dentro del container

```bash
# Entrar al container
docker compose exec web bash

# Ver variables
echo $SMTP_HOST
echo $SMTP_PORT
echo $SMTP_USER
echo $SMTP_PASSWORD
echo $SMTP_FROM

# O todas juntas
env | grep SMTP
```

---

## 🔧 Comandos de Debugging

### 1. Ver logs en tiempo real

```bash
# Todos los logs del servicio web
docker compose logs -f web

# Filtrar solo logs de email
docker compose logs -f web | grep -E "EMAIL|SMTP|smtp"

# Últimas 100 líneas
docker compose logs --tail=100 web
```

### 2. Probar conectividad SMTP desde el container

```bash
# Entrar al container
docker compose exec web bash

# Probar conexión TCP
apt-get update && apt-get install -y telnet
telnet smtp.gmail.com 587

# Respuesta esperada:
# Trying 142.250.80.108...
# Connected to smtp.gmail.com.
# Escape character is '^]'.
# 220 smtp.gmail.com ESMTP ...

# Probar con openssl (TLS)
apt-get install -y openssl
openssl s_client -starttls smtp -connect smtp.gmail.com:587
```

### 3. Probar Python SMTP directamente

```bash
# Desde dentro del container
docker compose exec web python3 << 'EOF'
import smtplib
import os

print("SMTP_HOST:", os.getenv('SMTP_HOST'))
print("SMTP_PORT:", os.getenv('SMTP_PORT'))
print("SMTP_USER:", os.getenv('SMTP_USER'))
print("SMTP_PASS:", "***" if os.getenv('SMTP_PASSWORD') else "NOT SET")

try:
    smtp = smtplib.SMTP(os.getenv('SMTP_HOST'), int(os.getenv('SMTP_PORT')), timeout=10)
    smtp.set_debuglevel(1)
    smtp.starttls()
    smtp.login(os.getenv('SMTP_USER'), os.getenv('SMTP_PASSWORD'))
    print("\n✅ AUTENTICACIÓN EXITOSA")
    smtp.quit()
except Exception as e:
    print(f"\n❌ ERROR: {e}")
EOF
```

### 4. Reiniciar servicios después de cambiar .env

```bash
# Detener
docker compose down

# Reconstruir (si cambiaste Dockerfile)
docker compose build web

# Levantar
docker compose up -d

# Ver logs
docker compose logs -f web
```

---

## ❌ Errores Comunes

### Error 1: Variables no configuradas

**Síntoma:**
```json
{
  "error": "❌ Variables de entorno faltantes: SMTP_USER, SMTP_PASSWORD",
  "missing_vars": ["SMTP_USER", "SMTP_PASSWORD"]
}
```

**Solución:**
1. Agregar las variables al archivo `.env`
2. Reiniciar: `docker compose down && docker compose up -d`
3. Verificar: `docker compose exec web env | grep SMTP`

---

### Error 2: SMTP Authentication Failed (535)

**Síntoma:**
```
smtplib.SMTPAuthenticationError: (535, b'5.7.8 Username and Password not accepted')
```

**Solución (Gmail):**
1. Ir a https://myaccount.google.com/security
2. Activar verificación en 2 pasos
3. Ir a https://myaccount.google.com/apppasswords
4. Crear "App Password" para "Mail"
5. Usar ese password (16 caracteres sin espacios) en `SMTP_PASSWORD`

**NO uses tu password de Gmail normal**, usa App Password.

---

### Error 3: Connection Timeout

**Síntoma:**
```
TimeoutError: [Errno 110] Connection timed out
```

**Posibles causas:**
- Firewall bloqueando puerto 587
- DNS no resuelve `smtp.gmail.com`
- Red del container no tiene acceso a internet

**Solución:**
```bash
# Probar DNS
docker compose exec web ping -c 3 smtp.gmail.com

# Probar conectividad
docker compose exec web telnet smtp.gmail.com 587

# Si falla, verificar red Docker
docker network ls
docker network inspect saas-stock_default
```

---

### Error 4: TLS Error

**Síntoma:**
```
ssl.SSLError: [SSL: WRONG_VERSION_NUMBER] wrong version number
```

**Causa:** Puerto incorrecto o TLS mal configurado.

**Solución:**
- Gmail SMTP: usar puerto **587** con `STARTTLS`
- NO usar puerto 465 (SSL implícito)
- Verificar `MAIL_USE_TLS = True` en `config.py`

---

### Error 5: "Mail disabled" en logs

**Síntoma:**
```
[MAIL DISABLED] Email skipped for user@example.com
```

**Causa:** `_mail_enabled()` retorna `False`.

**Solución:**
1. Verificar `MAIL_SUPPRESS_SEND = False` en config
2. Verificar que `MAIL_SERVER` esté configurado
3. Verificar que `MAIL_USERNAME` esté configurado

```bash
curl http://localhost:5000/test-email-config
```

---

## 📧 Configuración Gmail (Paso a Paso)

### 1. Activar verificación en 2 pasos

1. Ir a: https://myaccount.google.com/security
2. Click en "Verificación en 2 pasos"
3. Seguir el asistente (SMS, llamada, o app Google)
4. Confirmar que está activada (debe aparecer "Activa")

### 2. Crear App Password

1. Ir a: https://myaccount.google.com/apppasswords
2. Si no ves la opción:
   - Verificar que 2FA esté activado
   - Puede estar en "Seguridad" → "Cómo inicias sesión en Google"
3. Click "Crear contraseña de aplicación"
4. Seleccionar:
   - App: "Mail"
   - Dispositivo: "Otro (nombre personalizado)" → "SaaS Stock"
5. Click "Generar"
6. Copiar el password de 16 caracteres (ej: `abcd efgh ijkl mnop`)

### 3. Configurar en .env

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop  # ← Sin espacios
SMTP_FROM=tu-email@gmail.com
```

### 4. Reiniciar y probar

```bash
docker compose down
docker compose up -d
curl http://localhost:5000/test-email
docker compose logs -f web
```

---

## 🐳 Verificación en Container

### Checklist completo

```bash
# 1. Container corriendo
docker compose ps

# 2. Variables configuradas
docker compose exec web env | grep SMTP

# 3. Configuración Flask
curl http://localhost:5000/test-email-config | jq

# 4. Logs limpios
docker compose logs --tail=50 web

# 5. Test email
curl http://localhost:5000/test-email

# 6. Ver logs de SMTP debug
docker compose logs -f web | grep -E "send:|reply:|INFO.*EMAIL"

# 7. Verificar en Gmail
# - Bandeja de entrada de tandilaitech@gmail.com
# - Carpeta de spam
# - Enviados de tu cuenta SMTP_USER
```

---

## 🔥 Troubleshooting Avanzado

### Problema: Logs no aparecen

**Causa:** Buffering de Python en Gunicorn.

**Solución:**
```dockerfile
# En Dockerfile, agregar:
ENV PYTHONUNBUFFERED=1
```

```bash
# Rebuild
docker compose build web
docker compose up -d
```

### Problema: Email se envía pero no llega

**Verificar:**
1. Carpeta de spam en destinatario
2. Logs de Gmail (Gmail → Configuración → Ver todos los ajustes → Reenvío y correo POP/IMAP)
3. Blacklist del servidor SMTP: https://mxtoolbox.com/blacklists.aspx

### Problema: "Relay access denied"

**Causa:** SMTP server no permite relay sin autenticación.

**Solución:**
- Asegurar que `smtp.login()` se ejecute correctamente
- Verificar que `SMTP_FROM` sea una dirección permitida por el servidor

---

## 📊 Logs Exitosos - Referencia Visual

```
┌─────────────────────────────────────────────────────────────┐
│ FLUJO SMTP EXITOSO                                          │
└─────────────────────────────────────────────────────────────┘

1. Verificar config ✓
   ├─ SMTP_HOST: smtp.gmail.com
   ├─ SMTP_PORT: 587
   ├─ SMTP_USER: user@gmail.com
   └─ SMTP_PASSWORD: ***

2. Conectar ✓
   ├─ send: 'ehlo ...'
   └─ reply: '250-smtp.gmail.com ...'

3. TLS ✓
   ├─ send: 'STARTTLS'
   └─ reply: '220 Ready to start TLS'

4. Autenticar ✓
   ├─ send: 'AUTH PLAIN ...'
   └─ reply: '235 Accepted'

5. Enviar ✓
   ├─ send: 'MAIL FROM:<user@gmail.com>'
   ├─ reply: '250 OK'
   ├─ send: 'RCPT TO:<dest@gmail.com>'
   ├─ reply: '250 OK'
   ├─ send: 'DATA'
   └─ reply: '250 Message accepted'

6. Cerrar ✓
   └─ Connection closed
```

---

## 🎯 Resumen Ejecutivo

### Flujo de Testing Recomendado

```bash
# 1. Verificar config (sin enviar)
curl http://localhost:5000/test-email-config

# 2. Si OK, enviar test email
curl http://localhost:5000/test-email

# 3. Ver logs en tiempo real
docker compose logs -f web

# 4. Verificar email recibido
# - Inbox de tandilaitech@gmail.com
# - Spam si no aparece
```

### Si algo falla:

1. **Verificar variables:** `docker compose exec web env | grep SMTP`
2. **Revisar logs:** `docker compose logs --tail=100 web`
3. **Probar conectividad:** `docker compose exec web telnet smtp.gmail.com 587`
4. **Verificar App Password:** Crear nuevo en https://myaccount.google.com/apppasswords
5. **Reiniciar:** `docker compose down && docker compose up -d`

---

## 📚 Referencias

- Gmail SMTP: https://support.google.com/mail/answer/7126229
- App Passwords: https://support.google.com/accounts/answer/185833
- Python smtplib: https://docs.python.org/3/library/smtplib.html
- Flask-Mail: https://pythonhosted.org/Flask-Mail/

---

**Fecha:** 2026-01-22  
**Versión:** 1.0.0  
**Estado:** ✅ DEBUGGING COMPLETO IMPLEMENTADO
