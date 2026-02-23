-- =============================================================================
-- Migración: Crear payment_log o agregar payment_method
-- =============================================================================
-- Fecha: Febrero 2026
-- Descripción: Crea la tabla payment_log si no existe, o le agrega la columna 
--              payment_method si la tabla ya existía.
-- =============================================================================

DO $$
BEGIN
  -- 1. Crear la tabla si no existe en absoluto
  IF NOT EXISTS (
    SELECT FROM pg_tables
    WHERE schemaname = 'public' AND tablename  = 'payment_log'
  ) THEN
    CREATE TABLE payment_log (
        id SERIAL PRIMARY KEY,
        sale_id INTEGER NOT NULL REFERENCES sale(id) ON DELETE CASCADE,
        amount NUMERIC(10, 2) DEFAULT 0,
        date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH'
    );
  ELSE
    -- 2. Si ya existía, asegurarse de que tenga la columna payment_method
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_name='payment_log' AND column_name='payment_method'
    ) THEN
      ALTER TABLE payment_log
        ADD COLUMN payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH';
    END IF;
  END IF;
END $$;
