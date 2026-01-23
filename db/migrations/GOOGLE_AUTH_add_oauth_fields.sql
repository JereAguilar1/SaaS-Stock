-- Google OAuth Support Migration
-- Adds OAuth authentication fields to app_user table
-- Author: SaaS Stock Team
-- Date: 2026-01-23

BEGIN;

-- Add OAuth support columns to app_user
ALTER TABLE app_user
  ADD COLUMN IF NOT EXISTS google_sub VARCHAR(255),
  ADD COLUMN IF NOT EXISTS auth_provider VARCHAR(20) NOT NULL DEFAULT 'local',
  ADD COLUMN IF NOT EXISTS email_verified BOOLEAN NOT NULL DEFAULT FALSE;

-- Make password_hash nullable for OAuth users
ALTER TABLE app_user
  ALTER COLUMN password_hash DROP NOT NULL;

-- Create unique index for google_sub (for fast lookups and uniqueness)
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_user_google_sub 
  ON app_user(google_sub) 
  WHERE google_sub IS NOT NULL;

-- Add constraint for valid auth_provider values
ALTER TABLE app_user
  ADD CONSTRAINT chk_auth_provider 
  CHECK (auth_provider IN ('local', 'google'));

-- Add constraint: local users must have password_hash
ALTER TABLE app_user
  ADD CONSTRAINT chk_local_has_password 
  CHECK (
    (auth_provider = 'local' AND password_hash IS NOT NULL) OR
    (auth_provider != 'local')
  );

-- Update existing users to have email_verified = true
-- (they already registered successfully with email/password)
UPDATE app_user 
SET email_verified = TRUE 
WHERE auth_provider = 'local' AND email_verified = FALSE;

COMMIT;

-- Verification queries (run these after migration):
-- SELECT COUNT(*) FROM app_user WHERE auth_provider = 'local' AND email_verified = TRUE;
-- SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'app_user' AND column_name IN ('google_sub', 'auth_provider', 'email_verified', 'password_hash');
