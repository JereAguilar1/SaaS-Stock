-- FIX: Stock ADJUST trigger to support signed qty
-- Bug: ADJUST was always adding qty, causing stock inconsistency on sale edits
-- Fix: ADJUST now interprets qty as signed (negative = reduce, positive = increase)

BEGIN;

CREATE OR REPLACE FUNCTION trg_stock_move_line_after_ins()
RETURNS TRIGGER AS $$
DECLARE
  v_type stock_move_type;
  v_delta NUMERIC(12,3);
BEGIN
  SELECT type INTO v_type FROM stock_move WHERE id = NEW.stock_move_id;

  IF v_type = 'IN' THEN
    v_delta := NEW.qty;  -- IN: adds stock (positive qty)
  ELSIF v_type = 'OUT' THEN
    v_delta := -NEW.qty;  -- OUT: removes stock (negative delta from positive qty)
  ELSE
    -- ADJUST: qty is already signed (positive = add, negative = subtract)
    -- For corrections: if sold MORE -> qty is negative (reduce stock)
    --                  if sold LESS -> qty is positive (increase stock)
    v_delta := NEW.qty;  -- Use qty as-is (can be negative)
  END IF;

  PERFORM apply_stock_delta(NEW.product_id, v_delta);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMIT;
