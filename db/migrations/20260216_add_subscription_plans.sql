-- =====================================================
-- Mercado Pago Integration - Subscription Plans
-- Migration: 20260216_add_subscription_plans.sql
-- Description: Add dynamic plan management with Mercado Pago integration
-- =====================================================

-- =====================================================
-- TABLE: plans
-- Purpose: Store subscription plan definitions
-- =====================================================

CREATE TABLE plans (
    id BIGSERIAL PRIMARY KEY,
    
    -- Plan Information
    name VARCHAR(100) NOT NULL,                     -- Display name: 'Básico', 'Intermedio', 'Pro'
    code VARCHAR(50) NOT NULL UNIQUE,               -- Internal code: 'basic', 'intermediate', 'pro'
    description TEXT,                               -- Plan description for marketing
    
    -- Mercado Pago Integration
    mp_preapproval_plan_id VARCHAR(255),            -- Mercado Pago plan ID
    
    -- Pricing
    price DECIMAL(10, 2) NOT NULL,                  -- Monthly price
    currency VARCHAR(3) DEFAULT 'ARS',              -- Currency code
    billing_frequency VARCHAR(20) DEFAULT 'monthly', -- 'monthly', 'yearly'
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,                 -- Plan available for subscription
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for plans
CREATE INDEX idx_plans_code ON plans(code);
CREATE INDEX idx_plans_active ON plans(is_active);
CREATE INDEX idx_plans_mp_id ON plans(mp_preapproval_plan_id);

-- Comments
COMMENT ON TABLE plans IS 'Subscription plan definitions with Mercado Pago integration';
COMMENT ON COLUMN plans.code IS 'Unique internal identifier for the plan';
COMMENT ON COLUMN plans.mp_preapproval_plan_id IS 'Mercado Pago preapproval plan ID';
COMMENT ON COLUMN plans.billing_frequency IS 'Billing cycle: monthly or yearly';

-- =====================================================
-- TABLE: plan_features
-- Purpose: Store features/permissions for each plan
-- =====================================================

CREATE TABLE plan_features (
    id BIGSERIAL PRIMARY KEY,
    plan_id BIGINT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
    
    -- Feature Definition
    feature_key VARCHAR(100) NOT NULL,              -- 'module_sales', 'max_users', 'api_access'
    feature_value TEXT,                             -- Optional value: '5' for max_users, 'true' for boolean
    is_active BOOLEAN DEFAULT TRUE,                 -- Feature enabled/disabled
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(plan_id, feature_key)
);

-- Indexes for plan_features
CREATE INDEX idx_plan_features_plan ON plan_features(plan_id);
CREATE INDEX idx_plan_features_key ON plan_features(feature_key);
CREATE INDEX idx_plan_features_active ON plan_features(is_active);

-- Comments
COMMENT ON TABLE plan_features IS 'Features and permissions associated with each plan';
COMMENT ON COLUMN plan_features.feature_key IS 'Unique feature identifier (e.g., module_sales, max_users)';
COMMENT ON COLUMN plan_features.feature_value IS 'Optional feature value (e.g., 5 for max_users limit)';

-- =====================================================
-- ALTER TABLE: tenant_subscriptions
-- Purpose: Add Mercado Pago integration fields
-- =====================================================

ALTER TABLE tenant_subscriptions
    -- Link to plan table
    ADD COLUMN plan_id BIGINT REFERENCES plans(id),
    
    -- Mercado Pago Integration
    ADD COLUMN mp_subscription_id VARCHAR(255),     -- MP subscription ID
    ADD COLUMN mp_payer_id VARCHAR(255),            -- MP payer ID
    ADD COLUMN mp_status VARCHAR(50),               -- MP subscription status
    
    -- Billing
    ADD COLUMN next_billing_date TIMESTAMP WITH TIME ZONE,
    ADD COLUMN auto_recurring BOOLEAN DEFAULT FALSE; -- Is auto-recurring enabled

-- Indexes for new columns
CREATE INDEX idx_subscriptions_plan_id ON tenant_subscriptions(plan_id);
CREATE INDEX idx_subscriptions_mp_id ON tenant_subscriptions(mp_subscription_id);
CREATE INDEX idx_subscriptions_mp_payer ON tenant_subscriptions(mp_payer_id);
CREATE INDEX idx_subscriptions_next_billing ON tenant_subscriptions(next_billing_date);

-- Comments
COMMENT ON COLUMN tenant_subscriptions.plan_id IS 'Reference to the subscribed plan';
COMMENT ON COLUMN tenant_subscriptions.mp_subscription_id IS 'Mercado Pago subscription ID';
COMMENT ON COLUMN tenant_subscriptions.mp_payer_id IS 'Mercado Pago payer ID';
COMMENT ON COLUMN tenant_subscriptions.mp_status IS 'Mercado Pago subscription status';
COMMENT ON COLUMN tenant_subscriptions.auto_recurring IS 'Whether subscription auto-renews via Mercado Pago';

-- =====================================================
-- INITIAL DATA: Default Plans
-- =====================================================

-- Insert default plans
INSERT INTO plans (name, code, price, description, is_active) VALUES
('Básico', 'basic', 9999.00, 'Plan básico con funcionalidades esenciales para pequeños negocios', TRUE),
('Intermedio', 'intermediate', 19999.00, 'Plan intermedio con más usuarios y módulos avanzados', TRUE),
('Pro', 'pro', 39999.00, 'Plan profesional con todas las funcionalidades y soporte prioritario', TRUE);

-- =====================================================
-- INITIAL DATA: Plan Features
-- =====================================================

-- Features for Basic Plan (id=1)
INSERT INTO plan_features (plan_id, feature_key, feature_value, is_active) VALUES
(1, 'max_users', '3', TRUE),
(1, 'module_sales', 'true', TRUE),
(1, 'module_inventory', 'true', TRUE),
(1, 'module_customers', 'true', TRUE),
(1, 'module_reports_basic', 'true', TRUE),
(1, 'storage_limit_mb', '500', TRUE);

-- Features for Intermediate Plan (id=2)
INSERT INTO plan_features (plan_id, feature_key, feature_value, is_active) VALUES
(2, 'max_users', '10', TRUE),
(2, 'module_sales', 'true', TRUE),
(2, 'module_inventory', 'true', TRUE),
(2, 'module_customers', 'true', TRUE),
(2, 'module_suppliers', 'true', TRUE),
(2, 'module_quotes', 'true', TRUE),
(2, 'module_reports_advanced', 'true', TRUE),
(2, 'api_access_basic', 'true', TRUE),
(2, 'storage_limit_mb', '2000', TRUE),
(2, 'email_support', 'true', TRUE);

-- Features for Pro Plan (id=3)
INSERT INTO plan_features (plan_id, feature_key, feature_value, is_active) VALUES
(3, 'max_users', 'unlimited', TRUE),
(3, 'module_sales', 'true', TRUE),
(3, 'module_inventory', 'true', TRUE),
(3, 'module_customers', 'true', TRUE),
(3, 'module_suppliers', 'true', TRUE),
(3, 'module_quotes', 'true', TRUE),
(3, 'module_invoices', 'true', TRUE),
(3, 'module_reports_advanced', 'true', TRUE),
(3, 'module_analytics', 'true', TRUE),
(3, 'api_access_full', 'true', TRUE),
(3, 'storage_limit_mb', 'unlimited', TRUE),
(3, 'priority_support', 'true', TRUE),
(3, 'custom_branding', 'true', TRUE),
(3, 'multi_location', 'true', TRUE),
(3, 'advanced_permissions', 'true', TRUE);

-- =====================================================
-- DATA MIGRATION: Link existing subscriptions to plans
-- =====================================================

-- Update existing subscriptions to reference the new plan table
UPDATE tenant_subscriptions
SET plan_id = (
    CASE 
        WHEN plan_type = 'free' THEN 1   -- Basic plan
        WHEN plan_type = 'basic' THEN 1  -- Basic plan
        WHEN plan_type = 'pro' THEN 3    -- Pro plan
        ELSE 1                           -- Default to Basic
    END
)
WHERE plan_id IS NULL;

-- =====================================================
-- TRIGGERS: Auto-update updated_at timestamp
-- =====================================================

CREATE OR REPLACE FUNCTION update_plan_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_plan_timestamp
    BEFORE UPDATE ON plans
    FOR EACH ROW
    EXECUTE FUNCTION update_plan_updated_at();

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify tables were created
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_name IN ('plans', 'plan_features')
ORDER BY table_name;

-- Verify indexes were created
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('plans', 'plan_features', 'tenant_subscriptions')
AND indexname LIKE '%plan%'
ORDER BY tablename, indexname;

-- Show plans with feature count
SELECT 
    p.id,
    p.name,
    p.code,
    p.price,
    p.is_active,
    COUNT(pf.id) as feature_count
FROM plans p
LEFT JOIN plan_features pf ON p.id = pf.plan_id
GROUP BY p.id, p.name, p.code, p.price, p.is_active
ORDER BY p.price;

-- Show subscription migration status
SELECT 
    COUNT(*) as total_subscriptions,
    COUNT(plan_id) as linked_to_plan,
    COUNT(*) - COUNT(plan_id) as not_linked
FROM tenant_subscriptions;
