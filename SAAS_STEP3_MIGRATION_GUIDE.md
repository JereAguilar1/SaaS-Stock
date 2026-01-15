# PASO 3: Guía de Migración Multi-Tenant (Capa de Aplicación)

## ✅ Completado

### Modelos
- ✅ Creados modelos SaaS: `Tenant`, `AppUser`, `UserTenant`
- ✅ Actualizados TODOS los modelos del negocio con `tenant_id`
- ✅ Removidos constraints UNIQUE globales en modelos (ahora son por tenant en DB)

### Middleware y Seguridad
- ✅ Creado `app/middleware.py` con:
  - `load_user_and_tenant()` - carga contexto antes de cada request
  - `@require_login` - requiere autenticación
  - `@require_tenant` - requiere tenant seleccionado
  - `@require_role(min_role)` - control de roles OWNER/ADMIN/STAFF

### Autenticación
- ✅ Blueprint `app/blueprints/auth.py` reescrito:
  - `/register` - onboarding completo (user + tenant + user_tenant)
  - `/login` - autenticación email/password
  - `/select-tenant` - selección de tenant si tiene múltiples
  - `/logout` - cierre de sesión

### Templates
- ✅ `app/templates/auth/login.html` - nuevo diseño multi-tenant
- ✅ `app/templates/auth/register.html` - formulario de registro
- ✅ `app/templates/auth/select_tenant.html` - selección de negocio

### Configuración
- ✅ `app/__init__.py` actualizado:
  - Middleware `load_user_and_tenant` en `before_request`
  - Context processors para `invoice_alerts` y `current_tenant`
  - Removido middleware de password simple

## 🚧 Pendiente (Crítico)

### Aplicar Decorators a TODOS los Blueprints del Negocio

Cada ruta de negocio debe tener:
```python
@require_login
@require_tenant
def mi_ruta():
    ...
```

**Blueprints a actualizar:**
1. `app/blueprints/catalog.py` - Productos
2. `app/blueprints/sales.py` - Ventas
3. `app/blueprints/suppliers.py` - Proveedores
4. `app/blueprints/invoices.py` - Boletas
5. `app/blueprints/balance.py` - Balance
6. `app/blueprints/settings.py` - Configuración
7. `app/blueprints/quotes.py` - Presupuestos
8. `app/blueprints/missing_products.py` - Productos faltantes
9. `app/blueprints/main.py` - Rutas principales

**Patrón de actualización:**
```python
# Antes
@catalog_bp.route('/products')
def list_products():
    products = db_session.query(Product).all()
    ...

# Después
from app.middleware import require_login, require_tenant

@catalog_bp.route('/products')
@require_login
@require_tenant
def list_products():
    # Filtrar por tenant
    products = db_session.query(Product).filter_by(tenant_id=g.tenant_id).all()
    ...
```

### Filtrar Queries por tenant_id

**TODAS** las queries a tablas tenantizadas deben filtrar por `g.tenant_id`:

#### Queries de SELECT
```python
# Antes
products = db_session.query(Product).filter_by(active=True).all()

# Después
from flask import g
products = db_session.query(Product).filter_by(
    tenant_id=g.tenant_id,
    active=True
).all()
```

#### Queries de INSERT
```python
# Antes
product = Product(name='Test', uom_id=1, sale_price=100)

# Después
product = Product(
    tenant_id=g.tenant_id,
    name='Test',
    uom_id=1,
    sale_price=100
)
```

#### Queries de UPDATE por ID
```python
# Antes
product = db_session.query(Product).filter_by(id=product_id).first()

# Después
product = db_session.query(Product).filter_by(
    id=product_id,
    tenant_id=g.tenant_id  # IMPORTANTE: validar tenant
).first()

if not product:
    # 404 si no existe o no pertenece al tenant
    return "Not found", 404
```

#### Queries de DELETE
```python
# Antes
db_session.query(Product).filter_by(id=product_id).delete()

# Después
result = db_session.query(Product).filter_by(
    id=product_id,
    tenant_id=g.tenant_id
).delete()

if result == 0:
    return "Not found", 404
```

