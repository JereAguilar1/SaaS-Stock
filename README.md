# Sistema de Ferretería - Aplicación Web

Sistema web completo para gestión de ferretería con control de stock, ventas, compras y balance financiero.

> **⚠️ IMPORTANTE - Protección por Contraseña (MEJORA 8)**  
> Esta aplicación requiere una contraseña única para acceder. Debes configurar `APP_PASSWORD` en el archivo `.env` antes de iniciar la aplicación. Sin esta variable configurada, la aplicación bloqueará el acceso por seguridad.

## Stack Técnico

- **Backend**: Python 3.13+
- **Framework**: Flask 3.0.0
- **Templates**: Jinja2
- **UX Dinámica**: HTMX
- **Base de Datos**: PostgreSQL 16
- **ORM**: SQLAlchemy 2.0.36
- **Migraciones**: Alembic (opcional)

## Requisitos Previos

### Para Desarrollo Local
- Python 3.11 o superior
- PostgreSQL 16

### Para Docker (Recomendado)
- Docker Desktop o Docker Engine
- Docker Compose V2

## Configuración Local

### 1. Clonar el repositorio

```bash
cd c:\jere\Ferreteria\ferreteria-app
```

### 2. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

Crear un archivo `.env` en la raíz del proyecto con las siguientes variables:

```env
# Database Configuration
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
POSTGRES_DB=ferreteria
POSTGRES_USER=admin
POSTGRES_PASSWORD=admin123

# Flask Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=dev-secret-key-change-in-production

# Authentication (REQUIRED)
APP_PASSWORD=your-secure-password-here
```

### 4. Iniciar la base de datos PostgreSQL

Si usas Docker:

```bash
cd ..\Ferreteria-db
docker compose up -d
```

Verificar que el contenedor esté corriendo:

```bash
docker ps
```

### 5. Ejecutar la aplicación

```bash
python app.py
```

La aplicación estará disponible en:
- http://127.0.0.1:5000 (página principal)
- http://127.0.0.1:5000/health (verificación de salud y conexión DB)

---

## 🐳 Configuración con Docker (Recomendado)

### Ventajas de Docker
- ✅ No requiere instalar Python ni PostgreSQL localmente
- ✅ Entorno consistente en cualquier sistema operativo
- ✅ Fácil de iniciar, detener y reiniciar
- ✅ Aislamiento completo del sistema host

### Modo A: App + PostgreSQL en Docker (Todo en Contenedores)

Este es el modo más simple y recomendado para desarrollo y testing.

#### 1. Configurar Variables de Entorno

```bash
# Copiar el archivo de ejemplo
cp env.example .env

# Editar .env si necesitas cambiar algo (opcional)
# Los valores por defecto están listos para usar
```

#### 2. Iniciar Todo con Docker Compose

```bash
# Construir e iniciar ambos contenedores (app + db)
docker compose up --build

# O en modo detached (background)
docker compose up --build -d
```

#### 3. Verificar que Funciona

```bash
# Ver logs
docker compose logs -f web

# Verificar health
curl http://localhost:5000/health
```

#### 4. Acceder a la Aplicación

- **Aplicación:** http://localhost:5000
- **Health Check:** http://localhost:5000/health

#### 5. Inicializar Base de Datos

**Opción A: Restaurar desde backup**
```bash
# Copiar backup SQL al contenedor
docker compose cp backup.sql db:/tmp/

# Restaurar
docker compose exec db psql -U ferreteria -d ferreteria -f /tmp/backup.sql
```

**Opción B: Ejecutar seeds manualmente**
```bash
# Desde tu terminal local
docker compose exec web python seed_initial_data.py
```

**Opción C: Conectar con pgAdmin/DBeaver**
- Host: `localhost`
- Port: `5432`
- Database: `ferreteria`
- User: `ferreteria`
- Password: `ferreteria`

#### 6. Comandos Útiles

