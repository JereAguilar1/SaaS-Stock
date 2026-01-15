# PASO 3 - Testing Plan: Multi-Tenant Data Isolation

## Objetivo
Validar que el aislamiento de datos por `tenant_id` funciona correctamente en toda la aplicación.

## Setup de Test (Manual)

### Prerequisitos
1. Base de datos con migración SAAS_STEP2 aplicada
2. Aplicación Flask con PASO 3 completo (todos los blueprints tenantizados)

### Crear 2 Tenants de Prueba

```sql
-- Tenant 1: Ferretería López
INSERT INTO tenant (slug, name, active, created_at, updated_at)
VALUES ('ferreteria-lopez', 'Ferretería López', TRUE, NOW(), NOW())
RETURNING id; -- Anotar ID (ej: 1)

-- Tenant 2: Kiosco Central
INSERT INTO tenant (slug, name, active, created_at, updated_at)
VALUES ('kiosco-central', 'Kiosco Central', TRUE, NOW(), NOW())
RETURNING id; -- Anotar ID (ej: 2)
```

### Crear 2 Usuarios de Prueba

```sql
-- Usuario 1: lopez@test.com para Tenant 1
INSERT INTO app_user (email, password_hash, active, created_at, updated_at)
VALUES ('lopez@test.com', 'pbkdf2:sha256:600000$<hash>', TRUE, NOW(), NOW())
RETURNING id; -- Anotar ID

-- Usuario 2: kiosco@test.com para Tenant 2
INSERT INTO app_user (email, password_hash, active, created_at, updated_at)
VALUES ('kiosco@test.com', 'pbkdf2:sha256:600000$<hash>', TRUE, NOW(), NOW())
RETURNING id; -- Anotar ID
```

**Nota:** Generar password_hash con:
```python
from werkzeug.security import generate_password_hash
print(generate_password_hash('password123'))
```

### Asociar Usuarios a Tenants (OWNER)

```sql
-- Asociar lopez@test.com a Ferretería López
INSERT INTO user_tenant (user_id, tenant_id, role, created_at)
VALUES (1, 1, 'OWNER', NOW());

-- Asociar kiosco@test.com a Kiosco Central
INSERT INTO user_tenant (user_id, tenant_id, role, created_at)
VALUES (2, 2, 'OWNER', NOW());
```

---

## Test Cases

### TC-001: Login y Selección de Tenant
**Objetivo:** Validar que el usuario solo ve sus propios tenants.

**Pasos:**
1. Login como `lopez@test.com` / `password123`
2. Verificar que la sesión contiene `user_id` y `tenant_id=1`
3. Login como `kiosco@test.com` / `password123`
4. Verificar que la sesión contiene `user_id` y `tenant_id=2`

**Resultado esperado:**
- Cada usuario solo puede acceder a su tenant
- `g.tenant_id` se carga correctamente en `before_request`

---

### TC-002: Catálogo - Listado de Productos
**Objetivo:** Cada tenant solo ve sus propios productos.

**Setup:**
```sql
-- UOM global (sin tenant_id en este MVP, pero si lo tenantizamos, crear 2)
INSERT INTO uom (tenant_id, name, symbol) VALUES (1, 'Unidad', 'u');
INSERT INTO uom (tenant_id, name, symbol) VALUES (2, 'Unidad', 'u');

-- Producto de Ferretería López (tenant_id=1)
INSERT INTO product (tenant_id, sku, name, uom_id, active, sale_price)
VALUES (1, 'CLAVO-001', 'Clavo 2 pulgadas', 1, TRUE, 150.00);

-- Producto de Kiosco Central (tenant_id=2)
INSERT INTO product (tenant_id, sku, name, uom_id, active, sale_price)
VALUES (2, 'GASEOSA-COLA', 'Gaseosa Cola 1.5L', 2, TRUE, 500.00);
```

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/products`
3. Verificar que solo se muestra "Clavo 2 pulgadas"
4. Logout
5. Login como `kiosco@test.com`
6. Ir a `/products`
7. Verificar que solo se muestra "Gaseosa Cola 1.5L"

**Resultado esperado:**
- Cada tenant solo ve sus propios productos
- SKUs duplicados entre tenants no causan conflicto

---

### TC-003: Catálogo - Acceso Directo a Producto Ajeno
**Objetivo:** Validar que acceder a `/products/<id>` de otro tenant devuelve 404.

**Pasos:**
1. Login como `lopez@test.com`
2. Anotar ID del producto "Clavo 2 pulgadas" (ej: `product_id=1`)
3. Logout
4. Login como `kiosco@test.com`
5. Intentar acceder a `/products/1`

**Resultado esperado:**
- HTTP 404 (producto no encontrado)

---

### TC-004: Ventas - Crear Venta
**Objetivo:** Validar que las ventas se crean con `tenant_id` correcto.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/sales/new`
3. Agregar "Clavo 2 pulgadas" x 10
4. Confirmar venta (CASH)
5. Verificar en DB:
   ```sql
   SELECT id, tenant_id, total, status FROM sale ORDER BY id DESC LIMIT 1;
   -- Debe tener tenant_id=1
   ```

