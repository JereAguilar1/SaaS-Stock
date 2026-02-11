-- Migración: Agregar cliente por defecto "Consumidor Final"
-- Fecha: 2026-02-11
-- Descripción: Agrega columna is_default a customer y crea cliente por defecto para cada tenant

BEGIN;

-- Step 1: Add is_default column to customer table
ALTER TABLE customer
ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE;

-- Step 2: Create unique partial index: only ONE default customer per tenant
-- This prevents having multiple default customers for the same tenant
CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_tenant_default
ON customer(tenant_id) WHERE is_default = true;

-- Step 3: Create default customer "Consumidor Final" for each existing tenant
-- Only insert if the tenant doesn't already have a default customer
INSERT INTO customer (tenant_id, name, tax_id, email, phone, address, notes, active, is_default, created_at, updated_at)
SELECT 
    t.id,
    'Consumidor Final',
    NULL,
    NULL,
    NULL,
    NULL,
    'Cliente por defecto del sistema',
    true,
    true,  -- Mark as default
    now(),
    now()
FROM tenant t
WHERE NOT EXISTS (
    SELECT 1 
    FROM customer c 
    WHERE c.tenant_id = t.id 
    AND c.is_default = true
);

-- Step 4: Add index for performance on is_default queries
CREATE INDEX IF NOT EXISTS idx_customer_is_default 
ON customer(is_default) 
WHERE is_default = true;

COMMIT;

-- ROLLBACK Instructions (if needed):
-- BEGIN;
-- DROP INDEX IF EXISTS idx_customer_is_default;
-- DROP INDEX IF EXISTS idx_customer_tenant_default;
-- DELETE FROM customer WHERE is_default = true AND name = 'Consumidor Final';
-- ALTER TABLE customer DROP COLUMN IF EXISTS is_default;
-- COMMIT;
