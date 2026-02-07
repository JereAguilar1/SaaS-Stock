-- =============================================================================
-- TENANT LOGO CUSTOMIZATION: Add logo_url column to tenant table
-- =============================================================================
-- Fecha: 2026-02-07
-- Descripción: Permitir que cada tenant personalice el logo de su negocio
--              en el sidebar, con fallback al nombre del negocio.
-- =============================================================================

-- Add logo_url column to tenant table
-- VARCHAR(255) for S3 object keys (e.g., "logos/123/business_logo.png")
-- NULL by default (fallback to tenant name)
ALTER TABLE tenant
ADD COLUMN IF NOT EXISTS logo_url VARCHAR(255) DEFAULT NULL;

-- Add check constraint to ensure valid URL format if not null
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'chk_tenant_logo_url_valid'
    ) THEN
        ALTER TABLE tenant
        ADD CONSTRAINT chk_tenant_logo_url_valid 
        CHECK (logo_url IS NULL OR length(logo_url) > 0);
    END IF;
END$$;

-- Create index for faster queries when filtering by logo presence
CREATE INDEX IF NOT EXISTS idx_tenant_logo_url
ON tenant(logo_url) WHERE logo_url IS NOT NULL;

-- Comment on the column for documentation
COMMENT ON COLUMN tenant.logo_url IS 
'S3/MinIO object key for tenant business logo. Stored in logos/{tenant_id}/ prefix. NULL means use tenant name as fallback in UI.';

-- =============================================================================
-- Notas de migración:
-- =============================================================================
-- 1. Esta migración es compatible con datos existentes (DEFAULT NULL)
-- 2. Los tenants sin logo mostrarán su nombre en el sidebar
-- 3. El logo se sirve desde MinIO/S3 vía StorageService
-- 4. Para aplicar: psql -U [username] -d [database] -f db/migrations/20260207_add_tenant_logo.sql
-- 5. Para revertir (si es necesario):
--    DROP INDEX IF EXISTS idx_tenant_logo_url;
--    ALTER TABLE tenant DROP CONSTRAINT IF EXISTS chk_tenant_logo_url_valid;
--    ALTER TABLE tenant DROP COLUMN IF EXISTS logo_url;
-- =============================================================================
