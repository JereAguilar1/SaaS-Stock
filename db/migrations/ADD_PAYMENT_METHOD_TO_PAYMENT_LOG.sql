-- =============================================================================
-- Migración: Agregar payment_method a payment_log
-- =============================================================================
-- Fecha: Febrero 2026
-- Descripción: Agregar columna payment_method a la tabla payment_log
--              para registrar cómo se cobró cada cuota de Cuenta Corriente.
-- =============================================================================

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='payment_log' AND column_name='payment_method'
  ) THEN
    ALTER TABLE payment_log
      ADD COLUMN payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH';
  END IF;
END $$;

-- =============================================================================
-- Para revertir:
--   ALTER TABLE payment_log DROP COLUMN IF EXISTS payment_method;
-- =============================================================================
