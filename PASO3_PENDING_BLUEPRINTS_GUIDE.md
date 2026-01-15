# Guía de Implementación: Blueprints Restantes PASO 3
## Multi-Tenant App Layer Migration

**Estado:** 5 de 9 blueprints completados (55%)

### ✅ Blueprints Completados
1. ✅ `app/blueprints/catalog.py` - Productos, categorías, stock
2. ✅ `app/blueprints/suppliers.py` - Proveedores
3. ✅ `app/blueprints/settings.py` - UOM y Categories
4. ✅ `app/blueprints/missing_products.py` - Productos faltantes
5. ✅ `app/blueprints/main.py` - Health check (no requirió cambios)

### 🔄 Blueprints Pendientes (4)
Estos son **complejos** y requieren atención especial a transacciones, servicios auxiliares y tablas relacionadas:

1. ⏳ `app/blueprints/invoices.py` - Boletas de compra
2. ⏳ `app/blueprints/sales.py` - Ventas POS y gestión
3. ⏳ `app/blueprints/quotes.py` - Presupuestos y conversión a ventas
4. ⏳ `app/blueprints/balance.py` - Ledger financiero

---

## Patrón Estándar de Implementación

### A) Imports Requeridos
Agregar al inicio de cada blueprint:

```python
from flask import g, abort
from app.middleware import require_login, require_tenant
```

### B) Decoradores en Rutas
Aplicar a TODAS las rutas (excepto `/health` que no requiere auth):

```python
@bp.route('/ruta')
@require_login
@require_tenant
def mi_ruta():
    ...
```

### C) Filtrado por Tenant en Queries

#### Listados simples:
```python
# ANTES:
products = session.query(Product).all()

# DESPUÉS:
products = session.query(Product).filter(
    Product.tenant_id == g.tenant_id
).all()
```

#### Queries con JOIN:
```python
# ANTES:
query = session.query(Sale).join(Product)

# DESPUÉS:
query = session.query(Sale).filter(
    Sale.tenant_id == g.tenant_id
).join(Product)
```

#### Subqueries y agregaciones:
```python
# ANTES:
count = session.query(func.count(Product.id)).scalar()

# DESPUÉS:
count = session.query(func.count(Product.id)).filter(
    Product.tenant_id == g.tenant_id
).scalar()
```

### D) Validación por ID (Lookup individual)

```python
# ANTES:
invoice = session.query(PurchaseInvoice).filter_by(id=invoice_id).first()
if not invoice:
    flash('No encontrado', 'danger')
    return redirect(...)

# DESPUÉS:
invoice = session.query(PurchaseInvoice).filter(
    PurchaseInvoice.id == invoice_id,
    PurchaseInvoice.tenant_id == g.tenant_id
).first()

if not invoice:
    abort(404)  # Más seguro: no revelar existencia
```

### E) Inserts con tenant_id

```python
# ANTES:
sale = Sale(
    customer='Cliente',
    total_amount=100
)

# DESPUÉS:
sale = Sale(
    tenant_id=g.tenant_id,  # ⚠️ CRÍTICO
    customer='Cliente',
    total_amount=100
)
```

### F) Tablas Hijas SIN tenant_id

**Regla:** Tablas como `sale_line`, `purchase_invoice_line`, `stock_move_line`, `quote_line` **NO tienen `tenant_id`**.

**Validación:** SIEMPRE validar el parent ANTES de operar líneas:

```python
# 1) Validar parent pertenece al tenant
sale = session.query(Sale).filter(
    Sale.id == sale_id,
    Sale.tenant_id == g.tenant_id
).first()

if not sale:
    abort(404)

# 2) Ahora puedes operar líneas de forma segura
for line in sale.lines:
    # ... operaciones ...
```

### G) Validación de Relaciones (FK)

Cuando un modelo referencia otro por FK, validar que ambos pertenezcan al tenant:

```python
# Al crear PurchaseInvoice con supplier_id:
supplier = session.query(Supplier).filter(
    Supplier.id == supplier_id,
    Supplier.tenant_id == g.tenant_id
).first()

if not supplier:
    flash('Proveedor no encontrado o no pertenece a su negocio', 'danger')
    return redirect(...)

# Al crear líneas con product_id:
product = session.query(Product).filter(
    Product.id == product_id,
    Product.tenant_id == g.tenant_id
).first()

if not product:
    flash('Producto no encontrado o no pertenece a su negocio', 'danger')
    return redirect(...)
```

---