```bash
# Ver logs en tiempo real
docker compose logs -f

# Ver solo logs de la app
docker compose logs -f web

# Ver solo logs de la DB
docker compose logs -f db

# Entrar al contenedor de la app
docker compose exec web bash

# Entrar a psql
docker compose exec db psql -U ferreteria -d ferreteria

# Reiniciar servicios
docker compose restart

# Detener servicios
docker compose down

# Detener y eliminar volúmenes (⚠️ BORRA DATOS)
docker compose down -v

# Reconstruir imagen
docker compose build --no-cache
```

---

### Modo B: Solo App en Docker + PostgreSQL Externo

Si ya tienes PostgreSQL corriendo localmente o en un servidor externo.

#### 1. Configurar Variables de Entorno

Edita `.env`:

```env
# Para Windows/Mac con Docker Desktop
DB_HOST=host.docker.internal
DB_PORT=5432
DB_NAME=ferreteria
DB_USER=tu_usuario
DB_PASSWORD=tu_password

# Para Linux
# DB_HOST=172.17.0.1
# O la IP de tu host

SECRET_KEY=change-me
FLASK_DEBUG=0
```

#### 2. Iniciar Solo la App

```bash
# Iniciar solo el servicio web (sin db)
docker compose up web --build

# O en detached
docker compose up web --build -d
```

#### 3. Verificar Conexión

```bash
# La app debe conectarse a tu PostgreSQL externo
curl http://localhost:5000/health
```

---

### Troubleshooting Docker

#### Error: "Connection refused" o "could not connect to server"

**Problema:** La app no puede conectarse a la base de datos.

**Soluciones:**

1. **Modo A (DB en Docker):**
```bash
# Verificar que el contenedor db está corriendo
docker compose ps

# Ver logs de la DB
docker compose logs db

# Verificar health de DB
docker compose exec db pg_isready -U ferreteria
```

2. **Modo B (DB externa):**
- Verificar que `DB_HOST` está correctamente configurado
- Windows/Mac: usar `host.docker.internal`
- Linux: usar `172.17.0.1` o IP del host
- Verificar que el firewall permite conexiones al puerto de PostgreSQL

#### Error: "port is already allocated"

**Problema:** El puerto 5000 o 5432 ya está en uso.

**Solución:**
```bash
# Cambiar puerto en docker-compose.yml
# Para la app, cambiar:
ports:
  - "8000:5000"  # Acceder en http://localhost:8000

# Para la DB, cambiar:
ports:
  - "5433:5432"  # Y actualizar DB_PORT=5433 en .env
```

#### Error: Los scripts de init no se ejecutan

**Problema:** La base de datos ya tiene un volumen existente.

**Solución:**
```bash
# Eliminar volumen y recrear
docker compose down -v
docker compose up --build
```

#### Error: "exec format error" o "no such file"

**Problema:** Problemas con line endings en Windows.

**Solución:**
```bash
# Convertir line endings si es necesario
git config core.autocrlf input
git rm --cached -r .
git reset --hard
```

#### Ver estado de salud de contenedores

```bash
# Ver health checks
docker compose ps

# Inspeccionar un contenedor
docker inspect ferreteria-web

# Ver uso de recursos
docker stats
```

---

### Datos Persistentes

Los datos de PostgreSQL se guardan en un volumen Docker llamado `postgres_data`.

```bash
# Ver volúmenes
docker volume ls

# Inspeccionar volumen
docker volume inspect ferreteria-app_postgres_data

# Backup de datos
docker compose exec db pg_dump -U ferreteria -d ferreteria > backup_$(date +%Y%m%d).sql

# Restore de datos
docker compose exec -T db psql -U ferreteria -d ferreteria < backup.sql
```

#### Resetear Base de Datos Completamente

```bash
# ⚠️ ADVERTENCIA: Esto BORRA TODOS LOS DATOS

# Detener y eliminar volúmenes
docker compose down -v

# Iniciar de nuevo (DB vacía)
docker compose up --build

# Restaurar backup o ejecutar seeds
```

---

## Estructura del Proyecto

