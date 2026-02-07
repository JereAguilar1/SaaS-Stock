-- FIX: Relax Product Uniqueness Constraints
-- Purpose: Allow duplicate names and barcodes within a tenant, but keep SKU unique.
-- Reason: Users reported issues creating products with same names/barcodes.
-- Date: 2026-02-07

BEGIN;

-- =====================================================================
-- 1. REMOVE NAME UNIQUENESS
-- =====================================================================

-- Drop standard unique constraints if they exist
ALTER TABLE product DROP CONSTRAINT IF EXISTS product_name_key;
ALTER TABLE product DROP CONSTRAINT IF EXISTS product_tenant_id_name_key;

-- Drop unique indexes if they exist
DROP INDEX IF EXISTS product_name_key;
DROP INDEX IF EXISTS product_tenant_id_name_key;
-- Note: idx_product_tenant_name is NOT unique, so we keep it for performance

-- =====================================================================
-- 2. REMOVE BARCODE UNIQUENESS
-- =====================================================================

-- This was defined in 001_schema.sql as:
-- CREATE UNIQUE INDEX IF NOT EXISTS product_tenant_barcode_uniq
DROP INDEX IF EXISTS product_tenant_barcode_uniq;

-- Also try dropping standard constraints if they were created differently
ALTER TABLE product DROP CONSTRAINT IF EXISTS product_barcode_key;
ALTER TABLE product DROP CONSTRAINT IF EXISTS product_tenant_id_barcode_key;
DROP INDEX IF EXISTS product_barcode_key;

-- =====================================================================
-- 3. ENSURE SKU UNIQUENESS (Keep or Create)
-- =====================================================================

-- Remove any global SKU uniqueness (if it mistakenly exists)
ALTER TABLE product DROP CONSTRAINT IF EXISTS product_sku_key;
DROP INDEX IF EXISTS product_sku_key;

-- Ensure the correct tenant-scoped UNIQUE INDEX exists
-- (Matches 001_schema.sql definition)
CREATE UNIQUE INDEX IF NOT EXISTS product_tenant_sku_uniq 
    ON product(tenant_id, sku) WHERE sku IS NOT NULL;

COMMIT;