## 1. INVOICES Blueprint (`app/blueprints/invoices.py`)

### Modelos Involucrados
- `PurchaseInvoice` (tiene `tenant_id`) ✅
- `PurchaseInvoiceLine` (NO tiene `tenant_id`) ⚠️
- `Supplier` (tiene `tenant_id`) ✅
- `Product` (tiene `tenant_id`) ✅
- `FinanceLedger` (tiene `tenant_id`) ✅
- `ProductStock` (NO tiene `tenant_id`, pero relacionado a `Product`) ⚠️

### Rutas a Actualizar

#### `list_invoices()`
- Filtrar `PurchaseInvoice` por `tenant_id`
- Filtrar `Supplier` (dropdown) por `tenant_id`

```python
query = db_session.query(PurchaseInvoice).filter(
    PurchaseInvoice.tenant_id == g.tenant_id
)

suppliers = db_session.query(Supplier).filter(
    Supplier.tenant_id == g.tenant_id
).order_by(Supplier.name).all()
```

#### `view_invoice(invoice_id)`
- Validar que `PurchaseInvoice` pertenezca al tenant

```python
invoice = db_session.query(PurchaseInvoice).filter(
    PurchaseInvoice.id == invoice_id,
    PurchaseInvoice.tenant_id == g.tenant_id
).first()

if not invoice:
    abort(404)
```

#### `new_invoice()` (GET) y `add_line_to_draft()`
- Filtrar `Supplier` y `Product` por `tenant_id`

```python
suppliers = db_session.query(Supplier).filter(
    Supplier.tenant_id == g.tenant_id
).order_by(Supplier.name).all()

products = db_session.query(Product).filter(
    Product.tenant_id == g.tenant_id,
    Product.active == True
).order_by(Product.name).all()
```

#### `confirm_invoice()` (crea la boleta)
- Al llamar `create_invoice_with_lines()`, asegurar que:
  - Validar `supplier_id` pertenece al tenant
  - Validar cada `product_id` en líneas pertenece al tenant
  - Pasar `tenant_id=g.tenant_id` al crear `PurchaseInvoice`

**CRÍTICO:** Revisar `app/services/invoice_service.py`:

```python
# En create_invoice_with_lines():
def create_invoice_with_lines(db_session, tenant_id, supplier_id, ...):
    # Validar supplier
    supplier = db_session.query(Supplier).filter(
        Supplier.id == supplier_id,
        Supplier.tenant_id == tenant_id
    ).first()
    if not supplier:
        raise ValueError('Proveedor no encontrado')
    
    # Crear invoice
    invoice = PurchaseInvoice(
        tenant_id=tenant_id,  # ⚠️ CRÍTICO
        supplier_id=supplier_id,
        ...
    )
    
    # Para cada línea:
    for line_data in lines:
        product = db_session.query(Product).filter(
            Product.id == line_data['product_id'],
            Product.tenant_id == tenant_id
        ).first()
        if not product:
            raise ValueError(f'Producto {line_data["product_id"]} no encontrado')
        
        # Crear línea (NO tiene tenant_id)
        line = PurchaseInvoiceLine(...)
        invoice.lines.append(line)
    
    db_session.add(invoice)
    db_session.commit()
```

#### `pay_invoice_route(invoice_id)`
- Validar `PurchaseInvoice` pertenece al tenant
- Al llamar `pay_invoice()`, pasar `tenant_id`

**CRÍTICO:** Revisar `app/services/payment_service.py`:

```python
# En pay_invoice():
def pay_invoice(db_session, invoice_id, tenant_id, payment_method, payment_date):
    # Lock invoice
    invoice = db_session.query(PurchaseInvoice).filter(
        PurchaseInvoice.id == invoice_id,
        PurchaseInvoice.tenant_id == tenant_id
    ).with_for_update().first()
    
    if not invoice:
        raise ValueError('Boleta no encontrada')
    
    # ... validaciones ...
    
    # Crear ledger entry
    ledger = FinanceLedger(
        tenant_id=tenant_id,  # ⚠️ CRÍTICO
        entry_type='EXPENSE',
        amount=invoice.total_amount,
        description=f'Pago boleta {invoice.invoice_number}',
        ...
    )
    db_session.add(ledger)
    
    # Update invoice
    invoice.status = InvoiceStatus.PAID
    invoice.paid_date = payment_date
    
    db_session.commit()
```

---

## 2. SALES Blueprint (`app/blueprints/sales.py`)

