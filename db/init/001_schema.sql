-- PostgreSQL DDL for SaaS Comercial Multi-Tenant
-- Target: PostgreSQL 13+ (recommended 14+)
-- Architecture: Multi-tenant with tenant_id column separation
-- Notes:
-- 1) All business tables include tenant_id for data isolation
-- 2) reference_type/reference_id are "polymorphic" references (no FK)
-- 3) SALE must have >=1 line, PURCHASE_INVOICE must have >=1 line,
--    and totals must match sum(lines) via DEFERRABLE constraint triggers
-- 4) product_stock is maintained automatically from stock_move + stock_move_line via triggers
-- 5) Unique constraints are scoped per tenant (tenant_id + field)

BEGIN;

-- Optional (recommended) for better product search:
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =========================
-- SAAS CORE TABLES
-- =========================

-- Tenant: represents each business/organization
CREATE TABLE IF NOT EXISTS tenant (
    id BIGSERIAL PRIMARY KEY,
    slug VARCHAR(80) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    is_suspended BOOLEAN NOT NULL DEFAULT FALSE, -- Added in ADMIN_PANEL_V1
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tenant_active ON tenant(active);
CREATE INDEX IF NOT EXISTS idx_tenant_slug ON tenant(slug);
CREATE INDEX IF NOT EXISTS idx_tenant_is_suspended ON tenant(is_suspended);

-- Admin Users: Global platform administrators (isolated from tenants)
CREATE TABLE IF NOT EXISTS admin_users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login TIMESTAMPTZ NULL
);

CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);

-- Tenant Subscriptions: Plans and status for each tenant
CREATE TABLE IF NOT EXISTS tenant_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    plan_type VARCHAR(20) NOT NULL CHECK (plan_type IN ('free', 'basic', 'pro')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('trial', 'active', 'past_due', 'canceled')),
    trial_ends_at TIMESTAMPTZ,
    current_period_end TIMESTAMPTZ,
    amount NUMERIC(10, 2) DEFAULT 0.00,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON tenant_subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON tenant_subscriptions(status);

-- Tenant Payments: Manual payment records registered by admins
CREATE TABLE IF NOT EXISTS tenant_payments (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    amount NUMERIC(10, 2) NOT NULL,
    payment_date DATE NOT NULL,
    reference VARCHAR(255),
    notes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'paid' CHECK (status IN ('pending', 'paid')),
    created_by BIGINT REFERENCES admin_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_payments_tenant ON tenant_payments(tenant_id);

-- Admin Audit Logs: Tracks sensitive admin actions
CREATE TABLE IF NOT EXISTS admin_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    admin_user_id BIGINT NOT NULL REFERENCES admin_users(id),
    action VARCHAR(100) NOT NULL,
    target_tenant_id BIGINT REFERENCES tenant(id),
    details JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_admin_audit_admin ON admin_audit_logs(admin_user_id);
CREATE INDEX IF NOT EXISTS idx_admin_audit_tenant ON admin_audit_logs(target_tenant_id);

-- App User: platform users (email-based authentication)
CREATE TABLE IF NOT EXISTS app_user (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255), -- Nullable for OAuth users
    full_name VARCHAR(200),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- OAuth fields
    google_sub VARCHAR(255),
    auth_provider VARCHAR(20) NOT NULL DEFAULT 'local',
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT chk_auth_provider CHECK (auth_provider IN ('local', 'google')),
    CONSTRAINT chk_local_has_password CHECK (
        (auth_provider = 'local' AND password_hash IS NOT NULL) OR
        (auth_provider != 'local')
    )
);

CREATE INDEX IF NOT EXISTS idx_app_user_email ON app_user(email);
CREATE INDEX IF NOT EXISTS idx_app_user_active ON app_user(active);
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_user_google_sub ON app_user(google_sub) WHERE google_sub IS NOT NULL;

-- User-Tenant: many-to-many relationship with role
CREATE TABLE IF NOT EXISTS user_tenant (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL DEFAULT 'STAFF',
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT chk_user_tenant_role CHECK (role IN ('OWNER', 'ADMIN', 'STAFF')),
    CONSTRAINT user_tenant_unique UNIQUE (user_id, tenant_id)
);