```
ferreteria-app/
├── app/
│   ├── __init__.py           # Factory de la aplicación
│   ├── database.py           # Configuración de SQLAlchemy
│   ├── blueprints/           # Módulos de rutas
│   │   ├── main.py           # Rutas principales y health check
│   │   └── ...               # Otros blueprints (próximamente)
│   ├── models/               # Modelos SQLAlchemy
│   ├── services/             # Lógica de negocio y transacciones
│   ├── templates/            # Plantillas Jinja2
│   └── static/               # CSS, JS, imágenes
├── app.py                    # Punto de entrada
├── config.py                 # Configuración
├── requirements.txt          # Dependencias Python
├── .env                      # Variables de entorno (no versionado)
└── README.md                 # Este archivo
```

## Verificación de Funcionamiento

### Health Check

Para verificar que la aplicación está funcionando y conectada a la base de datos:

```bash
curl http://127.0.0.1:5000/health
```

O con Python:

```bash
python -c "import urllib.request; import json; response = urllib.request.urlopen('http://127.0.0.1:5000/health'); print(json.loads(response.read().decode()))"
```

Respuesta esperada:

```json
{
  "status": "healthy",
  "database": "connected",
  "message": "Database connection successful"
}
```

## Estado del Proyecto

### ✅ Fase 0: Bootstrapping (COMPLETADA)
- [x] Estructura del proyecto Flask
- [x] Configuración de dependencias
- [x] Configuración de variables de entorno
- [x] Conexión a PostgreSQL
- [x] Endpoint `/health` funcional

### ✅ Fase 1: Módulo de Productos + Stock (COMPLETADA)
- [x] Modelos SQLAlchemy (UOM, Category, Product, ProductStock)
- [x] Blueprint catalog con rutas CRUD
- [x] Listado de productos con stock actual
- [x] Búsqueda por nombre/SKU/barcode
- [x] Productos sin stock en gris con badge
- [x] Validaciones server-side
- [x] Formularios de creación/edición
- [x] Activar/desactivar productos
- [x] UI con Bootstrap 5

Ver [FASE1_TESTING.md](FASE1_TESTING.md) para instrucciones de prueba.

### ✅ Fase 2: Módulo de Ventas - POS (COMPLETADA)
- [x] Modelos SQLAlchemy (Sale, SaleLine, StockMove, StockMoveLine, FinanceLedger)
- [x] Blueprint sales con POS completo
- [x] Carrito en Flask session
- [x] Búsqueda de productos para venta
- [x] HTMX para agregar/actualizar/remover del carrito
- [x] Servicio transaccional `confirm_sale` con locking
- [x] Descuento automático de stock al confirmar
- [x] Registro de ingreso en finance_ledger
- [x] Validaciones de stock en tiempo real
- [x] UI responsive con Bootstrap 5

Ver [FASE2_TESTING.md](FASE2_TESTING.md) para instrucciones de prueba.

### ✅ Fase 3: Módulo de Compras/Boletas (COMPLETADA)
- [x] Modelos SQLAlchemy (Supplier, PurchaseInvoice, PurchaseInvoiceLine)
- [x] Blueprint suppliers con CRUD completo
- [x] Blueprint invoices con gestión de boletas
- [x] Nueva boleta con ítems obligatorios (draft en session)
- [x] Servicio transaccional `create_invoice_with_lines`
- [x] Aumento automático de stock (StockMove IN)
- [x] Validaciones: mínimo 1 ítem, qty > 0, producto activo
- [x] Validación de duplicado (supplier_id + invoice_number)
- [x] UI con HTMX para agregar/remover ítems
- [x] Listado con filtros (proveedor, estado)
- [x] Detalle de boleta
- [x] Estado PENDING por defecto (paid_at NULL)

Ver [FASE3_TESTING.md](FASE3_TESTING.md) para instrucciones de prueba.

