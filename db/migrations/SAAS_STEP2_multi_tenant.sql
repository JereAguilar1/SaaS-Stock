-- =====================================================================
-- SAAS STEP 2: Multi-Tenant Migration
-- =====================================================================
-- Purpose: Transform single-tenant schema to multi-tenant with tenant_id
-- Strategy: Add tenant tables, tenant_id columns, adjust uniques, add indexes
-- Author: SaaS Migration
-- Date: 2026-01-13
--
-- IMPORTANT: This migration is designed to run ONCE on an existing database.
-- It creates a default tenant and backfills all existing data to tenant_id=1.
-- =====================================================================

BEGIN;

-- =====================================================================
-- PART A: CREATE CORE SAAS TABLES
-- =====================================================================

-- Tenant table: represents each business/organization using the platform
CREATE TABLE IF NOT EXISTS tenant (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(80) NOT NULL UNIQUE,  -- URL-safe identifier (e.g., 'ferreteria-lopez')
    name VARCHAR(200) NOT NULL,  -- Display name
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_active ON tenant(active);
CREATE INDEX IF NOT EXISTS idx_tenant_slug ON tenant(slug);

-- App User table: platform users (email-based authentication)
CREATE TABLE IF NOT EXISTS app_user (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt/scrypt hash
    full_name VARCHAR(200),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_app_user_email ON app_user(email);
CREATE INDEX IF NOT EXISTS idx_app_user_active ON app_user(active);

-- User-Tenant relationship: many-to-many with role
CREATE TABLE IF NOT EXISTS user_tenant (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'STAFF',  -- OWNER, ADMIN, STAFF
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT chk_user_tenant_role CHECK (role IN ('OWNER', 'ADMIN', 'STAFF')),
    CONSTRAINT user_tenant_unique UNIQUE (user_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_user_tenant_user ON user_tenant(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tenant_tenant ON user_tenant(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_tenant_role ON user_tenant(role);

-- Auto-update triggers for updated_at
CREATE OR REPLACE FUNCTION trg_saas_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenant_set_updated_at ON tenant;
CREATE TRIGGER tenant_set_updated_at
    BEFORE UPDATE ON tenant
    FOR EACH ROW
    EXECUTE FUNCTION trg_saas_set_updated_at();

DROP TRIGGER IF EXISTS app_user_set_updated_at ON app_user;
CREATE TRIGGER app_user_set_updated_at
    BEFORE UPDATE ON app_user
    FOR EACH ROW
    EXECUTE FUNCTION trg_saas_set_updated_at();

-- =====================================================================
-- INSERT DEFAULT TENANT FOR BACKFILL COMPATIBILITY
-- =====================================================================
-- This ensures existing data can be migrated to tenant_id=1
INSERT INTO tenant (id, slug, name, active)
VALUES (1, 'default', 'Default Tenant', TRUE)
ON CONFLICT (id) DO NOTHING;

-- Reset sequence to avoid conflicts
SELECT setval('tenant_id_seq', (SELECT MAX(id) FROM tenant), true);

-- =====================================================================
-- PART B: ADD tenant_id TO ALL BUSINESS TABLES
-- =====================================================================
-- Strategy per table:
--   1) ADD COLUMN tenant_id BIGINT NULL
--   2) UPDATE SET tenant_id = 1 (backfill to default tenant)
--   3) ALTER COLUMN tenant_id SET NOT NULL
--   4) ADD FOREIGN KEY CONSTRAINT

-- ---------------------
-- 1. uom
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='uom' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE uom ADD COLUMN tenant_id BIGINT NULL;
        UPDATE uom SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE uom ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE uom ADD CONSTRAINT fk_uom_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 2. category
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='category' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE category ADD COLUMN tenant_id BIGINT NULL;
        UPDATE category SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE category ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE category ADD CONSTRAINT fk_category_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 3. product
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='product' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE product ADD COLUMN tenant_id BIGINT NULL;
        UPDATE product SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE product ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE product ADD CONSTRAINT fk_product_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 4. supplier
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='supplier' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE supplier ADD COLUMN tenant_id BIGINT NULL;
        UPDATE supplier SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE supplier ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE supplier ADD CONSTRAINT fk_supplier_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 5. sale
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='sale' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE sale ADD COLUMN tenant_id BIGINT NULL;
        UPDATE sale SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE sale ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE sale ADD CONSTRAINT fk_sale_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 6. purchase_invoice
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='purchase_invoice' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE purchase_invoice ADD COLUMN tenant_id BIGINT NULL;
        UPDATE purchase_invoice SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE purchase_invoice ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE purchase_invoice ADD CONSTRAINT fk_purchase_invoice_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 7. stock_move
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='stock_move' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE stock_move ADD COLUMN tenant_id BIGINT NULL;
        UPDATE stock_move SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE stock_move ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE stock_move ADD CONSTRAINT fk_stock_move_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 8. finance_ledger
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='finance_ledger' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE finance_ledger ADD COLUMN tenant_id BIGINT NULL;
        UPDATE finance_ledger SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE finance_ledger ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE finance_ledger ADD CONSTRAINT fk_finance_ledger_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 9. missing_product_request
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='missing_product_request' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE missing_product_request ADD COLUMN tenant_id BIGINT NULL;
        UPDATE missing_product_request SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE missing_product_request ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE missing_product_request ADD CONSTRAINT fk_missing_product_request_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- ---------------------
-- 10. quote
-- ---------------------
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='quote' AND column_name='tenant_id'
    ) THEN
        ALTER TABLE quote ADD COLUMN tenant_id BIGINT NULL;
        UPDATE quote SET tenant_id = 1 WHERE tenant_id IS NULL;
        ALTER TABLE quote ALTER COLUMN tenant_id SET NOT NULL;
        ALTER TABLE quote ADD CONSTRAINT fk_quote_tenant 
            FOREIGN KEY (tenant_id) REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT;
    END IF;
END $$;

-- Note: product_stock, sale_line, purchase_invoice_line, stock_move_line, quote_line
-- are child tables and inherit tenant_id via their parent relationships.
-- We don't add tenant_id to child tables to avoid denormalization complexity.

-- =====================================================================
-- PART C: ADJUST UNIQUE CONSTRAINTS TO BE TENANT-SCOPED
-- =====================================================================
-- Strategy: Drop global UNIQUE, create composite UNIQUE(tenant_id, field)

-- ---------------------
-- 1. uom: UNIQUE(name) -> UNIQUE(tenant_id, name)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'uom_name_key' AND conrelid = 'uom'::regclass
    ) THEN
        ALTER TABLE uom DROP CONSTRAINT uom_name_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uom_tenant_name_uniq ON uom(tenant_id, name);

