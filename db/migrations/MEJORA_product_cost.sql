-- MEJORA: Agregar campo cost (Precio de Compra) a productos
-- Fecha: 2026-02-04
-- Descripción: Permite calcular márgenes y valuación de inventario

-- Agregar columna cost a la tabla product
ALTER TABLE product ADD COLUMN cost NUMERIC(10, 2) NOT NULL DEFAULT 0.00;

-- Comentario para documentación
COMMENT ON COLUMN product.cost IS 'Precio de compra/costo unitario del producto para cálculo de márgenes';