### ✅ Fase 4: Pago de Boletas (COMPLETADA)
- [x] Servicio transaccional `pay_invoice` con lock FOR UPDATE
- [x] Ruta POST `/invoices/<id>/pay`
- [x] Actualización de boleta: status=PAID, paid_at=fecha
- [x] Registro de egreso en finance_ledger (EXPENSE, INVOICE_PAYMENT)
- [x] Validaciones: solo PENDING, fecha requerida, no duplicar
- [x] UI: formulario de pago en detalle de boleta
- [x] Filtro "Solo Pendientes" en listado
- [x] Botón "Pagar" para boletas pendientes
- [x] Transaccionalidad completa (rollback si falla)

Ver [FASE4_TESTING.md](FASE4_TESTING.md) para instrucciones de prueba.

### ✅ Fase 5: Balance Financiero (COMPLETADA)
- [x] Servicio `balance_service` con `get_balance_series`
- [x] Consultas eficientes con `date_trunc` (day/month/year)
- [x] Blueprint balance con ruta `/balance`
- [x] Vistas: Diaria, Mensual, Anual (tabs)
- [x] Filtros por rango de fechas (start/end)
- [x] Cálculo de ingresos, egresos y neto por período
- [x] Tarjetas de resumen con totales
- [x] Libro Mayor (ledger) para auditoría (`/balance/ledger`)
- [x] Movimientos manuales (INCOME/EXPENSE) con categoría y notas
- [x] Validaciones: start <= end, amount > 0
- [x] UI con Bootstrap y tabs interactivos

Ver [FASE5_TESTING.md](FASE5_TESTING.md) para instrucciones de prueba.

### ✅ Fase 6: Dockerización Completa (COMPLETADA)
- [x] Dockerfile con Python 3.11-slim + gunicorn
- [x] docker-compose.yml con servicios web y db
- [x] Healthchecks para web y db
- [x] Volumen persistente para PostgreSQL
- [x] Soporte para Modo A (todo en Docker) y Modo B (DB externa)
- [x] Variables de entorno flexibles (DATABASE_URL, DB_*, POSTGRES_*)
- [x] Estructura db/init para scripts de inicialización
- [x] .dockerignore optimizado
- [x] Usuario no-root por seguridad
- [x] README completo con instrucciones Docker
- [x] Troubleshooting y comandos útiles

Ver [FASE6_TESTING.md](FASE6_TESTING.md) para instrucciones de prueba Docker.

---

## 🎉 Proyecto Completado

Todas las fases del proyecto han sido implementadas exitosamente:
- ✅ **Fase 0:** Bootstrapping
- ✅ **Fase 1:** Módulo de Productos
- ✅ **Fase 2:** Módulo de Ventas (POS)
- ✅ **Fase 3:** Módulo de Compras/Boletas
- ✅ **Fase 4:** Pago de Boletas
- ✅ **Fase 5:** Balance Financiero
- ✅ **Fase 6:** Dockerización Completa

El sistema está listo para producción o desarrollo continuo.

## 🏢 Arquitectura Multi-Tenant (SaaS)

### Transformación a SaaS Multi-Tenant

El sistema ha sido transformado de single-tenant a multi-tenant usando separación por columna `tenant_id`. Esta arquitectura permite que múltiples negocios (ferreterías, kioscos, etc.) usen la misma instancia de la aplicación con completo aislamiento de datos.

### Decisión Arquitectónica

- **Estrategia:** Multi-tenant con una sola base de datos PostgreSQL
- **Aislamiento:** Columna `tenant_id` en todas las tablas del negocio
- **Escalabilidad:** Diseñado para escalar de 10 → 100 → 1,000+ clientes
- **Selección de tenant:** Por sesión (no subdominios en esta fase)

### Tablas Core del SaaS

El esquema incluye tres tablas fundamentales para el funcionamiento multi-tenant:

1. **`tenant`**: Representa cada negocio/organización
   - `id`, `slug`, `name`, `active`, timestamps
   
2. **`app_user`**: Usuarios de la plataforma (autenticación email/password)
   - `id`, `email`, `password_hash`, `full_name`, `active`, timestamps
   
3. **`user_tenant`**: Relación muchos-a-muchos con roles
   - Relaciona usuarios con tenants
   - Roles: `OWNER`, `ADMIN`, `STAFF`

