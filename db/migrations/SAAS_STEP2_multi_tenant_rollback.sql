-- =====================================================================
-- SAAS STEP 2 ROLLBACK: Revert Multi-Tenant Migration
-- =====================================================================
-- Purpose: Revert the multi-tenant changes back to single-tenant schema
-- WARNING: This will DROP all multi-tenant data except tenant_id=1
-- Use with EXTREME caution - data loss will occur for tenants other than default
-- =====================================================================

BEGIN;

-- =====================================================================
-- PART 1: REMOVE TENANT-SCOPED INDEXES
-- =====================================================================

-- Master data indexes
DROP INDEX IF EXISTS idx_uom_tenant_id;
DROP INDEX IF EXISTS idx_category_tenant_id;
DROP INDEX IF EXISTS idx_product_tenant_id;
DROP INDEX IF EXISTS idx_product_tenant_name;
DROP INDEX IF EXISTS idx_product_tenant_category;
DROP INDEX IF EXISTS idx_product_tenant_active;

-- Supplier indexes
DROP INDEX IF EXISTS idx_supplier_tenant_id;

-- Sales indexes
DROP INDEX IF EXISTS idx_sale_tenant_id;
DROP INDEX IF EXISTS idx_sale_tenant_datetime;
DROP INDEX IF EXISTS idx_sale_tenant_status;

-- Invoice indexes
DROP INDEX IF EXISTS idx_invoice_tenant_id;
DROP INDEX IF EXISTS idx_invoice_tenant_status;
DROP INDEX IF EXISTS idx_invoice_tenant_due_date;
DROP INDEX IF EXISTS idx_invoice_tenant_supplier_status;

-- Stock indexes
DROP INDEX IF EXISTS idx_stock_move_tenant_id;
DROP INDEX IF EXISTS idx_stock_move_tenant_date;

-- Finance ledger indexes
DROP INDEX IF EXISTS idx_ledger_tenant_id;
DROP INDEX IF EXISTS idx_ledger_tenant_datetime;
DROP INDEX IF EXISTS idx_ledger_tenant_type;

-- Missing products indexes
DROP INDEX IF EXISTS idx_missing_product_tenant_id;
DROP INDEX IF EXISTS idx_missing_product_tenant_status;

-- Quote indexes
DROP INDEX IF EXISTS idx_quote_tenant_id;
DROP INDEX IF EXISTS idx_quote_tenant_status_issued;
DROP INDEX IF EXISTS idx_quote_tenant_customer_name;

-- =====================================================================
-- PART 2: RESTORE GLOBAL UNIQUE CONSTRAINTS
-- =====================================================================

-- 1. uom: UNIQUE(tenant_id, name) -> UNIQUE(name)
DROP INDEX IF EXISTS uom_tenant_name_uniq;
ALTER TABLE uom ADD CONSTRAINT uom_name_key UNIQUE (name);

-- 2. category: UNIQUE(tenant_id, name) -> UNIQUE(name)
DROP INDEX IF EXISTS category_tenant_name_uniq;
ALTER TABLE category ADD CONSTRAINT category_name_key UNIQUE (name);

-- 3. product: UNIQUE(tenant_id, sku) -> UNIQUE(sku)
DROP INDEX IF EXISTS product_tenant_sku_uniq;
ALTER TABLE product ADD CONSTRAINT product_sku_key UNIQUE (sku);

-- 4. product: UNIQUE(tenant_id, barcode) -> UNIQUE(barcode)
DROP INDEX IF EXISTS product_tenant_barcode_uniq;
ALTER TABLE product ADD CONSTRAINT product_barcode_key UNIQUE (barcode);

-- 5. supplier: UNIQUE(tenant_id, name) -> UNIQUE(name)
DROP INDEX IF EXISTS supplier_tenant_name_uniq;
ALTER TABLE supplier ADD CONSTRAINT supplier_name_key UNIQUE (name);

