# ⚡ SMTP Quick Start - 5 Minutos

## 🎯 Objetivo
Configurar y probar SMTP en 5 minutos.

---

## 📋 Paso 1: Obtener App Password de Gmail (2 min)

1. Ir a: https://myaccount.google.com/apppasswords
2. Crear contraseña para "Mail" → "SaaS Stock"
3. Copiar el password de 16 caracteres (ej: `abcd efgh ijkl mnop`)

---

## ⚙️ Paso 2: Configurar Variables (1 min)

Editar archivo `.env` en la raíz del proyecto:

```bash
# Agregar estas líneas:
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=abcdefghijklmnop  # ← Sin espacios, 16 chars
SMTP_FROM=tu-email@gmail.com
```

**O** si usas `docker-compose.yml`:

```yaml
services:
  web:
    environment:
      - SMTP_HOST=smtp.gmail.com
      - SMTP_PORT=587
      - SMTP_USER=tu-email@gmail.com
      - SMTP_PASSWORD=abcdefghijklmnop
      - SMTP_FROM=tu-email@gmail.com
```

---

## 🔄 Paso 3: Reiniciar Container (1 min)

```bash
docker compose down
docker compose up -d
```

---

## ✅ Paso 4: Probar (1 min)

### Opción A: Script automático

```bash
chmod +x test_smtp.sh
./test_smtp.sh
```

### Opción B: Manual

```bash
# 1. Verificar config
curl http://localhost:5000/test-email-config

# 2. Enviar test
curl http://localhost:5000/test-email

# 3. Ver logs
docker compose logs -f web
```

---

## 🎉 Resultado Esperado

**En el terminal:**
```json
{
  "success": true,
  "message": "Email enviado exitosamente",
  "smtp_host": "smtp.gmail.com",
  "smtp_to": "tandilaitech@gmail.com"
}
```

**En los logs (`docker compose logs -f web`):**
```
INFO - ============================================================
INFO - INICIO TEST EMAIL - Verificando configuración SMTP
INFO - ============================================================
INFO - SMTP_HOST: smtp.gmail.com
INFO - ✓ Conexión SMTP establecida
INFO - ✓ TLS iniciado exitosamente
INFO - ✓ Autenticación exitosa
INFO - ✓ Email enviado exitosamente
INFO - ✅ TEST EMAIL COMPLETADO EXITOSAMENTE
```

**En Gmail:**
- Email en bandeja de `tandilaitech@gmail.com`
- Subject: "SMTP Test SaaS-Stock - Debugging"

---

## ❌ Si Algo Falla

### Error: "Variables faltantes"

**Solución:**
```bash
# Verificar que las variables estén en el container
docker compose exec web env | grep SMTP

# Si no aparecen, editaste el archivo correcto?
# Reiniciaste: docker compose down && docker compose up -d ?
```

### Error: "Authentication failed (535)"

**Solución:**
1. ¿Usaste App Password de Gmail? (NO tu password normal)
2. ¿Copiaste los 16 caracteres sin espacios?
3. ¿Tienes 2FA activado en Gmail?

Crear nuevo: https://myaccount.google.com/apppasswords

### Error: "Connection timeout"

**Solución:**
```bash
# Probar conectividad desde el container
docker compose exec web telnet smtp.gmail.com 587

# Si falla, problema de red/firewall
```

---

## 📝 Cambiar Email de Destino

Por defecto envía a `tandilaitech@gmail.com`.

Para cambiar, editar `app/blueprints/debug.py`:

```python
smtp_to = "tu-email-destino@gmail.com"  # Línea 30
```

O mejor, crear endpoint parametrizado:

```python
@debug_bp.route('/test-email/<to>')
def test_email(to):
    # ... usar 'to' como destinatario
```

---

## 🔗 Recursos

- **Debugging completo:** Ver `SMTP_DEBUGGING_GUIDE.md`
- **App Passwords:** https://myaccount.google.com/apppasswords
- **Gmail SMTP:** https://support.google.com/mail/answer/7126229

---

**Tiempo total:** ~5 minutos  
**Estado:** ✅ LISTO PARA USAR
