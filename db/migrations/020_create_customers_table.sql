CREATE TABLE IF NOT EXISTS customer (
    id BIGSERIAL PRIMARY KEY,
    tenant_id BIGINT NOT NULL,  -- CRÍTICO: El identificador de la empresa dueña del dato
    name VARCHAR(200) NOT NULL,
    tax_id VARCHAR(50),         -- CUIT/RUT/DNI
    email VARCHAR(255),
    phone VARCHAR(50),
    address TEXT,
    notes TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Restricción de Integridad Referencial (Aislamiento)
    CONSTRAINT fk_customer_tenant
        FOREIGN KEY (tenant_id)
        REFERENCES tenant(id)
        ON DELETE CASCADE
);

-- Índices de Performance y Seguridad
-- Indispensable para que las consultas siempre filtren por tenant_id rápidamente
CREATE INDEX idx_customer_tenant_id ON customer(tenant_id);

-- Opcional: Para buscar clientes rápidamente dentro de una empresa
CREATE INDEX idx_customer_search ON customer(tenant_id, name);