**Resultado esperado:**
- Sale creada con `tenant_id=1`
- StockMove OUT con `tenant_id=1`
- FinanceLedger INCOME con `tenant_id=1`

---

### TC-005: Ventas - Listado Solo Muestra Ventas del Tenant
**Objetivo:** Cada tenant solo ve sus propias ventas.

**Setup:**
```sql
-- Crear venta para Ferretería López
INSERT INTO sale (tenant_id, datetime, total, status) VALUES (1, NOW(), 1500.00, 'CONFIRMED');

-- Crear venta para Kiosco Central
INSERT INTO sale (tenant_id, datetime, total, status) VALUES (2, NOW(), 1000.00, 'CONFIRMED');
```

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/sales`
3. Verificar que solo se muestra la venta de $1500.00
4. Logout
5. Login como `kiosco@test.com`
6. Ir a `/sales`
7. Verificar que solo se muestra la venta de $1000.00

**Resultado esperado:**
- Listado filtrado por `Sale.tenant_id == g.tenant_id`

---

### TC-006: Ventas - Acceso Directo a Venta Ajena
**Objetivo:** Validar que acceder a `/sales/<id>` de otro tenant devuelve 404.

**Pasos:**
1. Login como `lopez@test.com`
2. Anotar ID de una venta propia (ej: `sale_id=1`)
3. Logout
4. Login como `kiosco@test.com`
5. Intentar acceder a `/sales/1`

**Resultado esperado:**
- HTTP 404 (venta no encontrada)

---

### TC-007: Presupuestos - Crear Presupuesto
**Objetivo:** Validar que los presupuestos se crean con `tenant_id` correcto.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/sales/new` (POS)
3. Agregar productos al carrito
4. Click en "Crear Presupuesto"
5. Completar datos del cliente
6. Verificar en DB:
   ```sql
   SELECT id, tenant_id, quote_number, customer_name FROM quote ORDER BY id DESC LIMIT 1;
   -- Debe tener tenant_id=1
   ```

**Resultado esperado:**
- Quote creada con `tenant_id=1`

---

### TC-008: Presupuestos - Listado y Acceso
**Objetivo:** Cada tenant solo ve sus propios presupuestos.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/quotes`
3. Verificar que solo se muestran presupuestos con `tenant_id=1`
4. Logout
5. Login como `kiosco@test.com`
6. Intentar acceder directamente a `/quotes/<id_de_lopez>`

**Resultado esperado:**
- HTTP 404 para presupuestos de otro tenant

---

### TC-009: Presupuestos - Descargar PDF de Presupuesto Ajeno
**Objetivo:** Validar que no se puede descargar PDF de presupuesto de otro tenant.

**Pasos:**
1. Login como `lopez@test.com`
2. Crear presupuesto (anotar ID, ej: `quote_id=1`)
3. Logout
4. Login como `kiosco@test.com`
5. Intentar acceder a `/quotes/1/pdf`

**Resultado esperado:**
- HTTP 404

---

### TC-010: Presupuestos - Convertir a Venta
**Objetivo:** Validar que al convertir un presupuesto, la venta creada tiene el mismo `tenant_id`.

**Pasos:**
1. Login como `lopez@test.com`
2. Crear presupuesto con productos (quote_id=X)
3. Convertir a venta desde `/quotes/X`
4. Verificar en DB:
   ```sql
   SELECT s.id, s.tenant_id, q.tenant_id AS quote_tenant_id
   FROM sale s
   JOIN quote q ON q.sale_id = s.id
   WHERE q.id = X;
   -- Ambos tenant_id deben ser iguales (1)
   ```

**Resultado esperado:**
- Sale creada con `tenant_id=1`
- StockMove OUT con `tenant_id=1`
- FinanceLedger INCOME con `tenant_id=1`

---

### TC-011: Balance - Vista Diaria/Mensual/Anual
**Objetivo:** Cada tenant solo ve su propio balance financiero.

**Setup:**
```sql
-- Crear ledger entries para ambos tenants
INSERT INTO finance_ledger (tenant_id, datetime, type, amount, category, reference_type, payment_method)
VALUES
  (1, NOW(), 'INCOME', 5000.00, 'Ventas', 'MANUAL', 'CASH'),
  (2, NOW(), 'INCOME', 3000.00, 'Ventas', 'MANUAL', 'TRANSFER');