### Tablas del Negocio Tenantizadas

Todas las tablas del negocio ahora incluyen `tenant_id`:

- **Catálogo:** `uom`, `category`, `product`, `product_stock`
- **Ventas:** `sale`, `sale_line`
- **Compras:** `supplier`, `purchase_invoice`, `purchase_invoice_line`
- **Stock:** `stock_move`, `stock_move_line`
- **Finanzas:** `finance_ledger`
- **Presupuestos:** `quote`, `quote_line`
- **Solicitudes:** `missing_product_request`

### Constraints UNIQUE por Tenant

Los constraints únicos ahora son por tenant, permitiendo que diferentes negocios tengan:
- Mismo SKU: `UNIQUE(tenant_id, sku)`
- Mismo código de barras: `UNIQUE(tenant_id, barcode)`
- Mismo nombre de categoría: `UNIQUE(tenant_id, name)`
- Mismo nombre de proveedor: `UNIQUE(tenant_id, name)`
- Mismo número de factura por proveedor: `UNIQUE(tenant_id, supplier_id, invoice_number)`
- Mismo número de presupuesto: `UNIQUE(tenant_id, quote_number)`

### Índices de Performance

Se han creado índices compuestos por tenant para optimizar queries:
- `(tenant_id, datetime)` en ventas y ledger
- `(tenant_id, status)` en facturas y cotizaciones
- `(tenant_id, name)` en productos y categorías
- `(tenant_id, category_id)` en productos

### Migración PASO 2

La migración `SAAS_STEP2_multi_tenant.sql` realiza:

1. **Crear tablas core SaaS** (tenant, app_user, user_tenant)
2. **Agregar tenant_id** a todas las tablas del negocio
3. **Backfill** de datos existentes al tenant default (id=1)
4. **Ajustar constraints** UNIQUE de globales a por-tenant
5. **Crear índices** compuestos por tenant para performance

#### Ejecutar la Migración

**Opción A: Docker Compose**
```bash
# Copiar el script al contenedor
docker compose cp db/migrations/SAAS_STEP2_multi_tenant.sql db:/tmp/

# Ejecutar la migración
docker compose exec db psql -U ferreteria -d ferreteria -f /tmp/SAAS_STEP2_multi_tenant.sql
```

**Opción B: PostgreSQL Local**
```bash
psql -U admin -d ferreteria -f db/migrations/SAAS_STEP2_multi_tenant.sql
```

**Opción C: Desde pgAdmin o DBeaver**
- Abrir el archivo `db/migrations/SAAS_STEP2_multi_tenant.sql`
- Ejecutar todo el script en una sola transacción

#### Rollback (Si es necesario)

⚠️ **ADVERTENCIA:** El rollback eliminará todos los datos de tenants diferentes al default (tenant_id=1)

```bash
# Docker
docker compose cp db/migrations/SAAS_STEP2_multi_tenant_rollback.sql db:/tmp/
docker compose exec db psql -U ferreteria -d ferreteria -f /tmp/SAAS_STEP2_multi_tenant_rollback.sql

# Local
psql -U admin -d ferreteria -f db/migrations/SAAS_STEP2_multi_tenant_rollback.sql
```

#### Validar la Migración

Después de ejecutar la migración, validar con estas queries:

```sql
-- Verificar que no hay tenant_id NULL (debe devolver 0 en todas)
SELECT 'uom' AS table_name, COUNT(*) AS null_count FROM uom WHERE tenant_id IS NULL
UNION ALL
SELECT 'category', COUNT(*) FROM category WHERE tenant_id IS NULL
UNION ALL
SELECT 'product', COUNT(*) FROM product WHERE tenant_id IS NULL
UNION ALL
SELECT 'sale', COUNT(*) FROM sale WHERE tenant_id IS NULL;

-- Ver tenant default
SELECT * FROM tenant WHERE id = 1;

-- Ver índices por tenant
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE indexname LIKE '%tenant%'
ORDER BY tablename, indexname;
```

### Próximos Pasos (PASO 3 - App Layer)

