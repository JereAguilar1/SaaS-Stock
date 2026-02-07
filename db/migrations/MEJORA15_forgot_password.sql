-- =============================================================================
-- MEJORA 15: Forgot Password (Token de Reseteo y Expiración)
-- =============================================================================
-- Fecha: Febrero 2026
-- Descripción: Agregar columnas reset_password_token y reset_password_expires
--              a la tabla app_user para el flujo de recuperación de contraseña.
-- =============================================================================

DO $$ 
BEGIN
  -- 1. Agregar columna reset_password_token
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='app_user' AND column_name='reset_password_token'
  ) THEN
    ALTER TABLE app_user
      ADD COLUMN reset_password_token VARCHAR(100) NULL;
  END IF;

  -- 2. Agregar columna reset_password_expires
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='app_user' AND column_name='reset_password_expires'
  ) THEN
    ALTER TABLE app_user
      ADD COLUMN reset_password_expires TIMESTAMP WITH TIME ZONE NULL;
  END IF;

END $$;

-- 3. Crear índice único para el token (si no existe)
--    Nota: Usamos IF NOT EXISTS en CREATE INDEX (disponible en PG 9.5+)
--    O un bloque DO anónimo si es versión antigua, pero asumimos soporte moderno.
CREATE UNIQUE INDEX IF NOT EXISTS idx_app_user_reset_token
ON app_user(reset_password_token)
WHERE reset_password_token IS NOT NULL;

-- =============================================================================
-- Notas de rollback:
-- ALTER TABLE app_user DROP COLUMN IF EXISTS reset_password_token;
-- ALTER TABLE app_user DROP COLUMN IF EXISTS reset_password_expires;
-- DROP INDEX IF EXISTS idx_app_user_reset_token;
-- =============================================================================
