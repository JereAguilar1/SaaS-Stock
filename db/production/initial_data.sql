-- ============================================================================
-- Sistema Ferretería - Datos Iniciales para Producción
-- ============================================================================
-- Versión: 1.0
-- Fecha: Enero 2026
-- Descripción: Datos maestros mínimos necesarios para iniciar el sistema
-- ============================================================================

BEGIN;

-- ============================================================================
-- UNIDADES DE MEDIDA (UOM)
-- ============================================================================

INSERT INTO uom (name, symbol) VALUES
  ('Unidad', 'ud'),
  ('Metro', 'm'),
  ('Metro cuadrado', 'm²'),
  ('Metro cúbico', 'm³'),
  ('Litro', 'l'),
  ('Kilogramo', 'kg'),
  ('Caja', 'caja'),
  ('Paquete', 'paq'),
  ('Rollo', 'rollo'),
  ('Bolsa', 'bolsa'),
  ('Juego', 'juego'),
  ('Par', 'par')
ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- CATEGORÍAS DE PRODUCTOS
-- ============================================================================

INSERT INTO category (name) VALUES
  ('Herramientas Manuales'),
  ('Herramientas Eléctricas'),
  ('Ferretería General'),
  ('Pintura y Accesorios'),
  ('Electricidad'),
  ('Plomería'),
  ('Construcción'),
  ('Cerrajería'),
  ('Jardín y Exterior'),
  ('Iluminación'),
  ('Seguridad'),
  ('Adhesivos y Selladores'),
  ('Abrasivos'),
  ('Fijaciones'),
  ('Otros')
ON CONFLICT (name) DO NOTHING;

COMMIT;

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================

-- Verificar UOMs insertadas
SELECT 'UOMs insertadas:' as info, COUNT(*) as count FROM uom;

-- Verificar categorías insertadas
SELECT 'Categorías insertadas:' as info, COUNT(*) as count FROM category;

-- ============================================================================
-- FIN
-- ============================================================================