-- ---------------------
-- 2. category: UNIQUE(name) -> UNIQUE(tenant_id, name)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'category_name_key' AND conrelid = 'category'::regclass
    ) THEN
        ALTER TABLE category DROP CONSTRAINT category_name_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS category_tenant_name_uniq ON category(tenant_id, name);

-- ---------------------
-- 3. product: UNIQUE(sku) -> UNIQUE(tenant_id, sku)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'product_sku_key' AND conrelid = 'product'::regclass
    ) THEN
        ALTER TABLE product DROP CONSTRAINT product_sku_key;
    END IF;
END $$;

-- Note: sku can be NULL, so we use partial unique index
CREATE UNIQUE INDEX IF NOT EXISTS product_tenant_sku_uniq 
    ON product(tenant_id, sku) WHERE sku IS NOT NULL;

-- ---------------------
-- 4. product: UNIQUE(barcode) -> UNIQUE(tenant_id, barcode)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'product_barcode_key' AND conrelid = 'product'::regclass
    ) THEN
        ALTER TABLE product DROP CONSTRAINT product_barcode_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS product_tenant_barcode_uniq 
    ON product(tenant_id, barcode) WHERE barcode IS NOT NULL;

-- ---------------------
-- 5. supplier: UNIQUE(name) -> UNIQUE(tenant_id, name)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'supplier_name_key' AND conrelid = 'supplier'::regclass
    ) THEN
        ALTER TABLE supplier DROP CONSTRAINT supplier_name_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS supplier_tenant_name_uniq ON supplier(tenant_id, name);

-- ---------------------
-- 6. purchase_invoice: UNIQUE(supplier_id, invoice_number) 
--    -> UNIQUE(tenant_id, supplier_id, invoice_number)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'supplier_invoice_number_uniq' AND conrelid = 'purchase_invoice'::regclass
    ) THEN
        ALTER TABLE purchase_invoice DROP CONSTRAINT supplier_invoice_number_uniq;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS purchase_invoice_tenant_supplier_number_uniq 
    ON purchase_invoice(tenant_id, supplier_id, invoice_number);

-- ---------------------
-- 7. missing_product_request: UNIQUE(normalized_name) -> UNIQUE(tenant_id, normalized_name)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'missing_product_request_normalized_name_key' 
        AND conrelid = 'missing_product_request'::regclass
    ) THEN
        ALTER TABLE missing_product_request DROP CONSTRAINT missing_product_request_normalized_name_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS missing_product_request_tenant_normalized_name_uniq 
    ON missing_product_request(tenant_id, normalized_name);

-- ---------------------
-- 8. quote: UNIQUE(quote_number) -> UNIQUE(tenant_id, quote_number)
-- ---------------------
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'quote_quote_number_key' AND conrelid = 'quote'::regclass
    ) THEN
        ALTER TABLE quote DROP CONSTRAINT quote_quote_number_key;
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS quote_tenant_quote_number_uniq 
    ON quote(tenant_id, quote_number);

-- Note: quote.sale_id UNIQUE remains global (sale_id is globally unique)
-- because a sale can only belong to one quote globally.

-- =====================================================================
-- PART D: CREATE TENANT-SCOPED PERFORMANCE INDEXES
-- =====================================================================
-- These indexes optimize tenant-scoped queries (WHERE tenant_id = X AND ...)

