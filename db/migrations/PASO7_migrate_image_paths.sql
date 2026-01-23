-- ============================================================================
-- PASO 7: Migración de Image Paths (Filesystem → S3 URLs)
-- ============================================================================
--
-- Este script actualiza los image_path existentes en la tabla product
-- para convertir rutas locales a URLs completas de S3/MinIO.
--
-- IMPORTANTE:
-- 1. Este script asume que ya migraste las imágenes físicas a MinIO/S3.
-- 2. Solo actualiza los paths en la base de datos.
-- 3. Para migrar archivos físicos, usa: infra/scripts/migrate_images_to_s3.sh
--
-- Autor: Arquitecto Backend Senior
-- Fecha: 2026-01-23
-- Versión: 1.7.0
-- ============================================================================

BEGIN;

-- Verificar productos con image_path que NO son URLs
SELECT 
    COUNT(*) as products_with_local_paths,
    COUNT(CASE WHEN image_path NOT LIKE 'http%' THEN 1 END) as need_migration
FROM product
WHERE image_path IS NOT NULL;

-- Actualizar image_path de filename local a URL completa
-- Antes: "123456_martillo.jpg"
-- Ahora: "http://localhost:9000/uploads/products/tenant_1/123456_martillo.jpg"

UPDATE product
SET image_path = CONCAT(
    'http://localhost:9000',  -- S3_PUBLIC_URL (cambiar según env)
    '/uploads',               -- S3_BUCKET
    '/products/tenant_', tenant_id, '/',
    image_path
)
WHERE 
    image_path IS NOT NULL
    AND image_path NOT LIKE 'http%';  -- Solo paths locales

-- Verificar resultado
SELECT 
    id,
    tenant_id,
    name,
    image_path
FROM product
WHERE image_path IS NOT NULL
LIMIT 10;

COMMIT;

-- ============================================================================
-- ROLLBACK (si es necesario)
-- ============================================================================
-- Para revertir (extraer filename de URL):
-- 
-- BEGIN;
-- 
-- UPDATE product
-- SET image_path = SUBSTRING(
--     image_path FROM '.*/([^/]+)$'
-- )
-- WHERE image_path LIKE 'http%';
-- 
-- COMMIT;
-- ============================================================================
