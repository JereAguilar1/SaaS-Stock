-- Add customer_id to sale table
ALTER TABLE sale
ADD COLUMN customer_id BIGINT;

-- Add foreign key constraint
ALTER TABLE sale
ADD CONSTRAINT fk_sale_customer
FOREIGN KEY (customer_id)
REFERENCES customer (id)
ON DELETE SET NULL;

-- Add index for performance
CREATE INDEX idx_sale_customer_id ON sale(customer_id);