### Modelos Involucrados
- `Sale` (tiene `tenant_id`) ✅
- `SaleLine` (NO tiene `tenant_id`) ⚠️
- `Product` (tiene `tenant_id`) ✅
- `ProductStock` (NO tiene `tenant_id`, join con Product) ⚠️
- `StockMove` (tiene `tenant_id`) ✅
- `StockMoveLine` (NO tiene `tenant_id`) ⚠️
- `FinanceLedger` (tiene `tenant_id`) ✅

### Rutas Críticas

#### `new_sale()` (POS - búsqueda de productos)
- Filtrar `Product` por `tenant_id` y `active=True`

```python
products = db_session.query(Product).outerjoin(ProductStock).filter(
    Product.tenant_id == g.tenant_id,
    Product.active == True
).order_by(Product.name).all()
```

#### `confirm_sale()` (transacción compleja)
Esta es la ruta MÁS CRÍTICA. Involucra:
1. Crear `Sale` con `tenant_id`
2. Crear `SaleLine` (sin tenant_id)
3. Crear `StockMove` con `tenant_id`
4. Crear `StockMoveLine` (sin tenant_id)
5. Lock `ProductStock` via `Product` (filtrado por tenant)
6. Crear `FinanceLedger` con `tenant_id`

**CRÍTICO:** Revisar `app/services/sales_service.py`:

```python
def confirm_sale(db_session, tenant_id, cart_data, customer_name, payment_method):
    # 1) Crear Sale
    sale = Sale(
        tenant_id=tenant_id,  # ⚠️ CRÍTICO
        customer=customer_name,
        payment_method=payment_method,
        status='CONFIRMED',
        ...
    )
    db_session.add(sale)
    db_session.flush()  # Get sale.id
    
    # 2) Crear StockMove
    stock_move = StockMove(
        tenant_id=tenant_id,  # ⚠️ CRÍTICO
        move_type='OUT',
        reference=f'VENTA-{sale.id}',
        ...
    )
    db_session.add(stock_move)
    db_session.flush()
    
    total = Decimal('0')
    
    # 3) Para cada item en cart:
    for item in cart_data:
        product_id = item['product_id']
        qty = item['qty']
        unit_price = item['unit_price']
        
        # Validar producto pertenece al tenant
        product = db_session.query(Product).filter(
            Product.id == product_id,
            Product.tenant_id == tenant_id
        ).first()
        if not product:
            raise ValueError(f'Producto {product_id} no encontrado en su negocio')
        
        # Lock product_stock via join
        product_stock = db_session.query(ProductStock).join(Product).filter(
            ProductStock.product_id == product_id,
            Product.tenant_id == tenant_id
        ).with_for_update().first()
        
        if not product_stock or product_stock.on_hand_qty < qty:
            raise ValueError(f'Stock insuficiente para {product.name}')
        
        # Crear SaleLine (sin tenant_id)
        sale_line = SaleLine(
            sale_id=sale.id,
            product_id=product_id,
            qty=qty,
            unit_price=unit_price,
            subtotal=qty * unit_price
        )
        db_session.add(sale_line)
        
        # Crear StockMoveLine (sin tenant_id)
        move_line = StockMoveLine(
            stock_move_id=stock_move.id,
            product_id=product_id,
            qty=qty
        )
        db_session.add(move_line)
        
        total += sale_line.subtotal
    
    # 4) Update sale total
    sale.total_amount = total
    
    # 5) Trigger de stock se ejecuta automáticamente (trigger_apply_stock_move)
    #    PERO el trigger ya filtra por tenant porque usa Product join
    
    # 6) Crear ledger entry
    ledger = FinanceLedger(
        tenant_id=tenant_id,  # ⚠️ CRÍTICO
        entry_type='INCOME',
        amount=total,
        description=f'Venta #{sale.id}',
        ...
    )
    db_session.add(ledger)
    
    db_session.commit()
    return sale
```

#### `edit_sale(sale_id)` (ajuste de stock)
- Validar `Sale` pertenece al tenant
- Al ajustar cantidades, solo afectar stock del tenant

**CRÍTICO:** Revisar `app/services/sale_adjustment_service.py`:

