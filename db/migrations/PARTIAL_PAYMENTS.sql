-- =====================================================================
-- PARTIAL PAYMENTS FOR PURCHASE INVOICES
-- =====================================================================
-- Purpose: Allow partial payments of purchase invoices
-- 1. Add PARTIALLY_PAID to invoice_status enum
-- 2. Add paid_amount to purchase_invoice
-- 3. Create purchase_invoice_payment table
-- =====================================================================

BEGIN;

-- 1. Add PARTIALLY_PAID status
ALTER TYPE invoice_status ADD VALUE IF NOT EXISTS 'PARTIALLY_PAID';

-- 2. Add paid_amount column to purchase_invoice
ALTER TABLE purchase_invoice 
ADD COLUMN IF NOT EXISTS paid_amount NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (paid_amount >= 0);

-- Update existing paid invoices to have paid_amount = total_amount
UPDATE purchase_invoice 
SET paid_amount = total_amount 
WHERE status = 'PAID' AND paid_amount = 0;

-- 3. Create purchase_invoice_payment table
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

-- 4. Constraint to ensure paid_amount <= total_amount (deferrable to allow updates)
-- Not strict constraint on DB level to allow flexibility during updates, handled by app logic,
-- but a trigger could enforce it. For now, relying on app logic as requested.

COMMIT;
