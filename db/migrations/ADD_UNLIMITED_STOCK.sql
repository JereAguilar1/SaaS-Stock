-- Add unlimited stock flag to products
ALTER TABLE product ADD COLUMN IF NOT EXISTS is_unlimited_stock BOOLEAN NOT NULL DEFAULT FALSE;
