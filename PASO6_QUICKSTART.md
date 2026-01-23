# 🚀 PASO 6: Quick Start - Roles y Gestión de Usuarios

## ✅ ¿Qué se implementó?

Sistema completo de gestión de usuarios multi-tenant con:
- ✅ 3 roles: OWNER, ADMIN, STAFF
- ✅ Sistema de invitaciones con JWT
- ✅ Email service (SMTP)
- ✅ Audit log para tracking
- ✅ UI completa

---

## 📦 Instalación

### 1. Instalar Dependencia

```bash
pip install Flask-Mail==0.9.1
```

### 2. Ejecutar Migración de DB

```bash
# Desarrollo
psql $DATABASE_URL -f db/migrations/PASO6_add_audit_log.sql

# Producción
docker compose -f docker-compose.prod.yml exec -T db psql -U saas_stock_user -d saas_stock_db < db/migrations/PASO6_add_audit_log.sql
```

### 3. Configurar SMTP

Agrega a `.env` (desarrollo) o `.env.prod` (producción):

```bash
# Gmail (recomendado para testing)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-app-password-de-16-caracteres
SMTP_FROM=noreply@tandil.site
```

**Importante:** Si usas Gmail, genera un "App Password":
1. Ve a https://myaccount.google.com/apppasswords
2. Crea "App Password" para "Mail"
3. Usa ese password (no tu password regular)

### 4. Reiniciar Aplicación

```bash
# Desarrollo
flask run

# Producción
docker compose -f docker-compose.prod.yml restart web
```

---

## 🎯 Uso Rápido

### Como OWNER invitar un usuario:

1. Iniciar sesión como OWNER
2. Ir a menú → "Gestión de Usuarios"
3. Click "Invitar Usuario"
4. Completar:
   - Email: nuevo@example.com
   - Nombre: Nuevo Usuario
   - Rol: ADMIN o STAFF
5. Click "Enviar Invitación"
6. Sistema envía email automáticamente
7. Usuario recibe link (válido 7 días)
8. Usuario completa registro

### Sin SMTP configurado:

Si no tienes SMTP, el sistema mostrará el link de invitación en la pantalla.
Copia el link y envíalo manualmente al usuario.

---

## 🔐 Permisos por Rol

| Funcionalidad | OWNER | ADMIN | STAFF |
|---------------|-------|-------|-------|
| Invitar usuarios | ✓ | ✗ | ✗ |
| Crear productos | ✓ | ✓ | ✗ |
| Registrar ventas | ✓ | ✓ | ✓ |
| Ver balance | ✓ | ✓ | ✗ |
| Gestionar facturas | ✓ | ✓ | ✗ |
| Crear presupuestos | ✓ | ✓ | ✓ |
| Convertir presupuestos | ✓ | ✓ | ✗ |

---

## 📁 Archivos Creados

**Nuevos (10):**
- `app/decorators/permissions.py` - Decorators de permisos
- `app/services/email_service.py` - Servicio de email
- `app/services/audit_service.py` - Servicio de audit log
- `app/models/audit_log.py` - Modelo AuditLog
- `app/blueprints/users.py` - Blueprint de usuarios
- `app/templates/users/list.html` - Lista usuarios
- `app/templates/users/invite.html` - Invitar usuario
- `app/templates/users/edit.html` - Editar rol
- `app/templates/users/accept_invite.html` - Aceptar invitación
- `db/migrations/PASO6_add_audit_log.sql` - Migración DB

**Modificados (5):**
- `app/__init__.py` - Registrado users_bp y Flask-Mail
- `app/middleware.py` - Agregado g.user_role
- `app/models/__init__.py` - Importado AuditLog
- `config.py` - Config SMTP
- `requirements.txt` - Flask-Mail

---

## 🧪 Testing Rápido

```bash
# 1. Iniciar sesión como OWNER
# 2. Ir a /users
# 3. Invitar usuario con email válido
# 4. Verificar que email se envía (o link se muestra)
# 5. Abrir link en ventana incógnito
# 6. Completar formulario de aceptación
# 7. Iniciar sesión con nuevo usuario
# 8. Verificar permisos según rol
```

---

## 🚨 Troubleshooting

### Email no se envía

**Problema:** Link se muestra en pantalla pero email no llega

**Solución:**
```bash
# Verificar variables SMTP en .env
cat .env | grep SMTP

# Ver logs
docker compose logs -f web | grep email

# Test SMTP manual
telnet smtp.gmail.com 587
```

### JWT token inválido

**Problema:** "Link de invitación inválido"

**Solución:**
- Token expira en 7 días
- Verificar que SECRET_KEY sea el mismo
- Generar nueva invitación

### Decorator no funciona

**Problema:** Usuario puede acceder a ruta prohibida

**Solución:**
- Orden correcto: `@require_login`, `@require_tenant`, luego `@owner_only`
- Verificar que middleware carga `g.user_role`
- Ver logs del middleware

---

## 📚 Documentación Completa

Ver `PASO6_IMPLEMENTATION_COMPLETE.md` para:
- Explicación técnica detallada
- Arquitectura del sistema
- Ejemplos de código
- Integración con audit log
- Seguridad

---

## 🎓 Para Developers

### Aplicar decoradores a nuevas rutas:

```python
from app.decorators.permissions import admin_or_owner

@my_bp.route('/sensitive')
@require_login
@require_tenant
@admin_or_owner  # Solo ADMIN o OWNER
def sensitive_action():
    # Tu código aquí
    pass
```

### Registrar acción en audit log:

```python
from app.services.audit_service import log_action
from app.models import AuditAction

# Después de acción importante
log_action(
    session=db_session,
    action=AuditAction.PRODUCT_DELETED,
    resource_type='product',
    resource_id=product.id,
    details={'name': product.name}
)
db_session.commit()
```

---

## ✅ Checklist

- [ ] Flask-Mail instalado
- [ ] Migración DB ejecutada
- [ ] Variables SMTP configuradas
- [ ] App reiniciada
- [ ] Link "Gestión de Usuarios" visible para OWNER
- [ ] Invitación funciona (email o link manual)
- [ ] Usuario puede aceptar invitación
- [ ] Nuevo usuario puede iniciar sesión
- [ ] Permisos por rol funcionan

---

**Listo para usar!** 🎉

Si algo falla, ver `PASO6_IMPLEMENTATION_COMPLETE.md` o logs con:
```bash
docker compose -f docker-compose.prod.yml logs -f web
```
