-- Google OAuth Support Migration - ROLLBACK
-- Removes OAuth authentication fields from app_user table
-- Author: SaaS Stock Team
-- Date: 2026-01-23

BEGIN;

-- Remove constraints
ALTER TABLE app_user
  DROP CONSTRAINT IF EXISTS chk_local_has_password,
  DROP CONSTRAINT IF EXISTS chk_auth_provider;

-- Remove index
DROP INDEX IF EXISTS idx_app_user_google_sub;

-- Remove OAuth columns
ALTER TABLE app_user
  DROP COLUMN IF EXISTS google_sub,
  DROP COLUMN IF EXISTS auth_provider,
  DROP COLUMN IF EXISTS email_verified;

-- Restore password_hash as NOT NULL
-- WARNING: This will fail if there are OAuth users without password_hash
-- You should manually set passwords or delete OAuth-only users before rollback
ALTER TABLE app_user
  ALTER COLUMN password_hash SET NOT NULL;

COMMIT;

-- Note: If rollback fails due to NULL password_hash values, run this first:
-- DELETE FROM app_user WHERE password_hash IS NULL;
-- Or set temporary passwords:
-- UPDATE app_user SET password_hash = 'DISABLED' WHERE password_hash IS NULL;
