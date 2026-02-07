-- MEJORA 19: Product Features Table
-- Adds the table to store custom key-value specifications for products

BEGIN;

CREATE TABLE IF NOT EXISTS product_feature (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL REFERENCES tenant(id) ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id) ON DELETE CASCADE,
    title VARCHAR(100) NOT NULL,
    description VARCHAR(255) NOT NULL
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_product_feature_product ON product_feature(product_id);
CREATE INDEX IF NOT EXISTS idx_product_feature_tenant ON product_feature(tenant_id);

-- Descriptions
COMMENT ON TABLE product_feature IS 'Custom key-value specifications for products (e.g., Color: Red)';

COMMIT;