```

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/balance`
3. Verificar que el total de ingresos es $5000.00
4. Logout
5. Login como `kiosco@test.com`
6. Ir a `/balance`
7. Verificar que el total de ingresos es $3000.00

**Resultado esperado:**
- Cada tenant solo ve su propio balance

---

### TC-012: Balance - Libro Mayor (Ledger)
**Objetivo:** Cada tenant solo ve sus propios movimientos en el libro mayor.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/balance/ledger`
3. Verificar que solo se muestran movimientos con `tenant_id=1`
4. Logout
5. Login como `kiosco@test.com`
6. Ir a `/balance/ledger`
7. Verificar que solo se muestran movimientos con `tenant_id=2`

**Resultado esperado:**
- Listado filtrado por `FinanceLedger.tenant_id == g.tenant_id`

---

### TC-013: Balance - Movimiento Manual
**Objetivo:** Validar que los movimientos manuales se crean con `tenant_id` correcto.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/balance/ledger/new`
3. Crear movimiento manual INCOME $2000 (CASH)
4. Verificar en DB:
   ```sql
   SELECT id, tenant_id, type, amount FROM finance_ledger ORDER BY id DESC LIMIT 1;
   -- Debe tener tenant_id=1
   ```

**Resultado esperado:**
- FinanceLedger creado con `tenant_id=1`

---

### TC-014: Top Productos - POS Dashboard
**Objetivo:** El top de productos vendidos solo muestra datos del tenant activo.

**Setup:**
```sql
-- Asegurar que hay ventas confirmadas para ambos tenants (TC-004 y TC-005)
```

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/sales/new` (POS)
3. Verificar que el widget "Top Vendidos" solo muestra productos de `tenant_id=1`
4. Logout
5. Login como `kiosco@test.com`
6. Ir a `/sales/new` (POS)
7. Verificar que el widget "Top Vendidos" solo muestra productos de `tenant_id=2`

**Resultado esperado:**
- `get_top_selling_products(session, g.tenant_id)` filtra correctamente

---

### TC-015: Proveedores - Listado y Creación
**Objetivo:** Cada tenant solo ve sus propios proveedores.

**Setup:**
```sql
-- Crear proveedor para tenant 1
INSERT INTO supplier (tenant_id, name) VALUES (1, 'Proveedor López');

-- Crear proveedor para tenant 2
INSERT INTO supplier (tenant_id, name) VALUES (2, 'Proveedor Kiosco');
```

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/suppliers`
3. Verificar que solo se muestra "Proveedor López"
4. Logout
5. Login como `kiosco@test.com`
6. Ir a `/suppliers`
7. Verificar que solo se muestra "Proveedor Kiosco"

**Resultado esperado:**
- Listado filtrado por `Supplier.tenant_id == g.tenant_id`

---

