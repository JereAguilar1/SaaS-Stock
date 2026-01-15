-- FIX: Allow negative qty in stock_move_line for ADJUST type
-- Bug: CHECK constraint (qty > 0) prevents signed qty for adjustments
-- Fix: Remove the constraint to allow negative qty for ADJUST corrections

BEGIN;

-- Drop the constraint that prevents negative qty
ALTER TABLE stock_move_line DROP CONSTRAINT IF EXISTS stock_move_line_qty_check;

-- Add a new constraint that allows qty != 0 (but not zero to prevent meaningless entries)
ALTER TABLE stock_move_line ADD CONSTRAINT stock_move_line_qty_nonzero_check CHECK (qty != 0);

COMMIT;