### Servicios a Actualizar

Los servicios en `app/services/` también deben filtrar por tenant_id:
- `balance_service.py`
- `invoice_alerts_service.py`
- `invoice_service.py`
- `payment_service.py`
- `quote_service.py`
- `sale_adjustment_service.py`
- `sales_service.py`
- `top_products_service.py`

**Patrón:**
```python
# Servicios deben recibir tenant_id como parámetro
def get_top_products(db_session, tenant_id, limit=10):
    return db_session.query(Product).filter_by(
        tenant_id=tenant_id,
        active=True
    ).limit(limit).all()
```

### Relaciones Entre Tablas

Cuando se crean relaciones (ej: sale → sale_line):
```python
# sale_line NO tiene tenant_id, pero hereda de sale
# Asegurarse que el producto pertenezca al mismo tenant

# CORRECTO
product = db_session.query(Product).filter_by(
    id=product_id,
    tenant_id=g.tenant_id  # Validar que producto es del tenant
).first()

if not product:
    return "Producto no encontrado", 404

sale_line = SaleLine(
    sale_id=sale.id,
    product_id=product.id,  # OK porque ya validamos tenant
    qty=qty,
    unit_price=product.sale_price
)
```

### Templates a Actualizar

El template `base.html` necesita:
1. Mostrar nombre del tenant actual en navbar
2. Link a "Cambiar negocio" si usuario tiene múltiples tenants
3. Mostrar nombre de usuario actual
4. Link de logout

```html
<!-- Agregar al navbar -->
<ul class="navbar-nav ms-auto">
    {% if current_tenant %}
    <li class="nav-item">
        <span class="navbar-text">
            <i class="bi bi-building"></i> {{ current_tenant.name }}
        </span>
    </li>
    {% endif %}
    
    {% if g.user %}
    <li class="nav-item dropdown">
        <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
            <i class="bi bi-person-circle"></i> {{ g.user.full_name or g.user.email }}
        </a>
        <ul class="dropdown-menu dropdown-menu-end">
            <li><a class="dropdown-item" href="{{ url_for('auth.select_tenant') }}">
                <i class="bi bi-arrow-left-right"></i> Cambiar Negocio
            </a></li>
            <li><hr class="dropdown-divider"></li>
            <li><a class="dropdown-item" href="{{ url_for('auth.logout') }}">
                <i class="bi bi-box-arrow-right"></i> Cerrar Sesión
            </a></li>
        </ul>
    </li>
    {% endif %}
</ul>
```

## Checklist de Verificación

### Por Blueprint
- [ ] Importar `require_login` y `require_tenant`
- [ ] Aplicar decorators a TODAS las rutas
- [ ] Actualizar TODAS las queries SELECT con `filter_by(tenant_id=g.tenant_id)`
- [ ] Actualizar TODOS los INSERT con `tenant_id=g.tenant_id`
- [ ] Validar tenant_id en UPDATE/DELETE por ID
- [ ] Probar manualmente cada ruta

### Por Servicio
- [ ] Agregar parámetro `tenant_id` a funciones
- [ ] Filtrar queries por `tenant_id`
- [ ] Actualizar llamadas desde blueprints para pasar `g.tenant_id`

### Testing Manual
- [ ] Registro de nuevo usuario funciona
- [ ] Login funciona
- [ ] Crear producto funciona (se asigna tenant_id correcto)
- [ ] Producto de tenant A no es visible desde tenant B
- [ ] Intentar acceder a /products/<id> de otro tenant devuelve 404
- [ ] Cerrar sesión funciona
- [ ] Usuario con múltiples tenants puede cambiar entre ellos

## Ejemplo Completo: catalog.py

Ver el primer commit de cambios en `catalog.py` como referencia para aplicar el mismo patrón a los demás blueprints.

## Próximos Pasos (No Urgente)

Después de completar el PASO 3:
- Actualizar tests unitarios
- Agregar perfiles de usuario (editar nombre, cambiar password)
- Agregar invitación de usuarios a tenants
- Agregar audit log de cambios
- Implementar límites por plan (fase SaaS-2)
