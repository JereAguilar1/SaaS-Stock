-- ============================================================================
-- Migration 010: POS Improvements
-- ============================================================================
-- Description: Add persistent cart (sale_draft), mixed payments (sale_payment),
--              and idempotency to prevent duplicate sales.
-- Date: 2026-01-29
-- ============================================================================

-- 1. Create sale_draft table (persistent cart)
CREATE TABLE sale_draft (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    
    -- Global discount (applied to entire cart)
    discount_type VARCHAR(10) CHECK (discount_type IN ('PERCENT', 'AMOUNT') OR discount_type IS NULL),
    discount_value NUMERIC(10, 2) DEFAULT 0 CHECK (discount_value >= 0),
    
    -- One draft per user per tenant
    UNIQUE(tenant_id, user_id)
);

CREATE INDEX idx_sale_draft_tenant_user ON sale_draft(tenant_id, user_id);
CREATE INDEX idx_sale_draft_user ON sale_draft(user_id);

COMMENT ON TABLE sale_draft IS 'Persistent cart for POS - survives page refreshes';
COMMENT ON COLUMN sale_draft.discount_type IS 'PERCENT or AMOUNT - applied to entire cart';
COMMENT ON COLUMN sale_draft.discount_value IS 'Discount value (percentage or fixed amount)';


-- 2. Create sale_draft_line table (cart items)
CREATE TABLE sale_draft_line (
    id BIGSERIAL PRIMARY KEY,
    draft_id BIGINT NOT NULL REFERENCES sale_draft(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    qty NUMERIC(10, 2) NOT NULL CHECK (qty > 0),
    
    -- Item-level discount (applied to this line only)
    discount_type VARCHAR(10) CHECK (discount_type IN ('PERCENT', 'AMOUNT') OR discount_type IS NULL),
    discount_value NUMERIC(10, 2) DEFAULT 0 CHECK (discount_value >= 0),
    
    -- One product per draft (can't add same product twice, update qty instead)
    UNIQUE(draft_id, product_id)
);

CREATE INDEX idx_sale_draft_line_draft ON sale_draft_line(draft_id);
CREATE INDEX idx_sale_draft_line_product ON sale_draft_line(product_id);

COMMENT ON TABLE sale_draft_line IS 'Individual items in the persistent cart';
COMMENT ON COLUMN sale_draft_line.discount_type IS 'PERCENT or AMOUNT - applied to this line only';
COMMENT ON COLUMN sale_draft_line.discount_value IS 'Discount value (percentage or fixed amount)';


-- 3. Create sale_payment table (mixed payment methods)
CREATE TABLE sale_payment (
    id BIGSERIAL PRIMARY KEY,
    sale_id BIGINT NOT NULL REFERENCES sale(id) ON DELETE CASCADE,
    payment_method VARCHAR(20) NOT NULL CHECK (payment_method IN ('CASH', 'TRANSFER', 'CARD')),
    amount NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    
    -- Only for CASH payments
    amount_received NUMERIC(10, 2) CHECK (amount_received IS NULL OR amount_received >= amount),
    change_amount NUMERIC(10, 2) CHECK (change_amount IS NULL OR change_amount >= 0)
);

CREATE INDEX idx_sale_payment_sale ON sale_payment(sale_id);

COMMENT ON TABLE sale_payment IS 'Individual payments for a sale - allows mixed payment methods';
COMMENT ON COLUMN sale_payment.amount_received IS 'Amount given by customer (CASH only)';
COMMENT ON COLUMN sale_payment.change_amount IS 'Change returned to customer (CASH only)';


-- 4. Add idempotency_key to sale table
ALTER TABLE sale ADD COLUMN idempotency_key VARCHAR(64) UNIQUE;

CREATE INDEX idx_sale_idempotency ON sale(idempotency_key) WHERE idempotency_key IS NOT NULL;

COMMENT ON COLUMN sale.idempotency_key IS 'UUID to prevent duplicate sales on double-submit/refresh';


-- ============================================================================
-- Verification Queries
-- ============================================================================

-- Verify tables created
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('sale_draft', 'sale_draft_line', 'sale_payment')
ORDER BY table_name;

-- Verify indexes created
SELECT indexname 
FROM pg_indexes 
WHERE schemaname = 'public' 
  AND tablename IN ('sale_draft', 'sale_draft_line', 'sale_payment', 'sale')
  AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;

-- Verify constraints
SELECT conname, contype, pg_get_constraintdef(oid) as definition
FROM pg_constraint
WHERE conrelid IN (
    'sale_draft'::regclass,
    'sale_draft_line'::regclass,
    'sale_payment'::regclass
)
ORDER BY conrelid::regclass::text, conname;
