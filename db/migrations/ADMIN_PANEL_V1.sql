-- =====================================================================
-- ADMIN PANEL V1: Admin Backoffice Infrastructure
-- =====================================================================
-- Purpose: Create admin security model and tenant suspension capability
-- Author: Admin Panel Implementation
-- Date: 2026-01-31
--
-- IMPORTANT: This migration creates a separate admin authentication system
-- that is completely isolated from tenant users. Admin users have NO tenant_id.
-- =====================================================================

BEGIN;

-- =====================================================================
-- PART A: CREATE ADMIN USERS TABLE
-- =====================================================================

-- Admin Users table: Global platform administrators (no tenant association)
CREATE TABLE IF NOT EXISTS admin_users (
    id BIGSERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,  -- scrypt hash
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_login TIMESTAMPTZ NULL  -- Track last admin login
);

-- Indexes for admin authentication
CREATE INDEX IF NOT EXISTS idx_admin_users_email ON admin_users(email);

COMMENT ON TABLE admin_users IS 'Global platform administrators - NO tenant_id (operates across all tenants)';
COMMENT ON COLUMN admin_users.email IS 'Admin login email (must be unique)';

-- =====================================================================
-- PART B: ADD TENANT SUSPENSION CAPABILITY
-- =====================================================================

-- Add is_suspended column to tenant table
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='tenant' AND column_name='is_suspended'
    ) THEN
        ALTER TABLE tenant ADD COLUMN is_suspended BOOLEAN NOT NULL DEFAULT FALSE;
        CREATE INDEX idx_tenant_is_suspended ON tenant(is_suspended);
        COMMENT ON COLUMN tenant.is_suspended IS 'If true, all users of this tenant are blocked from login';
    END IF;
END $$;

-- =====================================================================
-- PART C: PERFORMANCE INDEXES
-- =====================================================================

-- Index for admin dashboard queries (aggregate by tenant_id)
-- These already exist from SAAS_STEP2 migration, but we ensure they're there
CREATE INDEX IF NOT EXISTS idx_sale_tenant_id ON sale(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sale_status ON sale(status);
CREATE INDEX IF NOT EXISTS idx_sale_datetime ON sale(datetime DESC);

-- Index for tenant list queries (join to user_tenant for owner)
CREATE INDEX IF NOT EXISTS idx_user_tenant_role_tenant ON user_tenant(role, tenant_id);

-- =====================================================================
-- VALIDATION QUERIES (Keep commented, run manually to verify)
-- =====================================================================

-- Verify admin_users table structure
/*
\d admin_users
*/

-- Verify tenant.is_suspended column exists
/*
SELECT column_name, data_type, column_default 
FROM information_schema.columns 
WHERE table_name = 'tenant' AND column_name = 'is_suspended';
*/

-- Verify indexes
/*
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename IN ('admin_users', 'tenant')
ORDER BY tablename, indexname;
*/

COMMIT;

-- =====================================================================
-- MIGRATION COMPLETE
-- =====================================================================
-- Next steps:
-- 1. Create first admin user via: flask create-admin
-- 2. Admin login available at: /admin/login
-- 3. Tenant suspension takes effect immediately on login attempts
-- =====================================================================
