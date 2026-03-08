-- =============================================================================
-- Migración: Agregar tenant_id, paid_at, notes a sale_payment
-- =============================================================================
-- Fecha: Marzo 2026
-- Descripción: Corrección de esquema para asegurar que sale_payment 
--              tenga las columnas correctas para reportes y aislamiento tenant.
-- =============================================================================

BEGIN;

-- 1. Agregar tenant_id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='sale_payment' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE sale_payment ADD COLUMN tenant_id BIGINT;
        
        -- Default to the tenant of the sale
        UPDATE sale_payment sp
        SET tenant_id = s.tenant_id
        FROM sale s
        WHERE sp.sale_id = s.id;
        
        ALTER TABLE sale_payment ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE sale_payment ADD CONSTRAINT sale_payment_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES tenant(id);
    END IF;
END $$;

-- 2. Agregar paid_at
ALTER TABLE sale_payment ADD COLUMN IF NOT EXISTS paid_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- 3. Agregar notes
ALTER TABLE sale_payment ADD COLUMN IF NOT EXISTS notes TEXT;

-- 4. Indice por tenant
CREATE INDEX IF NOT EXISTS idx_sale_payment_tenant ON sale_payment(tenant_id);

COMMIT;
