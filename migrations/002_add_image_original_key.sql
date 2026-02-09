-- Add image_original_path column to product table
ALTER TABLE product ADD COLUMN image_original_path VARCHAR(255);

-- Backfill existing images as original (assuming current ones are the best we have)
UPDATE product SET image_original_path = image_path WHERE image_path IS NOT NULL;
