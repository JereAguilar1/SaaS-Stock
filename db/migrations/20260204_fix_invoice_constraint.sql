-- Fix constraint invoice_paid_at_consistency to allow PARTIALLY_PAID status
-- Previous definition was too restrictive: ((status = 'PAID' AND paid_at IS NOT NULL) OR (status = 'PENDING' AND paid_at IS NULL))
-- New definition: ((status = 'PAID' AND paid_at IS NOT NULL) OR (status != 'PAID'))

BEGIN;

ALTER TABLE purchase_invoice DROP CONSTRAINT IF EXISTS invoice_paid_at_consistency;

ALTER TABLE purchase_invoice ADD CONSTRAINT invoice_paid_at_consistency CHECK (
    (status = 'PAID' AND paid_at IS NOT NULL) OR
    (status != 'PAID')
);

COMMIT;
