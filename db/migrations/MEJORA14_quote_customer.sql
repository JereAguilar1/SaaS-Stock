-- ============================================================================
-- MEJORA 14: Datos de Cliente en Presupuestos
-- ============================================================================
-- Adds customer_name and customer_phone to quote table for basic customer tracking

BEGIN;

-- Add customer columns to quote table
ALTER TABLE quote
ADD COLUMN IF NOT EXISTS customer_name VARCHAR(255) NOT NULL DEFAULT '',
ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(50);

-- Remove default after adding column (for future rows)
ALTER TABLE quote ALTER COLUMN customer_name DROP DEFAULT;

-- Create indexes for efficient searching
CREATE INDEX IF NOT EXISTS idx_quote_customer_name ON quote(customer_name);
CREATE INDEX IF NOT EXISTS idx_quote_customer_phone ON quote(customer_phone);

-- Add comments
COMMENT ON COLUMN quote.customer_name IS 'Nombre del cliente (snapshot, no FK)';
COMMENT ON COLUMN quote.customer_phone IS 'Teléfono del cliente (opcional)';

COMMIT;
