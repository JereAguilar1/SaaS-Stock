-- =====================================================================
-- CUENTA CORRIENTE (CUSTOMER LEDGER) - SALE PAYMENT TRACKING
-- =====================================================================
-- Purpose: Add payment tracking columns to sale table
-- 1. Add payment_status column (PAID, PENDING, PARTIAL)
-- 2. Add amount_paid column
-- 3. Backfill existing sales as fully paid
-- =====================================================================

BEGIN;

-- 1. Add payment_status column
ALTER TABLE sale
ADD COLUMN IF NOT EXISTS payment_status VARCHAR(10) NOT NULL DEFAULT 'PAID'
CHECK (payment_status IN ('PAID', 'PENDING', 'PARTIAL'));

-- 2. Add amount_paid column
ALTER TABLE sale
ADD COLUMN IF NOT EXISTS amount_paid NUMERIC(10,2) NOT NULL DEFAULT 0
CHECK (amount_paid >= 0);

-- 3. Backfill existing sales: mark all as fully paid
UPDATE sale
SET amount_paid = total, payment_status = 'PAID'
WHERE amount_paid = 0;

-- 4. Index for efficient cuenta corriente queries
CREATE INDEX IF NOT EXISTS idx_sale_customer_payment_status
ON sale(customer_id, payment_status)
WHERE payment_status IN ('PENDING', 'PARTIAL');

COMMIT;