-- 6. purchase_invoice: UNIQUE(tenant_id, supplier_id, invoice_number) 
--    -> UNIQUE(supplier_id, invoice_number)
DROP INDEX IF EXISTS purchase_invoice_tenant_supplier_number_uniq;
ALTER TABLE purchase_invoice 
    ADD CONSTRAINT supplier_invoice_number_uniq UNIQUE (supplier_id, invoice_number);

-- 7. missing_product_request: UNIQUE(tenant_id, normalized_name) -> UNIQUE(normalized_name)
DROP INDEX IF EXISTS missing_product_request_tenant_normalized_name_uniq;
ALTER TABLE missing_product_request 
    ADD CONSTRAINT missing_product_request_normalized_name_key UNIQUE (normalized_name);

-- 8. quote: UNIQUE(tenant_id, quote_number) -> UNIQUE(quote_number)
DROP INDEX IF EXISTS quote_tenant_quote_number_uniq;
ALTER TABLE quote ADD CONSTRAINT quote_quote_number_key UNIQUE (quote_number);

-- =====================================================================
-- PART 3: REMOVE tenant_id COLUMNS
-- =====================================================================
-- WARNING: Data for tenants other than tenant_id=1 will be lost

-- Before dropping, delete all data that's not from default tenant
-- (To preserve referential integrity)
DELETE FROM quote WHERE tenant_id != 1;
DELETE FROM missing_product_request WHERE tenant_id != 1;
DELETE FROM finance_ledger WHERE tenant_id != 1;
DELETE FROM stock_move WHERE tenant_id != 1;
DELETE FROM purchase_invoice WHERE tenant_id != 1;
DELETE FROM sale WHERE tenant_id != 1;
DELETE FROM supplier WHERE tenant_id != 1;
DELETE FROM product WHERE tenant_id != 1;
DELETE FROM category WHERE tenant_id != 1;
DELETE FROM uom WHERE tenant_id != 1;

-- Drop FK constraints first
ALTER TABLE uom DROP CONSTRAINT IF EXISTS fk_uom_tenant;
ALTER TABLE category DROP CONSTRAINT IF EXISTS fk_category_tenant;
ALTER TABLE product DROP CONSTRAINT IF EXISTS fk_product_tenant;
ALTER TABLE supplier DROP CONSTRAINT IF EXISTS fk_supplier_tenant;
ALTER TABLE sale DROP CONSTRAINT IF EXISTS fk_sale_tenant;
ALTER TABLE purchase_invoice DROP CONSTRAINT IF EXISTS fk_purchase_invoice_tenant;
ALTER TABLE stock_move DROP CONSTRAINT IF EXISTS fk_stock_move_tenant;
ALTER TABLE finance_ledger DROP CONSTRAINT IF EXISTS fk_finance_ledger_tenant;
ALTER TABLE missing_product_request DROP CONSTRAINT IF EXISTS fk_missing_product_request_tenant;
ALTER TABLE quote DROP CONSTRAINT IF EXISTS fk_quote_tenant;

-- Drop tenant_id columns
ALTER TABLE uom DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE category DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE product DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE supplier DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE sale DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE purchase_invoice DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE stock_move DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE finance_ledger DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE missing_product_request DROP COLUMN IF EXISTS tenant_id;
ALTER TABLE quote DROP COLUMN IF EXISTS tenant_id;

-- =====================================================================
-- PART 4: DROP SAAS CORE TABLES
-- =====================================================================

DROP TABLE IF EXISTS user_tenant CASCADE;
DROP TABLE IF EXISTS app_user CASCADE;
DROP TABLE IF EXISTS tenant CASCADE;

-- Drop triggers
DROP TRIGGER IF EXISTS tenant_set_updated_at ON tenant;
DROP TRIGGER IF EXISTS app_user_set_updated_at ON app_user;
DROP FUNCTION IF EXISTS trg_saas_set_updated_at();

COMMIT;

-- =====================================================================
-- ROLLBACK COMPLETE
-- =====================================================================
-- The database schema has been reverted to single-tenant mode.
-- All data from tenant_id=1 has been preserved.
-- All data from other tenants has been deleted.
-- =====================================================================
