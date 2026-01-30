-- =============================================================================
-- MEJORA: Cambiar Stock Mínimo de NUMERIC a INTEGER
-- =============================================================================
-- Fecha: Enero 2026
-- Descripción: Cambiar el tipo de dato de min_stock_qty de NUMERIC(12,2) a INTEGER
--              ya que las cantidades mínimas de stock deben ser valores enteros.
-- =============================================================================

BEGIN;

-- Modificar la columna min_stock_qty de NUMERIC(12,2) a INTEGER
-- Los valores decimales existentes se truncarán automáticamente
ALTER TABLE product
ALTER COLUMN min_stock_qty TYPE INTEGER USING min_stock_qty::INTEGER;

-- El constraint CHECK y el índice se mantienen automáticamente
-- Verificar que el constraint existe (debería mantenerse)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'chk_min_stock_qty_non_negative'
    ) THEN
        ALTER TABLE product
        ADD CONSTRAINT chk_min_stock_qty_non_negative 
        CHECK (min_stock_qty >= 0);
    END IF;
END$$;

-- Actualizar el comentario de la columna
COMMENT ON COLUMN product.min_stock_qty IS 
'Stock mínimo requerido para el producto (valor entero). Si on_hand_qty <= min_stock_qty, se considera "poco stock". Si es 0, no aplica umbral.';

COMMIT;

-- =============================================================================
-- Notas de migración:
-- =============================================================================
-- 1. Esta migración convierte valores decimales a enteros (truncamiento)
-- 2. Ejemplo: 10.75 se convertirá en 10
-- 3. El índice idx_product_min_stock_qty se mantiene automáticamente
-- 4. Para aplicar: psql -U <usuario> -d <database> -f MEJORA_min_stock_qty_to_integer.sql
-- 5. Para revertir (si es necesario):
--    BEGIN;
--    ALTER TABLE product ALTER COLUMN min_stock_qty TYPE NUMERIC(12,2);
--    COMMENT ON COLUMN product.min_stock_qty IS 
--    'Stock mínimo requerido para el producto. Si on_hand_qty <= min_stock_qty, se considera "poco stock". Si es 0, no aplica umbral.';
--    COMMIT;
-- =============================================================================