```python
def adjust_sale_quantities(db_session, sale_id, tenant_id, new_lines):
    # 1) Validar sale pertenece al tenant
    sale = db_session.query(Sale).filter(
        Sale.id == sale_id,
        Sale.tenant_id == tenant_id
    ).with_for_update().first()
    
    if not sale:
        raise ValueError('Venta no encontrada')
    
    # 2) Calcular deltas y ajustar stock
    for line_id, new_qty in new_lines.items():
        line = db_session.query(SaleLine).filter_by(id=line_id).first()
        if not line or line.sale_id != sale_id:
            raise ValueError('Línea inválida')
        
        # Validar producto pertenece al tenant
        product = db_session.query(Product).filter(
            Product.id == line.product_id,
            Product.tenant_id == tenant_id
        ).first()
        if not product:
            raise ValueError('Producto no pertenece al tenant')
        
        # Lock stock via join
        product_stock = db_session.query(ProductStock).join(Product).filter(
            ProductStock.product_id == line.product_id,
            Product.tenant_id == tenant_id
        ).with_for_update().first()
        
        delta = new_qty - line.qty
        
        if delta > 0:
            # Necesita más stock
            if product_stock.on_hand_qty < delta:
                raise ValueError(f'Stock insuficiente para {product.name}')
        
        # Aplicar delta
        product_stock.on_hand_qty -= delta
        line.qty = new_qty
        line.subtotal = new_qty * line.unit_price
    
    # Recalcular total
    sale.total_amount = sum(l.subtotal for l in sale.lines)
    
    db_session.commit()
```

#### `top_products()` (servicio de analytics)
**CRÍTICO:** Revisar `app/services/top_products_service.py`:

```python
def get_top_selling_products(db_session, tenant_id, limit=10):
    # Query top productos por tenant
    top = db_session.query(
        Product.id,
        Product.name,
        func.sum(SaleLine.qty).label('total_qty'),
        func.count(Sale.id).label('sale_count')
    ).join(SaleLine, SaleLine.product_id == Product.id)\
     .join(Sale, Sale.id == SaleLine.sale_id)\
     .filter(
        Product.tenant_id == tenant_id,  # ⚠️ CRÍTICO
        Sale.tenant_id == tenant_id,     # ⚠️ CRÍTICO
        Sale.status == 'CONFIRMED'
    ).group_by(Product.id, Product.name)\
     .order_by(func.sum(SaleLine.qty).desc())\
     .limit(limit)\
     .all()
    
    return top
```

---

## 3. QUOTES Blueprint (`app/blueprints/quotes.py`)

### Modelos Involucrados
- `Quote` (tiene `tenant_id`) ✅
- `QuoteLine` (NO tiene `tenant_id`) ⚠️
- `Product` (tiene `tenant_id`) ✅

### Rutas Críticas

#### `list_quotes()`
```python
quotes = db_session.query(Quote).filter(
    Quote.tenant_id == g.tenant_id
).order_by(Quote.issued_at.desc()).all()
```

#### `create_quote_from_cart()`
```python
# Validar productos del cart
for item in cart_data:
    product = db_session.query(Product).filter(
        Product.id == item['product_id'],
        Product.tenant_id == g.tenant_id
    ).first()
    if not product:
        raise ValueError('Producto no encontrado')

# Crear quote
quote = Quote(
    tenant_id=g.tenant_id,  # ⚠️ CRÍTICO
    customer_name=customer,
    status='PENDING',
    ...
)

# Crear líneas (sin tenant_id)
for item in cart_data:
    line = QuoteLine(
        quote_id=quote.id,
        product_id=item['product_id'],
        product_snapshot_name=product.name,  # Snapshot
        qty=item['qty'],
        unit_price=item['unit_price'],
        subtotal=item['qty'] * item['unit_price']
    )
    quote.lines.append(line)

db_session.add(quote)
db_session.commit()
```

#### `convert_quote_to_sale(quote_id)` (servicio complejo)
**CRÍTICO:** Revisar `app/services/quote_service.py`:

```python
def convert_quote_to_sale(db_session, quote_id, tenant_id, payment_method):
    # 1) Validar quote pertenece al tenant
    quote = db_session.query(Quote).filter(
        Quote.id == quote_id,
        Quote.tenant_id == tenant_id
    ).with_for_update().first()
    
    if not quote or quote.status != 'PENDING':
        raise ValueError('Presupuesto no encontrado o no está pendiente')
    
    # 2) Convertir líneas de quote a cart_data
    cart_data = []
    for line in quote.lines:
        # Validar producto sigue existiendo y pertenece al tenant
        product = db_session.query(Product).filter(
            Product.id == line.product_id,
            Product.tenant_id == tenant_id
        ).first()
        if not product:
            raise ValueError(f'Producto {line.product_id} ya no existe')
        
        cart_data.append({
            'product_id': line.product_id,
            'qty': line.qty,
            'unit_price': line.unit_price
        })
    
    # 3) Crear venta usando sales_service
    sale = confirm_sale(db_session, tenant_id, cart_data, quote.customer_name, payment_method)
    
    # 4) Marcar quote como CONVERTED
    quote.status = 'CONVERTED'
    quote.converted_to_sale_id = sale.id
    
    db_session.commit()
    return sale
```