### TC-016: Facturas de Compra - Listado y Creación
**Objetivo:** Cada tenant solo ve sus propias facturas de compra.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/invoices`
3. Crear factura de compra para "Proveedor López"
4. Verificar que la factura tiene `tenant_id=1` en DB
5. Logout
6. Login como `kiosco@test.com`
7. Ir a `/invoices`
8. Verificar que NO se muestra la factura de López

**Resultado esperado:**
- Facturas filtradas por `PurchaseInvoice.tenant_id == g.tenant_id`

---

### TC-017: Stock - Movimientos de Stock
**Objetivo:** Los movimientos de stock están aislados por tenant.

**Pasos:**
1. Login como `lopez@test.com`
2. Crear movimiento de stock IN para un producto propio
3. Verificar en DB:
   ```sql
   SELECT id, tenant_id, type, reference_type FROM stock_move ORDER BY id DESC LIMIT 1;
   -- Debe tener tenant_id=1
   ```
4. Logout
5. Login como `kiosco@test.com`
6. Verificar que no puede ver el movimiento de stock de López (si hay UI de listado)

**Resultado esperado:**
- StockMove creado con `tenant_id=1`

---

### TC-018: Productos Faltantes - Solicitudes
**Objetivo:** Cada tenant solo ve sus propias solicitudes de productos faltantes.

**Pasos:**
1. Login como `lopez@test.com`
2. Ir a `/missing-products`
3. Solicitar producto faltante "Martillo"
4. Verificar en DB:
   ```sql
   SELECT id, tenant_id, name FROM missing_product_request ORDER BY id DESC LIMIT 1;
   -- Debe tener tenant_id=1
   ```
5. Logout
6. Login como `kiosco@test.com`
7. Ir a `/missing-products`
8. Verificar que NO se muestra "Martillo"

**Resultado esperado:**
- Solicitudes filtradas por `MissingProductRequest.tenant_id == g.tenant_id`

---

## Resumen de Validación SQL (Rápida)

Para verificar rápidamente que TODO está aislado por tenant, ejecutar:

```sql
-- Verificar que todas las tablas tenantizadas tienen registros con tenant_id correcto
SELECT 'uom' AS table_name, tenant_id, COUNT(*) FROM uom GROUP BY tenant_id
UNION ALL
SELECT 'category', tenant_id, COUNT(*) FROM category GROUP BY tenant_id
UNION ALL
SELECT 'product', tenant_id, COUNT(*) FROM product GROUP BY tenant_id
UNION ALL
SELECT 'sale', tenant_id, COUNT(*) FROM sale GROUP BY tenant_id
UNION ALL
SELECT 'supplier', tenant_id, COUNT(*) FROM supplier GROUP BY tenant_id
UNION ALL
SELECT 'purchase_invoice', tenant_id, COUNT(*) FROM purchase_invoice GROUP BY tenant_id
UNION ALL
SELECT 'stock_move', tenant_id, COUNT(*) FROM stock_move GROUP BY tenant_id
UNION ALL
SELECT 'finance_ledger', tenant_id, COUNT(*) FROM finance_ledger GROUP BY tenant_id
UNION ALL
SELECT 'missing_product_request', tenant_id, COUNT(*) FROM missing_product_request GROUP BY tenant_id
UNION ALL
SELECT 'quote', tenant_id, COUNT(*) FROM quote GROUP BY tenant_id
ORDER BY table_name, tenant_id;
```

**Resultado esperado:** Ninguna tabla debe tener registros con `tenant_id` NULL o incorrecto.

---

## Checklist de Seguridad Final

- [ ] TODAS las rutas del negocio están decoradas con `@require_login` y `@require_tenant`
- [ ] TODAS las queries de listado filtran por `Model.tenant_id == g.tenant_id`
- [ ] TODAS las operaciones por ID (ej: `/products/<id>`) validan tenant y devuelven 404 si no coincide
- [ ] TODOS los inserts en tablas tenantizadas setean `tenant_id = g.tenant_id`
- [ ] NUNCA se usa `.get(id)` sin filtro de tenant
- [ ] Los locks transaccionales (FOR UPDATE) incluyen filtro de tenant
- [ ] Los servicios transaccionales (quote_service, sale_adjustment_service, etc.) reciben y validan `tenant_id`
- [ ] El servicio `top_products_service` filtra por tenant
- [ ] El servicio `balance_service` filtra por tenant

---

## Próximos Pasos (Opcional)
- Automatizar tests con pytest + fixtures
- CI/CD con tests de aislamiento
- Auditoría de seguridad externa
- Stress testing con 10+ tenants
