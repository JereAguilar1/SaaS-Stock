CONTEXTO GENERAL (ROADMAP SaaS)
Tenemos una plataforma web ya construida (Flask + Postgres + Docker) para gestión de stock, ventas, compras/boletas, presupuestos PDF, y balance financiero.

Objetivo de negocio:
- Convertirla en un SaaS para ferreterías/kioscos/negocios similares.
- Escalar progresivamente: 10 clientes → 100 → 1.000 → miles.

DECISIÓN ARQUITECTÓNICA BASE:
- Multi-tenant con una sola base Postgres y separación por columna `tenant_id` en todas las tablas del negocio.
- Tenant seleccionado por sesión (no subdominios por ahora).

ENFOQUE POR FASES:
FASE SaaS-1 (10 clientes):
- Aislamiento de datos por tenant_id (DB + app).
- Login email/password.
- Un usuario por negocio (MVP), pero estructura preparada para múltiples usuarios/roles.
- Onboarding: crear cuenta + crear negocio + redirigir a /products vacío.

FASE SaaS-2 (100 clientes):
- Roles básicos OWNER/ADMIN/STAFF.
- Mejoras de onboarding, límites, métricas.
- Uploads a object storage (S3/Spaces).

FASE SaaS-3 (1.000+):
- App stateless con múltiples réplicas.
- Redis para sesiones y cache.
- PgBouncer.
- Observabilidad.

PRIORIDAD ACTUAL (PASO 2):
- Cambios SOLO de base de datos:
  1) Crear tablas core del SaaS: tenant, app_user, user_tenant (roles).
  2) Agregar tenant_id a todas las tablas del negocio existentes.
  3) Backfill con tenant default para compatibilidad con datos actuales.
  4) Ajustar uniques globales a uniques por tenant (tenant_id + campo).
  5) Agregar índices por tenant para performance.

PRÓXIMOS PASOS (DESPUÉS DEL PASO 2):
PASO 3 (App layer):
- Implementar autenticación real (login/logout).
- Selección de tenant por sesión.
- Middleware/guards: require_login y require_tenant.
- Asegurar que todas las queries filtren por tenant_id.
- Ajustar servicios transaccionales (ventas/boletas/presupuestos) para que validen tenant_id y hagan locking correcto por tenant.

PASO 4 (Infra mínima):
- Nginx + TLS.
- Backups automáticos.
- Logs y monitoreo básico.

IMPORTANTE:
- No introducir pagos/planes todavía.
- No subdominios todavía.
- En este punto NO tocamos el código: solo DB.
