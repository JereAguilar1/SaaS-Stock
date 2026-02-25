-- Migration 011: Add unit_price to sale_draft_line
-- Allows storing a custom unit price per draft line (POS cart)

ALTER TABLE sale_draft_line
ADD COLUMN IF NOT EXISTS unit_price NUMERIC(10, 2);

-- Backfill existing draft lines with the current product sale_price
UPDATE sale_draft_line sdl
SET unit_price = p.sale_price
FROM product p
WHERE sdl.product_id = p.id
  AND sdl.unit_price IS NULL;
