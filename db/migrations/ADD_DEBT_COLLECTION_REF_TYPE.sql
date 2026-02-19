-- =============================================================================
-- Migración: Agregar DEBT_COLLECTION al enum ledger_ref_type
-- =============================================================================
-- Fecha: Febrero 2026
-- Descripción: Agregar valor 'DEBT_COLLECTION' al tipo enum ledger_ref_type
--              para registrar cobros de deudas de Cuenta Corriente.
-- =============================================================================

-- Agregar nuevo valor al enum si no existe
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_enum
        WHERE enumlabel = 'DEBT_COLLECTION'
        AND enumtypid = (SELECT oid FROM pg_type WHERE typname = 'ledger_ref_type')
    ) THEN
        ALTER TYPE ledger_ref_type ADD VALUE 'DEBT_COLLECTION';
    END IF;
END$$;

-- =============================================================================
-- Nota: ALTER TYPE ADD VALUE no se puede revertir fácilmente en PostgreSQL.
-- Si necesita revertir, debe recrear el enum type completo.
-- =============================================================================