-- Master data indexes
CREATE INDEX IF NOT EXISTS idx_uom_tenant_id ON uom(tenant_id);
CREATE INDEX IF NOT EXISTS idx_category_tenant_id ON category(tenant_id);
CREATE INDEX IF NOT EXISTS idx_product_tenant_id ON product(tenant_id);
CREATE INDEX IF NOT EXISTS idx_product_tenant_name ON product(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_product_tenant_category ON product(tenant_id, category_id);
CREATE INDEX IF NOT EXISTS idx_product_tenant_active ON product(tenant_id, active);

-- Supplier indexes
CREATE INDEX IF NOT EXISTS idx_supplier_tenant_id ON supplier(tenant_id);

-- Sales indexes
CREATE INDEX IF NOT EXISTS idx_sale_tenant_id ON sale(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sale_tenant_datetime ON sale(tenant_id, datetime DESC);
CREATE INDEX IF NOT EXISTS idx_sale_tenant_status ON sale(tenant_id, status);

-- Invoice indexes
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_id ON purchase_invoice(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_status ON purchase_invoice(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_due_date ON purchase_invoice(tenant_id, due_date);
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_supplier_status 
    ON purchase_invoice(tenant_id, supplier_id, status);

-- Stock indexes
CREATE INDEX IF NOT EXISTS idx_stock_move_tenant_id ON stock_move(tenant_id);
CREATE INDEX IF NOT EXISTS idx_stock_move_tenant_date ON stock_move(tenant_id, date DESC);

-- Finance ledger indexes
CREATE INDEX IF NOT EXISTS idx_ledger_tenant_id ON finance_ledger(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ledger_tenant_datetime ON finance_ledger(tenant_id, datetime DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_tenant_type ON finance_ledger(tenant_id, type);

-- Missing products indexes
CREATE INDEX IF NOT EXISTS idx_missing_product_tenant_id ON missing_product_request(tenant_id);
CREATE INDEX IF NOT EXISTS idx_missing_product_tenant_status 
    ON missing_product_request(tenant_id, status);

-- Quote indexes
CREATE INDEX IF NOT EXISTS idx_quote_tenant_id ON quote(tenant_id);
CREATE INDEX IF NOT EXISTS idx_quote_tenant_status_issued 
    ON quote(tenant_id, status, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_quote_tenant_customer_name 
    ON quote(tenant_id, customer_name);

-- =====================================================================
-- VALIDATION QUERIES (Keep commented, run manually to verify)
-- =====================================================================

-- Check for NULL tenant_id in all tables (should return 0 for all)
/*
SELECT 'uom' AS table_name, COUNT(*) AS null_count FROM uom WHERE tenant_id IS NULL
UNION ALL
SELECT 'category', COUNT(*) FROM category WHERE tenant_id IS NULL
UNION ALL
SELECT 'product', COUNT(*) FROM product WHERE tenant_id IS NULL
UNION ALL
SELECT 'supplier', COUNT(*) FROM supplier WHERE tenant_id IS NULL
UNION ALL
SELECT 'sale', COUNT(*) FROM sale WHERE tenant_id IS NULL
UNION ALL
SELECT 'purchase_invoice', COUNT(*) FROM purchase_invoice WHERE tenant_id IS NULL
UNION ALL
SELECT 'stock_move', COUNT(*) FROM stock_move WHERE tenant_id IS NULL
UNION ALL
SELECT 'finance_ledger', COUNT(*) FROM finance_ledger WHERE tenant_id IS NULL
UNION ALL
SELECT 'missing_product_request', COUNT(*) FROM missing_product_request WHERE tenant_id IS NULL
UNION ALL
SELECT 'quote', COUNT(*) FROM quote WHERE tenant_id IS NULL;
*/

-- Verify unique constraints per tenant
/*
-- Example: Two tenants with same SKU should work
INSERT INTO tenant (slug, name) VALUES ('tenant2', 'Tenant 2');
INSERT INTO product (tenant_id, sku, name, uom_id, sale_price) 
VALUES (2, 'TEST-SKU', 'Test Product Tenant 2', 1, 100.00);
-- This should NOT conflict with tenant 1's 'TEST-SKU' if it exists
*/

-- View all tenant-scoped indexes
/*
SELECT schemaname, tablename, indexname
FROM pg_indexes
WHERE indexname LIKE '%tenant%'
ORDER BY tablename, indexname;
*/

-- View all tenant-scoped unique constraints
/*
SELECT conname, conrelid::regclass AS table_name
FROM pg_constraint
WHERE conname LIKE '%tenant%' AND contype = 'u'
ORDER BY conrelid::regclass::text;
*/

COMMIT;

-- =====================================================================
-- MIGRATION COMPLETE
-- =====================================================================
-- Next steps (STEP 3 - Application Layer):
-- 1. Update SQLAlchemy models to include tenant_id
-- 2. Implement authentication (login/logout)
-- 3. Add middleware for tenant selection via session
-- 4. Add require_login and require_tenant guards
-- 5. Update all queries to filter by tenant_id
-- 6. Update services to validate tenant_id and proper locking
-- =====================================================================