#### PDF generation (`download_quote_pdf(quote_id)`)
- Validar quote pertenece al tenant antes de generar PDF

```python
quote = db_session.query(Quote).filter(
    Quote.id == quote_id,
    Quote.tenant_id == g.tenant_id
).first()

if not quote:
    abort(404)
```

---

## 4. BALANCE Blueprint (`app/blueprints/balance.py`)

### Modelos Involucrados
- `FinanceLedger` (tiene `tenant_id`) ✅

### Rutas Críticas

#### `index()` (resumen financiero)
```python
# Totales por tenant
income_total = db_session.query(func.sum(FinanceLedger.amount)).filter(
    FinanceLedger.tenant_id == g.tenant_id,
    FinanceLedger.entry_type == 'INCOME'
).scalar() or Decimal('0')

expense_total = db_session.query(func.sum(FinanceLedger.amount)).filter(
    FinanceLedger.tenant_id == g.tenant_id,
    FinanceLedger.entry_type == 'EXPENSE'
).scalar() or Decimal('0')

balance = income_total - expense_total
```

#### `ledger_list()` (libro mayor)
```python
# Filtros
query = db_session.query(FinanceLedger).filter(
    FinanceLedger.tenant_id == g.tenant_id
)

# Filtros opcionales (entry_type, fecha desde/hasta)
if entry_type:
    query = query.filter(FinanceLedger.entry_type == entry_type)

if date_from:
    query = query.filter(FinanceLedger.datetime >= date_from)

if date_to:
    query = query.filter(FinanceLedger.datetime <= date_to)

entries = query.order_by(FinanceLedger.datetime.desc()).all()
```

#### `create_ledger_entry()` (movimiento manual)
```python
ledger = FinanceLedger(
    tenant_id=g.tenant_id,  # ⚠️ CRÍTICO
    entry_type=entry_type,
    amount=amount,
    description=description,
    datetime=datetime.now(),
    ...
)
db_session.add(ledger)
db_session.commit()
```

**CRÍTICO:** Revisar `app/services/balance_service.py` si existe:

```python
def calculate_balance(db_session, tenant_id, start_date=None, end_date=None):
    query = db_session.query(
        func.sum(
            func.case(
                (FinanceLedger.entry_type == 'INCOME', FinanceLedger.amount),
                else_=-FinanceLedger.amount
            )
        )
    ).filter(FinanceLedger.tenant_id == tenant_id)
    
    if start_date:
        query = query.filter(FinanceLedger.datetime >= start_date)
    if end_date:
        query = query.filter(FinanceLedger.datetime <= end_date)
    
    balance = query.scalar() or Decimal('0')
    return balance
```

---

## Checklist de Validación Final

Después de actualizar los 4 blueprints, ejecutar estos tests:

### 1. Test de Aislamiento Básico
```sql
-- Crear 2 usuarios en 2 tenants distintos
INSERT INTO tenant (slug, name, active) VALUES 
  ('test-a', 'Negocio A', true),
  ('test-b', 'Negocio B', true);

INSERT INTO app_user (email, password_hash, active) VALUES
  ('usera@test.com', 'hash_a', true),
  ('userb@test.com', 'hash_b', true);

INSERT INTO user_tenant (user_id, tenant_id, role) VALUES
  ((SELECT id FROM app_user WHERE email='usera@test.com'), 
   (SELECT id FROM tenant WHERE slug='test-a'), 
   'OWNER'),
  ((SELECT id FROM app_user WHERE email='userb@test.com'), 
   (SELECT id FROM tenant WHERE slug='test-b'), 
   'OWNER');

-- Login como userA → crear producto PA
-- Login como userB → crear producto PB
-- Verificar: userA NO ve PB, userB NO ve PA

-- Intentar acceder /products/<id_de_PB> desde tenant A → debe dar 404
```