CREATE INDEX IF NOT EXISTS idx_user_tenant_user ON user_tenant(user_id);
CREATE INDEX IF NOT EXISTS idx_user_tenant_tenant ON user_tenant(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_tenant_role ON user_tenant(role);

-- Audit Log: tracks critical user actions (tenant level)
CREATE TABLE IF NOT EXISTS audit_log (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id BIGINT,
    details TEXT,  -- JSON or text
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created ON audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- =========================
-- ENUM TYPES
-- =========================
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sale_status') THEN
    CREATE TYPE sale_status AS ENUM ('CONFIRMED', 'CANCELLED');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'invoice_status') THEN
    CREATE TYPE invoice_status AS ENUM ('PENDING', 'PARTIALLY_PAID', 'PAID');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stock_move_type') THEN
    CREATE TYPE stock_move_type AS ENUM ('IN', 'OUT', 'ADJUST');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'stock_ref_type') THEN
    CREATE TYPE stock_ref_type AS ENUM ('SALE', 'INVOICE', 'MANUAL');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ledger_type') THEN
    CREATE TYPE ledger_type AS ENUM ('INCOME', 'EXPENSE');
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ledger_ref_type') THEN
    CREATE TYPE ledger_ref_type AS ENUM ('SALE', 'INVOICE_PAYMENT', 'MANUAL');
  END IF;
END$$;

