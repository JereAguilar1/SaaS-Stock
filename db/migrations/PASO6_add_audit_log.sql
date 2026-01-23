-- PASO 6: Audit Log Table
-- Tracks critical user actions across all tenants
-- Run with: psql $DATABASE_URL -f db/migrations/PASO6_add_audit_log.sql

BEGIN;

-- Create audit_log table
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(50),
    resource_id INTEGER,
    details TEXT,  -- JSON or text with additional information
    ip_address VARCHAR(45),  -- IPv4 or IPv6
    user_agent VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant ON audit_log(tenant_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_tenant_created ON audit_log(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_resource ON audit_log(resource_type, resource_id);

-- Comments
COMMENT ON TABLE audit_log IS 'PASO 6: Audit trail for critical actions';
COMMENT ON COLUMN audit_log.action IS 'Action performed (e.g., USER_INVITED, SALE_CREATED)';
COMMENT ON COLUMN audit_log.resource_type IS 'Type of resource affected (e.g., product, sale)';
COMMENT ON COLUMN audit_log.resource_id IS 'ID of the affected resource';
COMMENT ON COLUMN audit_log.details IS 'Additional details in JSON format';

COMMIT;

-- Verify
SELECT 
    schemaname,
    tablename,
    indexname
FROM pg_indexes
WHERE tablename = 'audit_log'
ORDER BY indexname;

ECHO 'PASO 6: audit_log table created successfully';
