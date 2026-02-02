-- =====================================================
-- Admin Panel V2 - Subscriptions & Impersonation
-- Migration: ADMIN_PANEL_V2_SUBSCRIPTIONS.sql
-- =====================================================

-- =====================================================
-- TABLE: tenant_subscriptions
-- Purpose: Store subscription plans and status for each tenant
-- =====================================================

CREATE TABLE tenant_subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    
    -- Plan and Status
    plan_type VARCHAR(20) NOT NULL CHECK (plan_type IN ('free', 'basic', 'pro')),
    status VARCHAR(20) NOT NULL CHECK (status IN ('trial', 'active', 'past_due', 'canceled')),
    
    -- Dates
    trial_ends_at TIMESTAMP WITH TIME ZONE,
    current_period_end TIMESTAMP WITH TIME ZONE,
    
    -- Pricing
    amount DECIMAL(10, 2) DEFAULT 0.00,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(tenant_id)
);

-- Indexes for tenant_subscriptions
CREATE INDEX idx_subscriptions_tenant ON tenant_subscriptions(tenant_id);
CREATE INDEX idx_subscriptions_status ON tenant_subscriptions(status);
CREATE INDEX idx_subscriptions_plan ON tenant_subscriptions(plan_type);

-- Comments
COMMENT ON TABLE tenant_subscriptions IS 'Subscription plans and billing status for tenants';
COMMENT ON COLUMN tenant_subscriptions.plan_type IS 'Subscription plan: free, basic, or pro';
COMMENT ON COLUMN tenant_subscriptions.status IS 'Subscription status: trial, active, past_due, or canceled';
COMMENT ON COLUMN tenant_subscriptions.trial_ends_at IS 'When the trial period ends (if applicable)';
COMMENT ON COLUMN tenant_subscriptions.current_period_end IS 'End date of current billing period';

-- =====================================================
-- TABLE: tenant_payments
-- Purpose: Manual payment records for tenants
-- =====================================================

CREATE TABLE tenant_payments (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    
    -- Payment Details
    amount DECIMAL(10, 2) NOT NULL,
    payment_date DATE NOT NULL,
    reference VARCHAR(255),
    notes TEXT,
    
    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'paid' CHECK (status IN ('pending', 'paid')),
    
    -- Audit
    created_by BIGINT REFERENCES admin_users(id),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for tenant_payments
CREATE INDEX idx_payments_tenant ON tenant_payments(tenant_id);
CREATE INDEX idx_payments_date ON tenant_payments(payment_date DESC);
CREATE INDEX idx_payments_status ON tenant_payments(status);

-- Comments
COMMENT ON TABLE tenant_payments IS 'Manual payment records registered by admins';
COMMENT ON COLUMN tenant_payments.reference IS 'Payment reference number or transaction ID';
COMMENT ON COLUMN tenant_payments.created_by IS 'Admin user who registered this payment';

-- =====================================================
-- TABLE: admin_audit_logs
-- Purpose: Audit trail for all sensitive admin actions
-- =====================================================

CREATE TABLE admin_audit_logs (
    id BIGSERIAL PRIMARY KEY,
    
    -- Who
    admin_user_id BIGINT NOT NULL REFERENCES admin_users(id),
    
    -- What
    action VARCHAR(100) NOT NULL,
    
    -- Where (optional)
    target_tenant_id BIGINT REFERENCES tenant(id),
    
    -- Details
    details JSONB,
    
    -- Network
    ip_address VARCHAR(45),
    
    -- When
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for admin_audit_logs
CREATE INDEX idx_audit_admin ON admin_audit_logs(admin_user_id);
CREATE INDEX idx_audit_tenant ON admin_audit_logs(target_tenant_id);
CREATE INDEX idx_audit_action ON admin_audit_logs(action);
CREATE INDEX idx_audit_created ON admin_audit_logs(created_at DESC);

-- Comments
COMMENT ON TABLE admin_audit_logs IS 'Audit trail for all sensitive admin actions';
COMMENT ON COLUMN admin_audit_logs.action IS 'Action type: IMPERSONATION_START, IMPERSONATION_END, SUSPEND_TENANT, etc.';
COMMENT ON COLUMN admin_audit_logs.details IS 'Additional context in JSON format';
COMMENT ON COLUMN admin_audit_logs.ip_address IS 'IP address of the admin user';

-- =====================================================
-- INITIAL DATA: Create default subscriptions for existing tenants
-- =====================================================

-- Give all existing tenants a free trial subscription
INSERT INTO tenant_subscriptions (tenant_id, plan_type, status, trial_ends_at, current_period_end, amount)
SELECT 
    id,
    'free',
    'trial',
    NOW() + INTERVAL '30 days',
    NOW() + INTERVAL '30 days',
    0.00
FROM tenant
WHERE NOT EXISTS (
    SELECT 1 FROM tenant_subscriptions WHERE tenant_subscriptions.tenant_id = tenant.id
);

-- =====================================================
-- TRIGGERS: Auto-update updated_at timestamp
-- =====================================================

CREATE OR REPLACE FUNCTION update_subscription_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_subscription_timestamp
    BEFORE UPDATE ON tenant_subscriptions
    FOR EACH ROW
    EXECUTE FUNCTION update_subscription_updated_at();

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================

-- Verify tables were created
SELECT 
    table_name,
    (SELECT COUNT(*) FROM information_schema.columns WHERE table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'public' 
AND table_name IN ('tenant_subscriptions', 'tenant_payments', 'admin_audit_logs')
ORDER BY table_name;

-- Verify indexes were created
SELECT 
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
AND tablename IN ('tenant_subscriptions', 'tenant_payments', 'admin_audit_logs')
ORDER BY tablename, indexname;

-- Show subscription counts by status
SELECT 
    status,
    COUNT(*) as tenant_count
FROM tenant_subscriptions
GROUP BY status
ORDER BY status;
