-- ============================================================================
-- MEJORA 13: Presupuestos Persistidos (Quotes Module)
-- ============================================================================
-- Creates tables for quote management with conversion to sales

BEGIN;

-- -----------------------------------------------------------------------------
-- ENUM/CHECK for Quote Status
-- -----------------------------------------------------------------------------
-- Using CHECK constraint instead of ENUM for flexibility
-- Possible values: DRAFT, SENT, ACCEPTED, CANCELED

-- -----------------------------------------------------------------------------
-- TABLE: quote
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quote (
    id BIGSERIAL PRIMARY KEY,
    quote_number VARCHAR(64) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT',
    issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_until DATE,
    notes TEXT,
    payment_method VARCHAR(20),  -- CASH, TRANSFER (from MEJORA 12)
    total_amount NUMERIC(14,2) NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    sale_id BIGINT UNIQUE REFERENCES sale(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    CONSTRAINT chk_quote_status CHECK (status IN ('DRAFT', 'SENT', 'ACCEPTED', 'CANCELED')),
    CONSTRAINT chk_quote_payment_method CHECK (payment_method IS NULL OR payment_method IN ('CASH', 'TRANSFER')),
    CONSTRAINT chk_quote_accepted_has_sale CHECK (
        (status = 'ACCEPTED' AND sale_id IS NOT NULL) OR 
        (status != 'ACCEPTED')
    )
);

-- -----------------------------------------------------------------------------
-- TABLE: quote_line
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS quote_line (
    id BIGSERIAL PRIMARY KEY,
    quote_id BIGINT NOT NULL REFERENCES quote(id) ON UPDATE RESTRICT ON DELETE CASCADE,
    product_id BIGINT NOT NULL REFERENCES product(id) ON UPDATE RESTRICT ON DELETE RESTRICT,
    product_name_snapshot VARCHAR(200) NOT NULL,
    uom_snapshot VARCHAR(16),
    qty NUMERIC(12,3) NOT NULL CHECK (qty > 0),
    unit_price NUMERIC(14,2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(14,2) NOT NULL CHECK (line_total >= 0),
    
    CONSTRAINT chk_quote_line_total_consistency CHECK (line_total = round(qty * unit_price, 2))
);

-- -----------------------------------------------------------------------------
-- INDEXES
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_quote_number ON quote(quote_number);
CREATE INDEX IF NOT EXISTS idx_quote_status_issued ON quote(status, issued_at DESC);
CREATE INDEX IF NOT EXISTS idx_quote_sale_id ON quote(sale_id);
CREATE INDEX IF NOT EXISTS idx_quote_valid_until ON quote(valid_until);
CREATE INDEX IF NOT EXISTS idx_quote_line_quote_id ON quote_line(quote_id);
CREATE INDEX IF NOT EXISTS idx_quote_line_product_id ON quote_line(product_id);

-- -----------------------------------------------------------------------------
-- TRIGGER: auto-update updated_at on quote
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION trg_quote_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS quote_set_updated_at ON quote;
CREATE TRIGGER quote_set_updated_at
    BEFORE UPDATE ON quote
    FOR EACH ROW
    EXECUTE FUNCTION trg_quote_set_updated_at();

-- -----------------------------------------------------------------------------
-- COMMENTS
-- -----------------------------------------------------------------------------
COMMENT ON TABLE quote IS 'Presupuestos/cotizaciones que pueden convertirse a ventas';
COMMENT ON COLUMN quote.quote_number IS 'Número único de presupuesto (ej: PRES-20260112-153045-0001)';
COMMENT ON COLUMN quote.status IS 'Estado: DRAFT (creado), SENT (enviado), ACCEPTED (convertido a venta), CANCELED (cancelado)';
COMMENT ON COLUMN quote.valid_until IS 'Fecha hasta la cual el presupuesto es válido';
COMMENT ON COLUMN quote.payment_method IS 'Método de pago propuesto (puede ser NULL)';
COMMENT ON COLUMN quote.sale_id IS 'ID de la venta creada si fue convertido (ACCEPTED)';

COMMENT ON TABLE quote_line IS 'Líneas de presupuesto con snapshot de precios y nombres';
COMMENT ON COLUMN quote_line.product_name_snapshot IS 'Nombre del producto al momento del presupuesto';
COMMENT ON COLUMN quote_line.uom_snapshot IS 'Símbolo de UOM al momento del presupuesto';
COMMENT ON COLUMN quote_line.unit_price IS 'Precio unitario congelado al momento del presupuesto';

COMMIT;
