-- =============================================================================
-- MEJORA 12: Método de Pago (Efectivo/Transferencia)
-- =============================================================================
-- Fecha: Enero 2026
-- Descripción: Agregar columna payment_method a finance_ledger para distinguir
--              entre pagos en efectivo y transferencias bancarias.
-- =============================================================================

-- Agregar columna payment_method a finance_ledger
-- VARCHAR(20) para almacenar 'CASH' o 'TRANSFER'
-- DEFAULT 'CASH' para compatibilidad con datos existentes
DO $$ 
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_name='finance_ledger' AND column_name='payment_method'
  ) THEN
    ALTER TABLE finance_ledger
      ADD COLUMN payment_method VARCHAR(20) NOT NULL DEFAULT 'CASH';
  END IF;
END $$;

-- Agregar constraint para validar valores permitidos
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint 
        WHERE conname = 'chk_finance_ledger_payment_method'
    ) THEN
        ALTER TABLE finance_ledger
        ADD CONSTRAINT chk_finance_ledger_payment_method
        CHECK (payment_method IN ('CASH', 'TRANSFER'));
    END IF;
END$$;

-- Crear índice para optimizar consultas de filtrado por método
CREATE INDEX IF NOT EXISTS idx_finance_ledger_payment_method
ON finance_ledger(payment_method);

-- Comentario en la columna (opcional, para documentación)
COMMENT ON COLUMN finance_ledger.payment_method IS 
'Método de pago: CASH (efectivo/caja física) o TRANSFER (transferencia bancaria). Permite separar flujos de caja vs banco.';

-- =============================================================================
-- Notas de migración:
-- =============================================================================
-- 1. Esta migración es compatible con datos existentes (DEFAULT 'CASH')
-- 2. Todos los registros históricos quedarán como 'CASH' por defecto
-- 3. Se puede reclasificar manualmente si es necesario
-- 4. Para aplicar: psql -U ferreteria -d ferreteria -f MEJORA12_payment_method.sql
-- 5. Para revertir (si es necesario):
--    DROP INDEX IF EXISTS idx_finance_ledger_payment_method;
--    ALTER TABLE finance_ledger DROP CONSTRAINT IF EXISTS chk_finance_ledger_payment_method;
--    ALTER TABLE finance_ledger DROP COLUMN IF EXISTS payment_method;
-- =============================================================================
