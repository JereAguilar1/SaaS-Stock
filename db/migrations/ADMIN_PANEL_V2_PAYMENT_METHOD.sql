-- Migration: Add payment_method column to tenant_payments
-- Date: 2026-02-02
-- Description: Adds payment_method field to track how payments were made

-- Add payment_method column
ALTER TABLE tenant_payments 
ADD COLUMN payment_method VARCHAR(50) NOT NULL DEFAULT 'transfer';

-- Add check constraint
ALTER TABLE tenant_payments
DROP CONSTRAINT IF EXISTS check_payment_status;

ALTER TABLE tenant_payments
ADD CONSTRAINT check_payment_status 
CHECK (status IN ('pending', 'paid', 'void'));

ALTER TABLE tenant_payments
ADD CONSTRAINT check_payment_method 
CHECK (payment_method IN ('transfer', 'cash', 'stripe_manual', 'other'));

-- Add comment
COMMENT ON COLUMN tenant_payments.payment_method IS 'Method used for payment: transfer, cash, stripe_manual, other';
