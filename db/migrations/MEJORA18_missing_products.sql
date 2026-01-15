-- MEJORA 18: Missing Products Request Tracking
-- Allows tracking of products that customers request but are not in the system

BEGIN;

-- Create missing_product_request table
CREATE TABLE IF NOT EXISTS missing_product_request (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255) NOT NULL UNIQUE,
    request_count INTEGER NOT NULL DEFAULT 1 CHECK (request_count >= 0),
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'RESOLVED')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_requested_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_missing_product_status ON missing_product_request(status);
CREATE INDEX IF NOT EXISTS idx_missing_product_count_desc ON missing_product_request(request_count DESC);
CREATE INDEX IF NOT EXISTS idx_missing_product_last_requested_at ON missing_product_request(last_requested_at DESC);

-- Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION trg_missing_product_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS missing_product_set_updated_at ON missing_product_request;
CREATE TRIGGER missing_product_set_updated_at
    BEFORE UPDATE ON missing_product_request
    FOR EACH ROW
    EXECUTE FUNCTION trg_missing_product_set_updated_at();

COMMIT;

-- Sample queries for verification:
-- SELECT * FROM missing_product_request ORDER BY request_count DESC;
-- SELECT * FROM missing_product_request WHERE status = 'OPEN' ORDER BY request_count DESC;