**⚠️ IMPORTANTE:** La migración PASO 2 es SOLO cambios de base de datos. El código Python/Flask NO ha sido modificado todavía.

Para completar la transformación multi-tenant, se necesita:

1. **Autenticación Real:**
   - Implementar login/logout con email/password
   - Hash de contraseñas (bcrypt)
   - Sesiones seguras

2. **Middleware de Tenant:**
   - `require_login`: verificar usuario autenticado
   - `require_tenant`: verificar tenant seleccionado en sesión
   - Inyectar automáticamente `tenant_id` en queries

3. **Actualizar Modelos SQLAlchemy:**
   - Agregar `tenant_id` a todos los modelos del negocio
   - Crear modelos para `Tenant`, `AppUser`, `UserTenant`

4. **Filtrado Automático:**
   - Todas las queries deben filtrar por `tenant_id` de sesión
   - Agregar locking correcto en transacciones por tenant

5. **Onboarding:**
   - Flujo de registro: crear cuenta → crear negocio → setup inicial
   - Página inicial vacía con botón "Agregar Producto"

## Notas de Desarrollo

- La aplicación usa `pool_pre_ping=True` en SQLAlchemy para verificar las conexiones antes de usarlas
- El modo debug está habilitado para desarrollo (`FLASK_DEBUG=1`)
- No hay autenticación por el momento (se agregará en futuras fases)

## Troubleshooting

### Error de conexión a la base de datos

Verificar que:
1. PostgreSQL está corriendo: `docker ps`
2. Las credenciales en `.env` son correctas
3. El puerto en `.env` coincide con el puerto mapeado en Docker

### Error de importación de módulos

Reinstalar dependencias:

```bash
pip install --upgrade -r requirements.txt
```

---

## 🚀 Despliegue en Producción (PASO 4)

El sistema está listo para desplegar en un VPS con:
- ✅ **Docker Compose** con Nginx, PostgreSQL y Gunicorn
- ✅ **HTTPS automático** con Let's Encrypt (certbot)
- ✅ **Backups automáticos** de base de datos (cron)
- ✅ **Monitoreo** con Uptime Kuma
- ✅ **Security headers** y rate limiting
- ✅ **Multi-tenant** con aislamiento completo por tenant

### Guías de Despliegue

- **Guía Completa:** [`README_PROD_DEPLOY.md`](README_PROD_DEPLOY.md) - Setup detallado paso a paso
- **Quick Start:** [`PASO4_DEPLOYMENT_QUICKSTART.md`](PASO4_DEPLOYMENT_QUICKSTART.md) - Comandos rápidos
- **Backups:** [`infra/backups/README.md`](infra/backups/README.md) - Backup y restauración

### Comandos Rápidos

```bash
# Levantar en producción
docker compose -f docker-compose.prod.yml up -d

# Ver logs
docker compose -f docker-compose.prod.yml logs -f

# Backup manual
./infra/backups/backup_db.sh

# Verificar salud
curl https://your-domain.com/health
```

### Requisitos Mínimos VPS
- **CPU:** 2 vCPU
- **RAM:** 4GB
- **Disco:** 100GB NVMe
- **SO:** Ubuntu 22.04 LTS o Debian 11+
- **Clientes soportados:** ~10 clientes simultáneos

Para más de 10 clientes, ver guía de escalabilidad en [`README_PROD_DEPLOY.md`](README_PROD_DEPLOY.md).

---

## 📋 Roadmap del Proyecto

- ✅ **PASO 1:** MVP Definition
- ✅ **PASO 2:** Database Migration (Multi-Tenant)
- ✅ **PASO 3:** Application Layer (Auth + Tenant Context)
- ✅ **PASO 4:** Infraestructura Básica (Nginx, SSL, Backups)
- 🔜 **PASO 5:** CI/CD y Automatización
- 🔜 **PASO 6:** Escalabilidad (Redis, Object Storage)

---

**Versión**: 1.0.0 - MVP SaaS Multi-Tenant Completo  
**Última actualización**: Enero 2026

