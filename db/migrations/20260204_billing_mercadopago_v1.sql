-- =====================================================================
-- BILLING V1: Mercado Pago Integration
-- =====================================================================
-- Fecha: 2026-02-04
-- Descripción: Sistema de facturación con suscripciones recurrentes
--              mediante Mercado Pago (preapproval)
-- =====================================================================

BEGIN;

-- =====================================================================
-- 1. BILLING_PLAN: Planes de facturación disponibles
-- =====================================================================
CREATE TABLE IF NOT EXISTS billing_plan (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(50) NOT NULL UNIQUE,
    name VARCHAR(200) NOT NULL,
    price_amount NUMERIC(12,2) NOT NULL CHECK (price_amount >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'ARS',
    frequency INTEGER NOT NULL DEFAULT 1 CHECK (frequency > 0),
    frequency_type VARCHAR(20) NOT NULL DEFAULT 'months' CHECK (frequency_type IN ('days', 'months')),
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_billing_plan_code ON billing_plan(code);
CREATE INDEX IF NOT EXISTS idx_billing_plan_active ON billing_plan(active);

COMMENT ON TABLE billing_plan IS 'Planes de facturación disponibles para suscripción';
COMMENT ON COLUMN billing_plan.code IS 'Código único del plan (ej: PRO, ENTERPRISE)';
COMMENT ON COLUMN billing_plan.frequency IS 'Frecuencia de cobro (ej: 1 = cada 1 mes)';
COMMENT ON COLUMN billing_plan.frequency_type IS 'Tipo de frecuencia: days o months';

-- =====================================================================
-- 2. MP_SUBSCRIPTION: Suscripciones de Mercado Pago por tenant
-- =====================================================================
CREATE TABLE IF NOT EXISTS mp_subscription (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    plan_id BIGINT NOT NULL REFERENCES billing_plan(id),
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' 
        CHECK (status IN ('PENDING', 'ACTIVE', 'PAUSED', 'CANCELED', 'REJECTED', 'EXPIRED')),
    mp_preapproval_id VARCHAR(100) UNIQUE,
    mp_init_point TEXT,
    started_at TIMESTAMPTZ,
    cancelled_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_mp_subscription_tenant ON mp_subscription(tenant_id);
CREATE INDEX IF NOT EXISTS idx_mp_subscription_status ON mp_subscription(status);
CREATE INDEX IF NOT EXISTS idx_mp_subscription_preapproval ON mp_subscription(mp_preapproval_id);

COMMENT ON TABLE mp_subscription IS 'Suscripciones de Mercado Pago vinculadas a tenants';
COMMENT ON COLUMN mp_subscription.status IS 'PENDING: creada pero no confirmada | ACTIVE: pagando | PAUSED/CANCELED/REJECTED/EXPIRED: inactiva';
COMMENT ON COLUMN mp_subscription.mp_preapproval_id IS 'ID de preapproval en Mercado Pago';
COMMENT ON COLUMN mp_subscription.mp_init_point IS 'URL de checkout de Mercado Pago';
COMMENT ON COLUMN mp_subscription.metadata_json IS 'Datos adicionales de MP (payer_email, etc)';

-- =====================================================================
-- 3. MP_WEBHOOK_EVENT: Log de eventos webhook (idempotencia)
-- =====================================================================
CREATE TABLE IF NOT EXISTS mp_webhook_event (
    id BIGSERIAL PRIMARY KEY,
    topic VARCHAR(50) NOT NULL,
    mp_event_id VARCHAR(100),
    resource_id VARCHAR(100),
    payload_json JSONB NOT NULL,
    dedupe_key VARCHAR(64) NOT NULL UNIQUE,
    received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'RECEIVED' 
        CHECK (status IN ('RECEIVED', 'PROCESSING', 'PROCESSED', 'FAILED'))
);

CREATE INDEX IF NOT EXISTS idx_webhook_topic ON mp_webhook_event(topic);
CREATE INDEX IF NOT EXISTS idx_webhook_resource ON mp_webhook_event(resource_id);
CREATE INDEX IF NOT EXISTS idx_webhook_status ON mp_webhook_event(status);
CREATE INDEX IF NOT EXISTS idx_webhook_received ON mp_webhook_event(received_at);

COMMENT ON TABLE mp_webhook_event IS 'Log de eventos webhook de Mercado Pago para idempotencia';
COMMENT ON COLUMN mp_webhook_event.dedupe_key IS 'SHA256 hash para deduplicación de eventos';
COMMENT ON COLUMN mp_webhook_event.topic IS 'Tipo de evento: preapproval, payment, etc';
COMMENT ON COLUMN mp_webhook_event.mp_event_id IS 'ID del evento en MP (si viene en notificación)';
COMMENT ON COLUMN mp_webhook_event.resource_id IS 'ID del recurso afectado (preapproval_id)';

-- =====================================================================
-- 4. SEED: Plan PRO mensual
-- =====================================================================
INSERT INTO billing_plan (code, name, price_amount, currency, frequency, frequency_type, active)
VALUES 
    ('PRO', 'Plan PRO Mensual', 9900.00, 'ARS', 1, 'months', true)
ON CONFLICT (code) DO NOTHING;

COMMIT;

-- =====================================================================
-- NOTAS DE APLICACIÓN:
-- =====================================================================
-- Para aplicar esta migración en Docker:
--   docker exec -i Stock-db psql -U stock -d stock < db/migrations/20260204_billing_mercadopago_v1.sql
--
-- Para verificar:
--   docker exec -it Stock-db psql -U stock -d stock -c "SELECT * FROM billing_plan;"
--   docker exec -it Stock-db psql -U stock -d stock -c "\d mp_subscription"
-- =====================================================================
