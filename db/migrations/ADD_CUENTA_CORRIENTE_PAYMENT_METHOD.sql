-- =============================================================================
-- Migración: Agregar CUENTA_CORRIENTE como método de pago válido en finance_ledger
-- =============================================================================
-- Fecha: Febrero 2026
-- Descripción: Ampliar el CHECK constraint de payment_method para incluir
--              'CUENTA_CORRIENTE' (ventas a crédito) y 'CARD'.
-- =============================================================================

-- Eliminar constraint viejo y crear uno nuevo con los valores ampliados
ALTER TABLE finance_ledger DROP CONSTRAINT IF EXISTS chk_finance_ledger_payment_method;

ALTER TABLE finance_ledger
ADD CONSTRAINT chk_finance_ledger_payment_method
CHECK (payment_method IN ('CASH', 'TRANSFER', 'CARD', 'CUENTA_CORRIENTE'));

-- =============================================================================
-- Para revertir:
--   ALTER TABLE finance_ledger DROP CONSTRAINT IF EXISTS chk_finance_ledger_payment_method;
--   ALTER TABLE finance_ledger ADD CONSTRAINT chk_finance_ledger_payment_method
--     CHECK (payment_method IN ('CASH', 'TRANSFER'));
-- =============================================================================
