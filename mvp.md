MVP SaaS Multi-Tenant
Plataforma de Gestión de Stock, Ventas y Finanzas
Versión: MVP inicial (hasta 10 clientes)
Objetivo: Definir el alcance mínimo funcional y técnico para transformar la plataforma actual en un SaaS escalable.

1. Objetivo del MVP
El objetivo de este MVP es convertir la plataforma existente (gestión de stock, ventas, compras, presupuestos y balance) en un SaaS multi-tenant, permitiendo que múltiples negocios (ferreterías, kioscos u otros comercios similares) utilicen el sistema de forma simultánea, sin compartir datos entre sí, y con posibilidad de escalar progresivamente a cientos o miles de clientes.
Este MVP está diseñado para:
Soportar hasta 10 clientes reales en producción.
Reutilizar el 100% de la lógica de negocio existente.
Establecer una arquitectura correcta desde el inicio, evitando reescrituras futuras.

2. Alcance funcional del MVP
2.1 Qué incluye el MVP
Cada cliente (negocio / tenant) tendrá su propio entorno completamente aislado con acceso a:
Catálogo de productos (con imágenes).
Stock y stock mínimo por producto.
Ventas (POS) con:
efectivo / transferencia
ajuste automático de stock
Compras y boletas:
vencimientos
estados: pendiente, pagada, caducada
alertas de vencimiento
Proveedores.
Presupuestos:
creación
edición
conversión a venta
generación de PDF
Balance financiero:
diario / mensual / anual
libro mayor (ledger)
Productos faltantes (productos que los clientes piden pero no existen).
Formato de fechas y números acorde a Argentina.
Además:
Login con email y contraseña.
Cada negocio comienza con el sistema vacío (sin productos).
El negocio se selecciona por sesión (no por subdominio).

2.2 Qué NO incluye el MVP
Para mantener foco y velocidad, el MVP no incluye:
Cobros de suscripción (Stripe, MercadoPago, etc.).
Facturación electrónica.
Múltiples sucursales por negocio.
Roles avanzados (solo OWNER al inicio).
Subdominios por cliente.
Integraciones externas.
Auditoría avanzada o historial de cambios.
Estas funcionalidades quedan planificadas para etapas posteriores.

3. Concepto de Tenant (Negocio)
Un tenant representa un negocio independiente dentro del SaaS.
Cada tenant:
Tiene su propio conjunto de datos.
No puede ver ni acceder a datos de otros tenants.
Puede tener uno o más usuarios asociados (preparado, aunque el MVP use uno).
Ejemplos de tenants:
“Ferretería López”
“Kiosco Central”
“Corralón San Martín”

4. Modelo de Usuarios
4.1 Usuario (App User)
Un usuario representa a una persona que accede a la plataforma.
Características:
Se identifica por email + contraseña.
Puede estar asociado a uno o más negocios (estructura preparada).
Para el MVP, se asume 1 usuario = 1 negocio, pero el diseño permite escalar.

4.2 Relación Usuario ↔ Negocio
Se utiliza una tabla intermedia para permitir escalabilidad futura:
Un usuario puede pertenecer a varios negocios.
Un negocio puede tener varios usuarios.
Se puede asignar un rol (OWNER, ADMIN, STAFF), aunque el MVP solo use OWNER.

5. Multi-Tenancy: separación de datos
5.1 Estrategia elegida
Se utilizará una única base de datos PostgreSQL, donde todas las tablas del negocio incluyen una columna:
tenant_id

Esto permite:
Onboarding inmediato.
Costos bajos.
Escalabilidad progresiva.
Simplicidad operativa.

5.2 Regla principal de aislamiento
Toda información que pertenezca a un negocio debe tener tenant_id.
Toda consulta, inserción, actualización o eliminación:
Debe filtrar por tenant_id.
Nunca debe operar sobre datos de otro tenant.

6. Lista cerrada de tablas a tenantizar
Las siguientes tablas DEBEN incluir tenant_id:
6.1 Catálogo y Stock
category
product
product_stock
Nota: uom (unidades de medida) se define como global (no tenantizada).

6.2 Ventas
sale
sale_line
stock_move
stock_move_line
finance_ledger

6.3 Compras / Boletas
supplier
purchase_invoice
purchase_invoice_line

6.4 Presupuestos
quote
quote_line

6.5 Extras del negocio
missing_product_request (productos faltantes)
cualquier tabla futura relacionada al negocio

6.6 Tablas NO tenantizadas (core SaaS)
tenant
app_user
user_tenant
uom

7. Reglas de unicidad por tenant
Las restricciones únicas pasan a ser por tenant, no globales.
Ejemplos:
SKU de producto
Antes: UNIQUE(sku)
Ahora: UNIQUE(tenant_id, sku)
Proveedores
UNIQUE(tenant_id, name)
Número de boleta
UNIQUE(tenant_id, supplier_id, invoice_number)
Presupuestos
UNIQUE(tenant_id, quote_number)
Esto evita colisiones entre negocios distintos.

8. Flujo del usuario (MVP)
8.1 Registro
Usuario accede a /register.
Completa:
Email
Contraseña
Nombre del negocio
El sistema:
Crea el tenant.
Crea el usuario.
Asocia el usuario al tenant como OWNER.
Inicia sesión automáticamente.
Redirige a /products (catálogo vacío).

8.2 Login
Usuario accede a /login.
Ingresa email + contraseña.
El sistema valida credenciales.
Se carga el tenant asociado en sesión.
Redirige a la aplicación.

8.3 Uso de la aplicación
Todas las pantallas requieren:
usuario autenticado
tenant activo en sesión
Si falta alguno:
redirección a login o selección de negocio.

9. Aislamiento y seguridad de datos
Reglas obligatorias:
Todas las queries incluyen tenant_id.
Todos los inserts setean tenant_id.
Acceder a un ID que no pertenece al tenant devuelve:
404 o acceso denegado.
No se confía en IDs enviados por el cliente.
Esto garantiza que:
Dos negocios puedan usar el sistema al mismo tiempo.
No haya fugas de información.

10. Checklist de aceptación del MVP SaaS
El MVP se considera completo cuando:
Se pueden crear al menos 2 negocios.
Cada negocio ve su sistema vacío al iniciar.
Los datos no se cruzan entre negocios.
El flujo registro → login → uso funciona sin intervención manual.
Las funcionalidades existentes siguen funcionando igual que antes, pero aisladas por tenant.

11. Resultado del Paso 1 (MVP definido)
Con este documento queda definido:
El alcance funcional exacto del MVP.
Qué tablas se tenantizan y cuáles no.
Cómo es el flujo de usuario.
Cómo se garantiza el aislamiento.
Qué queda fuera del MVP.
Este documento sirve como:
Base técnica del proyecto SaaS.
Documento de alineación para desarrollo.