-- =========================
-- MASTER DATA (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS uom (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  name        VARCHAR(80)  NOT NULL,
  symbol      VARCHAR(16)  NOT NULL,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_uom_tenant_id ON uom(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS uom_tenant_name_uniq ON uom(tenant_id, name);

CREATE TABLE IF NOT EXISTS category (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  name        VARCHAR(120) NOT NULL,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_category_tenant_id ON category(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS category_tenant_name_uniq ON category(tenant_id, name);

CREATE TABLE IF NOT EXISTS product (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  sku         VARCHAR(64),
  barcode     VARCHAR(64),
  name        VARCHAR(200) NOT NULL,
  category_id BIGINT REFERENCES category(id) ON UPDATE RESTRICT ON DELETE SET NULL,
  uom_id      BIGINT NOT NULL REFERENCES uom(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  active      BOOLEAN NOT NULL DEFAULT TRUE,
  sale_price  NUMERIC(12,2) NOT NULL CHECK (sale_price >= 0),
  cost        NUMERIC(10,2) NOT NULL DEFAULT 0.00 CHECK (cost >= 0),
  image_path  VARCHAR(255),
  image_original_path VARCHAR(255),
  min_stock_qty INTEGER NOT NULL DEFAULT 0 CHECK (min_stock_qty >= 0),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_product_tenant_id ON product(tenant_id);
CREATE INDEX IF NOT EXISTS idx_product_tenant_name ON product(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_product_tenant_category ON product(tenant_id, category_id);
CREATE INDEX IF NOT EXISTS idx_product_tenant_active ON product(tenant_id, active);
CREATE INDEX IF NOT EXISTS idx_product_category ON product(category_id);
CREATE INDEX IF NOT EXISTS idx_product_uom ON product(uom_id);
CREATE INDEX IF NOT EXISTS idx_product_active ON product(active);
CREATE INDEX IF NOT EXISTS idx_product_name ON product(name);
CREATE INDEX IF NOT EXISTS idx_product_min_stock_qty ON product(min_stock_qty);

-- Tenant-scoped unique constraints (NULL values allowed)
CREATE UNIQUE INDEX IF NOT EXISTS product_tenant_sku_uniq 
    ON product(tenant_id, sku) WHERE sku IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS product_tenant_barcode_uniq 
    ON product(tenant_id, barcode) WHERE barcode IS NOT NULL;

-- Stock current snapshot (fast reads)
CREATE TABLE IF NOT EXISTS product_stock (
  product_id  BIGINT PRIMARY KEY REFERENCES product(id) ON UPDATE RESTRICT ON DELETE CASCADE,
  on_hand_qty NUMERIC(12,3) NOT NULL DEFAULT 0 CHECK (on_hand_qty >= 0),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Auto-create product_stock row on product creation
CREATE OR REPLACE FUNCTION trg_product_init_stock()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO product_stock(product_id, on_hand_qty)
  VALUES (NEW.id, 0)
  ON CONFLICT (product_id) DO NOTHING;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS product_init_stock ON product;
CREATE TRIGGER product_init_stock
AFTER INSERT ON product
FOR EACH ROW
EXECUTE FUNCTION trg_product_init_stock();

-- =========================
-- SALES (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS sale (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  datetime    TIMESTAMPTZ NOT NULL DEFAULT now(),
  total       NUMERIC(12,2) NOT NULL CHECK (total >= 0),
  status      sale_status NOT NULL DEFAULT 'CONFIRMED',
  idempotency_key VARCHAR(64) UNIQUE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sale_idempotency ON sale(idempotency_key) WHERE idempotency_key IS NOT NULL;


CREATE INDEX IF NOT EXISTS idx_sale_tenant_id ON sale(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sale_tenant_datetime ON sale(tenant_id, datetime DESC);
CREATE INDEX IF NOT EXISTS idx_sale_tenant_status ON sale(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_sale_datetime ON sale(datetime DESC);
CREATE INDEX IF NOT EXISTS idx_sale_status ON sale(status);

CREATE TABLE IF NOT EXISTS sale_line (
  id          BIGSERIAL PRIMARY KEY,
  sale_id     BIGINT NOT NULL REFERENCES sale(id) ON UPDATE RESTRICT ON DELETE CASCADE,
  product_id  BIGINT NOT NULL REFERENCES product(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  qty         NUMERIC(12,3) NOT NULL CHECK (qty > 0),
  unit_price  NUMERIC(12,2) NOT NULL CHECK (unit_price >= 0),
  line_total  NUMERIC(12,2) NOT NULL CHECK (line_total >= 0),
  CONSTRAINT sale_line_total_consistency CHECK (line_total = round(qty * unit_price, 2))
);

CREATE INDEX IF NOT EXISTS idx_sale_line_sale ON sale_line(sale_id);
CREATE INDEX IF NOT EXISTS idx_sale_line_product ON sale_line(product_id);

-- Mixed payment methods per sale
CREATE TABLE IF NOT EXISTS sale_payment (
    id BIGSERIAL PRIMARY KEY,
    sale_id BIGINT NOT NULL REFERENCES sale(id) ON DELETE CASCADE,
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('CASH', 'TRANSFER', 'CARD')),
    amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    
    -- Only for CASH payments
    amount_received NUMERIC(10, 2) CHECK (amount_received IS NULL OR amount_received >= amount),
    change_amount NUMERIC(10, 2) CHECK (change_amount IS NULL OR change_amount >= 0)
);

CREATE INDEX IF NOT EXISTS idx_sale_payment_sale ON sale_payment(sale_id);

-- Persistent cart for POS
CREATE TABLE IF NOT EXISTS sale_draft (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    
    -- Global discount (applied to entire cart)
    discount_type VARCHAR(10) CHECK (discount_type IN ('PERCENT', 'AMOUNT') OR discount_type IS NULL),
    discount_value NUMERIC(10, 2) DEFAULT 0 CHECK (discount_value >= 0),
    
    UNIQUE(tenant_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_sale_draft_tenant_user ON sale_draft(tenant_id, user_id);
CREATE INDEX IF NOT EXISTS idx_sale_draft_user ON sale_draft(user_id);

-- Individual items in the persistent cart
CREATE TABLE IF NOT EXISTS sale_draft_line (
    id BIGSERIAL PRIMARY KEY,
    draft_id BIGINT NOT NULL REFERENCES sale_draft(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    qty NUMERIC(10, 2) NOT NULL CHECK (qty > 0),
    
    -- Item-level discount (applied to this line only)
    discount_type VARCHAR(10) CHECK (discount_type IN ('PERCENT', 'AMOUNT') OR discount_type IS NULL),
    discount_value NUMERIC(10, 2) DEFAULT 0 CHECK (discount_value >= 0),
    
    UNIQUE(draft_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_sale_draft_line_draft ON sale_draft_line(draft_id);
CREATE INDEX IF NOT EXISTS idx_sale_draft_line_product ON sale_draft_line(product_id);


-- =========================
-- SUPPLIERS + INVOICES (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS supplier (
  id          BIGSERIAL PRIMARY KEY,
  tenant_id   BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  name        VARCHAR(200) NOT NULL,
  tax_id      VARCHAR(64),
  phone       VARCHAR(64),
  email       VARCHAR(200),
  notes       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_supplier_tenant_id ON supplier(tenant_id);
CREATE UNIQUE INDEX IF NOT EXISTS supplier_tenant_name_uniq ON supplier(tenant_id, name);

CREATE TABLE IF NOT EXISTS purchase_invoice (
  id            BIGSERIAL PRIMARY KEY,
  tenant_id     BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  supplier_id   BIGINT NOT NULL REFERENCES supplier(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  invoice_number VARCHAR(80) NOT NULL,
  invoice_date  DATE NOT NULL,
  due_date      DATE,
  total_amount  NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
  paid_amount   NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0),
  status        invoice_status NOT NULL DEFAULT 'PENDING',
  paid_at       DATE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT invoice_paid_at_consistency CHECK (
    (status = 'PAID' AND paid_at IS NOT NULL) OR
    (status != 'PAID')
  )
);

CREATE INDEX IF NOT EXISTS idx_invoice_tenant_id ON purchase_invoice(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_status ON purchase_invoice(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_due_date ON purchase_invoice(tenant_id, due_date);
CREATE INDEX IF NOT EXISTS idx_invoice_tenant_supplier_status 
    ON purchase_invoice(tenant_id, supplier_id, status);
CREATE INDEX IF NOT EXISTS idx_invoice_supplier ON purchase_invoice(supplier_id);
CREATE INDEX IF NOT EXISTS idx_invoice_status ON purchase_invoice(status);
CREATE INDEX IF NOT EXISTS idx_invoice_due_date ON purchase_invoice(due_date);
CREATE INDEX IF NOT EXISTS idx_invoice_date ON purchase_invoice(invoice_date);

-- Tenant-scoped unique for invoice number per supplier
CREATE UNIQUE INDEX IF NOT EXISTS purchase_invoice_tenant_supplier_number_uniq 
    ON purchase_invoice(tenant_id, supplier_id, invoice_number);

-- Fast "debt" queries per tenant
CREATE INDEX IF NOT EXISTS idx_invoice_pending_supplier
  ON purchase_invoice(supplier_id)
  WHERE status IN ('PENDING', 'PARTIALLY_PAID');

CREATE TABLE IF NOT EXISTS purchase_invoice_payment (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    invoice_id BIGINT NOT NULL REFERENCES purchase_invoice(id) ON DELETE CASCADE,
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('CASH', 'TRANSFER', 'CARD')),
    amount NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    paid_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by BIGINT REFERENCES app_user(id)
);

CREATE INDEX IF NOT EXISTS idx_invoice_payment_tenant ON purchase_invoice_payment(tenant_id);
CREATE INDEX IF NOT EXISTS idx_invoice_payment_invoice ON purchase_invoice_payment(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_payment_date ON purchase_invoice_payment(paid_at DESC);

CREATE TABLE IF NOT EXISTS purchase_invoice_line (
  id          BIGSERIAL PRIMARY KEY,
  invoice_id  BIGINT NOT NULL REFERENCES purchase_invoice(id) ON UPDATE RESTRICT ON DELETE CASCADE,
  product_id  BIGINT NOT NULL REFERENCES product(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  qty         NUMERIC(12,3) NOT NULL CHECK (qty > 0),
  unit_cost   NUMERIC(12,4) NOT NULL CHECK (unit_cost >= 0),
  line_total  NUMERIC(12,2) NOT NULL CHECK (line_total >= 0),
  CONSTRAINT invoice_line_total_consistency CHECK (line_total = round(qty * unit_cost, 2))
);

CREATE INDEX IF NOT EXISTS idx_invoice_line_invoice ON purchase_invoice_line(invoice_id);
CREATE INDEX IF NOT EXISTS idx_invoice_line_product ON purchase_invoice_line(product_id);

-- =========================
-- STOCK MOVES (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS stock_move (
  id             BIGSERIAL PRIMARY KEY,
  tenant_id      BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  date           TIMESTAMPTZ NOT NULL DEFAULT now(),
  type           stock_move_type NOT NULL,
  reference_type stock_ref_type NOT NULL,
  reference_id   BIGINT,
  notes          TEXT
);

CREATE INDEX IF NOT EXISTS idx_stock_move_tenant_id ON stock_move(tenant_id);
CREATE INDEX IF NOT EXISTS idx_stock_move_tenant_date ON stock_move(tenant_id, date DESC);
CREATE INDEX IF NOT EXISTS idx_stock_move_date ON stock_move(date DESC);
CREATE INDEX IF NOT EXISTS idx_stock_move_ref ON stock_move(reference_type, reference_id);

CREATE TABLE IF NOT EXISTS stock_move_line (
  id            BIGSERIAL PRIMARY KEY,
  stock_move_id BIGINT NOT NULL REFERENCES stock_move(id) ON UPDATE RESTRICT ON DELETE CASCADE,
  product_id    BIGINT NOT NULL REFERENCES product(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  qty           NUMERIC(12,3) NOT NULL CHECK (qty != 0),
  uom_id        BIGINT NOT NULL REFERENCES uom(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  unit_cost     NUMERIC(12,4) CHECK (unit_cost >= 0)
);

CREATE INDEX IF NOT EXISTS idx_stock_move_line_move ON stock_move_line(stock_move_id);
CREATE INDEX IF NOT EXISTS idx_stock_move_line_prod ON stock_move_line(product_id);

-- =========================
-- FINANCE LEDGER (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS finance_ledger (
  id             BIGSERIAL PRIMARY KEY,
  tenant_id      BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
  datetime       TIMESTAMPTZ NOT NULL DEFAULT now(),
  type           ledger_type NOT NULL,
  amount         NUMERIC(12,2) NOT NULL CHECK (amount >= 0),
  category       VARCHAR(80),
  reference_type ledger_ref_type NOT NULL,
  reference_id   BIGINT,
  notes          TEXT,
  payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH',
  
  CONSTRAINT chk_finance_ledger_payment_method CHECK (payment_method IN ('CASH', 'TRANSFER', 'CARD'))
);

CREATE INDEX IF NOT EXISTS idx_finance_ledger_payment_method ON finance_ledger(payment_method);

CREATE INDEX IF NOT EXISTS idx_ledger_tenant_id ON finance_ledger(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ledger_tenant_datetime ON finance_ledger(tenant_id, datetime DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_tenant_type ON finance_ledger(tenant_id, type);
CREATE INDEX IF NOT EXISTS idx_ledger_datetime ON finance_ledger(datetime DESC);
CREATE INDEX IF NOT EXISTS idx_ledger_type ON finance_ledger(type);
CREATE INDEX IF NOT EXISTS idx_ledger_ref ON finance_ledger(reference_type, reference_id);

-- =========================
-- MISSING PRODUCT REQUESTS (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS missing_product_request (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL,
    request_count INTEGER NOT NULL DEFAULT 1 CHECK (request_count >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_missing_product_tenant_id ON missing_product_request(tenant_id);
CREATE INDEX IF NOT EXISTS idx_missing_product_tenant_status 
    ON missing_product_request(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_missing_product_status ON missing_product_request(status);
CREATE INDEX IF NOT EXISTS idx_missing_product_count_desc ON missing_product_request(request_count DESC);
CREATE INDEX IF NOT EXISTS idx_missing_product_last_requested_at ON missing_product_request(last_requested_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS missing_product_request_tenant_normalized_name_uniq 
    ON missing_product_request(tenant_id, normalized_name);

-- =========================
-- QUOTES (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS quote (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    quote_number VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until DATE,
    notes TEXT,
    payment_method VARCHAR(20),
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    sale_id BIGINT UNIQUE REFERENCES sale(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT chk_quote_status CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'CANCELED')),
    CONSTRAINT chk_quote_payment_method CHECK (payment_method IS NULL OR payment_method IN ('CASH', 'TRANSFER')),
    CONSTRAINT chk_quote_accepted_has_sale CHECK (
        (status = 'ACCEPTED' AND sale_id IS NOT NULL) OR 
        (status != 'ACCEPTED')
    )
);

CREATE INDEX IF NOT EXISTS idx_quote_tenant_id ON quote(tenant_id);
CREATE INDEX IF NOT EXISTS idx_quote_tenant_status_issued 
    ON quote(tenant_id, status, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_quote_tenant_customer_name 
    ON quote(tenant_id, customer_name);
CREATE INDEX IF NOT EXISTS idx_quote_number ON quote(quote_number);
CREATE INDEX IF NOT EXISTS idx_quote_status_issued ON quote(status, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_quote_sale_id ON quote(sale_id);
CREATE INDEX IF NOT EXISTS idx_quote_valid_until ON quote(valid_until);
CREATE INDEX IF NOT EXISTS idx_quote_customer_name ON quote(customer_name);
CREATE INDEX IF NOT EXISTS idx_quote_customer_phone ON quote(customer_phone);

CREATE UNIQUE INDEX IF NOT EXISTS quote_tenant_quote_number_uniq 
    ON quote(tenant_id, quote_number);

CREATE TABLE IF NOT EXISTS quote_line (
    id BIGSERIAL PRIMARY KEY,
    quote_id BIGINT NOT NULL REFERENCES quote(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    product_name_snapshot VARCHAR(200) NOT NULL,
    uom_snapshot VARCHAR(16),
    qty NUMERIC(12,3) NOT NULL CHECK (qty > 0),
    unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(14,2) NOT NULL CHECK (line_total >= 0),
    
    CONSTRAINT chk_quote_line_total_consistency CHECK (line_total = round(qty * unit_price, 2))
);

CREATE INDEX IF NOT EXISTS idx_quote_line_quote_id ON quote_line(quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_line_product_id ON quote_line(product_id);

-- =========================
-- CONSTRAINT TRIGGERS (DEFERRABLE)
-- =========================

-- Helper: sale must have >=1 line
CREATE OR REPLACE FUNCTION chk_sale_has_lines()
RETURNS TRIGGER AS $$
DECLARE
  v_count BIGINT;
BEGIN
  SELECT COUNT(*) INTO v_count FROM sale_line WHERE sale_id = NEW.id;
  IF v_count < 1 THEN
    RAISE EXCEPTION 'SALE % must have at least one sale_line', NEW.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Helper: sale.total must match sum(line_total)
CREATE OR REPLACE FUNCTION chk_sale_total_matches_lines()
RETURNS TRIGGER AS $$
DECLARE
  v_sum NUMERIC(12,2);
BEGIN
  SELECT COALESCE(SUM(line_total), 0) INTO v_sum FROM sale_line WHERE sale_id = NEW.id;
  IF NEW.total <> v_sum THEN
    RAISE EXCEPTION 'SALE % total (%) does not match sum(lines) (%)', NEW.id, NEW.total, v_sum;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Helper: invoice must have >=1 line
CREATE OR REPLACE FUNCTION chk_invoice_has_lines()
RETURNS TRIGGER AS $$
DECLARE
  v_count BIGINT;
BEGIN
  SELECT COUNT(*) INTO v_count FROM purchase_invoice_line WHERE invoice_id = NEW.id;
  IF v_count < 1 THEN
    RAISE EXCEPTION 'INVOICE % must have at least one purchase_invoice_line', NEW.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Helper: invoice.total_amount must match sum(line_total)
CREATE OR REPLACE FUNCTION chk_invoice_total_matches_lines()
RETURNS TRIGGER AS $$
DECLARE
  v_sum NUMERIC(12,2);
BEGIN
  SELECT COALESCE(SUM(line_total), 0) INTO v_sum FROM purchase_invoice_line WHERE invoice_id = NEW.id;
  IF NEW.total_amount <> v_sum THEN
    RAISE EXCEPTION 'INVOICE % total_amount (%) does not match sum(lines) (%)', NEW.id, NEW.total_amount, v_sum;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- DEFERRABLE constraint triggers
DROP TRIGGER IF EXISTS trg_sale_has_lines ON sale;
CREATE CONSTRAINT TRIGGER trg_sale_has_lines
AFTER INSERT OR UPDATE ON sale
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION chk_sale_has_lines();

DROP TRIGGER IF EXISTS trg_sale_total_matches_lines ON sale;
CREATE CONSTRAINT TRIGGER trg_sale_total_matches_lines
AFTER INSERT OR UPDATE ON sale
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION chk_sale_total_matches_lines();

DROP TRIGGER IF EXISTS trg_invoice_has_lines ON purchase_invoice;
CREATE CONSTRAINT TRIGGER trg_invoice_has_lines
AFTER INSERT OR UPDATE ON purchase_invoice
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION chk_invoice_has_lines();

DROP TRIGGER IF EXISTS trg_invoice_total_matches_lines ON purchase_invoice;
CREATE CONSTRAINT TRIGGER trg_invoice_total_matches_lines
AFTER INSERT OR UPDATE ON purchase_invoice
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION chk_invoice_total_matches_lines();

-- =========================
-- STOCK SNAPSHOT MAINTENANCE
-- =========================
CREATE OR REPLACE FUNCTION apply_stock_delta(p_product_id BIGINT, p_delta NUMERIC)
RETURNS VOID AS $$
BEGIN
  INSERT INTO product_stock(product_id, on_hand_qty, updated_at)
  VALUES (p_product_id, GREATEST(p_delta, 0), now())
  ON CONFLICT (product_id) DO UPDATE
    SET on_hand_qty = product_stock.on_hand_qty + EXCLUDED.on_hand_qty,
        updated_at  = now();

  IF p_delta < 0 THEN
    UPDATE product_stock
      SET on_hand_qty = on_hand_qty + p_delta,
          updated_at  = now()
    WHERE product_id = p_product_id;

    IF (SELECT on_hand_qty FROM product_stock WHERE product_id = p_product_id) < 0 THEN
      RAISE EXCEPTION 'Stock would become negative for product_id %', p_product_id;
    END IF;
  END IF;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_stock_move_line_after_ins()
RETURNS TRIGGER AS $$
DECLARE
  v_type stock_move_type;
  v_delta NUMERIC(12,3);
BEGIN
  SELECT type INTO v_type FROM stock_move WHERE id = NEW.stock_move_id;

  IF v_type = 'IN' THEN
    v_delta := NEW.qty;
  ELSIF v_type = 'OUT' THEN
    v_delta := -NEW.qty;
  ELSE
    v_delta := NEW.qty;
  END IF;

  PERFORM apply_stock_delta(NEW.product_id, v_delta);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_stock_move_line_after_del()
RETURNS TRIGGER AS $$
DECLARE
  v_type stock_move_type;
  v_delta NUMERIC(12,3);
BEGIN
  SELECT type INTO v_type FROM stock_move WHERE id = OLD.stock_move_id;

  IF v_type = 'IN' THEN
    v_delta := -OLD.qty;
  ELSIF v_type = 'OUT' THEN
    v_delta := OLD.qty;
  ELSE
    v_delta := -OLD.qty;
  END IF;

  PERFORM apply_stock_delta(OLD.product_id, v_delta);
  RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS stock_move_line_after_ins ON stock_move_line;
CREATE TRIGGER stock_move_line_after_ins
AFTER INSERT ON stock_move_line
FOR EACH ROW
EXECUTE FUNCTION trg_stock_move_line_after_ins();

DROP TRIGGER IF EXISTS stock_move_line_after_del ON stock_move_line;
CREATE TRIGGER stock_move_line_after_del
AFTER DELETE ON stock_move_line
FOR EACH ROW
EXECUTE FUNCTION trg_stock_move_line_after_del();

-- =========================
-- UPDATED_AT TRIGGERS
-- =========================
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION trg_saas_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS product_set_updated_at ON product;
CREATE TRIGGER product_set_updated_at
BEFORE UPDATE ON product
FOR EACH ROW
EXECUTE FUNCTION trg_set_updated_at();

DROP TRIGGER IF EXISTS missing_product_set_updated_at ON missing_product_request;
CREATE TRIGGER missing_product_set_updated_at
    BEFORE UPDATE ON missing_product_request
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

DROP TRIGGER IF EXISTS quote_set_updated_at ON quote;
CREATE TRIGGER quote_set_updated_at
    BEFORE UPDATE ON quote
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

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

-- =========================
-- CUSTOMERS (MULTI-TENANT)
-- =========================
CREATE TABLE IF NOT EXISTS customer (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    tax_id VARCHAR(50),
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    notes TEXT,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_customer_tenant_id ON customer(tenant_id);
CREATE INDEX IF NOT EXISTS idx_customer_search ON customer(tenant_id, name);
CREATE INDEX IF NOT EXISTS idx_customer_is_default ON customer(is_default) WHERE is_default = true;
CREATE UNIQUE INDEX IF NOT EXISTS idx_customer_tenant_default 
    ON customer(tenant_id) WHERE is_default = true;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS customer_set_updated_at ON customer;
CREATE TRIGGER customer_set_updated_at
    BEFORE UPDATE ON customer
    FOR EACH ROW
    EXECUTE FUNCTION trg_set_updated_at();

COMMIT;

-- =============================================================================
-- DATA MIGRATIONS / SEEDS (NOT INCLUDED IN BASE SCHEMA)
-- =============================================================================
-- The following migrations contain data operations or complex updates that cannot 
-- be represented in a DDL schema file. They MUST be run manually or via migration tool
-- if migrating from an older version, but are not needed for a fresh install 
-- (assuming application handles data initialization).
--
-- 1. PASO7_migrate_image_paths.sql (Migrates local filenames to S3 URLs in `product.image_path`)
-- =============================================================================