### 2. Test de Boletas
```sql
-- Tenant A: crear boleta con proveedor de Tenant A
-- Tenant B: crear boleta con proveedor de Tenant B
-- Verificar:
SELECT tenant_id, supplier_id, invoice_number 
FROM purchase_invoice;

-- Debe haber 2 filas con tenant_id distintos

-- Pagar boleta de Tenant A
-- Verificar ledger:
SELECT tenant_id, entry_type, amount, description 
FROM finance_ledger 
WHERE entry_type='EXPENSE';

-- Debe tener tenant_id correcto
```

### 3. Test de Ventas y Stock
```sql
-- Tenant A: crear venta con producto PA (qty=2)
-- Verificar stock:
SELECT p.tenant_id, p.name, ps.on_hand_qty 
FROM product_stock ps 
JOIN product p ON p.id = ps.product_id
WHERE p.tenant_id = (SELECT id FROM tenant WHERE slug='test-a');

-- Stock de PA debe haber disminuido
-- Stock de productos de Tenant B NO debe cambiar
```

### 4. Test de Top Productos
```sql
-- Tenant A: crear 3 ventas con producto PA
-- Tenant B: crear 1 venta con producto PB
-- GET /sales/top-products desde Tenant A
-- Verificar: solo aparece PA, no PB
```

### 5. Test de Balance
```sql
-- Tenant A: 1 venta ($100), 1 pago de boleta ($50)
-- Balance Tenant A = $50
-- Tenant B: 1 venta ($200)
-- Balance Tenant B = $200
-- Verificar:
SELECT 
  tenant_id,
  SUM(CASE WHEN entry_type='INCOME' THEN amount ELSE -amount END) as balance
FROM finance_ledger
GROUP BY tenant_id;
```

---

## Orden de Implementación Recomendado

1. **Primero:** Actualizar los 4 blueprints pendientes (invoices, sales, quotes, balance)
2. **Segundo:** Actualizar servicios auxiliares:
   - `app/services/invoice_service.py`
   - `app/services/payment_service.py`
   - `app/services/sales_service.py`
   - `app/services/sale_adjustment_service.py`
   - `app/services/top_products_service.py`
   - `app/services/quote_service.py`
   - `app/services/balance_service.py` (si existe)
3. **Tercero:** Testing manual con checklist
4. **Cuarto:** Testing automatizado (opcional)

---

## Notas Críticas de Seguridad

### ⚠️ NUNCA hacer:
```python
# ❌ MAL: permite acceso cross-tenant
product = session.query(Product).filter_by(id=product_id).first()

# ❌ MAL: no valida tenant en update
invoice.status = 'PAID'
session.commit()
```

### ✅ SIEMPRE hacer:
```python
# ✅ BIEN: valida tenant
product = session.query(Product).filter(
    Product.id == product_id,
    Product.tenant_id == g.tenant_id
).first()

if not product:
    abort(404)

# ✅ BIEN: lock con validación de tenant
invoice = session.query(PurchaseInvoice).filter(
    PurchaseInvoice.id == invoice_id,
    PurchaseInvoice.tenant_id == g.tenant_id
).with_for_update().first()
```

### ⚠️ Stock Triggers
Los triggers de stock (`trigger_apply_stock_move`, `trigger_init_product_stock`) YA están preparados para multi-tenant porque:
- Usan `JOIN` con `product` y filtran por `product.tenant_id` implícitamente
- NO requieren modificación si los `StockMove` tienen `tenant_id` correcto

**Verificar en DB:**
```sql
SELECT 
  p.tenant_id,
  sm.tenant_id as move_tenant_id,
  sml.product_id,
  sml.qty
FROM stock_move_line sml
JOIN stock_move sm ON sm.id = sml.stock_move_id
JOIN product p ON p.id = sml.product_id
WHERE p.tenant_id != sm.tenant_id;

-- Debe retornar 0 filas (no hay inconsistencias)
```

---

## Próximos Pasos

1. Leer esta guía completamente
2. Implementar los 4 blueprints siguiendo el patrón exacto
3. Actualizar servicios auxiliares
4. Ejecutar tests del checklist
5. Crear documento final de validación: `PASO3_TESTING_RESULTS.md`

---

## Estado Final Esperado

Al completar:
- ✅ 9 de 9 blueprints migrados a multi-tenant
- ✅ 7+ servicios auxiliares actualizados
- ✅ 100% de rutas protegidas con `@require_login` y `@require_tenant`
- ✅ 100% de queries filtradas por `tenant_id`
- ✅ 0% cross-tenant data leakage
- ✅ Compatibilidad con tenant default (id=1) mantenida

**¡Adelante! 🚀**
