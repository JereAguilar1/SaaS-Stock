import re
import os

INPUT_FILE = r'c:\jere\Saas Stock\stock_2026-01-23.sql'
OUTPUT_FILE = r'c:\jere\Saas Stock\inyeccion_datos.sql'

# Orden de inserción para respetar FKs
TABLE_ORDER = [
    'uom',
    'category',
    'supplier',
    'product',
    'product_stock',
    'product_uom_price', # Depende de product y uom
    'purchase_invoice', # Depende supplier
    'purchase_invoice_line', # Depende invoice, product
    'purchase_invoice_payment',
    'sale',
    'sale_line',
    'quote',
    'quote_line',
    'missing_product_request',
    'stock_move',
    # 'stock_move_line' ? Vi triggers pero no la tabla en el grep. Si existe, agregar.
    'finance_ledger'
]

def parse_value(val):
    if val == r'\N':
        return 'NULL'
    # Intentar detectar si es número
    if re.match(r'^-?\d+(\.\d+)?$', val):
        return val
    if val == 't': return 'true'
    if val == 'f': return 'false'
    # Es string, escapar comillas simples
    escaped = val.replace("'", "''")
    return f"'{escaped}'"

def main():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: No se encuentra {INPUT_FILE}")
        return

    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Header con creación de Tenant y Usuario
    header_sql = """
BEGIN;

-- 1. Crear tabla de variables temporal
CREATE TEMP TABLE _vars (
    tenant_id bigint,
    user_id bigint
);

-- 2. Crear Tenant si no existe
INSERT INTO tenant (slug, name, active, created_at, updated_at)
VALUES ('ferreteria-migrada', 'Ferretería Migrada', true, NOW(), NOW())
ON CONFLICT (slug) DO UPDATE SET updated_at = NOW();

-- 3. Guardar ID de Tenant
INSERT INTO _vars (tenant_id)
SELECT id FROM tenant WHERE slug = 'ferreteria-migrada';

-- 4. Crear Usuario Admin
-- Password "password123" hasheado con scrypt (ejemplo genérico, debería funcionar con passlib/werkzeug defaults)
-- Hash: scrypt:32768:8:1$k... (Usaremos un placeholder, el usuario debería cambiarlo o resetearlo)
-- Mejor: Usar un hash válido pre-generado.
-- Hash para 'password123': scrypt:32768:8:1$wi1e6l5213$c2c52df851f5012f2757262176d65377f33d793838ae617c06041164925762002cd18f2537330335eef6318991a0293108c488661706680470d069da5c04df45
INSERT INTO app_user (email, password_hash, full_name, active, auth_provider, email_verified, created_at, updated_at)
VALUES ('admin@migracion.com', 'scrypt:32768:8:1$wi1e6l5213$c2c52df851f5012f2757262176d65377f33d793838ae617c06041164925762002cd18f2537330335eef6318991a0293108c488661706680470d069da5c04df45', 'Admin Migración', true, 'local', true, NOW(), NOW())
ON CONFLICT (email) DO UPDATE SET active = true;

-- 5. Guardar ID de Usuario
UPDATE _vars SET user_id = (SELECT id FROM app_user WHERE email = 'admin@migracion.com');

-- 6. Asociar Usuario al Tenant (Owner)
INSERT INTO user_tenant (user_id, tenant_id, role, active, created_at)
SELECT user_id, tenant_id, 'OWNER', true, NOW()
FROM _vars
ON CONFLICT DO NOTHING; -- Asumiendo que existe restricción única, si no, se duplicará.

-- INICIO DE IMPORTACIÓN DE DATOS
"""

    # Encontrar bloques COPY
    # COPY public.table_name (col1, col2) FROM stdin;
    # data...
    # \.
    
    copy_pattern = re.compile(r'COPY public\.(\w+) \((.*?)\) FROM stdin;\n(.*?)\n\\\.', re.DOTALL)
    matches = copy_pattern.findall(content)
    
    tables_data = {} # {table_name: {'cols': [col1, col2], 'rows': [[val1, val2], ...]}}
    
    for table_name, columns_str, data_block in matches:
        columns = [c.strip() for c in columns_str.split(',')]
        rows = []
        for line in data_block.split('\n'):
            if not line: continue
            # Split por tabulador \t
            vals = line.split('\t')
            rows.append(vals)
        tables_data[table_name] = {'cols': columns, 'rows': rows}
        print(f"Parsed {table_name}: {len(rows)} rows")

    # Generar SQL ordenado
    sql_statements = []
    
    processed_tables = set()
    
    # Función helper para generar INSERTs
    def generate_inserts(t_name):
        if t_name not in tables_data:
            return
        
        t_data = tables_data[t_name]
        cols = t_data['cols']
        rows = t_data['rows']
        
        # Verificar si ya tiene tenant_id (raro, pero posible)
        if 'tenant_id' in cols:
            final_cols = cols
            has_tenant = True
        else:
            final_cols = ['tenant_id'] + cols
            has_tenant = False
            
        cols_str = ', '.join(final_cols)
        
        # Generar bloques de INSERT (batching opcional, aquí todo en uno o varios)
        sql_statements.append(f"\n-- Data for {t_name}")
        
        for row in rows:
            values = []
            if not has_tenant:
                values.append("(SELECT tenant_id FROM _vars)")
            
            # Mapear valores de la fila
            if len(row) != len(cols):
                print(f"Warning: Row length mismatch in {t_name}")
                continue
                
            for v in row:
                values.append(parse_value(v))
            
            vals_str = ", ".join(values)
            sql_statements.append(f"INSERT INTO {t_name} ({cols_str}) VALUES ({vals_str});")
        
        processed_tables.add(t_name)

    # 1. Procesar orden explícito
    for t in TABLE_ORDER:
        generate_inserts(t)
        
    # 2. Procesar resto
    for t in tables_data:
        if t not in processed_tables:
            generate_inserts(t)

    # 3. Ajustar secuencias (setval)
    # Buscar ids máximos en los datos insertados y actualizar secuencias
    sql_statements.append("\n-- Actualizar secuencias")
    for t in tables_data:
        # Asumimos convención tabla_id_seq
        if 'id' in tables_data[t]['cols']:
            seq_name = f"{t}_id_seq"
            sql_statements.append(f"SELECT setval('{seq_name}', (SELECT MAX(id) FROM {t}), true);")

    footer_sql = """
COMMIT;
-- Fin de inyección
"""

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(header_sql)
        f.write('\n'.join(sql_statements))
        f.write(footer_sql)

    print(f"Generado {OUTPUT_FILE} con éxito.")

if __name__ == '__main__':
    main()
