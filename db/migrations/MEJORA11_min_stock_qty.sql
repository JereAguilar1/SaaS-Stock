-- =============================================================================
-- MEJORA 11: Stock Mínimo por Producto
-- =============================================================================
-- Fecha: Enero 2026
-- Descripción: Agregar columna min_stock_qty a la tabla product para permitir
--              umbrales de stock bajo personalizados por producto.
-- =============================================================================

-- Agregar columna min_stock_qty a la tabla product
-- NUMERIC(12,2) para soportar productos con UOM fraccionarios (KG, M, L)
-- DEFAULT 0 implica "sin mínimo configurado"
ALTER TABLE product
ADD COLUMN IF NOT EXISTS min_stock_qty NUMERIC(12,2) NOT NULL DEFAULT 0;

-- Agregar constraint para asegurar valores no negativos
-- PostgreSQL no soporta IF NOT EXISTS con ADD CONSTRAINT directamente
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

-- Crear índice para optimizar consultas de filtrado por stock bajo
CREATE INDEX IF NOT EXISTS idx_product_min_stock_qty
ON product(min_stock_qty);

-- Comentario en la columna (opcional, para documentación)
COMMENT ON COLUMN product.min_stock_qty IS 
'Stock mínimo requerido para el producto. Si on_hand_qty <= min_stock_qty, se considera "poco stock". Si es 0, no aplica umbral.';

-- =============================================================================
-- Notas de migración:
-- =============================================================================
-- 1. Esta migración es compatible con datos existentes (DEFAULT 0)
-- 2. No afecta triggers de stock_move ni product_stock
-- 3. min_stock_qty solo se usa para alertas visuales y filtros en UI
-- 4. Para aplicar: psql -U ferreteria -d ferreteria -f MEJORA11_min_stock_qty.sql
-- 5. Para revertir (si es necesario):
--    DROP INDEX IF EXISTS idx_product_min_stock_qty;
--    ALTER TABLE product DROP CONSTRAINT IF EXISTS chk_min_stock_qty_non_negative;
--    ALTER TABLE product DROP COLUMN IF EXISTS min_stock_qty;
-- =============================================================================
