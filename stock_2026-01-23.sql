--
-- PostgreSQL database dump
--

\restrict kCxIb5M6MRz2SQm1OrbSOXPQwsDNJrg7WINa6vup8D8nWUUw3u6VdrJCcFWbswb

-- Dumped from database version 16.11 (Debian 16.11-1.pgdg13+1)
-- Dumped by pg_dump version 16.11 (Debian 16.11-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: invoice_status; Type: TYPE; Schema: public; Owner: ferreteria
--

CREATE TYPE public.invoice_status AS ENUM (
    'PENDING',
    'PAID'
);


ALTER TYPE public.invoice_status OWNER TO ferreteria;

--
-- Name: ledger_ref_type; Type: TYPE; Schema: public; Owner: ferreteria
--

CREATE TYPE public.ledger_ref_type AS ENUM (
    'SALE',
    'INVOICE_PAYMENT',
    'MANUAL'
);


ALTER TYPE public.ledger_ref_type OWNER TO ferreteria;

--
-- Name: ledger_type; Type: TYPE; Schema: public; Owner: ferreteria
--

CREATE TYPE public.ledger_type AS ENUM (
    'INCOME',
    'EXPENSE'
);


ALTER TYPE public.ledger_type OWNER TO ferreteria;

--
-- Name: sale_status; Type: TYPE; Schema: public; Owner: ferreteria
--

CREATE TYPE public.sale_status AS ENUM (
    'CONFIRMED',
    'CANCELLED'
);


ALTER TYPE public.sale_status OWNER TO ferreteria;

--
-- Name: stock_move_type; Type: TYPE; Schema: public; Owner: ferreteria
--

CREATE TYPE public.stock_move_type AS ENUM (
    'IN',
    'OUT',
    'ADJUST'
);


ALTER TYPE public.stock_move_type OWNER TO ferreteria;

--
-- Name: stock_ref_type; Type: TYPE; Schema: public; Owner: ferreteria
--

CREATE TYPE public.stock_ref_type AS ENUM (
    'SALE',
    'INVOICE',
    'MANUAL'
);


ALTER TYPE public.stock_ref_type OWNER TO ferreteria;

--
-- Name: apply_stock_delta(bigint, numeric); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.apply_stock_delta(p_product_id bigint, p_delta numeric) RETURNS void
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO product_stock(product_id, on_hand_qty, updated_at)
  VALUES (p_product_id, GREATEST(p_delta, 0), now())
  ON CONFLICT (product_id) DO UPDATE
    SET on_hand_qty = product_stock.on_hand_qty + EXCLUDED.on_hand_qty,
        updated_at  = now();

  -- If delta is negative, we must subtract (we handle separately to keep GREATEST logic simple)
  IF p_delta < 0 THEN
    UPDATE product_stock
      SET on_hand_qty = on_hand_qty + p_delta,
          updated_at  = now()
    WHERE product_id = p_product_id;

    -- Prevent negative stock at DB level
    IF (SELECT on_hand_qty FROM product_stock WHERE product_id = p_product_id) < 0 THEN
      RAISE EXCEPTION 'Stock would become negative for product_id %', p_product_id;
    END IF;
  END IF;
END;
$$;


ALTER FUNCTION public.apply_stock_delta(p_product_id bigint, p_delta numeric) OWNER TO ferreteria;

--
-- Name: check_single_base_uom(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.check_single_base_uom() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
    base_count INTEGER;
BEGIN
    -- Si se está marcando como base, desmarcar las demás del mismo producto
    IF NEW.is_base = true THEN
        UPDATE product_uom_price
        SET is_base = false
        WHERE product_id = NEW.product_id
          AND id != COALESCE(NEW.id, -1)  -- En INSERT, NEW.id es NULL, usa -1
          AND is_base = true;
    END IF;
    
    -- Validar que después de esta operación haya al menos una UOM base
    -- Contar cuántas UOMs base habrá después de esta operación
    
    IF TG_OP = 'INSERT' THEN
        -- En INSERT, contar las existentes + la nueva si es base
        SELECT COUNT(*) INTO base_count
        FROM product_uom_price
        WHERE product_id = NEW.product_id
          AND is_base = true;
        
        -- Si la nueva es base, sumar 1
        IF NEW.is_base = true THEN
            base_count := base_count + 1;
        END IF;
        
    ELSIF TG_OP = 'UPDATE' THEN
        -- En UPDATE, contar incluyendo el cambio actual
        SELECT COUNT(*) INTO base_count
        FROM product_uom_price
        WHERE product_id = NEW.product_id
          AND is_base = true
          AND id != NEW.id;  -- Excluir el registro actual
        
        -- Si el registro actual será base, sumar 1
        IF NEW.is_base = true THEN
            base_count := base_count + 1;
        END IF;
    END IF;
    
    -- Validar que haya al menos una base
    IF base_count = 0 THEN
        RAISE EXCEPTION 'El producto debe tener al menos una UOM base';
    END IF;
    
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.check_single_base_uom() OWNER TO ferreteria;

--
-- Name: chk_invoice_has_lines(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.chk_invoice_has_lines() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_count BIGINT;
BEGIN
  SELECT COUNT(*) INTO v_count FROM purchase_invoice_line WHERE invoice_id = NEW.id;
  IF v_count < 1 THEN
    RAISE EXCEPTION 'INVOICE % must have at least one purchase_invoice_line', NEW.id;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.chk_invoice_has_lines() OWNER TO ferreteria;

--
-- Name: chk_invoice_total_matches_lines(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.chk_invoice_total_matches_lines() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_sum NUMERIC(12,2);
BEGIN
  SELECT COALESCE(SUM(line_total), 0) INTO v_sum FROM purchase_invoice_line WHERE invoice_id = NEW.id;
  IF NEW.total_amount <> v_sum THEN
    RAISE EXCEPTION 'INVOICE % total_amount (%) does not match sum(lines) (%)', NEW.id, NEW.total_amount, v_sum;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.chk_invoice_total_matches_lines() OWNER TO ferreteria;

--
-- Name: chk_sale_has_lines(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.chk_sale_has_lines() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_count BIGINT;
BEGIN
  SELECT COUNT(*) INTO v_count FROM sale_line WHERE sale_id = NEW.id;
  IF v_count < 1 THEN
    RAISE EXCEPTION 'SALE % must have at least one sale_line', NEW.id;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.chk_sale_has_lines() OWNER TO ferreteria;

--
-- Name: chk_sale_total_matches_lines(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.chk_sale_total_matches_lines() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_sum NUMERIC(12,2);
BEGIN
  SELECT COALESCE(SUM(line_total), 0) INTO v_sum FROM sale_line WHERE sale_id = NEW.id;
  IF NEW.total <> v_sum THEN
    RAISE EXCEPTION 'SALE % total (%) does not match sum(lines) (%)', NEW.id, NEW.total, v_sum;
  END IF;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.chk_sale_total_matches_lines() OWNER TO ferreteria;

--
-- Name: trg_missing_product_set_updated_at(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.trg_missing_product_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.trg_missing_product_set_updated_at() OWNER TO ferreteria;

--
-- Name: trg_product_init_stock(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.trg_product_init_stock() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  INSERT INTO product_stock(product_id, on_hand_qty)
  VALUES (NEW.id, 0)
  ON CONFLICT (product_id) DO NOTHING;
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.trg_product_init_stock() OWNER TO ferreteria;

--
-- Name: trg_quote_set_updated_at(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.trg_quote_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION public.trg_quote_set_updated_at() OWNER TO ferreteria;

--
-- Name: trg_set_updated_at(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.trg_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.trg_set_updated_at() OWNER TO ferreteria;

--
-- Name: trg_stock_move_line_after_del(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.trg_stock_move_line_after_del() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_type stock_move_type;
  v_delta NUMERIC(12,3);
BEGIN
  SELECT type INTO v_type FROM stock_move WHERE id = OLD.stock_move_id;

  IF v_type = 'IN' THEN
    v_delta := -OLD.qty;
  ELSIF v_type = 'OUT' THEN
    v_delta := OLD.qty;
  ELSE
    v_delta := -OLD.qty;
  END IF;

  PERFORM apply_stock_delta(OLD.product_id, v_delta);
  RETURN OLD;
END;
$$;


ALTER FUNCTION public.trg_stock_move_line_after_del() OWNER TO ferreteria;

--
-- Name: trg_stock_move_line_after_ins(); Type: FUNCTION; Schema: public; Owner: ferreteria
--

CREATE FUNCTION public.trg_stock_move_line_after_ins() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE
  v_type stock_move_type;
  v_delta NUMERIC(12,3);
BEGIN
  SELECT type INTO v_type FROM stock_move WHERE id = NEW.stock_move_id;

  IF v_type = 'IN' THEN
    v_delta := NEW.qty;  -- IN: adds stock (positive qty)
  ELSIF v_type = 'OUT' THEN
    v_delta := -NEW.qty;  -- OUT: removes stock (negative delta from positive qty)
  ELSE
    -- ADJUST: qty is already signed (positive = add, negative = subtract)
    -- For corrections: if sold MORE -> qty is negative (reduce stock)
    --                  if sold LESS -> qty is positive (increase stock)
    v_delta := NEW.qty;  -- Use qty as-is (can be negative)
  END IF;

  PERFORM apply_stock_delta(NEW.product_id, v_delta);
  RETURN NEW;
END;
$$;


ALTER FUNCTION public.trg_stock_move_line_after_ins() OWNER TO ferreteria;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: category; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.category (
    id bigint NOT NULL,
    name character varying(120) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.category OWNER TO ferreteria;

--
-- Name: category_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.category_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.category_id_seq OWNER TO ferreteria;

--
-- Name: category_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.category_id_seq OWNED BY public.category.id;


--
-- Name: finance_ledger; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.finance_ledger (
    id bigint NOT NULL,
    datetime timestamp with time zone DEFAULT now() NOT NULL,
    type public.ledger_type NOT NULL,
    amount numeric(12,2) NOT NULL,
    category character varying(80),
    reference_type public.ledger_ref_type NOT NULL,
    reference_id bigint,
    notes text,
    payment_method character varying(20) DEFAULT 'CASH'::character varying NOT NULL,
    CONSTRAINT chk_finance_ledger_payment_method CHECK (((payment_method)::text = ANY ((ARRAY['CASH'::character varying, 'TRANSFER'::character varying])::text[]))),
    CONSTRAINT finance_ledger_amount_check CHECK ((amount >= (0)::numeric))
);


ALTER TABLE public.finance_ledger OWNER TO ferreteria;

--
-- Name: COLUMN finance_ledger.payment_method; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.finance_ledger.payment_method IS 'Método de pago: CASH (efectivo/caja física) o TRANSFER (transferencia bancaria). Permite separar flujos de caja vs banco.';


--
-- Name: finance_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.finance_ledger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.finance_ledger_id_seq OWNER TO ferreteria;

--
-- Name: finance_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.finance_ledger_id_seq OWNED BY public.finance_ledger.id;


--
-- Name: missing_product_request; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.missing_product_request (
    id bigint NOT NULL,
    name character varying(255) NOT NULL,
    normalized_name character varying(255) NOT NULL,
    request_count integer DEFAULT 1 NOT NULL,
    status character varying(20) DEFAULT 'OPEN'::character varying NOT NULL,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    last_requested_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT missing_product_request_request_count_check CHECK ((request_count >= 0)),
    CONSTRAINT missing_product_request_status_check CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'RESOLVED'::character varying])::text[])))
);


ALTER TABLE public.missing_product_request OWNER TO ferreteria;

--
-- Name: missing_product_request_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.missing_product_request_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.missing_product_request_id_seq OWNER TO ferreteria;

--
-- Name: missing_product_request_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.missing_product_request_id_seq OWNED BY public.missing_product_request.id;


--
-- Name: product; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.product (
    id bigint NOT NULL,
    sku character varying(64),
    barcode character varying(64),
    name character varying(200) NOT NULL,
    category_id bigint,
    uom_id bigint NOT NULL,
    active boolean DEFAULT true NOT NULL,
    sale_price numeric(12,2) NOT NULL,
    image_path character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    min_stock_qty numeric(12,2) DEFAULT 0 NOT NULL,
    CONSTRAINT chk_min_stock_qty_non_negative CHECK ((min_stock_qty >= (0)::numeric)),
    CONSTRAINT product_sale_price_check CHECK ((sale_price >= (0)::numeric))
);


ALTER TABLE public.product OWNER TO ferreteria;

--
-- Name: COLUMN product.min_stock_qty; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.product.min_stock_qty IS 'Stock mínimo requerido para el producto. Si on_hand_qty <= min_stock_qty, se considera "poco stock". Si es 0, no aplica umbral.';


--
-- Name: product_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.product_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.product_id_seq OWNER TO ferreteria;

--
-- Name: product_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.product_id_seq OWNED BY public.product.id;


--
-- Name: product_stock; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.product_stock (
    product_id bigint NOT NULL,
    on_hand_qty numeric(12,3) DEFAULT 0 NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT product_stock_on_hand_qty_check CHECK ((on_hand_qty >= (0)::numeric))
);


ALTER TABLE public.product_stock OWNER TO ferreteria;

--
-- Name: product_uom_price; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.product_uom_price (
    id bigint NOT NULL,
    product_id bigint NOT NULL,
    uom_id bigint NOT NULL,
    sale_price numeric(12,2) NOT NULL,
    conversion_to_base numeric(12,4) DEFAULT 1 NOT NULL,
    is_base boolean DEFAULT false NOT NULL,
    sku character varying(255),
    barcode character varying(255),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT product_uom_price_conversion_to_base_check CHECK ((conversion_to_base > (0)::numeric)),
    CONSTRAINT product_uom_price_sale_price_check CHECK ((sale_price >= (0)::numeric))
);


ALTER TABLE public.product_uom_price OWNER TO ferreteria;

--
-- Name: TABLE product_uom_price; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON TABLE public.product_uom_price IS 'Precios y UOMs por producto. Permite vender un producto en múltiples unidades.';


--
-- Name: COLUMN product_uom_price.conversion_to_base; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.product_uom_price.conversion_to_base IS 'Factor de conversión a la unidad base. Ej: 1 rollo = 100 metros → conversion_to_base = 100';


--
-- Name: COLUMN product_uom_price.is_base; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.product_uom_price.is_base IS 'Indica si esta es la UOM base del producto (solo una por producto debe ser true)';


--
-- Name: product_uom_price_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.product_uom_price_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.product_uom_price_id_seq OWNER TO ferreteria;

--
-- Name: product_uom_price_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.product_uom_price_id_seq OWNED BY public.product_uom_price.id;


--
-- Name: purchase_invoice; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.purchase_invoice (
    id bigint NOT NULL,
    supplier_id bigint NOT NULL,
    invoice_number character varying(80) NOT NULL,
    invoice_date date NOT NULL,
    due_date date,
    total_amount numeric(12,2) NOT NULL,
    status public.invoice_status DEFAULT 'PENDING'::public.invoice_status NOT NULL,
    paid_at date,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT invoice_paid_at_consistency CHECK ((((status = 'PAID'::public.invoice_status) AND (paid_at IS NOT NULL)) OR ((status = 'PENDING'::public.invoice_status) AND (paid_at IS NULL)))),
    CONSTRAINT purchase_invoice_total_amount_check CHECK ((total_amount >= (0)::numeric))
);


ALTER TABLE public.purchase_invoice OWNER TO ferreteria;

--
-- Name: purchase_invoice_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.purchase_invoice_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_invoice_id_seq OWNER TO ferreteria;

--
-- Name: purchase_invoice_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.purchase_invoice_id_seq OWNED BY public.purchase_invoice.id;


--
-- Name: purchase_invoice_line; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.purchase_invoice_line (
    id bigint NOT NULL,
    invoice_id bigint NOT NULL,
    product_id bigint NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_cost numeric(12,4) NOT NULL,
    line_total numeric(12,2) NOT NULL,
    CONSTRAINT invoice_line_total_consistency CHECK ((line_total = round((qty * unit_cost), 2))),
    CONSTRAINT purchase_invoice_line_line_total_check CHECK ((line_total >= (0)::numeric)),
    CONSTRAINT purchase_invoice_line_qty_check CHECK ((qty > (0)::numeric)),
    CONSTRAINT purchase_invoice_line_unit_cost_check CHECK ((unit_cost >= (0)::numeric))
);


ALTER TABLE public.purchase_invoice_line OWNER TO ferreteria;

--
-- Name: purchase_invoice_line_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.purchase_invoice_line_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_invoice_line_id_seq OWNER TO ferreteria;

--
-- Name: purchase_invoice_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.purchase_invoice_line_id_seq OWNED BY public.purchase_invoice_line.id;


--
-- Name: purchase_invoice_payment; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.purchase_invoice_payment (
    id bigint NOT NULL,
    invoice_id bigint NOT NULL,
    paid_at date NOT NULL,
    amount numeric(12,2) NOT NULL,
    notes character varying(500),
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT purchase_invoice_payment_amount_check CHECK ((amount > (0)::numeric))
);


ALTER TABLE public.purchase_invoice_payment OWNER TO ferreteria;

--
-- Name: TABLE purchase_invoice_payment; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON TABLE public.purchase_invoice_payment IS 'Pagos parciales de boletas de compra. Permite adelantos y pagos en cuotas.';


--
-- Name: COLUMN purchase_invoice_payment.invoice_id; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.purchase_invoice_payment.invoice_id IS 'Referencia a la boleta que se está pagando';


--
-- Name: COLUMN purchase_invoice_payment.paid_at; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.purchase_invoice_payment.paid_at IS 'Fecha en que se realizó el pago (puede ser distinta a created_at)';


--
-- Name: COLUMN purchase_invoice_payment.amount; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.purchase_invoice_payment.amount IS 'Monto del pago parcial. Debe ser > 0 y <= saldo pendiente';


--
-- Name: purchase_invoice_payment_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.purchase_invoice_payment_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.purchase_invoice_payment_id_seq OWNER TO ferreteria;

--
-- Name: purchase_invoice_payment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.purchase_invoice_payment_id_seq OWNED BY public.purchase_invoice_payment.id;


--
-- Name: quote; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.quote (
    id bigint NOT NULL,
    quote_number character varying(64) NOT NULL,
    status character varying(20) DEFAULT 'DRAFT'::character varying NOT NULL,
    issued_at timestamp with time zone DEFAULT now() NOT NULL,
    valid_until date,
    notes text,
    payment_method character varying(20),
    total_amount numeric(14,2) DEFAULT 0 NOT NULL,
    sale_id bigint,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    customer_name character varying(255) NOT NULL,
    customer_phone character varying(50),
    CONSTRAINT chk_quote_accepted_has_sale CHECK (((((status)::text = 'ACCEPTED'::text) AND (sale_id IS NOT NULL)) OR ((status)::text <> 'ACCEPTED'::text))),
    CONSTRAINT chk_quote_payment_method CHECK (((payment_method IS NULL) OR ((payment_method)::text = ANY ((ARRAY['CASH'::character varying, 'TRANSFER'::character varying])::text[])))),
    CONSTRAINT chk_quote_status CHECK (((status)::text = ANY ((ARRAY['DRAFT'::character varying, 'SENT'::character varying, 'ACCEPTED'::character varying, 'CANCELED'::character varying])::text[]))),
    CONSTRAINT quote_total_amount_check CHECK ((total_amount >= (0)::numeric))
);


ALTER TABLE public.quote OWNER TO ferreteria;

--
-- Name: TABLE quote; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON TABLE public.quote IS 'Presupuestos/cotizaciones que pueden convertirse a ventas';


--
-- Name: COLUMN quote.quote_number; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.quote_number IS 'Número único de presupuesto (ej: PRES-20260112-153045-0001)';


--
-- Name: COLUMN quote.status; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.status IS 'Estado: DRAFT (creado), SENT (enviado), ACCEPTED (convertido a venta), CANCELED (cancelado)';


--
-- Name: COLUMN quote.valid_until; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.valid_until IS 'Fecha hasta la cual el presupuesto es válido';


--
-- Name: COLUMN quote.payment_method; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.payment_method IS 'Método de pago propuesto (puede ser NULL)';


--
-- Name: COLUMN quote.sale_id; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.sale_id IS 'ID de la venta creada si fue convertido (ACCEPTED)';


--
-- Name: COLUMN quote.customer_name; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.customer_name IS 'Nombre del cliente (snapshot, no FK)';


--
-- Name: COLUMN quote.customer_phone; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote.customer_phone IS 'Teléfono del cliente (opcional)';


--
-- Name: quote_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.quote_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.quote_id_seq OWNER TO ferreteria;

--
-- Name: quote_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.quote_id_seq OWNED BY public.quote.id;


--
-- Name: quote_line; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.quote_line (
    id bigint NOT NULL,
    quote_id bigint NOT NULL,
    product_id bigint NOT NULL,
    product_name_snapshot character varying(200) NOT NULL,
    uom_snapshot character varying(16),
    qty numeric(12,3) NOT NULL,
    unit_price numeric(14,2) NOT NULL,
    line_total numeric(14,2) NOT NULL,
    CONSTRAINT chk_quote_line_total_consistency CHECK ((line_total = round((qty * unit_price), 2))),
    CONSTRAINT quote_line_line_total_check CHECK ((line_total >= (0)::numeric)),
    CONSTRAINT quote_line_qty_check CHECK ((qty > (0)::numeric)),
    CONSTRAINT quote_line_unit_price_check CHECK ((unit_price >= (0)::numeric))
);


ALTER TABLE public.quote_line OWNER TO ferreteria;

--
-- Name: TABLE quote_line; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON TABLE public.quote_line IS 'Líneas de presupuesto con snapshot de precios y nombres';


--
-- Name: COLUMN quote_line.product_name_snapshot; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote_line.product_name_snapshot IS 'Nombre del producto al momento del presupuesto';


--
-- Name: COLUMN quote_line.uom_snapshot; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote_line.uom_snapshot IS 'Símbolo de UOM al momento del presupuesto';


--
-- Name: COLUMN quote_line.unit_price; Type: COMMENT; Schema: public; Owner: ferreteria
--

COMMENT ON COLUMN public.quote_line.unit_price IS 'Precio unitario congelado al momento del presupuesto';


--
-- Name: quote_line_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.quote_line_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.quote_line_id_seq OWNER TO ferreteria;

--
-- Name: quote_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.quote_line_id_seq OWNED BY public.quote_line.id;


--
-- Name: sale; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.sale (
    id bigint NOT NULL,
    datetime timestamp with time zone DEFAULT now() NOT NULL,
    total numeric(12,2) NOT NULL,
    status public.sale_status DEFAULT 'CONFIRMED'::public.sale_status NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT sale_total_check CHECK ((total >= (0)::numeric))
);


ALTER TABLE public.sale OWNER TO ferreteria;

--
-- Name: sale_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.sale_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sale_id_seq OWNER TO ferreteria;

--
-- Name: sale_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.sale_id_seq OWNED BY public.sale.id;


--
-- Name: sale_line; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.sale_line (
    id bigint NOT NULL,
    sale_id bigint NOT NULL,
    product_id bigint NOT NULL,
    qty numeric(12,3) NOT NULL,
    unit_price numeric(12,2) NOT NULL,
    line_total numeric(12,2) NOT NULL,
    uom_id bigint NOT NULL,
    CONSTRAINT sale_line_line_total_check CHECK ((line_total >= (0)::numeric)),
    CONSTRAINT sale_line_qty_check CHECK ((qty > (0)::numeric)),
    CONSTRAINT sale_line_total_consistency CHECK ((line_total = round((qty * unit_price), 2))),
    CONSTRAINT sale_line_unit_price_check CHECK ((unit_price >= (0)::numeric))
);


ALTER TABLE public.sale_line OWNER TO ferreteria;

--
-- Name: sale_line_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.sale_line_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sale_line_id_seq OWNER TO ferreteria;

--
-- Name: sale_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.sale_line_id_seq OWNED BY public.sale_line.id;


--
-- Name: stock_move; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.stock_move (
    id bigint NOT NULL,
    date timestamp with time zone DEFAULT now() NOT NULL,
    type public.stock_move_type NOT NULL,
    reference_type public.stock_ref_type NOT NULL,
    reference_id bigint,
    notes text
);


ALTER TABLE public.stock_move OWNER TO ferreteria;

--
-- Name: stock_move_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.stock_move_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stock_move_id_seq OWNER TO ferreteria;

--
-- Name: stock_move_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.stock_move_id_seq OWNED BY public.stock_move.id;


--
-- Name: stock_move_line; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.stock_move_line (
    id bigint NOT NULL,
    stock_move_id bigint NOT NULL,
    product_id bigint NOT NULL,
    qty numeric(12,3) NOT NULL,
    uom_id bigint NOT NULL,
    unit_cost numeric(12,4),
    CONSTRAINT stock_move_line_qty_check CHECK ((qty <> (0)::numeric)),
    CONSTRAINT stock_move_line_unit_cost_check CHECK ((unit_cost >= (0)::numeric))
);


ALTER TABLE public.stock_move_line OWNER TO ferreteria;

--
-- Name: stock_move_line_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.stock_move_line_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.stock_move_line_id_seq OWNER TO ferreteria;

--
-- Name: stock_move_line_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.stock_move_line_id_seq OWNED BY public.stock_move_line.id;


--
-- Name: supplier; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.supplier (
    id bigint NOT NULL,
    name character varying(200) NOT NULL,
    tax_id character varying(64),
    phone character varying(64),
    email character varying(200),
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.supplier OWNER TO ferreteria;

--
-- Name: supplier_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.supplier_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.supplier_id_seq OWNER TO ferreteria;

--
-- Name: supplier_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.supplier_id_seq OWNED BY public.supplier.id;


--
-- Name: uom; Type: TABLE; Schema: public; Owner: ferreteria
--

CREATE TABLE public.uom (
    id bigint NOT NULL,
    name character varying(80) NOT NULL,
    symbol character varying(16) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.uom OWNER TO ferreteria;

--
-- Name: uom_id_seq; Type: SEQUENCE; Schema: public; Owner: ferreteria
--

CREATE SEQUENCE public.uom_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.uom_id_seq OWNER TO ferreteria;

--
-- Name: uom_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: ferreteria
--

ALTER SEQUENCE public.uom_id_seq OWNED BY public.uom.id;


--
-- Name: category id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.category ALTER COLUMN id SET DEFAULT nextval('public.category_id_seq'::regclass);


--
-- Name: finance_ledger id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.finance_ledger ALTER COLUMN id SET DEFAULT nextval('public.finance_ledger_id_seq'::regclass);


--
-- Name: missing_product_request id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.missing_product_request ALTER COLUMN id SET DEFAULT nextval('public.missing_product_request_id_seq'::regclass);


--
-- Name: product id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product ALTER COLUMN id SET DEFAULT nextval('public.product_id_seq'::regclass);


--
-- Name: product_uom_price id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_uom_price ALTER COLUMN id SET DEFAULT nextval('public.product_uom_price_id_seq'::regclass);


--
-- Name: purchase_invoice id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice ALTER COLUMN id SET DEFAULT nextval('public.purchase_invoice_id_seq'::regclass);


--
-- Name: purchase_invoice_line id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_line ALTER COLUMN id SET DEFAULT nextval('public.purchase_invoice_line_id_seq'::regclass);


--
-- Name: purchase_invoice_payment id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_payment ALTER COLUMN id SET DEFAULT nextval('public.purchase_invoice_payment_id_seq'::regclass);


--
-- Name: quote id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote ALTER COLUMN id SET DEFAULT nextval('public.quote_id_seq'::regclass);


--
-- Name: quote_line id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote_line ALTER COLUMN id SET DEFAULT nextval('public.quote_line_id_seq'::regclass);


--
-- Name: sale id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale ALTER COLUMN id SET DEFAULT nextval('public.sale_id_seq'::regclass);


--
-- Name: sale_line id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale_line ALTER COLUMN id SET DEFAULT nextval('public.sale_line_id_seq'::regclass);


--
-- Name: stock_move id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move ALTER COLUMN id SET DEFAULT nextval('public.stock_move_id_seq'::regclass);


--
-- Name: stock_move_line id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move_line ALTER COLUMN id SET DEFAULT nextval('public.stock_move_line_id_seq'::regclass);


--
-- Name: supplier id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.supplier ALTER COLUMN id SET DEFAULT nextval('public.supplier_id_seq'::regclass);


--
-- Name: uom id; Type: DEFAULT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.uom ALTER COLUMN id SET DEFAULT nextval('public.uom_id_seq'::regclass);


--
-- Data for Name: category; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.category (id, name, created_at) FROM stdin;
1	Herramienta electrica	2026-01-13 21:39:41.866389+00
2	Herramientas manuales	2026-01-13 21:40:55.898548+00
3	Pintura y accesorios	2026-01-13 21:41:15.336654+00
4	Electricidad	2026-01-13 21:41:26.355861+00
5	Plomeria	2026-01-13 21:41:35.183548+00
6	BULONERA	2026-01-13 23:00:49.94726+00
7	JARDINERIA	2026-01-13 23:21:39.811347+00
8	PERSONALES	2026-01-14 22:26:13.136176+00
9	LIMPIEZA	2026-01-14 22:36:29.878667+00
10	PEGAMENTO	2026-01-14 22:57:49.62572+00
11	LUBRICANTES	2026-01-14 23:01:24.543438+00
12	VENENO	2026-01-14 23:25:38.214527+00
\.


--
-- Data for Name: finance_ledger; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.finance_ledger (id, datetime, type, amount, category, reference_type, reference_id, notes, payment_method) FROM stdin;
1	2026-01-14 14:29:40.828492+00	INCOME	8500.00	Ventas	SALE	6	Ingreso por venta #6	CASH
2	2026-01-14 21:50:08.928204+00	INCOME	41400.00	Ventas	SALE	7	Ingreso por venta #7	CASH
3	2026-01-14 22:17:46.084116+00	EXPENSE	869533.00	\N	INVOICE_PAYMENT	3	Pago boleta #13194 - MATELEC	CASH
4	2026-01-15 21:35:09.625099+00	INCOME	2000.00	Ventas	SALE	8	Ingreso por venta #8	CASH
5	2026-01-16 23:51:53.796551+00	INCOME	3000.00	Ventas	SALE	9	Ingreso por venta #9	CASH
6	2026-01-16 23:51:53.92361+00	INCOME	3000.00	Ventas	SALE	10	Ingreso por venta #10	CASH
7	2026-01-17 14:26:39.945139+00	INCOME	3000.00	Ventas	SALE	11	Ingreso por venta #11	CASH
8	2026-01-17 15:07:22.322094+00	INCOME	18000.00	Ventas	SALE	12	Ingreso por venta #12	CASH
9	2026-01-17 15:25:15.706344+00	INCOME	3700.00	Ventas	SALE	13	Ingreso por venta #13	TRANSFER
10	2026-01-17 18:21:03.414431+00	INCOME	8000.00	Ventas	SALE	14	Ingreso por venta #14	CASH
11	2026-01-17 20:54:36.191421+00	EXPENSE	13860.00	\N	INVOICE_PAYMENT	14	Pago boleta #2909 - PAULO OLGUIN	CASH
12	2026-01-17 21:47:01.700367+00	INCOME	3400.00	Ventas	SALE	15	Ingreso por venta #15	CASH
13	2026-01-17 21:56:03.661802+00	INCOME	3440.00	Ventas	SALE	16	Ingreso por venta #16	CASH
14	2026-01-17 22:01:59.01922+00	INCOME	5300.00	Ventas	SALE	17	Ingreso por venta #17	CASH
15	2026-01-17 22:14:09.84524+00	INCOME	3860.00	Ventas	SALE	18	Ingreso por venta #18	TRANSFER
16	2026-01-17 22:31:37.456424+00	INCOME	1020.00	Ventas	SALE	19	Ingreso por venta #19	CASH
17	2026-01-17 22:32:49.352393+00	INCOME	1300.00	Ventas	SALE	20	Ingreso por venta #20	CASH
18	2026-01-17 22:53:41.600544+00	INCOME	2000.00	Ventas	SALE	21	Ingreso por venta #21	CASH
19	2026-01-17 22:58:26.631131+00	INCOME	19000.00	Ventas	SALE	22	Ingreso por venta #22	CASH
20	2026-01-17 22:59:48.075431+00	INCOME	7000.00	Ventas	SALE	23	Ingreso por venta #23	CASH
21	2026-01-17 23:30:05.07328+00	INCOME	9000.00	Ventas	SALE	24	Ingreso por venta #24	CASH
22	2026-01-17 23:34:41.859531+00	INCOME	8650.00	Ventas	SALE	25	Ingreso por venta #25	CASH
23	2026-01-17 23:40:35.657806+00	INCOME	8000.00	Ventas	SALE	26	Ingreso por venta #26	CASH
24	2026-01-18 00:08:29.351518+00	INCOME	4100.00	Ventas	SALE	27	Ingreso por venta #27	TRANSFER
25	2026-01-18 13:04:23.621438+00	INCOME	5650.00	Ventas	SALE	28	Ingreso por venta #28	CASH
26	2026-01-18 13:13:39.197074+00	INCOME	1500.00	Ventas	SALE	29	Ingreso por venta #29	CASH
27	2026-01-18 13:14:32.27499+00	INCOME	1500.00	Ventas	SALE	30	Ingreso por venta #30	CASH
28	2026-01-18 13:19:19.875405+00	INCOME	6700.00	Ventas	SALE	31	Ingreso por venta #31	TRANSFER
29	2026-01-18 13:25:44.546091+00	INCOME	750.00	Ventas	SALE	32	Ingreso por venta #32	CASH
30	2026-01-18 13:48:08.353596+00	INCOME	16000.00	Ventas	SALE	33	Ingreso por venta #33	CASH
31	2026-01-18 13:50:03.932027+00	INCOME	5650.00	Ventas	SALE	34	Ingreso por venta #34	CASH
32	2026-01-18 13:58:30.836945+00	INCOME	1800.00	Ventas	SALE	35	Ingreso por venta #35	CASH
33	2026-01-18 14:05:44.801334+00	INCOME	120.00	Ventas	SALE	36	Ingreso por venta #36	CASH
34	2026-01-18 14:09:51.99147+00	INCOME	22850.00	Ventas	SALE	37	Ingreso por venta #37	TRANSFER
35	2026-01-18 14:15:00.478897+00	INCOME	6500.00	Ventas	SALE	38	Ingreso por venta #38	CASH
36	2026-01-18 14:35:40.920029+00	INCOME	3000.00	Ventas	SALE	39	Ingreso por venta #39	TRANSFER
37	2026-01-18 14:40:53.244319+00	INCOME	3000.00	Ventas	SALE	40	Ingreso por venta #40	CASH
38	2026-01-18 14:46:35.942275+00	INCOME	2000.00	Ventas	SALE	41	Ingreso por venta #41	CASH
39	2026-01-18 14:52:27.74884+00	INCOME	7800.00	Ventas	SALE	42	Ingreso por venta #42	TRANSFER
40	2026-01-18 14:56:00.464842+00	INCOME	4500.00	Ventas	SALE	43	Ingreso por venta #43	CASH
41	2026-01-18 15:08:35.577749+00	INCOME	5250.00	Ventas	SALE	44	Ingreso por venta #44	CASH
42	2026-01-18 15:08:57.024393+00	INCOME	200.00	Ventas	SALE	45	Ingreso por venta #45	CASH
43	2026-01-18 15:10:05.039516+00	INCOME	16000.00	Ventas	SALE	46	Ingreso por venta #46	CASH
44	2026-01-18 15:19:26.536279+00	INCOME	9000.00	Ventas	SALE	47	Ingreso por venta #47	CASH
45	2026-01-18 15:24:36.719318+00	INCOME	4240.00	Ventas	SALE	48	Ingreso por venta #48	CASH
46	2026-01-18 15:30:56.953605+00	INCOME	1350.00	Ventas	SALE	49	Ingreso por venta #49	CASH
47	2026-01-18 15:33:45.898195+00	INCOME	5850.00	Ventas	SALE	50	Ingreso por venta #50	CASH
48	2026-01-18 15:56:52.114442+00	INCOME	12875.00	Ventas	SALE	51	Ingreso por venta #51	CASH
49	2026-01-18 15:59:36.909958+00	INCOME	380.00	Ventas	SALE	52	Ingreso por venta #52	CASH
50	2026-01-18 16:13:35.773929+00	INCOME	3100.00	Ventas	SALE	53	Ingreso por venta #53	TRANSFER
51	2026-01-18 16:22:33.446828+00	INCOME	2000.00	Ventas	SALE	54	Ingreso por venta #54	CASH
52	2026-01-18 16:31:25.677375+00	INCOME	1500.00	Ventas	SALE	55	Ingreso por venta #55	CASH
53	2026-01-18 16:34:24.608762+00	INCOME	4150.00	Ventas	SALE	56	Ingreso por venta #56	CASH
54	2026-01-18 16:36:02.130314+00	INCOME	2150.00	Ventas	SALE	57	Ingreso por venta #57	CASH
55	2026-01-18 16:58:16.212823+00	INCOME	4200.00	Ventas	SALE	58	Ingreso por venta #58	CASH
56	2026-01-18 16:59:28.217075+00	INCOME	9500.00	Ventas	SALE	59	Ingreso por venta #59	CASH
57	2026-01-18 17:24:37.934765+00	INCOME	17700.00	Ventas	SALE	60	Ingreso por venta #60	TRANSFER
58	2026-01-18 17:26:15.312577+00	INCOME	2100.00	Ventas	SALE	61	Ingreso por venta #61	CASH
59	2026-01-18 17:40:00.706179+00	INCOME	300.00	Ventas	SALE	62	Ingreso por venta #62	CASH
60	2026-01-18 17:41:39.424225+00	INCOME	3700.00	Ventas	SALE	63	Ingreso por venta #63	CASH
61	2026-01-18 17:43:27.593593+00	INCOME	34900.00	Ventas	SALE	64	Ingreso por venta #64	TRANSFER
62	2026-01-18 17:47:16.414444+00	INCOME	15300.00	Ventas	SALE	65	Ingreso por venta #65	TRANSFER
63	2026-01-18 17:54:12.458315+00	INCOME	16300.00	Ventas	SALE	66	Ingreso por venta #66	TRANSFER
64	2026-01-18 17:54:26.52102+00	INCOME	10950.00	Ventas	SALE	67	Ingreso por venta #67	CASH
65	2026-01-18 17:57:12.076857+00	INCOME	22150.00	Ventas	SALE	68	Ingreso por venta #68	TRANSFER
66	2026-01-18 18:06:50.093093+00	INCOME	2500.00	Ventas	SALE	69	Ingreso por venta #69	CASH
67	2026-01-18 18:20:59.502862+00	INCOME	3480.00	Ventas	SALE	70	Ingreso por venta #70	TRANSFER
68	2026-01-18 18:24:11.057424+00	INCOME	29870.00	Ventas	SALE	71	Ingreso por venta #71	TRANSFER
69	2026-01-18 18:46:02.044287+00	INCOME	3000.00	Ventas	SALE	72	Ingreso por venta #72	TRANSFER
70	2026-01-18 18:51:01.550267+00	INCOME	200.00	Ventas	SALE	73	Ingreso por venta #73	CASH
71	2026-01-18 18:51:17.611065+00	INCOME	1500.00	Ventas	SALE	74	Ingreso por venta #74	CASH
72	2026-01-18 19:17:54.571761+00	INCOME	760.00	Ventas	SALE	75	Ingreso por venta #75	CASH
73	2026-01-18 19:19:05.928371+00	INCOME	200.00	Ventas	SALE	76	Ingreso por venta #76	CASH
74	2026-01-19 20:50:08.694588+00	INCOME	43450.00	Ventas	SALE	77	Ingreso por venta #77	CASH
75	2026-01-19 20:50:41.609335+00	INCOME	3000.00	Ventas	SALE	78	Ingreso por venta #78	CASH
76	2026-01-19 20:54:52.840755+00	INCOME	4160.00	Ventas	SALE	79	Ingreso por venta #79	CASH
78	2026-01-19 20:59:13.68466+00	INCOME	600.00	Ventas	SALE	81	Ingreso por venta #81	CASH
80	2026-01-19 21:06:30.595827+00	INCOME	2160.00	Ventas	SALE	83	Ingreso por venta #83	CASH
82	2026-01-19 21:18:27.250875+00	INCOME	1000.00	Ventas	SALE	85	Ingreso por venta #85	CASH
83	2026-01-19 21:23:39.05344+00	INCOME	200.00	Ventas	SALE	86	Ingreso por venta #86	CASH
86	2026-01-19 21:33:43.399114+00	INCOME	13400.00	Ventas	SALE	89	Ingreso por venta #89	CASH
88	2026-01-19 21:43:30.799335+00	INCOME	3300.00	Ventas	SALE	91	Ingreso por venta #91	CASH
89	2026-01-19 21:55:30.713555+00	INCOME	56500.00	Ventas	SALE	92	Ingreso por venta #92	TRANSFER
91	2026-01-19 22:39:07.306764+00	INCOME	1500.00	Ventas	SALE	94	Ingreso por venta #94	CASH
92	2026-01-19 22:40:27.078354+00	INCOME	2000.00	Ventas	SALE	95	Ingreso por venta #95	CASH
94	2026-01-19 22:44:49.571712+00	INCOME	8100.00	Ventas	SALE	97	Ingreso por venta #97	CASH
96	2026-01-19 22:47:23.557105+00	INCOME	800.00	Ventas	SALE	99	Ingreso por venta #99	CASH
97	2026-01-19 22:47:40.189724+00	INCOME	600.00	Ventas	SALE	100	Ingreso por venta #100	CASH
98	2026-01-19 23:06:31.307821+00	INCOME	3400.00	Ventas	SALE	101	Ingreso por venta #101	TRANSFER
100	2026-01-19 23:19:24.28102+00	INCOME	240.00	Ventas	SALE	103	Ingreso por venta #103	CASH
103	2026-01-19 23:33:35.797095+00	INCOME	6400.00	Ventas	SALE	106	Ingreso por venta #106	CASH
104	2026-01-19 23:41:09.436806+00	INCOME	12300.00	Ventas	SALE	107	Ingreso por venta #107	TRANSFER
105	2026-01-19 23:44:58.852224+00	INCOME	6500.00	Ventas	SALE	108	Ingreso por venta #108	CASH
106	2026-01-19 23:59:50.978083+00	INCOME	5000.00	Ventas	SALE	109	Ingreso por venta #109	CASH
77	2026-01-19 20:58:38.317847+00	INCOME	36500.00	Ventas	SALE	80	Ingreso por venta #80	TRANSFER
79	2026-01-19 21:03:47.721478+00	INCOME	1600.00	Ventas	SALE	82	Ingreso por venta #82	CASH
81	2026-01-19 21:17:43.157106+00	INCOME	3600.00	Ventas	SALE	84	Ingreso por venta #84	CASH
84	2026-01-19 21:28:45.107051+00	INCOME	8800.00	Ventas	SALE	87	Ingreso por venta #87	TRANSFER
85	2026-01-19 21:29:44.546608+00	INCOME	9600.00	Ventas	SALE	88	Ingreso por venta #88	CASH
87	2026-01-19 21:38:14.991791+00	INCOME	1020.00	Ventas	SALE	90	Ingreso por venta #90	CASH
90	2026-01-19 22:38:28.073079+00	INCOME	7000.00	Ventas	SALE	93	Ingreso por venta #93	CASH
93	2026-01-19 22:41:36.455155+00	INCOME	21550.00	Ventas	SALE	96	Ingreso por venta #96	CASH
95	2026-01-19 22:46:24.279771+00	INCOME	7500.00	Ventas	SALE	98	Ingreso por venta #98	CASH
99	2026-01-19 23:11:06.186293+00	INCOME	6000.00	Ventas	SALE	102	Ingreso por venta #102	TRANSFER
101	2026-01-19 23:25:13.106+00	INCOME	1500.00	Ventas	SALE	104	Ingreso por venta #104	CASH
102	2026-01-19 23:30:04.248217+00	INCOME	9000.00	Ventas	SALE	105	Ingreso por venta #105	CASH
107	2026-01-20 19:08:24.045159+00	INCOME	6350.00	Ventas	SALE	110	Ingreso por venta #110	CASH
108	2026-01-20 20:15:23.28495+00	INCOME	2700.00	Ventas	SALE	111	Ingreso por venta #111	CASH
109	2026-01-20 20:18:19.014453+00	INCOME	6000.00	Ventas	SALE	112	Ingreso por venta #112	CASH
110	2026-01-20 20:21:14.543874+00	INCOME	4400.00	Ventas	SALE	113	Ingreso por venta #113	CASH
111	2026-01-20 20:23:46.494301+00	INCOME	10000.00	Ventas	SALE	114	Ingreso por venta #114	CASH
112	2026-01-20 20:38:25.798805+00	INCOME	4600.00	Ventas	SALE	115	Ingreso por venta #115	CASH
113	2026-01-20 20:43:29.770676+00	INCOME	53950.00	Ventas	SALE	116	Ingreso por venta #116	CASH
114	2026-01-20 20:47:22.234285+00	INCOME	15050.00	Ventas	SALE	117	Ingreso por venta #117	CASH
115	2026-01-20 20:50:34.994212+00	INCOME	3200.00	Ventas	SALE	118	Ingreso por venta #118	CASH
116	2026-01-20 20:53:50.634655+00	INCOME	200.00	Ventas	SALE	119	Ingreso por venta #119	CASH
117	2026-01-20 21:14:52.992526+00	INCOME	330.00	Ventas	SALE	120	Ingreso por venta #120	CASH
118	2026-01-20 21:15:28.649738+00	INCOME	2000.00	Ventas	SALE	121	Ingreso por venta #121	CASH
119	2026-01-20 21:15:54.66576+00	INCOME	1000.00	Ventas	SALE	122	Ingreso por venta #122	CASH
120	2026-01-20 21:17:23.380835+00	INCOME	1000.00	Ventas	SALE	123	Ingreso por venta #123	CASH
121	2026-01-20 21:22:49.248877+00	INCOME	3400.00	Ventas	SALE	124	Ingreso por venta #124	CASH
122	2026-01-20 21:27:37.09357+00	INCOME	6600.00	Ventas	SALE	125	Ingreso por venta #125	CASH
123	2026-01-20 21:42:38.024064+00	INCOME	30200.00	Ventas	SALE	126	Ingreso por venta #126	TRANSFER
124	2026-01-20 22:56:36.213348+00	INCOME	16200.00	Ventas	SALE	127	Ingreso por venta #127	CASH
125	2026-01-20 22:58:16.033506+00	INCOME	2630.00	Ventas	SALE	128	Ingreso por venta #128	TRANSFER
126	2026-01-20 23:15:38.60457+00	INCOME	3400.00	Ventas	SALE	129	Ingreso por venta #129	CASH
127	2026-01-20 23:31:20.859794+00	INCOME	3400.00	Ventas	SALE	130	Ingreso por venta #130	CASH
128	2026-01-20 23:43:20.169924+00	INCOME	7260.00	Ventas	SALE	131	Ingreso por venta #131	CASH
129	2026-01-20 23:51:05.059009+00	INCOME	1480.00	Ventas	SALE	132	Ingreso por venta #132	CASH
130	2026-01-21 00:25:19.642234+00	INCOME	6000.00	Ventas	SALE	133	Ingreso por venta #133	TRANSFER
131	2026-01-21 12:58:52.923426+00	INCOME	2500.00	Ventas	SALE	134	Ingreso por venta #134	CASH
132	2026-01-21 12:59:14.401285+00	INCOME	2000.00	Ventas	SALE	135	Ingreso por venta #135	CASH
133	2026-01-21 13:04:16.769554+00	INCOME	10000.00	Ventas	SALE	136	Ingreso por venta #136	CASH
134	2026-01-21 13:40:59.641669+00	INCOME	6300.00	Ventas	SALE	137	Ingreso por venta #137	TRANSFER
135	2026-01-21 19:32:58.29025+00	INCOME	1750.00	Ventas	SALE	138	Ingreso por venta #138	CASH
136	2026-01-21 20:28:06.889314+00	INCOME	3300.00	Ventas	SALE	139	Ingreso por venta #139	TRANSFER
137	2026-01-21 20:42:34.383287+00	INCOME	3000.00	Ventas	SALE	140	Ingreso por venta #140	TRANSFER
138	2026-01-21 20:50:57.415837+00	INCOME	1250.00	Ventas	SALE	141	Ingreso por venta #141	CASH
139	2026-01-21 21:29:40.424101+00	INCOME	17900.00	Ventas	SALE	142	Ingreso por venta #142	CASH
140	2026-01-21 21:30:21.28069+00	INCOME	4400.00	Ventas	SALE	143	Ingreso por venta #143	TRANSFER
141	2026-01-21 21:30:44.444037+00	INCOME	4500.00	Ventas	SALE	144	Ingreso por venta #144	CASH
142	2026-01-21 21:32:44.476307+00	INCOME	2400.00	Ventas	SALE	145	Ingreso por venta #145	CASH
143	2026-01-21 21:37:54.434297+00	INCOME	7500.00	Ventas	SALE	146	Ingreso por venta #146	TRANSFER
144	2026-01-21 21:38:14.592488+00	INCOME	2800.00	Ventas	SALE	147	Ingreso por venta #147	CASH
145	2026-01-21 21:38:51.48316+00	INCOME	200.00	Ventas	SALE	148	Ingreso por venta #148	CASH
146	2026-01-21 21:39:29.799398+00	INCOME	4750.00	Ventas	SALE	149	Ingreso por venta #149	CASH
147	2026-01-21 21:40:01.846891+00	INCOME	12600.00	Ventas	SALE	150	Ingreso por venta #150	CASH
148	2026-01-21 21:40:46.952822+00	INCOME	6000.00	Ventas	SALE	151	Ingreso por venta #151	CASH
149	2026-01-21 21:41:58.353591+00	INCOME	2500.00	Ventas	SALE	152	Ingreso por venta #152	CASH
150	2026-01-21 21:42:37.426656+00	INCOME	11600.00	Ventas	SALE	153	Ingreso por venta #153	CASH
151	2026-01-21 21:48:44.328343+00	INCOME	16160.00	Ventas	SALE	154	Ingreso por venta #154	CASH
152	2026-01-21 22:04:03.306832+00	INCOME	7000.00	Ventas	SALE	155	Ingreso por venta #155	CASH
153	2026-01-21 22:09:40.2994+00	INCOME	5600.00	Ventas	SALE	156	Ingreso por venta #156	CASH
154	2026-01-21 22:10:23.767444+00	INCOME	4240.00	Ventas	SALE	157	Ingreso por venta #157	TRANSFER
155	2026-01-21 22:59:39.775541+00	INCOME	5000.00	Ventas	SALE	158	Ingreso por venta #158	CASH
156	2026-01-21 22:59:50.078064+00	INCOME	1500.00	Ventas	SALE	159	Ingreso por venta #159	CASH
157	2026-01-21 23:13:04.132864+00	INCOME	2650.00	Ventas	SALE	160	Ingreso por venta #160	CASH
158	2026-01-21 23:13:39.447735+00	INCOME	8000.00	Ventas	SALE	161	Ingreso por venta #161	CASH
159	2026-01-21 23:32:38.413124+00	INCOME	1250.00	Ventas	SALE	162	Ingreso por venta #162	CASH
160	2026-01-21 23:44:02.491098+00	INCOME	14650.00	Ventas	SALE	163	Ingreso por venta #163	TRANSFER
161	2026-01-21 23:44:33.346753+00	INCOME	3300.00	Ventas	SALE	164	Ingreso por venta #164	CASH
162	2026-01-21 23:46:41.081062+00	INCOME	9500.00	Ventas	SALE	165	Ingreso por venta #165	CASH
163	2026-01-22 00:12:47.642945+00	INCOME	25000.00	Ventas	SALE	166	Ingreso por venta #166	CASH
164	2026-01-22 00:52:50.567734+00	INCOME	13750.00	Ventas	SALE	167	Ingreso por venta #167	CASH
165	2026-01-22 00:54:06.082084+00	INCOME	4000.00	Ventas	SALE	168	Ingreso por venta #168	CASH
166	2026-01-22 19:59:22.00583+00	INCOME	21600.00	Ventas	SALE	169	Ingreso por venta #169	TRANSFER
167	2026-01-22 19:59:50.832884+00	INCOME	2100.00	Ventas	SALE	170	Ingreso por venta #170	TRANSFER
168	2026-01-22 20:01:04.965596+00	INCOME	5000.00	Ventas	SALE	171	Ingreso por venta #171	CASH
169	2026-01-22 20:04:04.064326+00	INCOME	600.00	Ventas	SALE	172	Ingreso por venta #172	CASH
170	2026-01-22 20:14:42.733985+00	INCOME	1400.00	Ventas	SALE	173	Ingreso por venta #173	CASH
171	2026-01-22 20:15:27.841926+00	INCOME	3750.00	Ventas	SALE	174	Ingreso por venta #174	CASH
172	2026-01-22 20:17:29.367414+00	INCOME	6000.00	Ventas	SALE	175	Ingreso por venta #175	CASH
173	2026-01-22 21:45:16.986776+00	INCOME	4650.00	Ventas	SALE	176	Ingreso por venta #176	CASH
174	2026-01-22 21:47:59.737257+00	INCOME	600.00	Ventas	SALE	177	Ingreso por venta #177	CASH
175	2026-01-22 22:09:19.099517+00	INCOME	17300.00	Ventas	SALE	178	Ingreso por venta #178	CASH
176	2026-01-22 22:29:32.401772+00	INCOME	400.00	Ventas	SALE	179	Ingreso por venta #179	CASH
177	2026-01-22 22:30:14.065922+00	EXPENSE	316449.00	\N	INVOICE_PAYMENT	8	Pago boleta #3349 - LA ROSA	CASH
178	2026-01-22 22:30:55.031969+00	EXPENSE	38988.00	\N	INVOICE_PAYMENT	18	Pago boleta #3361 - LA ROSA	CASH
179	2026-01-22 22:32:20.248038+00	INCOME	2000.00	Ventas	SALE	180	Ingreso por venta #180	CASH
180	2026-01-22 22:36:54.83852+00	INCOME	8035.00	Ventas	SALE	181	Ingreso por venta #181	CASH
181	2026-01-22 22:42:15.478441+00	INCOME	6500.00	Ventas	SALE	182	Ingreso por venta #182	CASH
182	2026-01-22 22:43:22.701432+00	INCOME	6000.00	Ventas	SALE	183	Ingreso por venta #183	CASH
183	2026-01-22 22:43:45.553947+00	INCOME	400.00	Ventas	SALE	184	Ingreso por venta #184	CASH
184	2026-01-22 22:44:09.91406+00	INCOME	6000.00	Ventas	SALE	185	Ingreso por venta #185	CASH
185	2026-01-22 22:44:35.630548+00	INCOME	3750.00	Ventas	SALE	186	Ingreso por venta #186	CASH
186	2026-01-22 22:45:06.617506+00	INCOME	2000.00	Ventas	SALE	187	Ingreso por venta #187	CASH
187	2026-01-22 22:46:02.49627+00	INCOME	15150.00	Ventas	SALE	188	Ingreso por venta #188	CASH
188	2026-01-22 22:46:31.022149+00	INCOME	6000.00	Ventas	SALE	189	Ingreso por venta #189	CASH
189	2026-01-22 22:50:59.472371+00	INCOME	1875.00	Ventas	SALE	190	Ingreso por venta #190	CASH
190	2026-01-22 22:56:33.586263+00	INCOME	4500.00	Ventas	SALE	191	Ingreso por venta #191	CASH
191	2026-01-22 22:59:19.819271+00	INCOME	2000.00	Ventas	SALE	192	Ingreso por venta #192	CASH
192	2026-01-22 23:28:28.854306+00	INCOME	4800.00	Ventas	SALE	193	Ingreso por venta #193	CASH
193	2026-01-22 23:41:47.630006+00	INCOME	19550.00	Ventas	SALE	194	Ingreso por venta #194	TRANSFER
194	2026-01-22 23:52:02.633747+00	INCOME	5000.00	Ventas	SALE	195	Ingreso por venta #195	CASH
195	2026-01-23 00:25:05.69243+00	EXPENSE	109248.00	\N	INVOICE_PAYMENT	20	Pago boleta #2921 - PAULO OLGUIN	CASH
196	2026-01-23 00:26:44.88193+00	INCOME	1500.00	Ventas	SALE	196	Ingreso por venta #196	CASH
197	2026-01-23 01:00:28.904283+00	INCOME	21600.00	Ventas	SALE	197	Ingreso por venta #197	CASH
198	2026-01-23 01:02:08.871018+00	INCOME	27500.00	Ventas	SALE	198	Ingreso por venta #198	CASH
199	2026-01-23 01:03:06.90195+00	INCOME	3200.00	Ventas	SALE	199	Ingreso por venta #199	CASH
200	2026-01-23 01:03:53.146088+00	INCOME	7650.00	Ventas	SALE	200	Ingreso por venta #200	CASH
\.


--
-- Data for Name: missing_product_request; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.missing_product_request (id, name, normalized_name, request_count, status, notes, created_at, updated_at, last_requested_at) FROM stdin;
1	Veneno para mosca (pump)	veneno para mosca (pump)	2	RESOLVED	\N	2026-01-13 21:27:04.572686+00	2026-01-20 23:12:24.698515+00	2026-01-13 21:27:29.341385+00
\.


--
-- Data for Name: product; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.product (id, sku, barcode, name, category_id, uom_id, active, sale_price, image_path, created_at, updated_at, min_stock_qty) FROM stdin;
1	\N	\N	ABRAZADERA BANDA 12MM	\N	1	t	1500.00	\N	2026-01-13 21:09:43.435809+00	2026-01-13 21:38:41.535331+00	10.00
2	None	None	BORDEADORA TRAMONTINA	1	1	t	115200.00	\N	2026-01-13 21:18:34.665506+00	2026-01-13 21:40:05.721888+00	0.00
3	\N	\N	MARTILLO BOLITA 113GRS MANGO FIBRA	2	1	t	10750.00	\N	2026-01-13 21:20:04.274746+00	2026-01-13 21:42:16.345442+00	0.00
4	\N	\N	MARTILLO BOLITA 113GRS MANGO MADERA	2	1	t	8500.00	\N	2026-01-13 21:20:43.830058+00	2026-01-13 21:42:28.855557+00	0.00
5	\N	\N	MARTILLO BOLITA 450GRS MANGO FIBRA	2	1	t	10750.00	\N	2026-01-13 21:21:21.031438+00	2026-01-13 21:42:40.308044+00	0.00
6	\N	\N	MARTILLO BOLITA 450GRS MANGO MADERA	2	1	t	15150.00	\N	2026-01-13 21:21:57.582736+00	2026-01-13 21:43:03.465749+00	0.00
8	\N	\N	TORNILLO PUNTA AGUJA T4 6 X 5/8	6	1	t	10.00	\N	2026-01-13 23:07:07.25178+00	2026-01-13 23:07:07.25178+00	0.00
9	\N	\N	TORNILLO PUNTA AGUJA 6 X 3/4	6	1	t	10.00	\N	2026-01-13 23:08:30.419255+00	2026-01-13 23:08:30.419255+00	0.00
11	\N	\N	TORNILLO TANQUE 1/4 X 3	6	1	t	290.00	\N	2026-01-13 23:11:11.45146+00	2026-01-13 23:11:11.45146+00	0.00
12	\N	\N	TORNILLO TANQUE 5/16 x 3	6	1	t	430.00	\N	2026-01-13 23:11:49.252394+00	2026-01-13 23:11:49.252394+00	0.00
13	\N	\N	LLANA DENTADA	2	1	t	10500.00	\N	2026-01-13 23:12:52.496617+00	2026-01-13 23:12:52.496617+00	0.00
14	\N	\N	CLAVOS PARIS 1¨X 100 GRS	6	3	t	900.00	\N	2026-01-13 23:16:41.318667+00	2026-01-13 23:16:41.318667+00	0.00
15	\N	\N	CLAVOS PARIS 1 1/2´ X 100 GRS	6	3	t	900.00	\N	2026-01-13 23:17:43.28346+00	2026-01-13 23:17:43.28346+00	0.00
16	\N	\N	CLAVOS PARIS 2" 1/2  X 100 GRS	6	3	t	900.00	\N	2026-01-13 23:18:24.813317+00	2026-01-13 23:18:24.813317+00	0.00
17	\N	\N	ADAPTADOR PARA PICO CANILLA  1/2 PLASTICO	7	1	t	2000.00	\N	2026-01-13 23:22:16.140654+00	2026-01-13 23:22:16.140654+00	0.00
10	\N	\N	TORNILLO TANQUE 1/4 X 2	6	1	t	170.00	\N	2026-01-13 23:09:54.433575+00	2026-01-13 23:22:36.516649+00	0.00
18	\N	\N	CLAVO DE CABEZA DE  PLOMO 2 1/2"	6	1	t	95.00	\N	2026-01-13 23:24:45.867721+00	2026-01-13 23:24:45.867721+00	0.00
19	\N	\N	CLAVO DE CABEZA DE  PLOMO 3"	6	1	t	100.00	\N	2026-01-13 23:25:25.800114+00	2026-01-13 23:25:25.800114+00	0.00
20	\N	\N	CLAVO DE CABEZA DE  PLOMO 4"	6	1	t	125.00	\N	2026-01-13 23:26:06.988713+00	2026-01-13 23:26:06.988713+00	0.00
7	\N	\N	TORNILLO FIX 4 X 60MM	6	1	t	45.00	\N	2026-01-13 23:06:03.28906+00	2026-01-13 23:35:40.570374+00	0.00
21	\N	\N	CABLECANAL 20X10X2000	4	1	t	3600.00	\N	2026-01-13 23:38:44.388631+00	2026-01-13 23:38:44.388631+00	0.00
22	\N	\N	BUSCAPOLO	4	1	t	3000.00	\N	2026-01-13 23:39:33.263595+00	2026-01-13 23:39:33.263595+00	0.00
23	\N	\N	CABLECANAL 14x7x2000	4	1	t	2900.00	\N	2026-01-13 23:40:52.901499+00	2026-01-13 23:40:52.901499+00	0.00
24	\N	\N	CABLECANAL 40X16X2000	4	1	t	11600.00	\N	2026-01-13 23:42:09.146833+00	2026-01-13 23:42:09.146833+00	0.00
25	\N	\N	CABLECANAL 27X30X2000	4	1	t	11900.00	\N	2026-01-13 23:43:06.124936+00	2026-01-13 23:43:06.124936+00	0.00
26	\N	\N	TUBO LUZ PVC RIGIDO	4	1	t	3000.00	\N	2026-01-13 23:44:33.111475+00	2026-01-13 23:44:33.111475+00	0.00
27	\N	\N	CURVA PARA CAÑO PVC 20MM	4	1	t	550.00	\N	2026-01-13 23:45:40.682611+00	2026-01-13 23:45:40.682611+00	0.00
28	\N	\N	CONECTOR PARA TUBO DE PVC 20MM	4	1	t	250.00	\N	2026-01-13 23:47:25.679391+00	2026-01-13 23:47:25.679391+00	0.00
29	\N	\N	UNION PARA TUBO PVC 20MM	4	1	t	200.00	\N	2026-01-13 23:48:19.509204+00	2026-01-13 23:48:19.509204+00	0.00
30	\N	\N	RIEL DIN PARA TERMICA 35CM X  10CM ZINCADO	4	5	t	2200.00	\N	2026-01-13 23:50:34.788804+00	2026-01-13 23:50:34.788804+00	0.00
31	\N	\N	RIEL DIN VARILLA 35MM X 1M	4	5	t	12150.00	\N	2026-01-13 23:51:40.355303+00	2026-01-13 23:51:40.355303+00	0.00
32	\N	\N	CURVA PARA TUBO PVC 25MM	4	1	t	750.00	\N	2026-01-13 23:52:59.577225+00	2026-01-13 23:52:59.577225+00	0.00
33	\N	\N	CAÑO CORRUGADO 3/4 BLANCO	4	5	t	500.00	\N	2026-01-13 23:54:24.402667+00	2026-01-13 23:54:24.402667+00	0.00
34	\N	\N	CAÑO CORRUGADO 1"	4	5	t	750.00	\N	2026-01-13 23:55:16.867673+00	2026-01-13 23:55:16.867673+00	0.00
35	\N	\N	CAJA MIGNON 5X5 PVC/CHAPA	4	1	t	500.00	\N	2026-01-13 23:59:10.925907+00	2026-01-13 23:59:10.925907+00	0.00
36	\N	\N	CAJA RECTANGULAR PVC/CHAPA 5 X 10	4	1	t	450.00	\N	2026-01-14 00:02:27.601774+00	2026-01-14 00:02:27.601774+00	0.00
37	\N	\N	TAPA PLASTICA PARA CAJA RECTANGULAR 5 X 10	4	1	t	600.00	\N	2026-01-14 00:04:40.963037+00	2026-01-14 00:04:40.963037+00	0.00
38	\N	\N	TAPA CIEGA PARA CAJA MIGNON 5 X 5	4	1	t	600.00	\N	2026-01-14 00:05:46.107609+00	2026-01-14 00:05:46.107609+00	0.00
39	\N	\N	TAPA CIEGA PRESION OCTOGONAL	4	1	t	200.00	\N	2026-01-14 00:06:53.793552+00	2026-01-14 00:06:53.793552+00	0.00
40	\N	\N	PORTALAMPARA	4	1	t	1750.00	\N	2026-01-14 00:07:50.241586+00	2026-01-14 00:07:50.241586+00	0.00
41	\N	\N	INTERRUPTOR DIFERENCIAL 2X25A	4	1	t	43000.00	\N	2026-01-14 00:09:21.953793+00	2026-01-14 00:09:21.953793+00	0.00
42	\N	\N	TIRA LED LUZ BLANCA	4	5	t	6000.00	\N	2026-01-14 00:11:55.789764+00	2026-01-14 00:11:55.789764+00	0.00
43	\N	\N	CAÑO PLASTICO FLEXIBLE AZUL DE LUZ 3/4	4	5	t	500.00	\N	2026-01-14 00:13:49.225633+00	2026-01-14 00:13:49.225633+00	0.00
44	\N	\N	LAMPARA LED 15 W	4	1	t	3400.00	\N	2026-01-14 00:14:34.63193+00	2026-01-14 00:14:34.63193+00	0.00
46	\N	\N	LAMPARA LED ALTA 25 W	4	1	t	4900.00	\N	2026-01-14 00:17:22.781974+00	2026-01-14 00:17:22.781974+00	0.00
47	\N	\N	LAMPARA LED ALTA 45 W	4	1	t	10500.00	\N	2026-01-14 00:19:38.237937+00	2026-01-14 00:19:38.237937+00	0.00
48	\N	\N	PORTALAMPARA GRANDE	4	1	t	10350.00	\N	2026-01-14 00:21:36.646268+00	2026-01-14 00:21:36.646268+00	0.00
49	\N	\N	ZAPATILLA 4 TOMA C/CABLE 1,5 MTR	4	1	t	12750.00	\N	2026-01-14 00:22:48.233851+00	2026-01-14 00:22:48.233851+00	0.00
50	\N	\N	LLAVE PUNTO Y TOMA 5 X 10	4	1	t	6000.00	\N	2026-01-14 00:24:34.464382+00	2026-01-14 00:24:34.464382+00	0.00
51	\N	\N	TOMA DOBLE 5 X 10 BLANCO	4	1	t	6800.00	\N	2026-01-14 00:25:58.588134+00	2026-01-14 00:25:58.588134+00	0.00
52	\N	\N	MODULO TOMA	4	1	t	2150.00	\N	2026-01-14 00:28:31.338758+00	2026-01-14 00:28:31.338758+00	0.00
53	\N	\N	TAPON CIEGO BLANCO	4	1	t	270.00	\N	2026-01-14 00:29:34.934043+00	2026-01-14 00:29:34.934043+00	0.00
54	\N	\N	TAPA CIEGA PARA BASTIDOR 5 X 10	4	1	t	1500.00	\N	2026-01-14 00:30:41.564041+00	2026-01-14 00:30:41.564041+00	0.00
55	\N	\N	TOMA DOBLE CON BASTIDOR INCORPORADO	4	1	t	4800.00	\N	2026-01-14 00:31:59.828412+00	2026-01-14 00:31:59.828412+00	0.00
56	\N	\N	TAPA 3 MODULOS BLANCA	4	1	t	1000.00	\N	2026-01-14 00:32:46.53255+00	2026-01-14 00:32:46.53255+00	0.00
57	\N	\N	CAMPANILLA EXTERIOR	4	1	t	34150.00	\N	2026-01-14 00:34:04.727659+00	2026-01-14 00:34:04.727659+00	0.00
58	\N	\N	CINTA AISLADORA  15MM	4	1	t	1500.00	\N	2026-01-14 00:36:46.295705+00	2026-01-14 00:36:46.295705+00	0.00
59	\N	\N	CINTA AUTOSOLDABLE 4,57M	4	1	t	4100.00	\N	2026-01-14 00:37:38.995512+00	2026-01-14 00:37:38.995512+00	0.00
60	\N	\N	PROLONGACION PARA CALEFON 2M	4	1	t	5600.00	\N	2026-01-14 00:38:42.454364+00	2026-01-14 00:38:42.454364+00	0.00
62	\N	\N	FICHA VELADOR	4	1	t	1250.00	\N	2026-01-14 00:41:22.892209+00	2026-01-14 00:41:22.892209+00	0.00
64	\N	\N	PILA ENERGIZER AA	4	1	t	1750.00	\N	2026-01-14 22:24:58.874349+00	2026-01-14 22:24:58.874349+00	5.00
65	\N	\N	ENCENDEDOR	8	1	t	500.00	\N	2026-01-14 22:29:14.728331+00	2026-01-14 22:29:14.728331+00	5.00
66	\N	\N	SOPLADOR DE AIRE STARDOM INALAMBRICO	1	1	t	61150.00	\N	2026-01-14 22:33:58.254084+00	2026-01-14 22:33:58.254084+00	5.00
61	\N	\N	FICHA ENCHUFE KALOP	4	1	t	1850.00	\N	2026-01-14 00:40:09.538537+00	2026-01-21 23:48:10.427302+00	10.00
45	\N	\N	LAMPARA LED 6W BOMBITA	4	1	t	2500.00	\N	2026-01-14 00:16:22.245615+00	2026-01-21 23:53:53.373075+00	5.00
67	\N	\N	ESPUMA LIMPIATAPIZADO	9	1	t	6000.00	\N	2026-01-14 22:37:54.752774+00	2026-01-14 22:37:54.752774+00	3.00
68	\N	\N	SILICONA MULTIUSO EN AEROSOL	9	1	t	8000.00	\N	2026-01-14 22:43:00.345737+00	2026-01-14 22:43:00.345737+00	3.00
69	\N	\N	CHISPERO	8	1	t	3000.00	\N	2026-01-14 22:49:58.736612+00	2026-01-14 22:49:58.736612+00	3.00
70	\N	\N	SERRUCHO 20 "	2	1	t	9950.00	\N	2026-01-14 22:53:33.533644+00	2026-01-14 22:53:33.533644+00	1.00
71	\N	\N	UNIPOX 25ML	10	1	t	3300.00	\N	2026-01-14 22:58:18.973213+00	2026-01-14 22:58:18.973213+00	3.00
73	\N	\N	WD-40 220 GRS FLEXI TAPA	11	1	t	17200.00	\N	2026-01-14 23:03:50.396616+00	2026-01-14 23:03:50.396616+00	1.00
74	\N	\N	FASTIX EXTERIOR 290 GRS	10	1	t	21500.00	\N	2026-01-14 23:04:46.588656+00	2026-01-14 23:04:46.588656+00	1.00
75	\N	\N	EL PULPITO 400 GRS. TUBO APLICADOR	10	1	t	29000.00	\N	2026-01-14 23:05:33.495873+00	2026-01-14 23:05:33.495873+00	0.00
76	\N	\N	CEBO PARA CARACOL 100 GRS BABOTOX	12	1	t	3500.00	\N	2026-01-14 23:28:24.392199+00	2026-01-14 23:28:24.392199+00	2.00
78	\N	\N	CEBO PARA CARACOL 200 GRS BABOTOX	12	1	t	4800.00	\N	2026-01-14 23:39:07.084631+00	2026-01-14 23:39:07.084631+00	0.00
79	\N	\N	LIJA ANTIEMPASTE 400 GR	3	1	t	1550.00	\N	2026-01-14 23:39:54.145644+00	2026-01-14 23:40:16.090925+00	5.00
80	\N	\N	LIJA ANTIEMPASTE 320 GR	3	1	t	1550.00	\N	2026-01-14 23:43:28.404123+00	2026-01-14 23:43:28.404123+00	0.00
81	\N	\N	LIJA ANTIEMPASTE 220 GR	3	1	t	1000.00	\N	2026-01-14 23:47:32.229666+00	2026-01-14 23:47:32.229666+00	5.00
82	\N	\N	LIJA ANTIEMPASTE 180 GR	3	1	t	1000.00	\N	2026-01-14 23:50:32.381689+00	2026-01-14 23:50:32.381689+00	5.00
84	\N	\N	CEPILLOS COPA ACERO BRONCEADO ONDULADO 75MM	3	1	t	11150.00	\N	2026-01-15 00:08:41.799044+00	2026-01-15 00:08:41.799044+00	1.00
85	\N	\N	AEROSOL KUWit 440	3	1	t	8000.00	\N	2026-01-15 00:09:37.875699+00	2026-01-15 00:09:37.875699+00	0.00
86	\N	\N	ULTRA GRANO PLUS 50 GRS RATA	12	1	t	3000.00	\N	2026-01-15 00:11:41.100128+00	2026-01-15 00:12:20.190761+00	4.00
87	\N	\N	HORMIGUICIDA GRANO X 250 GRS	12	1	t	5500.00	\N	2026-01-15 00:14:04.66582+00	2026-01-15 00:14:04.66582+00	1.00
88	\N	\N	HORMIGUICIDA GRANO X 100 GRS	12	1	t	2600.00	\N	2026-01-15 00:14:29.328743+00	2026-01-15 00:14:29.328743+00	2.00
89	\N	\N	CEPILLOS CONICO ACERO BRONCEADO ONDULADO 75MM	3	1	t	18500.00	\N	2026-01-15 00:16:12.834861+00	2026-01-15 00:16:12.834861+00	1.00
90	\N	\N	DISCO ABRASIVO 115X1	3	1	t	1500.00	\N	2026-01-15 00:18:11.994143+00	2026-01-15 00:18:11.994143+00	5.00
91	\N	\N	VALVULA METALICA 1/2	5	1	t	7700.00	\N	2026-01-15 00:19:59.243092+00	2026-01-15 00:19:59.243092+00	1.00
92	\N	\N	CODO ESPIGA-ROSCA HEMBRA 1/2	5	1	t	500.00	\N	2026-01-15 00:21:08.689846+00	2026-01-15 00:21:08.689846+00	5.00
93	\N	\N	ZAPATILLA 4 TOMA C/CABLE 5 MTR	4	1	t	23900.00	\N	2026-01-15 00:22:18.142881+00	2026-01-15 00:22:18.142881+00	1.00
94	\N	\N	LATEX INTERIOR/EXTERIOR BLANCO 1L	3	1	t	7500.00	\N	2026-01-15 21:30:55.118892+00	2026-01-15 21:31:20.215662+00	2.00
96	\N	\N	PINTURA PARA CIELORRASO 1L	3	1	t	6550.00	\N	2026-01-15 21:49:42.400078+00	2026-01-15 21:49:42.400078+00	1.00
97	\N	\N	LATEX INTERIOR/EXTERIOR BLANCO 4L	3	1	t	25450.00	\N	2026-01-15 21:50:39.95321+00	2026-01-15 21:50:39.95321+00	1.00
95	\N	\N	LATEX INTERIOR/EXTERIOR BLANCO 20L	3	1	t	117600.00	\N	2026-01-15 21:48:48.695547+00	2026-01-15 21:55:30.695431+00	1.00
98	\N	\N	LATEX INTERIOR/EXTERIOR X 10L	3	1	t	59990.00	\N	2026-01-15 21:56:28.584991+00	2026-01-15 21:56:28.584991+00	1.00
99	\N	\N	ENDUIDO INTERIOR 1L	3	1	t	5400.00	\N	2026-01-15 21:59:39.570451+00	2026-01-15 21:59:39.570451+00	1.00
101	\N	\N	ACIDO MURIATICO 1L	9	1	t	3000.00	\N	2026-01-15 23:22:15.59638+00	2026-01-15 23:22:15.59638+00	2.00
102	\N	\N	AGUARRAZ 1L	3	1	t	3750.00	\N	2026-01-15 23:26:19.768635+00	2026-01-15 23:26:19.768635+00	5.00
103	\N	\N	THINNER 1L	3	1	t	5650.00	\N	2026-01-15 23:33:39.882892+00	2026-01-15 23:33:39.882892+00	5.00
104	\N	\N	AGUA DESTILADA 1L	9	1	t	1500.00	\N	2026-01-15 23:46:20.303519+00	2026-01-15 23:46:20.303519+00	5.00
105	\N	\N	ENTONADOR UNIVERSAL 120CC	3	1	t	8750.00	\N	2026-01-15 23:55:18.666545+00	2026-01-15 23:55:18.666545+00	1.00
106	\N	\N	ENTONADOR UNIVERSAL 30CC	3	1	t	2950.00	\N	2026-01-15 23:56:00.299977+00	2026-01-15 23:56:00.299977+00	5.00
107	\N	\N	PISTOLA SILICONA 7MM	1	1	t	13900.00	\N	2026-01-16 20:35:58.009573+00	2026-01-16 20:35:58.009573+00	1.00
108	\N	\N	PISTOLA SILICONA 12MM	1	1	t	29340.00	\N	2026-01-16 20:37:05.515825+00	2026-01-16 20:37:05.515825+00	1.00
109	\N	\N	WD-40 155 GRS	11	1	t	9100.00	\N	2026-01-16 20:59:02.717287+00	2026-01-16 20:59:02.717287+00	2.00
72	\N	\N	WD-40 311 GRS	11	1	t	14100.00	\N	2026-01-14 23:02:05.873684+00	2026-01-16 21:02:55.598611+00	3.00
110	\N	\N	MACHO CONO 1/4X20	2	1	t	4250.00	\N	2026-01-16 21:19:53.466134+00	2026-01-16 21:19:53.466134+00	1.00
111	\N	\N	MACHO CONO 5/16X24	2	1	t	6250.00	\N	2026-01-16 21:20:58.479791+00	2026-01-16 21:20:58.479791+00	1.00
112	\N	\N	MACHO CONO 3/8X24	2	1	t	7150.00	\N	2026-01-16 21:22:09.092521+00	2026-01-16 21:22:09.092521+00	1.00
63	\N	\N	PILA REDONDA CR2032	4	1	t	1500.00	\N	2026-01-14 00:42:41.056973+00	2026-01-16 21:30:07.602254+00	4.00
113	\N	\N	DISCO ABRASIVO 115X1.6	3	1	t	1500.00	\N	2026-01-16 21:51:04.185619+00	2026-01-16 21:51:04.185619+00	4.00
114	\N	\N	LLAVE FRANCESA 6" BRITEX	2	1	t	14850.00	\N	2026-01-16 21:54:44.669949+00	2026-01-16 21:54:44.669949+00	1.00
115	\N	\N	LLAVE FRANCESA 6" WEMBLEY	2	1	t	14000.00	\N	2026-01-16 22:02:17.858773+00	2026-01-16 22:02:17.858773+00	1.00
116	\N	\N	LLAVE FRANCESA 8" WEMBLEY	2	1	t	18800.00	\N	2026-01-16 22:04:20.247724+00	2026-01-16 22:04:20.247724+00	1.00
117	\N	\N	LLAVE FRANCESA 10" WEMBLEY	2	1	t	26450.00	\N	2026-01-16 22:05:17.369976+00	2026-01-16 22:05:17.369976+00	1.00
118	\N	\N	LLAVE FRANCESA 12" WEMBLEY	2	1	t	41200.00	\N	2026-01-16 22:06:58.297048+00	2026-01-16 22:06:58.297048+00	1.00
120	\N	\N	LLAVE T HEXAGONAL LARGA 11MM WEMBLEY	2	1	t	11550.00	\N	2026-01-16 22:24:19.702818+00	2026-01-16 22:24:19.702818+00	1.00
121	\N	\N	LLAVE T HEXAGONAL LARGA 17MM WEMBLEY	2	1	t	15150.00	\N	2026-01-16 22:25:00.005823+00	2026-01-16 22:25:00.005823+00	1.00
122	\N	\N	LLAVE T HEXAGONAL LARGA 15MM WEMBLEY	2	1	t	15000.00	\N	2026-01-16 22:41:59.266077+00	2026-01-16 22:41:59.266077+00	1.00
123	\N	\N	LLAVE T HEXAGONAL LARGA 14MM WEMBLEY	2	1	t	11680.00	\N	2026-01-16 22:42:56.318089+00	2026-01-16 22:44:33.634578+00	1.00
119	\N	\N	LLAVE T HEXAGONAL LARGA 13MM WEMBLEY	2	1	t	11600.00	\N	2026-01-16 22:24:19.074289+00	2026-01-16 22:45:34.80035+00	1.00
124	\N	\N	LLAVE T HEXAGONAL LARGA 12MM WEMBLEY	2	1	t	11590.00	\N	2026-01-16 22:46:38.033317+00	2026-01-16 22:46:38.033317+00	1.00
125	\N	\N	LLAVE T HEXAGONAL LARGA 10MM WEMBLEY	2	1	t	11500.00	\N	2026-01-16 22:47:30.438635+00	2026-01-16 22:47:30.438635+00	1.00
126	\N	\N	LLAVE T HEXAGONAL LARGA 9MM WEMBLEY	2	1	t	11490.00	\N	2026-01-16 22:48:18.861088+00	2026-01-16 22:48:18.861088+00	1.00
127	\N	\N	LLAVE T HEXAGONAL LARGA 8MM WEMBLEY	2	1	t	11450.00	\N	2026-01-16 22:49:01.264282+00	2026-01-16 22:49:01.264282+00	1.00
128	\N	\N	LLAVE T HEXAGONAL LARGA 7MM WEMBLEY	2	1	t	11400.00	\N	2026-01-16 22:49:37.360493+00	2026-01-16 22:49:37.360493+00	1.00
129	\N	\N	MECHA PARA MADERA BISELADORA 5MM	2	1	t	8600.00	\N	2026-01-16 22:58:19.967252+00	2026-01-16 22:58:19.967252+00	1.00
130	\N	\N	MECHA PARA MADERA BISELADORA 8MM	2	1	t	9100.00	\N	2026-01-16 23:01:08.5838+00	2026-01-16 23:01:08.5838+00	1.00
131	\N	\N	MECHA PARA MADERA BISELADORA 6MM	2	1	t	8700.00	\N	2026-01-16 23:02:09.337437+00	2026-01-16 23:02:09.337437+00	1.00
100	\N	\N	ENDUIDO EXTERIOR 1L	3	1	t	6350.00	\N	2026-01-15 23:07:48.050818+00	2026-01-18 16:27:55.505583+00	1.00
83	\N	\N	LIJA ANTIEMPASTE 150 GR	3	1	t	1500.00	\N	2026-01-15 00:05:57.989318+00	2026-01-21 21:37:26.833596+00	5.00
132	\N	\N	MECHA PARA MADERA BISELADORA 4MM	2	1	t	8250.00	\N	2026-01-16 23:03:03.34311+00	2026-01-16 23:03:03.34311+00	1.00
133	\N	\N	MECHA PARA MADERA BISELADORA 3MM	2	1	t	8150.00	\N	2026-01-16 23:03:42.531769+00	2026-01-16 23:03:42.531769+00	1.00
134	\N	\N	GRAMPAS 11,3X0,7X10MM	2	6	t	2000.00	\N	2026-01-16 23:21:42.317149+00	2026-01-16 23:21:42.317149+00	2.00
135	\N	\N	GRAMPAS 11,3X1,2X10MM	2	6	t	4350.00	\N	2026-01-16 23:23:26.049511+00	2026-01-16 23:23:26.049511+00	2.00
136	\N	\N	GRAMPAS 11,3X0,7X8MM	2	6	t	5900.00	\N	2026-01-16 23:33:03.124107+00	2026-01-16 23:33:03.124107+00	2.00
137	\N	\N	MECHA WIDIA DE 10	2	1	t	6100.00	\N	2026-01-17 12:51:29.64968+00	2026-01-17 12:51:29.64968+00	1.00
138	\N	\N	MECHA WIDIA DE 12	2	1	t	7400.00	\N	2026-01-17 12:54:02.094391+00	2026-01-17 12:54:02.094391+00	1.00
139	\N	\N	MECHA WIDIA DE 4	2	1	t	2600.00	\N	2026-01-17 12:55:26.778993+00	2026-01-17 12:55:26.778993+00	1.00
140	\N	\N	MECHA WIDIA DE 5	2	1	t	2700.00	\N	2026-01-17 13:03:57.737149+00	2026-01-17 13:03:57.737149+00	1.00
141	\N	\N	MECHA WIDIA DE 6	2	1	t	3300.00	\N	2026-01-17 13:05:03.249381+00	2026-01-17 13:05:03.249381+00	1.00
142	\N	\N	MECHA WIDIA DE 8	2	1	t	4400.00	\N	2026-01-17 13:05:44.240122+00	2026-01-17 13:05:44.240122+00	1.00
143	\N	\N	ENGRAMPADORA LIVIANA BREMEN	2	1	t	34500.00	\N	2026-01-17 13:08:12.418775+00	2026-01-17 13:08:12.418775+00	1.00
144	\N	\N	ENGRAMPADORA LIVIANA BRITEX	2	1	t	13150.00	\N	2026-01-17 13:09:27.747177+00	2026-01-17 13:09:27.747177+00	1.00
145	\N	\N	CINTA CORTINA BLANCA	\N	5	t	1200.00	\N	2026-01-17 13:11:49.203684+00	2026-01-17 13:11:49.203684+00	10.00
146	\N	\N	CINTA CORTINA REFORZADA	\N	5	t	1800.00	\N	2026-01-17 13:12:20.172269+00	2026-01-17 13:12:20.172269+00	10.00
147	\N	\N	POXIRAN 450GRS	10	7	t	22300.00	\N	2026-01-17 13:14:27.306095+00	2026-01-17 13:14:27.306095+00	1.00
148	\N	\N	POXIRAN 850GRS	10	7	t	34000.00	\N	2026-01-17 13:15:11.236542+00	2026-01-17 13:15:11.236542+00	1.00
149	\N	\N	SOLDADOR LAPIZ	1	1	t	5000.00	\N	2026-01-17 13:21:50.910775+00	2026-01-17 13:21:50.910775+00	1.00
150	\N	\N	POXIRAN 23GRS	10	6	t	4900.00	\N	2026-01-17 13:28:01.622325+00	2026-01-17 13:28:01.622325+00	1.00
151	\N	\N	POXIRAN 45GRS	10	6	t	7850.00	\N	2026-01-17 13:29:35.508689+00	2026-01-17 13:29:35.508689+00	1.00
152	\N	\N	POXIRAN 90GRS	10	6	t	15500.00	\N	2026-01-17 13:30:55.584347+00	2026-01-17 13:30:55.584347+00	1.00
153	\N	\N	PASTILLA DE CLORO CHICA	9	1	t	750.00	\N	2026-01-17 13:31:24.271198+00	2026-01-17 13:31:24.271198+00	10.00
154	\N	\N	PASTILLA DE CLORO GRANDE	9	1	t	2500.00	\N	2026-01-17 13:31:57.679958+00	2026-01-17 13:31:57.679958+00	10.00
155	\N	\N	CLORO GRANULADO	9	7	t	11500.00	\N	2026-01-17 13:32:35.335704+00	2026-01-17 13:32:35.335704+00	1.00
156	\N	\N	CLORO CAUCHET 5L	9	8	t	10500.00	\N	2026-01-17 13:33:55.018914+00	2026-01-17 13:33:55.018914+00	1.00
157	\N	\N	POXILINA 70GRS	10	6	t	7000.00	\N	2026-01-17 13:44:15.64444+00	2026-01-17 13:44:15.64444+00	2.00
158	\N	\N	AEROSOL KUWiT 155GRS	3	1	t	5000.00	\N	2026-01-17 13:45:40.641812+00	2026-01-17 13:45:40.641812+00	5.00
159	\N	\N	MEMBRANA AUTOADHESIVA 10CM ANCHO	3	5	t	2100.00	\N	2026-01-17 13:46:32.49707+00	2026-01-17 13:46:32.49707+00	5.00
160	\N	\N	MEMBRANA AUTOADHESIVA 25CM ANCHO	3	5	t	5400.00	\N	2026-01-17 13:47:36.056165+00	2026-01-17 13:47:36.056165+00	1.00
161	\N	\N	POXIPOL GRIS 21GRS	10	6	t	6000.00	\N	2026-01-17 13:50:21.48974+00	2026-01-17 13:50:51.738166+00	1.00
162	\N	\N	POXIPOL TRANSPARENTE 21GRS	10	6	t	6000.00	\N	2026-01-17 13:51:23.756409+00	2026-01-17 13:51:23.756409+00	1.00
164	\N	\N	CANILLA MOYNOCOMANDO PARA COCINA FAUSIL	5	1	t	44550.00	\N	2026-01-17 13:56:13.488587+00	2026-01-17 13:56:13.488587+00	1.00
165	\N	\N	FLOR DUCHA CUADRADA	5	1	t	9000.00	\N	2026-01-17 13:56:45.668118+00	2026-01-17 13:56:45.668118+00	1.00
163	\N	\N	CANILLA MOYNOCOMANDO PARA BAÑO RORY	5	1	t	60550.00	\N	2026-01-17 13:55:17.190554+00	2026-01-17 13:59:20.561337+00	1.00
166	\N	\N	DISCO FLAP 40GRS	3	1	t	3300.00	\N	2026-01-17 14:00:33.880944+00	2026-01-17 14:00:33.880944+00	1.00
167	\N	\N	DISCO FLAP 60GRS	3	1	t	3300.00	\N	2026-01-17 14:01:24.560232+00	2026-01-17 14:01:24.560232+00	1.00
168	\N	\N	DISCO FLAP 80GRS	3	1	t	3300.00	\N	2026-01-17 14:01:46.311146+00	2026-01-17 14:01:46.311146+00	1.00
170	\N	\N	DISCO FLAP 120GRS	3	1	t	3300.00	\N	2026-01-17 14:02:56.970265+00	2026-01-17 14:02:56.970265+00	1.00
171	\N	\N	DISCO FLAP 150GRS	3	1	t	3300.00	\N	2026-01-17 14:03:23.317897+00	2026-01-17 14:03:23.317897+00	1.00
172	\N	\N	DISCO FLAP 240GRS	3	1	t	3300.00	\N	2026-01-17 14:03:50.344917+00	2026-01-17 14:03:50.344917+00	1.00
173	\N	\N	DISCO FLAP 320GRS	3	1	t	3300.00	\N	2026-01-17 14:04:19.176323+00	2026-01-17 14:04:19.176323+00	1.00
174	\N	\N	FASTIX INTERIOR 25GRS	10	6	t	6000.00	\N	2026-01-17 14:08:01.613614+00	2026-01-17 14:08:01.613614+00	1.00
175	\N	\N	FASTIX EXTERIOR 25GRS	10	6	t	6000.00	\N	2026-01-17 14:10:55.88543+00	2026-01-17 14:10:55.88543+00	1.00
176	\N	\N	FASTIX MOTORES 25GRS	10	6	t	7500.00	\N	2026-01-17 14:11:32.971657+00	2026-01-17 14:11:32.971657+00	1.00
177	\N	\N	FASTIX ALTA TEMPERATURA 25GRS	10	6	t	7450.00	\N	2026-01-17 14:13:42.75219+00	2026-01-17 14:13:42.75219+00	1.00
178	\N	\N	FASTIX INTERIOR 280GRS	10	1	t	11950.00	\N	2026-01-17 14:15:43.441419+00	2026-01-17 14:15:43.441419+00	1.00
179	\N	\N	EL PULPITO 50 GRS.	10	1	t	6000.00	\N	2026-01-17 14:21:55.491882+00	2026-01-17 14:21:55.491882+00	1.00
180	\N	\N	ECOLE 9GRS	10	6	t	5000.00	\N	2026-01-17 14:22:32.234565+00	2026-01-17 14:22:32.234565+00	1.00
181	\N	\N	TARUGO CON TOPE 8	6	1	t	50.00	\N	2026-01-17 14:25:33.423368+00	2026-01-17 14:25:33.423368+00	50.00
182	\N	\N	TARUGO CON TOPE 12	6	1	t	60.00	\N	2026-01-17 14:27:29.358835+00	2026-01-17 14:27:29.358835+00	25.00
183	\N	\N	TARUGO CON TOPE 10	6	1	t	90.00	\N	2026-01-17 14:28:04.912508+00	2026-01-17 14:28:04.912508+00	10.00
184	\N	\N	TARUGO CON TOPE 6	6	1	t	30.00	\N	2026-01-17 14:28:39.913166+00	2026-01-17 14:28:39.913166+00	50.00
185	\N	\N	TARUGO CON TOPE 5	6	1	t	20.00	\N	2026-01-17 14:29:02.294981+00	2026-01-17 14:29:02.294981+00	50.00
186	\N	\N	REGADORES SAPITO	7	1	t	1000.00	\N	2026-01-17 14:32:51.119958+00	2026-01-17 14:32:51.119958+00	2.00
187	\N	\N	MANGUERA REFORZADA AZUL	7	5	t	1800.00	\N	2026-01-17 14:34:20.359419+00	2026-01-17 14:34:20.359419+00	15.00
188	\N	\N	POXI MIX EXTERIOR 500GRS	10	6	t	5550.00	\N	2026-01-17 14:35:51.134147+00	2026-01-17 14:37:04.661865+00	2.00
189	\N	\N	ZAPATILLA 4 TOMA S/CABLE	4	1	t	7000.00	\N	2026-01-17 14:49:24.084569+00	2026-01-17 14:49:24.084569+00	1.00
190	\N	\N	POXI MIX INTERIOR 500GRS	10	6	t	5250.00	\N	2026-01-17 14:53:40.671269+00	2026-01-17 14:53:40.671269+00	1.00
191	\N	\N	AMOLADORA ANGULAR	1	1	t	779000.00	\N	2026-01-17 15:08:06.600402+00	2026-01-17 15:08:06.600402+00	1.00
192	\N	\N	FUELLE BACHA EXTENSIBLE	5	1	t	2400.00	\N	2026-01-17 15:11:31.661225+00	2026-01-17 15:11:31.661225+00	1.00
193	\N	\N	LAMPARA DISCROICA 4,5W	4	1	t	4000.00	\N	2026-01-17 15:15:10.790201+00	2026-01-17 15:15:10.790201+00	5.00
194	\N	\N	LAMPARA PERITA 5W	4	1	t	2500.00	\N	2026-01-17 15:15:37.619438+00	2026-01-17 15:15:37.619438+00	5.00
195	\N	\N	LAMPARA LED 9W	4	1	t	2150.00	\N	2026-01-17 15:16:36.859661+00	2026-01-17 15:16:36.859661+00	5.00
196	\N	\N	LAMPARA LED 11W	4	1	t	2600.00	\N	2026-01-17 15:17:08.683576+00	2026-01-17 15:17:08.683576+00	5.00
197	\N	\N	LAMPARA LED 13W	4	1	t	1800.00	\N	2026-01-17 15:17:34.896552+00	2026-01-17 15:17:34.896552+00	5.00
198	\N	\N	LAMPARA LED 14W	4	1	t	3400.00	\N	2026-01-17 15:18:04.239389+00	2026-01-17 15:18:04.239389+00	5.00
199	\N	\N	LIJA ANTIEMPASTE 120 GR	3	1	t	1500.00	\N	2026-01-17 15:22:53.524878+00	2026-01-17 15:22:53.524878+00	5.00
200	\N	\N	FICHA ENCHUFE REFORZADO	4	1	t	2000.00	\N	2026-01-17 15:25:55.450715+00	2026-01-17 15:25:55.450715+00	10.00
201	\N	\N	PRECINTOS 10CM	4	1	t	20.00	\N	2026-01-17 15:42:19.27379+00	2026-01-17 15:42:19.27379+00	100.00
202	\N	\N	PRECINTOS 15CM	4	1	t	40.00	\N	2026-01-17 15:51:46.650689+00	2026-01-17 15:51:46.650689+00	100.00
203	\N	\N	PRECINTOS 20CM	4	1	t	60.00	\N	2026-01-17 15:53:34.78451+00	2026-01-17 15:53:34.78451+00	100.00
205	\N	\N	PRECINTOS 30CM	4	1	t	100.00	\N	2026-01-17 15:54:36.39191+00	2026-01-17 15:54:36.39191+00	100.00
206	\N	\N	PRECINTOS 40CM	4	1	t	200.00	\N	2026-01-17 15:55:07.784742+00	2026-01-17 15:55:07.784742+00	100.00
207	\N	\N	PAVA ELECTRICA	\N	1	t	25800.00	\N	2026-01-17 16:46:08.802354+00	2026-01-17 16:46:08.802354+00	2.00
208	\N	\N	SOPAPA PLASTICA DE 1 1/2	5	1	t	3600.00	\N	2026-01-17 20:45:43.106646+00	2026-01-17 20:45:43.106646+00	1.00
209	\N	\N	FLOTANTE PLASTICO P/DEPOSITO COLGAR BOYA	5	1	t	4800.00	\N	2026-01-17 20:48:13.942512+00	2026-01-17 20:48:13.942512+00	1.00
210	\N	\N	LA GOTITA	10	1	t	2000.00	\N	2026-01-17 20:51:51.912931+00	2026-01-17 20:51:51.912931+00	1.00
211	\N	\N	LA GOTITA EN GEL	10	1	t	2500.00	\N	2026-01-17 20:52:22.183316+00	2026-01-17 20:52:22.183316+00	1.00
213	\N	\N	CABLE TALLER 3X2,5	4	5	t	3000.00	\N	2026-01-17 21:50:32.698773+00	2026-01-17 21:50:32.698773+00	100.00
215	\N	\N	ARANDELA DE GOMA 1/2	5	1	t	100.00	\N	2026-01-17 21:54:46.345463+00	2026-01-17 21:54:46.345463+00	10.00
216	\N	\N	SOPORTE DE CORTINA LARGO MEDIANO	8	1	t	880.00	\N	2026-01-17 21:55:21.533859+00	2026-01-17 21:55:21.533859+00	10.00
217	\N	\N	PINTURA SINTETICO 1/4L	3	7	t	5300.00	\N	2026-01-17 22:01:40.417098+00	2026-01-17 22:01:40.417098+00	2.00
218	\N	\N	SOPORTE ESPEJO REFORZADO	8	1	t	550.00	\N	2026-01-17 22:10:28.64351+00	2026-01-17 22:10:28.64351+00	1.00
219	\N	\N	ESQUINERO ANGULO 6X6	2	1	t	690.00	\N	2026-01-17 22:13:28.76342+00	2026-01-17 22:13:28.76342+00	3.00
221	\N	\N	HORMIGUICIDA GELTEK GEL JERINGA 12GRS	12	1	t	9200.00	\N	2026-01-17 22:19:39.277289+00	2026-01-17 22:19:39.277289+00	1.00
222	\N	\N	HORMIGUICIDA GELTEK GEL JERINGA 6GRS	12	1	t	5800.00	\N	2026-01-17 22:21:48.539567+00	2026-01-17 22:21:48.539567+00	1.00
223	\N	\N	BOYA MINI HONGO ECONOMICA	7	1	t	1900.00	\N	2026-01-17 22:28:38.733833+00	2026-01-17 22:28:38.733833+00	1.00
224	\N	\N	SOGA FINITA	\N	5	t	100.00	\N	2026-01-17 22:29:19.066649+00	2026-01-17 22:29:19.066649+00	10.00
225	\N	\N	PITON CERRADO SIN TOPE 12	6	1	t	820.00	\N	2026-01-17 22:30:11.716226+00	2026-01-17 22:30:11.716226+00	5.00
226	\N	\N	ADAPTADOR TRES PATAS A 2 PATAS	4	1	t	1300.00	\N	2026-01-17 22:32:27.023465+00	2026-01-17 22:32:27.023465+00	5.00
227	\N	\N	ZAPATILLA 4 TOMA C/CABLE 2,5 MTR	4	1	t	17500.00	\N	2026-01-17 22:36:14.746301+00	2026-01-17 22:36:14.746301+00	1.00
77	\N	\N	DISCO C/VELCRO DE LIJA 40 GRS	3	1	t	2000.00	\N	2026-01-14 23:37:06.253038+00	2026-01-17 22:41:08.184899+00	5.00
229	\N	\N	DISCO C/VELCRO DE LIJA 60 GRS	3	1	t	3000.00	\N	2026-01-17 22:45:20.958561+00	2026-01-17 22:45:20.958561+00	2.00
228	\N	\N	DISCO C/VELCRO DE LIJA 120 GRS	3	1	t	2000.00	\N	2026-01-17 22:44:15.672233+00	2026-01-17 22:46:20.309169+00	3.00
230	\N	\N	FIELTRO 25CM	2	1	t	2000.00	\N	2026-01-17 22:53:20.679059+00	2026-01-17 22:53:20.679059+00	5.00
231	\N	\N	ENCHUFE MACHO 2 PATAS	4	1	t	1500.00	\N	2026-01-17 22:55:32.958973+00	2026-01-17 22:55:32.958973+00	2.00
232	\N	\N	DESTAPA CAÑERIA EN GEL CAUCHET 1L	9	1	t	7000.00	\N	2026-01-17 22:59:32.253872+00	2026-01-17 22:59:32.253872+00	1.00
233	\N	\N	ADAPTADOR BRASILERO	4	1	t	3000.00	\N	2026-01-17 23:05:30.459365+00	2026-01-17 23:05:30.459365+00	1.00
234	\N	\N	DISCO C/VELCRO DE LIJA 80 GRS	3	1	t	3000.00	\N	2026-01-17 23:08:18.086441+00	2026-01-17 23:08:18.086441+00	2.00
235	\N	\N	DISCO C/VELCRO DE LIJA 80 GRS	3	1	t	3000.00	\N	2026-01-17 23:08:18.697105+00	2026-01-17 23:08:18.697105+00	2.00
236	\N	\N	CAÑO DE HIERRO 1/2 PARA CORTINA	8	5	t	3500.00	\N	2026-01-17 23:10:36.841776+00	2026-01-17 23:10:36.841776+00	4.00
237	\N	\N	BANDEJA CHATA PARA PINTURA	3	1	t	6000.00	\N	2026-01-17 23:12:13.667898+00	2026-01-17 23:12:13.667898+00	1.00
238	\N	\N	BANDEJA DE COLGAR PARA PINTURA	3	1	t	6000.00	\N	2026-01-17 23:13:05.318404+00	2026-01-17 23:13:05.318404+00	1.00
239	\N	\N	TAPA INODORO	5	1	t	16850.00	\N	2026-01-17 23:21:39.529976+00	2026-01-17 23:21:39.529976+00	1.00
240	\N	\N	DISCO ULTRA STRIP	3	1	t	13200.00	\N	2026-01-17 23:23:02.045716+00	2026-01-17 23:23:02.045716+00	1.00
241	\N	\N	NYLON NEGRO 2,5M DE ANCHO	\N	5	t	4500.00	\N	2026-01-17 23:29:45.952822+00	2026-01-17 23:29:45.952822+00	1.00
242	\N	\N	RESISTENCIA ALUMINIO CALEFON ELECTRICO	5	1	t	4000.00	\N	2026-01-17 23:31:05.275306+00	2026-01-17 23:31:05.275306+00	1.00
243	\N	\N	FLOR DE DUCHA PARA CALEFON ELECTRICO	5	1	t	800.00	\N	2026-01-17 23:31:58.067386+00	2026-01-17 23:31:58.067386+00	1.00
244	\N	\N	CANILLA PARA CALEFON ELECTRICO	5	1	t	3850.00	\N	2026-01-17 23:32:39.799808+00	2026-01-17 23:32:39.799808+00	1.00
245	\N	\N	TEE 1/2 ROJA	5	1	t	850.00	\N	2026-01-17 23:57:58.900473+00	2026-01-17 23:57:58.900473+00	2.00
246	\N	\N	TEE 3/4 ROJA	5	1	t	100.00	\N	2026-01-17 23:58:28.004766+00	2026-01-17 23:58:28.004766+00	2.00
248	\N	\N	ROSCA CON TUERCA 3/4 ROJA	5	1	t	350.00	\N	2026-01-17 23:59:34.070529+00	2026-01-18 00:00:30.488746+00	2.00
249	\N	\N	TARUGO PARA HUECO 5	3	1	t	25.00	\N	2026-01-18 00:02:12.307642+00	2026-01-18 00:02:12.307642+00	10.00
250	\N	\N	TARUGO PARA HUECO 6	6	1	t	30.00	\N	2026-01-18 00:02:42.93074+00	2026-01-18 00:02:42.93074+00	10.00
251	\N	\N	TARUGO PARA HUECO 8	6	1	t	40.00	\N	2026-01-18 00:03:07.504312+00	2026-01-18 00:03:07.504312+00	10.00
252	\N	\N	TARUGO PARA HUECO 10	6	1	t	65.00	\N	2026-01-18 00:03:36.374022+00	2026-01-18 00:03:36.374022+00	10.00
253	\N	\N	TARUGO PARA HUECO 12	6	1	t	120.00	\N	2026-01-18 00:04:06.636584+00	2026-01-18 00:04:06.636584+00	10.00
254	\N	\N	TORNILLO PUNTA AGUJA T4 6 X 1-1/2	6	1	t	25.00	\N	2026-01-18 00:05:17.858013+00	2026-01-18 00:05:17.858013+00	10.00
255	\N	\N	RASTRILLO EXTENSIBLE DE METAL	7	1	t	35000.00	\N	2026-01-18 12:57:10.159235+00	2026-01-18 12:57:10.159235+00	1.00
256	\N	\N	RASTRILLO PLASTICO GRANDE	7	1	t	3550.00	\N	2026-01-18 12:58:59.657837+00	2026-01-18 12:58:59.657837+00	1.00
257	\N	\N	PALO DE ESCOBA	9	1	t	2100.00	\N	2026-01-18 13:02:21.956851+00	2026-01-18 13:02:21.956851+00	2.00
258	\N	\N	SEMILLA	7	9	t	2100.00	\N	2026-01-18 13:05:41.954174+00	2026-01-18 13:05:41.954174+00	3.00
259	\N	\N	TORNILLOS FIX 6X70	6	1	t	90.00	\N	2026-01-18 13:06:48.428532+00	2026-01-18 13:06:48.428532+00	10.00
260	\N	\N	MECHA DE ACERO 4	2	1	t	3000.00	\N	2026-01-18 13:07:39.765675+00	2026-01-18 13:07:39.765675+00	1.00
261	\N	\N	PARCHES N°2	\N	1	t	100.00	\N	2026-01-18 13:12:06.928509+00	2026-01-18 13:12:06.928509+00	5.00
262	\N	\N	SOLUCION PEGA PARCHE	10	1	t	1000.00	\N	2026-01-18 13:12:39.231395+00	2026-01-18 13:12:39.231395+00	2.00
263	\N	\N	COMPRESOR 12V	1	1	t	45000.00	\N	2026-01-18 13:16:00.214451+00	2026-01-18 13:16:00.214451+00	1.00
264	\N	\N	LIJA ANTIEMPASTE 100 GR	3	1	t	1000.00	\N	2026-01-18 13:16:40.28674+00	2026-01-18 13:16:40.28674+00	3.00
265	\N	\N	TORNILLO PUNTA AGUJA 6 X 2 1/2	6	1	t	25.00	\N	2026-01-18 13:24:54.757153+00	2026-01-18 13:24:54.757153+00	20.00
266	\N	\N	HILO SISAL	8	1	t	2000.00	\N	2026-01-18 13:45:34.815198+00	2026-01-18 13:45:34.815198+00	2.00
267	\N	\N	CINTA EMBALAR MARRON	10	1	t	3000.00	\N	2026-01-18 13:46:15.909307+00	2026-01-18 13:46:15.909307+00	2.00
268	\N	\N	GUANTES DE ENCARNE	7	1	t	5000.00	\N	2026-01-18 13:46:44.097548+00	2026-01-18 13:46:44.097548+00	2.00
347	\N	\N	HOSTIA	5	1	t	200.00	\N	2026-01-19 21:19:42.184226+00	2026-01-19 21:19:42.184226+00	1.00
212	\N	\N	CABLE TALLER 2X2,5	4	5	t	2350.00	\N	2026-01-17 21:49:21.49945+00	2026-01-22 03:05:10.888132+00	10.00
214	\N	\N	CABLE COAXIL	4	5	t	1000.00	\N	2026-01-17 21:51:18.730526+00	2026-01-22 03:07:34.175247+00	10.00
220	\N	\N	CABLE DE ACERO	\N	5	t	1500.00	\N	2026-01-17 22:16:20.060778+00	2026-01-22 03:08:24.186978+00	10.00
269	\N	\N	TORNILLO PUNTA MECHA 8X9/16	6	1	t	20.00	\N	2026-01-18 14:05:11.514349+00	2026-01-18 14:05:11.514349+00	20.00
270	\N	\N	TORNILLO PUNTA MECHA 8X3/4	6	1	t	25.00	\N	2026-01-18 14:07:47.149815+00	2026-01-18 14:07:47.149815+00	20.00
271	\N	\N	TORNILLO PUNTA MECHA 8X1	6	1	t	30.00	\N	2026-01-18 14:08:43.24378+00	2026-01-18 14:08:43.24378+00	20.00
272	\N	\N	TORNILLO PUNTA MECHA 8X1 1/2	6	1	t	35.00	\N	2026-01-18 14:12:28.23871+00	2026-01-18 14:12:28.23871+00	20.00
273	\N	\N	GRAMPAS SUJETA CABLE	4	6	t	5000.00	\N	2026-01-18 14:14:29.840705+00	2026-01-18 14:14:29.840705+00	2.00
274	\N	\N	ACEITE MULTIUSO HOGAR	11	1	t	3000.00	\N	2026-01-18 14:35:24.455309+00	2026-01-18 14:35:24.455309+00	1.00
275	\N	\N	ACOPLE MACHO CON POLLERA 1/2	5	1	t	200.00	\N	2026-01-18 14:45:31.416565+00	2026-01-18 14:45:31.416565+00	2.00
276	\N	\N	TANZA PARA BORDEADORA 1	7	5	t	200.00	\N	2026-01-18 14:46:11.875405+00	2026-01-18 14:46:11.875405+00	20.00
277	\N	\N	TELA ESMERIL 80	3	1	t	1750.00	\N	2026-01-18 14:47:26.281249+00	2026-01-18 14:47:26.281249+00	2.00
278	\N	\N	TELA ESMERIL 60	3	1	t	1750.00	\N	2026-01-18 14:48:03.322355+00	2026-01-18 14:48:03.322355+00	5.00
279	\N	\N	NIVEL DE MANO	2	1	t	7500.00	\N	2026-01-18 14:50:25.320547+00	2026-01-18 14:50:25.320547+00	1.00
280	\N	\N	ACOPLE RAPIDO DE 1/2 PARA CANILLA	5	1	t	2500.00	\N	2026-01-18 14:54:13.597319+00	2026-01-18 14:54:13.597319+00	2.00
281	\N	\N	TELA ESMERIL 120	3	1	t	1750.00	\N	2026-01-18 15:00:11.727697+00	2026-01-18 15:00:11.727697+00	5.00
282	\N	\N	PINCEL 7	3	1	t	1700.00	\N	2026-01-18 15:05:16.783396+00	2026-01-18 15:05:16.783396+00	1.00
283	\N	\N	PINCEL 10	3	1	t	2000.00	\N	2026-01-18 15:05:51.660357+00	2026-01-18 15:05:51.660357+00	2.00
284	\N	\N	PINCEL 15	3	1	t	2700.00	\N	2026-01-18 15:06:21.370435+00	2026-01-18 15:06:21.370435+00	2.00
285	\N	\N	PINCEL 20	3	1	t	3300.00	\N	2026-01-18 15:06:56.927671+00	2026-01-18 15:06:56.927671+00	2.00
286	\N	\N	PINCEL 25	3	1	t	4350.00	\N	2026-01-18 15:07:28.151892+00	2026-01-18 15:07:28.151892+00	2.00
287	\N	\N	PINCEL 30	3	1	t	5250.00	\N	2026-01-18 15:08:12.494077+00	2026-01-18 15:08:12.494077+00	2.00
288	\N	\N	ESQUINERO ANGULO 12X12	6	1	t	1920.00	\N	2026-01-18 15:11:03.029786+00	2026-01-18 15:11:03.029786+00	2.00
289	\N	\N	LLAVE COMBINADA 11	2	1	t	8850.00	\N	2026-01-18 15:15:52.749378+00	2026-01-18 15:15:52.749378+00	1.00
290	\N	\N	TORNILLO HEXAGONAL 11X1-1/2	6	1	t	100.00	\N	2026-01-18 15:17:11.581385+00	2026-01-18 15:17:11.581385+00	5.00
291	\N	\N	TUERCA 1/4	6	1	t	50.00	\N	2026-01-18 15:18:39.614728+00	2026-01-18 15:18:39.614728+00	10.00
292	\N	\N	TORNILLO TANQUE 5/32X2-1/2	6	1	t	75.00	\N	2026-01-18 15:22:00.161525+00	2026-01-18 15:22:00.161525+00	10.00
293	\N	\N	TUERCA 5/32	6	1	t	25.00	\N	2026-01-18 15:22:30.032677+00	2026-01-18 15:22:30.032677+00	10.00
294	\N	\N	MANGUERA REFORZADA 1/2	7	5	t	900.00	\N	2026-01-18 15:30:31.333647+00	2026-01-18 15:30:31.333647+00	15.00
295	\N	\N	FLEXIBLE 1/2 40CM	5	1	t	5850.00	\N	2026-01-18 15:33:20.347754+00	2026-01-18 15:33:20.347754+00	1.00
296	\N	\N	ESCALERA 8 ESCALONES	2	1	t	100000.00	\N	2026-01-18 15:46:22.715909+00	2026-01-18 15:46:22.715909+00	1.00
297	\N	\N	ESCALERA 5 ESCALONES	2	1	t	63200.00	\N	2026-01-18 15:46:50.720978+00	2026-01-18 15:46:50.720978+00	1.00
298	\N	\N	ESCALERA 3 ESCALONES	2	1	t	38200.00	\N	2026-01-18 15:47:17.633816+00	2026-01-18 15:47:17.633816+00	1.00
299	\N	\N	PLAFON LED  REDONDO 6W	4	1	t	8000.00	\N	2026-01-18 15:52:37.663482+00	2026-01-18 15:52:37.663482+00	1.00
300	\N	\N	MECHA DE ACERO 5	6	1	t	3900.00	\N	2026-01-18 15:53:03.431049+00	2026-01-18 15:53:03.431049+00	1.00
301	\N	\N	TORNILLO TANQUE 5/32X1/4	6	1	t	40.00	\N	2026-01-18 15:55:55.353011+00	2026-01-18 15:55:55.353011+00	10.00
302	\N	\N	TORNILLO FIX 6 X 40MM	6	1	t	55.00	\N	2026-01-18 15:58:53.78607+00	2026-01-18 15:58:53.78607+00	10.00
303	\N	\N	ABRAZADERA BANDA 7MM	6	1	t	1000.00	\N	2026-01-18 16:08:48.347244+00	2026-01-18 16:08:48.347244+00	10.00
304	\N	\N	MANGUERA NEGRA 1/2	5	5	t	500.00	\N	2026-01-18 16:09:46.225744+00	2026-01-18 16:13:13.378732+00	10.00
306	\N	\N	TANZA PARA BORDEADORA CUADRADA 2,5	7	5	t	200.00	\N	2026-01-18 16:22:11.20271+00	2026-01-18 16:22:11.20271+00	10.00
307	\N	\N	ACOPLE MACHO CON POLLERA 3/4	5	1	t	350.00	\N	2026-01-18 16:26:18.986446+00	2026-01-18 16:26:18.986446+00	5.00
308	\N	\N	ACOPLE MACHO CON POLLERA 1¨	5	1	t	750.00	\N	2026-01-18 16:26:59.58408+00	2026-01-18 16:26:59.58408+00	2.00
309	\N	\N	PITON ESCUADRA S/TOPE 6	6	1	t	170.00	\N	2026-01-18 16:32:17.59111+00	2026-01-18 16:32:17.59111+00	5.00
310	\N	\N	BARRA SILICONA GRUESA	10	1	t	700.00	\N	2026-01-18 16:32:52.69915+00	2026-01-18 16:32:52.69915+00	5.00
311	\N	\N	BARRA SILICONA FINA	10	1	t	300.00	\N	2026-01-18 16:35:21.859714+00	2026-01-18 16:35:21.859714+00	5.00
312	\N	\N	ESQUINERO ANGULO 25X25	6	1	t	300.00	\N	2026-01-18 16:54:45.028491+00	2026-01-18 16:54:45.028491+00	5.00
313	\N	\N	GUANTES MOTEADO	8	1	t	1500.00	\N	2026-01-18 16:59:08.003183+00	2026-01-18 16:59:08.003183+00	5.00
314	\N	\N	LIJA ANTIEMPASTE 80 GR	3	1	t	1000.00	\N	2026-01-18 17:22:16.533479+00	2026-01-18 17:22:16.533479+00	2.00
315	\N	\N	ESPATULA PLANA CHICA AMARILLA	3	1	t	500.00	\N	2026-01-18 17:23:22.296229+00	2026-01-18 17:23:22.296229+00	5.00
316	\N	\N	ESPATULA PLANA GRANDE NARANJA	3	1	t	1000.00	\N	2026-01-18 17:24:10.563477+00	2026-01-18 17:24:10.563477+00	5.00
317	\N	\N	SOGA FINA 6	\N	5	t	300.00	\N	2026-01-18 17:25:56.657851+00	2026-01-18 17:25:56.657851+00	5.00
318	\N	\N	SELLADOR FIJADOR 1L	3	1	t	4900.00	\N	2026-01-18 17:45:52.11967+00	2026-01-18 17:45:52.11967+00	1.00
319	\N	\N	RODILLO 8	3	1	t	1800.00	\N	2026-01-18 17:50:47.949853+00	2026-01-18 17:50:47.949853+00	1.00
320	\N	\N	PINTURA SINTETICA 1/2	3	1	t	8850.00	\N	2026-01-18 17:51:49.112209+00	2026-01-18 17:51:49.112209+00	1.00
321	\N	\N	SIFON SIMPLE	5	1	t	10950.00	\N	2026-01-18 17:53:46.062185+00	2026-01-18 17:53:46.062185+00	1.00
322	\N	\N	PINTURA SINTETICA 1L	3	1	t	15000.00	\N	2026-01-18 17:55:37.972556+00	2026-01-18 17:55:37.972556+00	0.00
323	\N	\N	MANGUERA CRISTAL	5	5	t	800.00	\N	2026-01-18 17:57:46.284015+00	2026-01-18 17:57:46.284015+00	5.00
324	\N	\N	VARILLA ROSCADA 3/8	6	1	t	1500.00	\N	2026-01-18 18:08:41.160824+00	2026-01-18 18:08:41.160824+00	1.00
325	\N	\N	CERRADURA PRIVE	\N	1	t	27560.00	\N	2026-01-18 18:09:24.682363+00	2026-01-18 18:09:24.682363+00	1.00
326	\N	\N	ARANDELA PLANA 7/16	6	1	t	65.00	\N	2026-01-18 18:10:29.001387+00	2026-01-18 18:10:29.001387+00	10.00
327	\N	\N	TUERCA 5/16	6	1	t	50.00	\N	2026-01-18 18:11:15.511906+00	2026-01-18 18:11:15.511906+00	5.00
328	\N	\N	CAÑO TERMOFUSION 30	5	5	t	2200.00	\N	2026-01-18 18:18:20.797637+00	2026-01-18 18:18:20.797637+00	1.00
329	\N	\N	CURVA 40X45	5	1	t	870.00	\N	2026-01-18 18:19:11.745744+00	2026-01-18 18:19:11.745744+00	1.00
330	\N	\N	TUERCA 3/8	6	1	t	70.00	\N	2026-01-18 18:23:21.959587+00	2026-01-18 18:23:21.959587+00	10.00
331	\N	\N	ARANDELA DE GOMA 1/2 AGUA CALIENTE	5	1	t	200.00	\N	2026-01-18 18:35:42.914718+00	2026-01-18 18:35:42.914718+00	4.00
339	\N	\N	VASTAGO 1/2 DE AGUA CALIENTE	5	1	t	660.00	\N	2026-01-18 19:13:29.071004+00	2026-01-18 19:13:29.071004+00	5.00
340	\N	\N	TARUGO PARA DURLOCK 6	6	1	t	50.00	\N	2026-01-18 19:18:30.930783+00	2026-01-18 19:18:30.930783+00	10.00
341	\N	\N	DUCHADOR	5	1	t	23950.00	\N	2026-01-19 20:42:02.32059+00	2026-01-19 20:42:02.32059+00	1.00
342	\N	\N	SODA CAUSTICA	9	10	t	1600.00	\N	2026-01-19 21:03:10.989752+00	2026-01-19 21:03:10.989752+00	1.00
343	\N	\N	ARANDELA 1/4	6	1	t	45.00	\N	2026-01-19 21:06:00.352277+00	2026-01-19 21:06:00.352277+00	10.00
344	\N	\N	PILA AAA	4	1	t	1700.00	\N	2026-01-19 21:12:11.110313+00	2026-01-19 21:12:11.110313+00	2.00
345	\N	\N	MACETA 21	7	1	t	3000.00	\N	2026-01-19 21:15:23.063688+00	2026-01-19 21:15:23.063688+00	1.00
346	\N	\N	GUANTE DE NITRILO	9	11	t	300.00	\N	2026-01-19 21:17:11.063278+00	2026-01-19 21:17:11.063278+00	10.00
348	\N	\N	SOMBRILLA	7	1	t	18900.00	\N	2026-01-19 21:24:14.48267+00	2026-01-19 21:24:14.48267+00	1.00
349	\N	\N	PINZA SEGURO SEGUER	2	1	t	8800.00	\N	2026-01-19 21:28:03.35482+00	2026-01-19 21:28:03.35482+00	1.00
350	\N	\N	FOTOCEDULA	4	1	t	9600.00	\N	2026-01-19 21:29:26.05895+00	2026-01-19 21:29:26.05895+00	1.00
351	\N	\N	CABLE UNIPOLAR 6MM	4	5	t	1500.00	\N	2026-01-19 21:31:08.113315+00	2026-01-19 21:31:08.113315+00	20.00
352	\N	\N	TERMINALES ELECTRONICOS	4	1	t	200.00	\N	2026-01-19 21:32:25.027605+00	2026-01-19 21:32:25.027605+00	5.00
353	\N	\N	PUNTA DESTORNILLADOR DOBLE	2	1	t	1000.00	\N	2026-01-19 21:37:28.912717+00	2026-01-19 21:37:28.912717+00	1.00
354	\N	\N	MECHA DE ACERO 6	2	1	t	5050.00	\N	2026-01-19 21:39:22.661862+00	2026-01-19 21:39:22.661862+00	1.00
355	\N	\N	MANGUERA CORRUGADA 3/4	4	5	t	500.00	\N	2026-01-19 22:04:32.662635+00	2026-01-19 22:04:32.662635+00	5.00
356	\N	\N	MANGUERA CORRUGADA 1/2	4	5	t	500.00	\N	2026-01-19 22:06:04.162966+00	2026-01-19 22:06:04.162966+00	10.00
357	\N	\N	LIJA AL AGUA 600	3	1	t	1000.00	\N	2026-01-19 22:40:05.574491+00	2026-01-19 22:40:05.574491+00	5.00
358	\N	\N	MECHA DE ACERO 12	2	1	t	21550.00	\N	2026-01-19 22:41:18.217777+00	2026-01-19 22:41:18.217777+00	1.00
359	\N	\N	TANZA PARA BORDEADORA 2	7	5	t	200.00	\N	2026-01-19 22:47:06.828615+00	2026-01-19 22:47:06.828615+00	10.00
360	\N	\N	SOGAC4MM	\N	5	t	350.00	\N	2026-01-19 22:52:15.516565+00	2026-01-19 22:52:15.516565+00	10.00
361	\N	\N	ESPATULA PLASTICA 15CM	3	1	t	3000.00	\N	2026-01-19 23:13:22.331745+00	2026-01-19 23:13:22.331745+00	1.00
362	\N	\N	ESPATULA PLASTICA 8CM	3	1	t	2300.00	\N	2026-01-19 23:14:08.186378+00	2026-01-19 23:14:08.186378+00	1.00
363	\N	\N	ESPATULA PLASTICA 4CM	3	1	t	1500.00	\N	2026-01-19 23:14:44.84882+00	2026-01-19 23:14:44.84882+00	1.00
364	\N	\N	TORNILLO FIX 4X50	6	1	t	30.00	\N	2026-01-19 23:18:54.08914+00	2026-01-19 23:18:54.08914+00	20.00
365	\N	\N	CABALLATE	3	1	t	22000.00	\N	2026-01-19 23:21:07.995903+00	2026-01-19 23:21:07.995903+00	1.00
366	\N	\N	SOPORTE DE MADERA PARA CORTINA	9	1	t	3000.00	\N	2026-01-19 23:29:36.80105+00	2026-01-19 23:29:36.80105+00	5.00
367	\N	\N	ESPATULA DE ACERO 12,5CM	3	1	t	4300.00	\N	2026-01-19 23:31:36.012299+00	2026-01-19 23:31:36.012299+00	1.00
368	\N	\N	ESPATULA DE ACERO 10CM	3	1	t	3200.00	\N	2026-01-19 23:33:15.402518+00	2026-01-19 23:33:15.402518+00	1.00
369	\N	\N	ESPATULA DE ACERO GALGO 10CM	3	1	t	8300.00	\N	2026-01-19 23:34:42.398778+00	2026-01-19 23:34:42.398778+00	1.00
370	\N	\N	CUTTER 18MM	2	1	t	8900.00	\N	2026-01-19 23:39:23.607522+00	2026-01-19 23:39:23.607522+00	1.00
371	\N	\N	PINCEL GIOTTO 26	3	1	t	3400.00	\N	2026-01-19 23:40:38.615974+00	2026-01-19 23:40:38.615974+00	1.00
372	\N	\N	CUTTER 9MM	3	1	t	6000.00	\N	2026-01-19 23:41:54.567261+00	2026-01-19 23:41:54.567261+00	1.00
373	\N	\N	CANDADO50MM	8	1	t	6500.00	\N	2026-01-19 23:44:42.761789+00	2026-01-19 23:44:42.761789+00	1.00
374	\N	\N	MANGUERA LIVIANA DE JARDIN DE 1/2	7	5	t	800.00	\N	2026-01-19 23:49:04.285016+00	2026-01-19 23:49:04.285016+00	15.00
375	\N	\N	RODILLO CUBREMAS 22	3	1	t	22000.00	\N	2026-01-19 23:55:25.296766+00	2026-01-19 23:55:25.296766+00	1.00
376	\N	\N	REVOQUE FINO X 2KG	3	1	t	2500.00	\N	2026-01-19 23:58:47.482222+00	2026-01-19 23:59:30.96607+00	1.00
377	\N	\N	RODILLO CUBREMAS 17	3	1	t	6600.00	\N	2026-01-20 00:00:35.38175+00	2026-01-20 00:02:27.843194+00	1.00
378	\N	\N	RODILLO ANTIGOTAS 17	3	1	t	5400.00	\N	2026-01-20 00:04:58.708881+00	2026-01-20 00:04:58.708881+00	1.00
379	\N	\N	RODILLO ANTIGOTAS 22	3	1	t	6100.00	\N	2026-01-20 00:08:14.979175+00	2026-01-20 00:08:14.979175+00	1.00
380	\N	\N	RODILLO ARTE FOAM 16	3	1	t	5450.00	\N	2026-01-20 00:12:22.861709+00	2026-01-20 00:12:22.861709+00	1.00
381	\N	\N	RODILLO ARTE FOAM 7	3	1	t	4900.00	\N	2026-01-20 00:13:03.108017+00	2026-01-20 00:13:03.108017+00	1.00
382	\N	\N	GANCHO PLASTICO PARA CORTINA BAÑO	9	1	t	200.00	\N	2026-01-20 00:18:24.978532+00	2026-01-20 00:18:24.978532+00	10.00
383	\N	\N	SIFON DOBLE	5	1	t	20950.00	\N	2026-01-20 00:23:17.3485+00	2026-01-20 00:23:17.3485+00	1.00
384	\N	\N	PISTOLA APLICADORA DE SILICONA PROFESIONAL	2	1	t	14850.00	\N	2026-01-20 00:28:55.177641+00	2026-01-20 00:28:55.177641+00	1.00
385	\N	\N	TERRAJA PARA CAÑO	5	1	t	21300.00	\N	2026-01-20 00:29:50.531859+00	2026-01-20 00:29:50.531859+00	1.00
386	\N	\N	PISTOLA APLICADORA DE SILICONA REFORZADA	2	1	t	10100.00	\N	2026-01-20 00:31:55.316265+00	2026-01-20 00:31:55.316265+00	1.00
387	\N	\N	PERCHA AUTOADHESIVA OVALADA	10	1	t	3750.00	\N	2026-01-20 00:36:25.851445+00	2026-01-20 00:36:25.851445+00	1.00
388	\N	\N	PERCHA AUTOADHESIVA REDONDA X6	10	1	t	4550.00	\N	2026-01-20 00:37:49.968781+00	2026-01-20 00:37:49.968781+00	1.00
389	\N	\N	PERCHA AUTOADHESIVA CUADRADA X2	10	1	t	3750.00	\N	2026-01-20 00:39:10.710943+00	2026-01-20 00:39:10.710943+00	1.00
390	\N	\N	ULTRA CEBO MOSCA	12	9	t	3200.00	\N	2026-01-20 00:40:50.54684+00	2026-01-20 00:40:50.54684+00	1.00
391	\N	\N	COCINA PORTATIL PARA CAMPING	\N	1	t	64850.00	\N	2026-01-20 00:43:59.16502+00	2026-01-20 00:43:59.16502+00	1.00
392	\N	\N	ESTAÑO 63%	4	1	t	8500.00	\N	2026-01-20 00:45:12.179791+00	2026-01-20 00:45:12.179791+00	2.00
393	\N	\N	GUANTES NITRILO NARANJA	9	11	t	3300.00	\N	2026-01-20 00:46:45.096108+00	2026-01-20 00:46:45.096108+00	2.00
394	\N	\N	LIQUIDO DESINFECTANTE TRIUNFO 1/2 L	9	1	t	6000.00	\N	2026-01-20 20:17:44.87062+00	2026-01-20 20:17:44.87062+00	1.00
395	\N	\N	LIQUIDO DESINFECTANTE TRIUNFO 1 L	9	1	t	9200.00	\N	2026-01-20 20:19:38.465487+00	2026-01-20 20:19:38.465487+00	1.00
396	\N	\N	TORNILLO FIX 18X12	6	1	t	10.00	\N	2026-01-20 20:26:49.078402+00	2026-01-20 20:26:49.078402+00	50.00
397	\N	\N	FELPA CUADRADA AUTOADHESIVA SABELCORT	9	12	t	4500.00	\N	2026-01-20 20:34:10.556997+00	2026-01-20 20:34:10.556997+00	1.00
398	\N	\N	FELPA REDONDA AUTOADHESIVA SABELCORT	9	12	t	4500.00	\N	2026-01-20 20:35:55.636978+00	2026-01-20 20:35:55.636978+00	1.00
399	\N	\N	TOPETINAS AUTOADHESIVAS SABELCORT X4	9	12	t	3500.00	\N	2026-01-20 20:37:41.282552+00	2026-01-20 20:37:41.282552+00	1.00
400	\N	\N	MECHA WIDIA LARGA 12MM	2	1	t	9700.00	\N	2026-01-20 20:42:08.363335+00	2026-01-20 20:42:08.363335+00	1.00
401	\N	\N	REGADOR ASPERSOR CON BASE ESQUI	7	1	t	12550.00	\N	2026-01-20 20:45:25.020241+00	2026-01-20 20:45:25.020241+00	1.00
402	\N	\N	RASTRILLO PLASTICO MEDIANO	7	1	t	3200.00	\N	2026-01-20 20:49:58.745078+00	2026-01-20 20:49:58.745078+00	1.00
403	\N	\N	TANZA PARA BORDEADORA 2,5	7	5	t	200.00	\N	2026-01-20 21:16:51.907598+00	2026-01-20 21:16:51.907598+00	10.00
404	\N	\N	MODULO TECLA  EXTERIOR	4	1	t	1700.00	\N	2026-01-20 21:22:26.418022+00	2026-01-20 21:22:26.418022+00	1.00
405	\N	\N	ADHESIVO DE CONTACTO ESPECIAL FORTEX 1KG	10	7	t	19000.00	\N	2026-01-20 21:25:23.039261+00	2026-01-20 21:25:23.039261+00	1.00
406	\N	\N	ADHESIVO DE CONTACTO ESPECIAL FORTEX 1/2KG	10	7	t	10700.00	\N	2026-01-20 21:26:17.218656+00	2026-01-20 21:26:17.218656+00	1.00
407	\N	\N	ADHESIVO DE CONTACTO ESPECIAL FORTEX 1/4KG	10	7	t	6600.00	\N	2026-01-20 21:27:17.598289+00	2026-01-20 21:27:17.598289+00	1.00
408	\N	\N	INFLADOR ROTTWEILER	2	1	t	30200.00	\N	2026-01-20 21:42:19.969783+00	2026-01-20 21:42:19.969783+00	1.00
409	\N	\N	CAÑO 110	5	5	t	6500.00	\N	2026-01-20 22:55:32.762845+00	2026-01-20 22:55:32.762845+00	1.00
410	\N	\N	CUPLA 110	5	1	t	3200.00	\N	2026-01-20 22:55:58.359298+00	2026-01-20 22:55:58.359298+00	1.00
411	\N	\N	ESCALERA 7 ESCALONES	7	1	t	89000.00	\N	2026-01-20 23:03:09.529177+00	2026-01-20 23:03:09.529177+00	1.00
412	\N	\N	CINTA METRICA 5MTRS	2	1	t	4600.00	\N	2026-01-20 23:07:47.921823+00	2026-01-20 23:07:47.921823+00	1.00
413	\N	\N	CINTA METRICA 3MTRS	2	1	t	4200.00	\N	2026-01-20 23:11:19.755528+00	2026-01-20 23:11:19.755528+00	1.00
414	\N	\N	CINTA METRICA 2MTRS	2	1	t	11200.00	\N	2026-01-20 23:12:15.056445+00	2026-01-20 23:12:15.056445+00	1.00
415	\N	\N	GANCHO ESTIRA TEJIDOS 5/16X8	6	1	t	700.00	\N	2026-01-20 23:18:20.206634+00	2026-01-20 23:18:20.206634+00	5.00
416	\N	\N	TORNILLO FIX 18 X 25MM	6	1	t	15.00	\N	2026-01-20 23:21:29.209878+00	2026-01-20 23:21:29.209878+00	20.00
417	\N	\N	MECHA COPA 6 PCS	2	12	t	6650.00	\N	2026-01-20 23:27:12.358791+00	2026-01-20 23:27:12.358791+00	1.00
418	\N	\N	PILAS C2	4	1	t	1700.00	\N	2026-01-20 23:30:28.367687+00	2026-01-20 23:30:28.367687+00	1.00
419	\N	\N	LLAVE DE PASO PVC 1/2	5	1	t	2800.00	\N	2026-01-20 23:34:30.78542+00	2026-01-20 23:34:30.78542+00	1.00
420	\N	\N	SOPORTE ESTANTE 25X20	\N	1	t	3500.00	\N	2026-01-20 23:39:41.469205+00	2026-01-20 23:39:41.469205+00	2.00
421	\N	\N	TORNILLO FIX 5X40	6	1	t	35.00	\N	2026-01-20 23:41:47.146306+00	2026-01-20 23:41:47.146306+00	20.00
422	\N	\N	SOPORTE ESTANTE 15X20	\N	1	t	3300.00	\N	2026-01-20 23:44:29.691547+00	2026-01-20 23:44:29.691547+00	2.00
423	\N	\N	TIRAFONDO 12	6	1	t	250.00	\N	2026-01-20 23:49:56.656275+00	2026-01-20 23:49:56.656275+00	5.00
424	\N	\N	ESCALERA ALUMINIO MULTIUSO 4X4	2	1	t	250000.00	\N	2026-01-20 23:52:58.402096+00	2026-01-20 23:52:58.402096+00	1.00
425	\N	\N	SACABICHOS	7	1	t	5000.00	\N	2026-01-21 00:04:40.778725+00	2026-01-21 00:04:40.778725+00	1.00
426	\N	\N	DIYUNTOR INTERRUPTOR	4	1	t	43000.00	\N	2026-01-21 00:06:20.151976+00	2026-01-21 00:06:20.151976+00	1.00
427	\N	\N	SOPAPA CHICA DE GOMA	9	1	t	2500.00	\N	2026-01-21 12:58:18.691478+00	2026-01-21 12:58:18.691478+00	1.00
428	\N	\N	CANDADO 38MM	8	1	t	3300.00	\N	2026-01-21 20:27:42.270298+00	2026-01-21 20:27:42.270298+00	1.00
429	\N	\N	MANGUERA DE CARGA LAVARROPA	9	1	t	7100.00	\N	2026-01-21 21:15:55.339655+00	2026-01-21 21:19:24.281423+00	1.00
430	\N	\N	CANILLA DE PVC DE 1/2	5	1	t	2400.00	\N	2026-01-21 21:32:18.873347+00	2026-01-21 21:32:18.873347+00	1.00
431	\N	\N	MECHA DE ACERO 2,5	6	1	t	2800.00	\N	2026-01-21 21:35:46.82497+00	2026-01-21 21:35:46.82497+00	1.00
432	\N	\N	CINTA AISLADORA NEGRA 25M	4	1	t	2500.00	\N	2026-01-21 21:41:33.264501+00	2026-01-21 21:41:33.264501+00	1.00
433	\N	\N	TUBO LED 120CM	4	1	t	3950.00	\N	2026-01-21 21:56:00.683521+00	2026-01-21 21:56:00.683521+00	1.00
434	\N	\N	TUBO LED 60CM	4	1	t	3500.00	\N	2026-01-21 22:25:03.093622+00	2026-01-21 22:25:03.093622+00	1.00
435	\N	\N	ZOCALO PARA TUBO DE LED DE 60CM	4	1	t	3000.00	\N	2026-01-21 22:26:31.265579+00	2026-01-21 22:26:31.265579+00	1.00
436	\N	\N	ZOCALO PARA TUBO DE LED DE 120CM	4	1	t	3650.00	\N	2026-01-21 22:27:01.95499+00	2026-01-21 22:27:01.95499+00	1.00
437	\N	\N	LAMPARA PERFUME	4	1	t	1850.00	\N	2026-01-21 22:30:31.635195+00	2026-01-21 22:30:31.635195+00	2.00
438	\N	\N	CURVA PLANA 20X10 BLANCA	4	1	t	1000.00	\N	2026-01-21 22:49:13.944472+00	2026-01-21 22:49:13.944472+00	2.00
439	\N	\N	TERMINAL PALA SIN COBERTURA	4	1	t	200.00	\N	2026-01-21 22:55:43.589641+00	2026-01-21 22:55:43.589641+00	10.00
440	\N	\N	BISAGRA LIBRO N°88	\N	1	t	2500.00	\N	2026-01-21 22:59:22.152394+00	2026-01-21 22:59:22.152394+00	2.00
441	\N	\N	CUPLA DE 25  TERMOFUSION	5	1	t	700.00	\N	2026-01-21 23:10:48.419911+00	2026-01-21 23:10:48.419911+00	2.00
442	\N	\N	TEFLON 1/2	5	1	t	550.00	\N	2026-01-21 23:12:46.882908+00	2026-01-21 23:12:46.882908+00	2.00
204	\N	\N	PRECINTOS 25CM	4	1	t	75.00	\N	2026-01-17 15:54:05.165759+00	2026-01-21 23:21:14.819503+00	100.00
443	\N	\N	HERRAJE CON RUEDITA PARA PLACARD	\N	1	t	1250.00	\N	2026-01-21 23:32:24.347819+00	2026-01-21 23:32:24.347819+00	1.00
444	\N	\N	ALGUICIDA 1L	\N	1	t	9500.00	\N	2026-01-21 23:46:23.609033+00	2026-01-21 23:46:23.609033+00	1.00
445	\N	\N	UNION RECTA PARA CANAL	4	1	t	1000.00	\N	2026-01-22 00:07:48.332246+00	2026-01-22 00:07:48.332246+00	2.00
446	\N	\N	MECHA ESCALONADA 4-32MM	2	1	t	25000.00	\N	2026-01-22 00:12:09.025012+00	2026-01-22 00:12:09.025012+00	1.00
447	\N	\N	LLAVE PUNTO Y TOMA EXTERIOR	4	1	t	3550.00	\N	2026-01-22 00:16:23.554152+00	2026-01-22 00:16:23.554152+00	1.00
448	\N	\N	TOMA EXTERIOR	4	1	t	2000.00	\N	2026-01-22 00:18:08.401339+00	2026-01-22 00:18:08.401339+00	1.00
449	\N	\N	TOMA DOBLE EXTERIOR	4	1	t	4000.00	\N	2026-01-22 00:27:02.521998+00	2026-01-22 00:27:02.521998+00	1.00
450	\N	\N	TOMA EXTERIOR DE 20A	4	1	t	3200.00	\N	2026-01-22 00:32:25.212369+00	2026-01-22 00:32:25.212369+00	1.00
451	\N	\N	LAMPARA BIPIN G9	4	1	t	9200.00	\N	2026-01-22 00:34:40.362214+00	2026-01-22 00:34:40.362214+00	1.00
452	\N	\N	PLAFON LED 18W	4	1	t	10600.00	\N	2026-01-22 00:37:25.225122+00	2026-01-22 00:38:37.576926+00	1.00
453	\N	\N	PLAFON LED 12W	4	1	t	10260.00	\N	2026-01-22 00:40:24.840415+00	2026-01-22 00:40:24.840415+00	1.00
454	\N	\N	PLAFON LED 24W	4	1	t	19500.00	\N	2026-01-22 00:42:53.943816+00	2026-01-22 00:42:53.943816+00	1.00
455	\N	\N	DISCO DIAMANTE PARA CORTE DE VIDRIO 115X22MM	3	1	t	21300.00	\N	2026-01-22 00:45:43.692759+00	2026-01-22 00:45:43.692759+00	1.00
456	\N	\N	KIT COMPLETO PARA REPARACION DE GOMERA	7	1	t	1250.00	\N	2026-01-22 00:52:14.983488+00	2026-01-22 00:52:14.983488+00	1.00
457	\N	\N	TRIPLE PIRAMIDE	4	1	t	4000.00	\N	2026-01-22 00:53:51.426765+00	2026-01-22 00:53:51.426765+00	1.00
458	\N	\N	THINNER SELLO DE ORO	3	1	t	5650.00	\N	2026-01-22 10:34:19.822286+00	2026-01-22 10:34:19.822286+00	1.00
459	\N	\N	TIRAS GOMA MOCHILA	9	1	t	200.00	\N	2026-01-22 20:03:28.256742+00	2026-01-22 20:03:28.256742+00	0.00
460	\N	\N	SELLA ROSCA POMO 25CC HIRO3	5	1	t	3650.00	\N	2026-01-22 21:08:58.66079+00	2026-01-22 21:08:58.66079+00	1.00
461	\N	\N	TEFLON 3/4	5	1	t	1000.00	\N	2026-01-22 21:13:50.619147+00	2026-01-22 21:13:50.619147+00	1.00
462	\N	\N	TEFLON 1"	5	1	t	1000.00	\N	2026-01-22 21:13:50.942922+00	2026-01-22 21:26:14.191231+00	10.00
463	\N	\N	CUERITO 3/4	5	1	t	300.00	\N	2026-01-22 21:47:07.135704+00	2026-01-22 21:47:07.135704+00	1.00
464	\N	\N	TORNILLO FIX 6X60	6	1	t	55.00	\N	2026-01-22 22:35:24.756548+00	2026-01-22 22:35:24.756548+00	10.00
465	\N	\N	VIRUTA FINA	9	1	t	5500.00	\N	2026-01-22 22:40:29.625854+00	2026-01-22 22:40:29.625854+00	1.00
466	\N	\N	VIRUTA GRUESA	9	1	t	5500.00	\N	2026-01-22 22:41:03.008329+00	2026-01-22 22:41:03.008329+00	1.00
467	\N	\N	PITON CERRADO S/TOPE N°8	6	1	t	750.00	\N	2026-01-22 22:47:54.609067+00	2026-01-22 22:47:54.609067+00	1.00
469	\N	\N	TERMOCONTRIBLE 3MM	4	5	t	4500.00	\N	2026-01-22 22:53:21.004976+00	2026-01-22 22:53:21.004976+00	1.00
468	\N	\N	TERMOCONTRIBLE 6MM	4	5	t	4500.00	\N	2026-01-22 22:52:29.462502+00	2026-01-22 22:54:17.957505+00	1.00
470	\N	\N	TERMOCONTRAIBLE 13	4	5	t	8650.00	\N	2026-01-22 22:55:18.484007+00	2026-01-22 22:55:18.484007+00	1.00
471	\N	\N	PALANCA DE MOCHILA DE PLASTICO	5	1	t	2000.00	\N	2026-01-22 22:57:14.331218+00	2026-01-22 22:57:14.331218+00	2.00
472	\N	\N	PALANCA DE MOCHILA DE METAL	5	1	t	11550.00	\N	2026-01-22 22:58:19.184766+00	2026-01-22 22:58:19.184766+00	1.00
473	\N	\N	ESPUMA AUTOPOLISH 1L	3	1	t	19550.00	\N	2026-01-22 23:41:19.822883+00	2026-01-22 23:41:19.822883+00	1.00
474	\N	\N	LAMPARA MACROLED	4	1	t	5000.00	\N	2026-01-22 23:51:38.308828+00	2026-01-22 23:51:38.308828+00	1.00
475	\N	\N	LAMPARA LED CANDIL 1,5W	4	1	t	3400.00	\N	2026-01-22 23:52:46.501067+00	2026-01-22 23:52:46.501067+00	1.00
476	\N	\N	LAMPARA R75LED 8W	4	1	t	14500.00	\N	2026-01-22 23:54:16.220423+00	2026-01-22 23:54:16.220423+00	1.00
477	\N	\N	ACOPLE COMPRESION 1/2	5	1	t	4600.00	\N	2026-01-23 00:00:09.324962+00	2026-01-23 00:00:09.324962+00	1.00
478	\N	\N	ACOPLE COMPRESION 3/4	5	1	t	5700.00	\N	2026-01-23 00:03:43.536107+00	2026-01-23 00:03:43.536107+00	1.00
479	\N	\N	ACOPLE COMPRESION 1	5	1	t	7850.00	\N	2026-01-23 00:04:55.429712+00	2026-01-23 00:04:55.429712+00	1.00
305	\N	\N	ESPIGA 1/2 NEGRA	5	1	t	250.00	\N	2026-01-18 16:10:28.592749+00	2026-01-23 00:07:52.016824+00	5.00
247	\N	\N	ROSCA CON TUERCA 1/2 ROJA	5	1	t	300.00	\N	2026-01-17 23:59:06.237789+00	2026-01-23 00:10:38.034771+00	2.00
480	\N	\N	ROSCA CON TUERCA 1/2 EPOXI	5	1	t	3800.00	\N	2026-01-23 00:14:16.746789+00	2026-01-23 00:14:16.746789+00	1.00
481	\N	\N	ROSCA CON TUERCA 3/4 EPOXI	5	1	t	4300.00	\N	2026-01-23 00:15:11.554371+00	2026-01-23 00:15:11.554371+00	1.00
482	\N	\N	CONEX CORRUGADA MOCHILA 2/T	5	1	t	4600.00	\N	2026-01-23 00:18:55.556308+00	2026-01-23 00:18:55.556308+00	1.00
483	\N	\N	CANILLA DE METAL DE 1/2	5	1	t	7500.00	\N	2026-01-23 01:01:44.848987+00	2026-01-23 01:01:44.848987+00	2.00
\.


--
-- Data for Name: product_stock; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.product_stock (product_id, on_hand_qty, updated_at) FROM stdin;
6	2.000	2026-01-13 21:25:10.351255+00
5	2.000	2026-01-13 21:25:10.351255+00
3	2.000	2026-01-13 21:25:10.351255+00
2	1.000	2026-01-13 21:25:10.351255+00
93	4.000	2026-01-18 17:43:27.589002+00
52	19.000	2026-01-18 16:36:02.127492+00
10	200.000	2026-01-13 23:35:17.970419+00
12	200.000	2026-01-13 23:35:17.970419+00
13	12.000	2026-01-13 23:35:17.970419+00
14	2.000	2026-01-13 23:35:17.970419+00
16	2.000	2026-01-13 23:35:17.970419+00
18	500.000	2026-01-13 23:35:17.970419+00
19	500.000	2026-01-13 23:35:17.970419+00
20	500.000	2026-01-13 23:35:17.970419+00
7	200.000	2026-01-13 23:35:17.970419+00
58	83.000	2026-01-22 00:46:12.793663+00
61	106.000	2026-01-22 00:46:12.793663+00
25	5.000	2026-01-14 00:57:45.636678+00
26	60.000	2026-01-14 00:57:45.636678+00
27	20.000	2026-01-14 00:57:45.636678+00
28	20.000	2026-01-14 00:57:45.636678+00
29	10.000	2026-01-14 00:57:45.636678+00
30	10.000	2026-01-14 00:57:45.636678+00
31	2.000	2026-01-14 00:57:45.636678+00
32	5.000	2026-01-14 00:57:45.636678+00
33	50.000	2026-01-14 00:57:45.636678+00
34	25.000	2026-01-14 00:57:45.636678+00
35	10.000	2026-01-14 00:57:45.636678+00
36	20.000	2026-01-14 00:57:45.636678+00
37	20.000	2026-01-14 00:57:45.636678+00
38	20.000	2026-01-14 00:57:45.636678+00
39	20.000	2026-01-14 00:57:45.636678+00
40	20.000	2026-01-14 00:57:45.636678+00
41	3.000	2026-01-14 00:57:45.636678+00
42	1.000	2026-01-14 00:57:45.636678+00
43	100.000	2026-01-14 00:57:45.636678+00
308	10.000	2026-01-18 16:26:59.590826+00
46	2.000	2026-01-14 00:57:45.636678+00
47	2.000	2026-01-14 00:57:45.636678+00
48	5.000	2026-01-14 00:57:45.636678+00
49	5.000	2026-01-14 00:57:45.636678+00
8	570.000	2026-01-18 17:40:00.700895+00
53	120.000	2026-01-14 00:57:45.636678+00
54	20.000	2026-01-14 00:57:45.636678+00
55	10.000	2026-01-14 00:57:45.636678+00
56	10.000	2026-01-14 00:57:45.636678+00
57	2.000	2026-01-14 00:57:45.636678+00
84	0.000	2026-01-18 14:09:51.985688+00
60	10.000	2026-01-14 00:57:45.636678+00
289	0.000	2026-01-18 15:19:26.530621+00
23	19.000	2026-01-14 21:50:08.918209+00
4	0.000	2026-01-14 21:50:08.918209+00
300	4.000	2026-01-18 15:56:52.107039+00
323	50.000	2026-01-18 17:57:46.287739+00
51	20.000	2026-01-14 22:17:35.804665+00
115	1.000	2026-01-17 16:46:35.009566+00
59	10.000	2026-01-14 22:17:35.804665+00
290	49.000	2026-01-18 15:19:26.530621+00
44	19.000	2026-01-17 21:47:01.693812+00
65	25.000	2026-01-14 22:56:07.974939+00
70	5.000	2026-01-14 22:56:07.974939+00
288	8.000	2026-01-18 15:24:36.713874+00
66	1.000	2026-01-14 23:09:57.721525+00
68	12.000	2026-01-14 23:09:57.721525+00
67	12.000	2026-01-14 23:09:57.721525+00
73	2.000	2026-01-14 23:12:43.46236+00
74	4.000	2026-01-14 23:12:43.46236+00
75	4.000	2026-01-14 23:12:43.46236+00
254	3.000	2026-01-22 22:50:59.469066+00
297	1.000	2026-01-18 15:46:50.727056+00
78	4.000	2026-01-15 00:35:02.448922+00
79	15.000	2026-01-15 00:35:02.448922+00
80	15.000	2026-01-15 00:35:02.448922+00
303	488.000	2026-01-22 22:45:06.615136+00
107	3.000	2026-01-16 20:40:11.325213+00
313	46.000	2026-01-22 23:28:28.847199+00
86	30.000	2026-01-15 00:35:02.448922+00
87	4.000	2026-01-15 00:35:02.448922+00
89	1.000	2026-01-15 00:35:02.448922+00
91	5.000	2026-01-15 00:35:02.448922+00
99	5.000	2026-01-18 17:47:16.409425+00
92	50.000	2026-01-15 00:35:02.448922+00
94	6.000	2026-01-16 00:24:50.584374+00
97	4.000	2026-01-16 00:24:50.584374+00
98	3.000	2026-01-16 00:24:50.584374+00
103	20.000	2026-01-18 17:57:12.072589+00
69	47.000	2026-01-22 22:46:31.019458+00
133	1.000	2026-01-17 00:18:17.022072+00
17	44.000	2026-01-21 22:09:40.29315+00
298	1.000	2026-01-18 15:47:17.637827+00
22	5.000	2026-01-21 23:13:39.444266+00
106	10.000	2026-01-16 00:24:50.584374+00
105	7.000	2026-01-16 00:24:50.584374+00
108	2.000	2026-01-16 20:40:11.325213+00
112	5.000	2026-01-16 21:35:06.800789+00
111	10.000	2026-01-16 21:35:06.800789+00
110	10.000	2026-01-16 21:35:06.800789+00
63	10.000	2026-01-16 21:35:06.800789+00
301	985.000	2026-01-18 15:56:52.107039+00
327	100.000	2026-01-18 18:11:15.517436+00
9	580.000	2026-01-18 16:34:24.602888+00
304	49.000	2026-01-18 16:13:35.769403+00
100	5.000	2026-01-20 19:08:24.037212+00
15	1100.000	2026-01-18 16:19:47.180677+00
24	4.000	2026-01-21 21:42:37.423897+00
104	23.000	2026-01-21 22:59:50.072643+00
355	100.000	2026-01-19 22:04:32.671925+00
21	10.000	2026-01-22 03:06:03.589886+00
132	1.000	2026-01-17 00:18:17.022072+00
129	1.000	2026-01-17 00:18:17.022072+00
131	1.000	2026-01-17 00:18:17.022072+00
130	1.000	2026-01-17 00:18:17.022072+00
136	2.000	2026-01-17 00:18:17.022072+00
134	5.000	2026-01-17 00:18:17.022072+00
135	4.000	2026-01-17 00:18:17.022072+00
353	14.000	2026-01-22 20:17:29.364183+00
102	21.000	2026-01-22 22:44:35.627136+00
139	0.000	2026-01-17 12:55:26.778993+00
469	9.000	2026-01-22 22:56:33.583024+00
339	4.000	2026-01-18 19:17:54.566008+00
11	94.000	2026-01-19 21:06:30.591529+00
345	2.000	2026-01-19 21:17:43.153592+00
343	94.000	2026-01-19 21:06:30.591529+00
396	990.000	2026-01-20 20:38:25.793468+00
77	5.000	2026-01-17 23:23:39.796193+00
349	0.000	2026-01-19 21:28:45.104264+00
467	48.000	2026-01-22 22:50:59.469066+00
350	1.000	2026-01-19 21:29:44.542393+00
96	1.000	2026-01-21 00:19:10.226881+00
385	1.000	2026-01-20 00:29:50.538163+00
382	150.000	2026-01-21 00:07:06.00775+00
383	5.000	2026-01-20 00:47:35.896751+00
384	2.000	2026-01-20 00:47:35.896751+00
478	10.000	2026-01-23 00:24:44.584644+00
81	29.000	2026-01-20 00:47:35.896751+00
424	1.000	2026-01-21 00:07:06.00775+00
95	2.000	2026-01-21 00:20:41.97121+00
88	3.000	2026-01-21 00:23:16.175584+00
83	25.000	2026-01-21 21:37:54.431634+00
409	1.000	2026-01-20 22:56:36.208188+00
62	19.000	2026-01-21 20:50:57.407784+00
76	1.000	2026-01-21 21:30:21.27387+00
429	0.000	2026-01-21 21:29:40.413629+00
356	100.000	2026-01-19 22:06:04.168062+00
291	99.000	2026-01-18 15:19:26.530621+00
292	46.000	2026-01-18 15:24:36.713874+00
411	2.000	2026-01-21 00:07:06.00775+00
299	1.000	2026-01-18 15:56:52.107039+00
468	10.000	2026-01-22 22:52:29.475119+00
389	5.000	2026-01-20 00:47:35.896751+00
309	75.000	2026-01-18 16:34:24.602888+00
391	2.000	2026-01-20 00:47:35.896751+00
315	18.000	2026-01-18 17:24:37.92835+00
417	2.000	2026-01-21 00:07:06.00775+00
425	5.000	2026-01-21 00:07:06.00775+00
318	4.000	2026-01-18 17:47:16.409425+00
397	3.000	2026-01-20 20:38:25.793468+00
319	1.000	2026-01-18 17:54:12.449403+00
426	3.000	2026-01-21 00:07:06.00775+00
149	2.000	2026-01-21 00:10:44.699544+00
322	19.000	2026-01-18 17:57:12.072589+00
403	95.000	2026-01-20 21:17:23.37761+00
324	9.000	2026-01-18 18:24:11.049667+00
470	10.000	2026-01-22 22:55:18.488609+00
404	0.000	2026-01-20 21:22:49.246225+00
410	3.000	2026-01-20 22:56:36.208188+00
340	96.000	2026-01-18 19:19:05.91948+00
195	9.000	2026-01-20 22:58:16.028503+00
211	3.000	2026-01-21 21:29:40.413629+00
418	0.000	2026-01-20 23:31:20.854089+00
250	94.000	2026-01-20 23:43:20.164143+00
302	1.000	2026-01-21 21:29:40.413629+00
421	196.000	2026-01-20 23:43:20.164143+00
253	96.000	2026-01-20 23:51:05.054496+00
393	8.000	2026-01-22 23:28:28.847199+00
317	87.000	2026-01-21 21:29:40.413629+00
85	26.000	2026-01-21 21:48:44.319355+00
1	195.000	2026-01-21 22:09:40.29315+00
436	6.000	2026-01-21 22:27:01.963975+00
305	59.000	2026-01-23 00:24:44.584644+00
440	18.000	2026-01-21 22:59:39.771687+00
480	10.000	2026-01-23 00:24:44.584644+00
443	9.000	2026-01-21 23:32:38.408456+00
390	17.000	2026-01-23 01:03:06.899361+00
446	0.000	2026-01-22 00:12:47.637026+00
460	9.000	2026-01-23 01:03:53.14178+00
438	50.000	2026-01-22 00:46:12.793663+00
450	10.000	2026-01-22 00:46:12.793663+00
452	4.000	2026-01-22 00:46:12.793663+00
453	1.000	2026-01-22 00:46:12.793663+00
454	13.000	2026-01-22 00:46:12.793663+00
456	6.000	2026-01-22 00:52:50.562763+00
463	8.000	2026-01-22 21:47:59.730371+00
181	37.000	2026-01-22 22:36:54.833599+00
466	2.000	2026-01-22 22:41:03.012934+00
357	12.000	2026-01-22 22:42:15.474268+00
465	2.000	2026-01-22 22:42:15.474268+00
481	5.000	2026-01-23 00:15:11.56731+00
471	9.000	2026-01-22 22:59:19.813378+00
479	3.000	2026-01-23 00:24:44.584644+00
416	1000.000	2026-01-21 00:07:06.00775+00
247	50.000	2026-01-23 00:24:44.584644+00
201	1000.000	2026-01-19 20:52:31.822919+00
114	1.000	2026-01-17 16:46:35.009566+00
116	1.000	2026-01-17 16:46:35.009566+00
117	1.000	2026-01-17 16:46:35.009566+00
118	1.000	2026-01-17 16:46:35.009566+00
138	10.000	2026-01-17 16:46:35.009566+00
137	10.000	2026-01-17 16:46:35.009566+00
141	10.000	2026-01-17 16:46:35.009566+00
140	10.000	2026-01-17 16:46:35.009566+00
125	1.000	2026-01-17 16:46:35.009566+00
120	1.000	2026-01-17 16:46:35.009566+00
124	1.000	2026-01-17 16:46:35.009566+00
119	1.000	2026-01-17 16:46:35.009566+00
123	1.000	2026-01-17 16:46:35.009566+00
122	1.000	2026-01-17 16:46:35.009566+00
121	1.000	2026-01-17 16:46:35.009566+00
128	1.000	2026-01-17 16:46:35.009566+00
127	1.000	2026-01-17 16:46:35.009566+00
126	1.000	2026-01-17 16:46:35.009566+00
143	1.000	2026-01-17 16:46:35.009566+00
144	1.000	2026-01-17 16:46:35.009566+00
64	40.000	2026-01-17 16:46:35.009566+00
251	86.000	2026-01-22 22:29:32.393724+00
190	7.000	2026-01-17 16:46:35.009566+00
72	11.000	2026-01-17 16:46:35.009566+00
177	6.000	2026-01-17 16:46:35.009566+00
175	6.000	2026-01-17 16:46:35.009566+00
176	7.000	2026-01-17 16:46:35.009566+00
412	5.000	2026-01-21 00:26:17.807976+00
347	20.000	2026-01-23 00:24:44.584644+00
204	1230.000	2026-01-22 00:46:12.793663+00
150	6.000	2026-01-17 16:46:35.009566+00
147	2.000	2026-01-17 16:46:35.009566+00
151	2.000	2026-01-17 16:46:35.009566+00
152	2.000	2026-01-17 16:46:35.009566+00
148	1.000	2026-01-17 16:46:35.009566+00
191	1.000	2026-01-17 16:46:35.009566+00
163	1.000	2026-01-17 16:46:35.009566+00
164	1.000	2026-01-17 16:46:35.009566+00
145	50.000	2026-01-17 16:46:35.009566+00
170	10.000	2026-01-17 16:46:35.009566+00
171	10.000	2026-01-17 16:46:35.009566+00
172	10.000	2026-01-17 16:46:35.009566+00
173	10.000	2026-01-17 16:46:35.009566+00
166	10.000	2026-01-17 16:46:35.009566+00
167	10.000	2026-01-17 16:46:35.009566+00
168	10.000	2026-01-17 16:46:35.009566+00
180	2.000	2026-01-17 16:46:35.009566+00
179	2.000	2026-01-17 16:46:35.009566+00
161	7.000	2026-01-17 16:46:35.009566+00
207	2.000	2026-01-17 16:46:35.009566+00
208	5.000	2026-01-17 20:54:29.073089+00
209	3.000	2026-01-17 20:54:29.073089+00
45	40.000	2026-01-22 00:46:12.793663+00
155	1.000	2026-01-17 20:54:29.073089+00
210	2.000	2026-01-17 20:54:29.073089+00
71	11.000	2026-01-19 21:43:30.793981+00
217	9.000	2026-01-17 22:01:59.014698+00
248	3.000	2026-01-21 23:13:04.128087+00
214	50.000	2026-01-17 21:57:51.601594+00
189	2.000	2026-01-17 22:56:25.061+00
153	80.000	2026-01-23 00:26:44.877653+00
218	3.000	2026-01-17 22:14:09.840403+00
219	46.000	2026-01-17 22:14:09.840403+00
220	90.000	2026-01-17 22:16:20.063689+00
200	39.000	2026-01-23 01:03:53.14178+00
221	2.000	2026-01-17 23:23:39.796193+00
231	4.000	2026-01-17 22:58:26.625766+00
224	98.000	2026-01-17 22:31:37.452771+00
222	3.000	2026-01-17 23:23:39.796193+00
225	14.000	2026-01-17 22:31:37.452771+00
232	3.000	2026-01-17 22:59:48.068778+00
101	20.000	2026-01-22 22:09:19.091053+00
228	5.000	2026-01-17 22:45:57.763277+00
227	9.000	2026-01-17 23:23:39.796193+00
229	5.000	2026-01-17 23:23:39.796193+00
230	9.000	2026-01-17 22:53:41.594359+00
233	10.000	2026-01-17 23:05:30.465691+00
226	10.000	2026-01-17 23:06:21.721302+00
234	5.000	2026-01-17 23:08:18.089802+00
235	5.000	2026-01-17 23:08:18.699965+00
236	40.000	2026-01-17 23:23:39.796193+00
237	2.000	2026-01-17 23:23:39.796193+00
238	2.000	2026-01-17 23:23:39.796193+00
239	2.000	2026-01-17 23:23:39.796193+00
215	41.000	2026-01-18 19:17:54.566008+00
243	9.000	2026-01-17 23:34:41.852742+00
241	18.000	2026-01-17 23:30:05.066245+00
246	5.000	2026-01-17 23:58:28.007752+00
255	1.000	2026-01-18 12:57:10.165006+00
242	6.000	2026-01-17 23:34:41.852742+00
244	19.000	2026-01-17 23:34:41.852742+00
160	0.000	2026-01-23 01:00:28.89996+00
158	25.000	2026-01-21 23:13:39.444266+00
249	100.000	2026-01-18 00:02:12.318725+00
194	10.000	2026-01-21 00:21:12.535467+00
165	3.000	2026-01-18 16:01:33.871547+00
252	100.000	2026-01-18 00:03:36.376914+00
198	10.000	2026-01-21 00:21:39.647186+00
197	10.000	2026-01-21 00:22:09.211649+00
196	10.000	2026-01-21 00:22:33.743118+00
245	4.000	2026-01-18 00:08:29.345335+00
258	30.000	2026-01-18 13:05:41.957494+00
213	50.000	2026-01-21 00:26:51.757445+00
256	3.000	2026-01-18 13:04:23.616115+00
109	9.000	2026-01-18 14:09:51.985688+00
162	5.000	2026-01-18 13:48:08.348295+00
257	19.000	2026-01-18 13:04:23.616115+00
178	5.000	2026-01-18 16:20:29.827893+00
154	89.000	2026-01-22 20:01:04.962422+00
186	5.000	2026-01-19 21:18:27.248284+00
263	1.000	2026-01-18 13:16:00.218473+00
113	42.000	2026-01-22 22:44:09.91115+00
261	95.000	2026-01-18 13:13:39.192369+00
259	170.000	2026-01-18 13:19:19.871257+00
192	5.000	2026-01-18 16:21:08.368406+00
182	98.000	2026-01-18 14:52:27.742809+00
142	9.000	2026-01-21 21:29:40.413629+00
183	98.000	2026-01-18 14:52:27.742809+00
398	8.000	2026-01-20 20:35:55.649963+00
293	975.000	2026-01-19 21:06:30.591529+00
358	4.000	2026-01-19 22:41:36.452468+00
216	14.000	2026-01-21 22:10:23.763988+00
159	6.000	2026-01-22 19:59:50.828353+00
174	1.000	2026-01-21 00:25:19.638035+00
157	5.000	2026-01-21 22:04:03.3004+00
392	21.000	2026-01-20 00:47:35.896751+00
193	9.000	2026-01-20 20:23:46.490857+00
206	1499.000	2026-01-20 20:53:50.631808+00
82	45.000	2026-01-21 21:39:29.795607+00
405	2.000	2026-01-20 21:25:23.05086+00
146	46.500	2026-01-21 13:40:59.638286+00
414	1.000	2026-01-20 23:12:15.063807+00
185	96.000	2026-01-20 22:58:16.028503+00
430	3.000	2026-01-21 21:32:44.472738+00
431	9.000	2026-01-21 21:38:14.587217+00
199	37.000	2026-01-21 21:40:46.948356+00
187	13.000	2026-01-21 21:40:01.843651+00
202	342.000	2026-01-21 21:48:44.319355+00
184	79.000	2026-01-22 22:09:19.091053+00
262	14.000	2026-01-18 13:13:39.192369+00
264	14.000	2026-01-18 13:19:19.871257+00
419	5.000	2026-01-21 00:07:06.00775+00
265	90.000	2026-01-18 13:25:44.542617+00
266	16.000	2026-01-18 13:48:08.348295+00
295	5.000	2026-01-18 15:33:45.895639+00
472	1.000	2026-01-22 22:58:19.189978+00
427	9.000	2026-01-21 12:58:52.884963+00
310	48.000	2026-01-18 16:34:24.602888+00
316	20.000	2026-01-18 17:24:10.571581+00
240	1.000	2026-01-18 17:24:37.92835+00
360	96.000	2026-01-19 23:06:31.302669+00
325	2.000	2026-01-18 18:24:11.049667+00
341	9.000	2026-01-19 20:42:02.336469+00
434	7.000	2026-01-21 22:25:03.102944+00
294	23.500	2026-01-19 20:50:08.686538+00
368	2.000	2026-01-19 23:33:35.793391+00
373	10.000	2026-01-19 23:44:58.849188+00
377	5.000	2026-01-20 00:47:35.896751+00
473	0.000	2026-01-22 23:41:47.627661+00
394	5.000	2026-01-20 20:18:19.010077+00
395	5.000	2026-01-20 20:19:38.471572+00
399	7.000	2026-01-20 20:37:41.293065+00
156	0.000	2026-01-21 23:44:02.482873+00
212	68.000	2026-01-20 20:43:29.762588+00
400	0.000	2026-01-20 20:43:29.762588+00
223	2.000	2026-01-21 23:44:02.482873+00
401	0.000	2026-01-20 20:47:22.225802+00
482	10.000	2026-01-23 00:24:44.584644+00
359	86.000	2026-01-20 21:15:28.642458+00
406	3.000	2026-01-20 21:26:17.230384+00
407	1.000	2026-01-20 21:27:37.088201+00
306	25.500	2026-01-20 22:58:16.028503+00
413	7.000	2026-01-20 23:11:19.767394+00
422	15.000	2026-01-20 23:44:29.70836+00
444	3.000	2026-01-21 23:46:41.07761+00
374	125.000	2026-01-23 01:02:08.86483+00
437	28.000	2026-01-22 00:46:12.793663+00
432	59.000	2026-01-22 00:46:12.793663+00
203	1050.000	2026-01-22 00:46:12.793663+00
447	11.000	2026-01-22 00:46:12.793663+00
448	12.000	2026-01-22 00:46:12.793663+00
451	10.000	2026-01-22 00:46:12.793663+00
457	6.000	2026-01-22 00:54:06.076454+00
441	46.000	2026-01-22 20:14:42.726585+00
461	9.000	2026-01-22 21:45:16.979092+00
188	9.000	2026-01-22 22:09:19.091053+00
205	755.000	2026-01-22 22:09:19.091053+00
260	4.000	2026-01-18 13:19:19.871257+00
296	1.000	2026-01-18 15:46:22.731403+00
307	10.000	2026-01-18 16:26:18.994638+00
268	24.000	2026-01-18 13:48:08.348295+00
311	50.000	2026-01-18 16:35:21.865324+00
408	3.000	2026-01-21 00:07:06.00775+00
380	5.000	2026-01-21 00:13:56.6752+00
312	36.000	2026-01-18 16:58:16.20752+00
270	280.000	2026-01-18 14:09:51.985688+00
271	480.000	2026-01-18 14:09:51.985688+00
415	100.000	2026-01-21 00:24:53.752251+00
474	8.000	2026-01-22 23:52:02.629793+00
283	4.000	2026-01-21 12:59:14.393891+00
274	5.000	2026-01-18 14:35:40.915415+00
267	8.000	2026-01-18 14:40:53.236353+00
272	750.000	2026-01-21 19:32:58.28665+00
475	4.000	2026-01-22 23:53:16.007125+00
314	20.000	2026-01-19 23:11:06.179045+00
320	9.000	2026-01-18 17:54:12.449403+00
279	0.000	2026-01-18 14:52:27.742809+00
321	3.000	2026-01-18 17:54:26.518223+00
361	4.000	2026-01-19 23:13:22.340798+00
281	25.000	2026-01-18 15:00:11.733655+00
476	1.000	2026-01-22 23:54:16.224949+00
328	4.000	2026-01-18 18:18:20.802194+00
287	12.000	2026-01-18 15:08:12.505054+00
277	23.000	2026-01-18 15:08:35.569402+00
362	1.000	2026-01-19 23:14:08.190985+00
278	19.000	2026-01-18 15:08:35.569402+00
275	9.000	2026-01-18 15:08:57.018875+00
363	3.000	2026-01-19 23:14:44.853762+00
428	12.000	2026-01-21 20:28:06.885271+00
285	2.000	2026-01-18 15:10:05.033336+00
329	1.000	2026-01-18 18:20:59.497078+00
477	7.000	2026-01-23 00:24:44.584644+00
326	44.000	2026-01-18 18:24:11.049667+00
364	92.000	2026-01-19 23:19:24.277311+00
330	94.000	2026-01-18 18:24:11.049667+00
365	2.000	2026-01-19 23:21:08.003173+00
331	9.000	2026-01-18 18:51:01.542916+00
346	15.000	2026-01-21 21:30:21.27387+00
90	96.000	2026-01-21 21:30:44.44111+00
366	97.000	2026-01-19 23:30:04.245025+00
348	1.000	2026-01-19 21:24:14.492007+00
367	5.000	2026-01-19 23:31:36.020227+00
369	1.000	2026-01-19 23:34:42.406341+00
351	993.000	2026-01-19 21:33:43.394326+00
352	43.000	2026-01-19 21:33:43.394326+00
269	493.000	2026-01-19 21:38:14.987581+00
354	5.000	2026-01-19 21:39:22.667917+00
433	9.000	2026-01-21 21:56:00.695256+00
483	9.000	2026-01-23 01:02:08.86483+00
370	3.000	2026-01-19 23:41:09.432564+00
342	2.000	2026-01-21 22:10:23.763988+00
372	4.000	2026-01-19 23:41:54.574647+00
435	2.000	2026-01-21 22:26:31.276435+00
376	4.000	2026-01-19 23:59:50.974285+00
381	1.000	2026-01-20 00:13:03.117432+00
344	20.000	2026-01-20 00:47:35.896751+00
375	5.000	2026-01-20 00:47:35.896751+00
379	5.000	2026-01-20 00:47:35.896751+00
282	25.000	2026-01-20 00:47:35.896751+00
386	2.000	2026-01-20 00:47:35.896751+00
387	5.000	2026-01-20 00:47:35.896751+00
388	5.000	2026-01-20 00:47:35.896751+00
284	1.000	2026-01-20 20:15:23.277816+00
273	5.000	2026-01-20 20:43:29.762588+00
280	2.000	2026-01-20 20:47:22.225802+00
442	13.000	2026-01-21 23:13:04.128087+00
402	3.000	2026-01-20 20:50:34.991351+00
439	250.000	2026-01-22 00:46:12.793663+00
371	5.000	2026-01-20 23:15:38.598285+00
445	20.000	2026-01-22 00:46:12.793663+00
449	10.000	2026-01-22 00:46:12.793663+00
420	7.000	2026-01-20 23:43:20.164143+00
455	1.000	2026-01-22 00:46:12.793663+00
423	496.000	2026-01-20 23:51:05.054496+00
458	22.000	2026-01-22 10:34:19.835281+00
459	7.000	2026-01-22 20:04:04.06156+00
462	0.000	2026-01-22 21:43:17.070082+00
464	43.000	2026-01-22 22:36:54.833599+00
50	14.000	2026-01-22 22:43:22.698637+00
276	985.000	2026-01-22 22:43:45.54926+00
286	1.000	2026-01-22 22:46:02.491227+00
378	3.000	2026-01-22 22:46:02.491227+00
\.


--
-- Data for Name: product_uom_price; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.product_uom_price (id, product_id, uom_id, sale_price, conversion_to_base, is_base, sku, barcode, created_at, updated_at) FROM stdin;
1	1	1	1500.00	1.0000	t	\N	\N	2026-01-13 21:09:43.435809+00	2026-01-18 18:41:16.728239+00
2	2	1	115200.00	1.0000	t	None	None	2026-01-13 21:18:34.665506+00	2026-01-18 18:41:16.728239+00
3	3	1	10750.00	1.0000	t	\N	\N	2026-01-13 21:20:04.274746+00	2026-01-18 18:41:16.728239+00
4	4	1	8500.00	1.0000	t	\N	\N	2026-01-13 21:20:43.830058+00	2026-01-18 18:41:16.728239+00
5	5	1	10750.00	1.0000	t	\N	\N	2026-01-13 21:21:21.031438+00	2026-01-18 18:41:16.728239+00
6	6	1	15150.00	1.0000	t	\N	\N	2026-01-13 21:21:57.582736+00	2026-01-18 18:41:16.728239+00
7	8	1	10.00	1.0000	t	\N	\N	2026-01-13 23:07:07.25178+00	2026-01-18 18:41:16.728239+00
8	9	1	10.00	1.0000	t	\N	\N	2026-01-13 23:08:30.419255+00	2026-01-18 18:41:16.728239+00
9	11	1	290.00	1.0000	t	\N	\N	2026-01-13 23:11:11.45146+00	2026-01-18 18:41:16.728239+00
10	12	1	430.00	1.0000	t	\N	\N	2026-01-13 23:11:49.252394+00	2026-01-18 18:41:16.728239+00
11	13	1	10500.00	1.0000	t	\N	\N	2026-01-13 23:12:52.496617+00	2026-01-18 18:41:16.728239+00
12	14	3	900.00	1.0000	t	\N	\N	2026-01-13 23:16:41.318667+00	2026-01-18 18:41:16.728239+00
13	15	3	900.00	1.0000	t	\N	\N	2026-01-13 23:17:43.28346+00	2026-01-18 18:41:16.728239+00
14	16	3	900.00	1.0000	t	\N	\N	2026-01-13 23:18:24.813317+00	2026-01-18 18:41:16.728239+00
15	17	1	2000.00	1.0000	t	\N	\N	2026-01-13 23:22:16.140654+00	2026-01-18 18:41:16.728239+00
16	10	1	170.00	1.0000	t	\N	\N	2026-01-13 23:09:54.433575+00	2026-01-18 18:41:16.728239+00
17	18	1	95.00	1.0000	t	\N	\N	2026-01-13 23:24:45.867721+00	2026-01-18 18:41:16.728239+00
18	19	1	100.00	1.0000	t	\N	\N	2026-01-13 23:25:25.800114+00	2026-01-18 18:41:16.728239+00
19	20	1	125.00	1.0000	t	\N	\N	2026-01-13 23:26:06.988713+00	2026-01-18 18:41:16.728239+00
20	7	1	45.00	1.0000	t	\N	\N	2026-01-13 23:06:03.28906+00	2026-01-18 18:41:16.728239+00
22	22	1	3000.00	1.0000	t	\N	\N	2026-01-13 23:39:33.263595+00	2026-01-18 18:41:16.728239+00
23	23	1	2900.00	1.0000	t	\N	\N	2026-01-13 23:40:52.901499+00	2026-01-18 18:41:16.728239+00
24	24	1	11600.00	1.0000	t	\N	\N	2026-01-13 23:42:09.146833+00	2026-01-18 18:41:16.728239+00
25	25	1	11900.00	1.0000	t	\N	\N	2026-01-13 23:43:06.124936+00	2026-01-18 18:41:16.728239+00
26	26	1	3000.00	1.0000	t	\N	\N	2026-01-13 23:44:33.111475+00	2026-01-18 18:41:16.728239+00
27	27	1	550.00	1.0000	t	\N	\N	2026-01-13 23:45:40.682611+00	2026-01-18 18:41:16.728239+00
28	28	1	250.00	1.0000	t	\N	\N	2026-01-13 23:47:25.679391+00	2026-01-18 18:41:16.728239+00
29	29	1	200.00	1.0000	t	\N	\N	2026-01-13 23:48:19.509204+00	2026-01-18 18:41:16.728239+00
30	30	5	2200.00	1.0000	t	\N	\N	2026-01-13 23:50:34.788804+00	2026-01-18 18:41:16.728239+00
31	31	5	12150.00	1.0000	t	\N	\N	2026-01-13 23:51:40.355303+00	2026-01-18 18:41:16.728239+00
32	32	1	750.00	1.0000	t	\N	\N	2026-01-13 23:52:59.577225+00	2026-01-18 18:41:16.728239+00
33	33	5	500.00	1.0000	t	\N	\N	2026-01-13 23:54:24.402667+00	2026-01-18 18:41:16.728239+00
34	34	5	750.00	1.0000	t	\N	\N	2026-01-13 23:55:16.867673+00	2026-01-18 18:41:16.728239+00
35	35	1	500.00	1.0000	t	\N	\N	2026-01-13 23:59:10.925907+00	2026-01-18 18:41:16.728239+00
36	36	1	450.00	1.0000	t	\N	\N	2026-01-14 00:02:27.601774+00	2026-01-18 18:41:16.728239+00
37	37	1	600.00	1.0000	t	\N	\N	2026-01-14 00:04:40.963037+00	2026-01-18 18:41:16.728239+00
38	38	1	600.00	1.0000	t	\N	\N	2026-01-14 00:05:46.107609+00	2026-01-18 18:41:16.728239+00
39	39	1	200.00	1.0000	t	\N	\N	2026-01-14 00:06:53.793552+00	2026-01-18 18:41:16.728239+00
40	40	1	1750.00	1.0000	t	\N	\N	2026-01-14 00:07:50.241586+00	2026-01-18 18:41:16.728239+00
41	41	1	43000.00	1.0000	t	\N	\N	2026-01-14 00:09:21.953793+00	2026-01-18 18:41:16.728239+00
42	42	5	6000.00	1.0000	t	\N	\N	2026-01-14 00:11:55.789764+00	2026-01-18 18:41:16.728239+00
43	43	5	500.00	1.0000	t	\N	\N	2026-01-14 00:13:49.225633+00	2026-01-18 18:41:16.728239+00
44	44	1	3400.00	1.0000	t	\N	\N	2026-01-14 00:14:34.63193+00	2026-01-18 18:41:16.728239+00
45	46	1	4900.00	1.0000	t	\N	\N	2026-01-14 00:17:22.781974+00	2026-01-18 18:41:16.728239+00
46	47	1	10500.00	1.0000	t	\N	\N	2026-01-14 00:19:38.237937+00	2026-01-18 18:41:16.728239+00
47	48	1	10350.00	1.0000	t	\N	\N	2026-01-14 00:21:36.646268+00	2026-01-18 18:41:16.728239+00
48	49	1	12750.00	1.0000	t	\N	\N	2026-01-14 00:22:48.233851+00	2026-01-18 18:41:16.728239+00
49	50	1	6000.00	1.0000	t	\N	\N	2026-01-14 00:24:34.464382+00	2026-01-18 18:41:16.728239+00
50	51	1	6800.00	1.0000	t	\N	\N	2026-01-14 00:25:58.588134+00	2026-01-18 18:41:16.728239+00
51	52	1	2150.00	1.0000	t	\N	\N	2026-01-14 00:28:31.338758+00	2026-01-18 18:41:16.728239+00
52	53	1	270.00	1.0000	t	\N	\N	2026-01-14 00:29:34.934043+00	2026-01-18 18:41:16.728239+00
53	54	1	1500.00	1.0000	t	\N	\N	2026-01-14 00:30:41.564041+00	2026-01-18 18:41:16.728239+00
54	55	1	4800.00	1.0000	t	\N	\N	2026-01-14 00:31:59.828412+00	2026-01-18 18:41:16.728239+00
55	56	1	1000.00	1.0000	t	\N	\N	2026-01-14 00:32:46.53255+00	2026-01-18 18:41:16.728239+00
56	57	1	34150.00	1.0000	t	\N	\N	2026-01-14 00:34:04.727659+00	2026-01-18 18:41:16.728239+00
57	58	1	1500.00	1.0000	t	\N	\N	2026-01-14 00:36:46.295705+00	2026-01-18 18:41:16.728239+00
58	59	1	4100.00	1.0000	t	\N	\N	2026-01-14 00:37:38.995512+00	2026-01-18 18:41:16.728239+00
59	60	1	5600.00	1.0000	t	\N	\N	2026-01-14 00:38:42.454364+00	2026-01-18 18:41:16.728239+00
60	62	1	1250.00	1.0000	t	\N	\N	2026-01-14 00:41:22.892209+00	2026-01-18 18:41:16.728239+00
61	64	1	1750.00	1.0000	t	\N	\N	2026-01-14 22:24:58.874349+00	2026-01-18 18:41:16.728239+00
62	65	1	500.00	1.0000	t	\N	\N	2026-01-14 22:29:14.728331+00	2026-01-18 18:41:16.728239+00
63	66	1	61150.00	1.0000	t	\N	\N	2026-01-14 22:33:58.254084+00	2026-01-18 18:41:16.728239+00
66	67	1	6000.00	1.0000	t	\N	\N	2026-01-14 22:37:54.752774+00	2026-01-18 18:41:16.728239+00
67	68	1	8000.00	1.0000	t	\N	\N	2026-01-14 22:43:00.345737+00	2026-01-18 18:41:16.728239+00
68	69	1	3000.00	1.0000	t	\N	\N	2026-01-14 22:49:58.736612+00	2026-01-18 18:41:16.728239+00
69	70	1	9950.00	1.0000	t	\N	\N	2026-01-14 22:53:33.533644+00	2026-01-18 18:41:16.728239+00
70	71	1	3300.00	1.0000	t	\N	\N	2026-01-14 22:58:18.973213+00	2026-01-18 18:41:16.728239+00
71	73	1	17200.00	1.0000	t	\N	\N	2026-01-14 23:03:50.396616+00	2026-01-18 18:41:16.728239+00
72	74	1	21500.00	1.0000	t	\N	\N	2026-01-14 23:04:46.588656+00	2026-01-18 18:41:16.728239+00
73	75	1	29000.00	1.0000	t	\N	\N	2026-01-14 23:05:33.495873+00	2026-01-18 18:41:16.728239+00
74	76	1	3500.00	1.0000	t	\N	\N	2026-01-14 23:28:24.392199+00	2026-01-18 18:41:16.728239+00
75	78	1	4800.00	1.0000	t	\N	\N	2026-01-14 23:39:07.084631+00	2026-01-18 18:41:16.728239+00
76	79	1	1550.00	1.0000	t	\N	\N	2026-01-14 23:39:54.145644+00	2026-01-18 18:41:16.728239+00
77	80	1	1550.00	1.0000	t	\N	\N	2026-01-14 23:43:28.404123+00	2026-01-18 18:41:16.728239+00
78	81	1	1000.00	1.0000	t	\N	\N	2026-01-14 23:47:32.229666+00	2026-01-18 18:41:16.728239+00
79	82	1	1000.00	1.0000	t	\N	\N	2026-01-14 23:50:32.381689+00	2026-01-18 18:41:16.728239+00
81	84	1	11150.00	1.0000	t	\N	\N	2026-01-15 00:08:41.799044+00	2026-01-18 18:41:16.728239+00
82	85	1	8000.00	1.0000	t	\N	\N	2026-01-15 00:09:37.875699+00	2026-01-18 18:41:16.728239+00
83	86	1	3000.00	1.0000	t	\N	\N	2026-01-15 00:11:41.100128+00	2026-01-18 18:41:16.728239+00
84	87	1	5500.00	1.0000	t	\N	\N	2026-01-15 00:14:04.66582+00	2026-01-18 18:41:16.728239+00
86	89	1	18500.00	1.0000	t	\N	\N	2026-01-15 00:16:12.834861+00	2026-01-18 18:41:16.728239+00
87	90	1	1500.00	1.0000	t	\N	\N	2026-01-15 00:18:11.994143+00	2026-01-18 18:41:16.728239+00
88	91	1	7700.00	1.0000	t	\N	\N	2026-01-15 00:19:59.243092+00	2026-01-18 18:41:16.728239+00
89	92	1	500.00	1.0000	t	\N	\N	2026-01-15 00:21:08.689846+00	2026-01-18 18:41:16.728239+00
90	93	1	23900.00	1.0000	t	\N	\N	2026-01-15 00:22:18.142881+00	2026-01-18 18:41:16.728239+00
91	94	1	7500.00	1.0000	t	\N	\N	2026-01-15 21:30:55.118892+00	2026-01-18 18:41:16.728239+00
93	97	1	25450.00	1.0000	t	\N	\N	2026-01-15 21:50:39.95321+00	2026-01-18 18:41:16.728239+00
95	98	1	59990.00	1.0000	t	\N	\N	2026-01-15 21:56:28.584991+00	2026-01-18 18:41:16.728239+00
96	99	1	5400.00	1.0000	t	\N	\N	2026-01-15 21:59:39.570451+00	2026-01-18 18:41:16.728239+00
97	101	1	3000.00	1.0000	t	\N	\N	2026-01-15 23:22:15.59638+00	2026-01-18 18:41:16.728239+00
98	102	1	3750.00	1.0000	t	\N	\N	2026-01-15 23:26:19.768635+00	2026-01-18 18:41:16.728239+00
99	103	1	5650.00	1.0000	t	\N	\N	2026-01-15 23:33:39.882892+00	2026-01-18 18:41:16.728239+00
100	104	1	1500.00	1.0000	t	\N	\N	2026-01-15 23:46:20.303519+00	2026-01-18 18:41:16.728239+00
101	105	1	8750.00	1.0000	t	\N	\N	2026-01-15 23:55:18.666545+00	2026-01-18 18:41:16.728239+00
102	106	1	2950.00	1.0000	t	\N	\N	2026-01-15 23:56:00.299977+00	2026-01-18 18:41:16.728239+00
103	107	1	13900.00	1.0000	t	\N	\N	2026-01-16 20:35:58.009573+00	2026-01-18 18:41:16.728239+00
104	108	1	29340.00	1.0000	t	\N	\N	2026-01-16 20:37:05.515825+00	2026-01-18 18:41:16.728239+00
105	109	1	9100.00	1.0000	t	\N	\N	2026-01-16 20:59:02.717287+00	2026-01-18 18:41:16.728239+00
106	72	1	14100.00	1.0000	t	\N	\N	2026-01-14 23:02:05.873684+00	2026-01-18 18:41:16.728239+00
107	110	1	4250.00	1.0000	t	\N	\N	2026-01-16 21:19:53.466134+00	2026-01-18 18:41:16.728239+00
108	111	1	6250.00	1.0000	t	\N	\N	2026-01-16 21:20:58.479791+00	2026-01-18 18:41:16.728239+00
109	112	1	7150.00	1.0000	t	\N	\N	2026-01-16 21:22:09.092521+00	2026-01-18 18:41:16.728239+00
110	63	1	1500.00	1.0000	t	\N	\N	2026-01-14 00:42:41.056973+00	2026-01-18 18:41:16.728239+00
111	113	1	1500.00	1.0000	t	\N	\N	2026-01-16 21:51:04.185619+00	2026-01-18 18:41:16.728239+00
112	114	1	14850.00	1.0000	t	\N	\N	2026-01-16 21:54:44.669949+00	2026-01-18 18:41:16.728239+00
113	115	1	14000.00	1.0000	t	\N	\N	2026-01-16 22:02:17.858773+00	2026-01-18 18:41:16.728239+00
114	116	1	18800.00	1.0000	t	\N	\N	2026-01-16 22:04:20.247724+00	2026-01-18 18:41:16.728239+00
115	117	1	26450.00	1.0000	t	\N	\N	2026-01-16 22:05:17.369976+00	2026-01-18 18:41:16.728239+00
116	118	1	41200.00	1.0000	t	\N	\N	2026-01-16 22:06:58.297048+00	2026-01-18 18:41:16.728239+00
117	120	1	11550.00	1.0000	t	\N	\N	2026-01-16 22:24:19.702818+00	2026-01-18 18:41:16.728239+00
118	121	1	15150.00	1.0000	t	\N	\N	2026-01-16 22:25:00.005823+00	2026-01-18 18:41:16.728239+00
119	122	1	15000.00	1.0000	t	\N	\N	2026-01-16 22:41:59.266077+00	2026-01-18 18:41:16.728239+00
120	123	1	11680.00	1.0000	t	\N	\N	2026-01-16 22:42:56.318089+00	2026-01-18 18:41:16.728239+00
121	119	1	11600.00	1.0000	t	\N	\N	2026-01-16 22:24:19.074289+00	2026-01-18 18:41:16.728239+00
122	124	1	11590.00	1.0000	t	\N	\N	2026-01-16 22:46:38.033317+00	2026-01-18 18:41:16.728239+00
123	125	1	11500.00	1.0000	t	\N	\N	2026-01-16 22:47:30.438635+00	2026-01-18 18:41:16.728239+00
124	126	1	11490.00	1.0000	t	\N	\N	2026-01-16 22:48:18.861088+00	2026-01-18 18:41:16.728239+00
125	127	1	11450.00	1.0000	t	\N	\N	2026-01-16 22:49:01.264282+00	2026-01-18 18:41:16.728239+00
126	128	1	11400.00	1.0000	t	\N	\N	2026-01-16 22:49:37.360493+00	2026-01-18 18:41:16.728239+00
127	129	1	8600.00	1.0000	t	\N	\N	2026-01-16 22:58:19.967252+00	2026-01-18 18:41:16.728239+00
128	130	1	9100.00	1.0000	t	\N	\N	2026-01-16 23:01:08.5838+00	2026-01-18 18:41:16.728239+00
129	131	1	8700.00	1.0000	t	\N	\N	2026-01-16 23:02:09.337437+00	2026-01-18 18:41:16.728239+00
130	100	1	6350.00	1.0000	t	\N	\N	2026-01-15 23:07:48.050818+00	2026-01-18 18:41:16.728239+00
131	132	1	8250.00	1.0000	t	\N	\N	2026-01-16 23:03:03.34311+00	2026-01-18 18:41:16.728239+00
132	133	1	8150.00	1.0000	t	\N	\N	2026-01-16 23:03:42.531769+00	2026-01-18 18:41:16.728239+00
133	134	6	2000.00	1.0000	t	\N	\N	2026-01-16 23:21:42.317149+00	2026-01-18 18:41:16.728239+00
134	135	6	4350.00	1.0000	t	\N	\N	2026-01-16 23:23:26.049511+00	2026-01-18 18:41:16.728239+00
135	136	6	5900.00	1.0000	t	\N	\N	2026-01-16 23:33:03.124107+00	2026-01-18 18:41:16.728239+00
136	137	1	6100.00	1.0000	t	\N	\N	2026-01-17 12:51:29.64968+00	2026-01-18 18:41:16.728239+00
137	138	1	7400.00	1.0000	t	\N	\N	2026-01-17 12:54:02.094391+00	2026-01-18 18:41:16.728239+00
138	139	1	2600.00	1.0000	t	\N	\N	2026-01-17 12:55:26.778993+00	2026-01-18 18:41:16.728239+00
139	140	1	2700.00	1.0000	t	\N	\N	2026-01-17 13:03:57.737149+00	2026-01-18 18:41:16.728239+00
140	141	1	3300.00	1.0000	t	\N	\N	2026-01-17 13:05:03.249381+00	2026-01-18 18:41:16.728239+00
141	142	1	4400.00	1.0000	t	\N	\N	2026-01-17 13:05:44.240122+00	2026-01-18 18:41:16.728239+00
142	143	1	34500.00	1.0000	t	\N	\N	2026-01-17 13:08:12.418775+00	2026-01-18 18:41:16.728239+00
143	144	1	13150.00	1.0000	t	\N	\N	2026-01-17 13:09:27.747177+00	2026-01-18 18:41:16.728239+00
144	145	5	1200.00	1.0000	t	\N	\N	2026-01-17 13:11:49.203684+00	2026-01-18 18:41:16.728239+00
145	146	5	1800.00	1.0000	t	\N	\N	2026-01-17 13:12:20.172269+00	2026-01-18 18:41:16.728239+00
146	147	7	22300.00	1.0000	t	\N	\N	2026-01-17 13:14:27.306095+00	2026-01-18 18:41:16.728239+00
147	148	7	34000.00	1.0000	t	\N	\N	2026-01-17 13:15:11.236542+00	2026-01-18 18:41:16.728239+00
149	150	6	4900.00	1.0000	t	\N	\N	2026-01-17 13:28:01.622325+00	2026-01-18 18:41:16.728239+00
150	151	6	7850.00	1.0000	t	\N	\N	2026-01-17 13:29:35.508689+00	2026-01-18 18:41:16.728239+00
151	152	6	15500.00	1.0000	t	\N	\N	2026-01-17 13:30:55.584347+00	2026-01-18 18:41:16.728239+00
154	155	7	11500.00	1.0000	t	\N	\N	2026-01-17 13:32:35.335704+00	2026-01-18 18:41:16.728239+00
155	156	8	10500.00	1.0000	t	\N	\N	2026-01-17 13:33:55.018914+00	2026-01-18 18:41:16.728239+00
156	157	6	7000.00	1.0000	t	\N	\N	2026-01-17 13:44:15.64444+00	2026-01-18 18:41:16.728239+00
157	158	1	5000.00	1.0000	t	\N	\N	2026-01-17 13:45:40.641812+00	2026-01-18 18:41:16.728239+00
160	161	6	6000.00	1.0000	t	\N	\N	2026-01-17 13:50:21.48974+00	2026-01-18 18:41:16.728239+00
161	162	6	6000.00	1.0000	t	\N	\N	2026-01-17 13:51:23.756409+00	2026-01-18 18:41:16.728239+00
162	164	1	44550.00	1.0000	t	\N	\N	2026-01-17 13:56:13.488587+00	2026-01-18 18:41:16.728239+00
163	165	1	9000.00	1.0000	t	\N	\N	2026-01-17 13:56:45.668118+00	2026-01-18 18:41:16.728239+00
164	163	1	60550.00	1.0000	t	\N	\N	2026-01-17 13:55:17.190554+00	2026-01-18 18:41:16.728239+00
165	166	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:00:33.880944+00	2026-01-18 18:41:16.728239+00
166	167	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:01:24.560232+00	2026-01-18 18:41:16.728239+00
167	168	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:01:46.311146+00	2026-01-18 18:41:16.728239+00
169	170	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:02:56.970265+00	2026-01-18 18:41:16.728239+00
170	171	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:03:23.317897+00	2026-01-18 18:41:16.728239+00
171	172	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:03:50.344917+00	2026-01-18 18:41:16.728239+00
172	173	1	3300.00	1.0000	t	\N	\N	2026-01-17 14:04:19.176323+00	2026-01-18 18:41:16.728239+00
173	174	6	6000.00	1.0000	t	\N	\N	2026-01-17 14:08:01.613614+00	2026-01-18 18:41:16.728239+00
174	175	6	6000.00	1.0000	t	\N	\N	2026-01-17 14:10:55.88543+00	2026-01-18 18:41:16.728239+00
175	176	6	7500.00	1.0000	t	\N	\N	2026-01-17 14:11:32.971657+00	2026-01-18 18:41:16.728239+00
176	177	6	7450.00	1.0000	t	\N	\N	2026-01-17 14:13:42.75219+00	2026-01-18 18:41:16.728239+00
177	178	1	11950.00	1.0000	t	\N	\N	2026-01-17 14:15:43.441419+00	2026-01-18 18:41:16.728239+00
178	179	1	6000.00	1.0000	t	\N	\N	2026-01-17 14:21:55.491882+00	2026-01-18 18:41:16.728239+00
179	180	6	5000.00	1.0000	t	\N	\N	2026-01-17 14:22:32.234565+00	2026-01-18 18:41:16.728239+00
181	182	1	60.00	1.0000	t	\N	\N	2026-01-17 14:27:29.358835+00	2026-01-18 18:41:16.728239+00
182	183	1	90.00	1.0000	t	\N	\N	2026-01-17 14:28:04.912508+00	2026-01-18 18:41:16.728239+00
185	186	1	1000.00	1.0000	t	\N	\N	2026-01-17 14:32:51.119958+00	2026-01-18 18:41:16.728239+00
187	188	6	5550.00	1.0000	t	\N	\N	2026-01-17 14:35:51.134147+00	2026-01-18 18:41:16.728239+00
188	189	1	7000.00	1.0000	t	\N	\N	2026-01-17 14:49:24.084569+00	2026-01-18 18:41:16.728239+00
189	190	6	5250.00	1.0000	t	\N	\N	2026-01-17 14:53:40.671269+00	2026-01-18 18:41:16.728239+00
190	191	1	779000.00	1.0000	t	\N	\N	2026-01-17 15:08:06.600402+00	2026-01-18 18:41:16.728239+00
191	192	1	2400.00	1.0000	t	\N	\N	2026-01-17 15:11:31.661225+00	2026-01-18 18:41:16.728239+00
198	199	1	1500.00	1.0000	t	\N	\N	2026-01-17 15:22:53.524878+00	2026-01-18 18:41:16.728239+00
199	200	1	2000.00	1.0000	t	\N	\N	2026-01-17 15:25:55.450715+00	2026-01-18 18:41:16.728239+00
206	207	1	25800.00	1.0000	t	\N	\N	2026-01-17 16:46:08.802354+00	2026-01-18 18:41:16.728239+00
207	208	1	3600.00	1.0000	t	\N	\N	2026-01-17 20:45:43.106646+00	2026-01-18 18:41:16.728239+00
208	209	1	4800.00	1.0000	t	\N	\N	2026-01-17 20:48:13.942512+00	2026-01-18 18:41:16.728239+00
209	210	1	2000.00	1.0000	t	\N	\N	2026-01-17 20:51:51.912931+00	2026-01-18 18:41:16.728239+00
210	211	1	2500.00	1.0000	t	\N	\N	2026-01-17 20:52:22.183316+00	2026-01-18 18:41:16.728239+00
214	215	1	100.00	1.0000	t	\N	\N	2026-01-17 21:54:46.345463+00	2026-01-18 18:41:16.728239+00
215	216	1	880.00	1.0000	t	\N	\N	2026-01-17 21:55:21.533859+00	2026-01-18 18:41:16.728239+00
216	217	7	5300.00	1.0000	t	\N	\N	2026-01-17 22:01:40.417098+00	2026-01-18 18:41:16.728239+00
217	218	1	550.00	1.0000	t	\N	\N	2026-01-17 22:10:28.64351+00	2026-01-18 18:41:16.728239+00
218	219	1	690.00	1.0000	t	\N	\N	2026-01-17 22:13:28.76342+00	2026-01-18 18:41:16.728239+00
220	221	1	9200.00	1.0000	t	\N	\N	2026-01-17 22:19:39.277289+00	2026-01-18 18:41:16.728239+00
221	222	1	5800.00	1.0000	t	\N	\N	2026-01-17 22:21:48.539567+00	2026-01-18 18:41:16.728239+00
222	223	1	1900.00	1.0000	t	\N	\N	2026-01-17 22:28:38.733833+00	2026-01-18 18:41:16.728239+00
223	224	5	100.00	1.0000	t	\N	\N	2026-01-17 22:29:19.066649+00	2026-01-18 18:41:16.728239+00
224	225	1	820.00	1.0000	t	\N	\N	2026-01-17 22:30:11.716226+00	2026-01-18 18:41:16.728239+00
225	226	1	1300.00	1.0000	t	\N	\N	2026-01-17 22:32:27.023465+00	2026-01-18 18:41:16.728239+00
226	227	1	17500.00	1.0000	t	\N	\N	2026-01-17 22:36:14.746301+00	2026-01-18 18:41:16.728239+00
227	77	1	2000.00	1.0000	t	\N	\N	2026-01-14 23:37:06.253038+00	2026-01-18 18:41:16.728239+00
228	229	1	3000.00	1.0000	t	\N	\N	2026-01-17 22:45:20.958561+00	2026-01-18 18:41:16.728239+00
229	228	1	2000.00	1.0000	t	\N	\N	2026-01-17 22:44:15.672233+00	2026-01-18 18:41:16.728239+00
230	230	1	2000.00	1.0000	t	\N	\N	2026-01-17 22:53:20.679059+00	2026-01-18 18:41:16.728239+00
231	231	1	1500.00	1.0000	t	\N	\N	2026-01-17 22:55:32.958973+00	2026-01-18 18:41:16.728239+00
232	232	1	7000.00	1.0000	t	\N	\N	2026-01-17 22:59:32.253872+00	2026-01-18 18:41:16.728239+00
233	233	1	3000.00	1.0000	t	\N	\N	2026-01-17 23:05:30.459365+00	2026-01-18 18:41:16.728239+00
234	234	1	3000.00	1.0000	t	\N	\N	2026-01-17 23:08:18.086441+00	2026-01-18 18:41:16.728239+00
235	235	1	3000.00	1.0000	t	\N	\N	2026-01-17 23:08:18.697105+00	2026-01-18 18:41:16.728239+00
236	236	5	3500.00	1.0000	t	\N	\N	2026-01-17 23:10:36.841776+00	2026-01-18 18:41:16.728239+00
237	237	1	6000.00	1.0000	t	\N	\N	2026-01-17 23:12:13.667898+00	2026-01-18 18:41:16.728239+00
238	238	1	6000.00	1.0000	t	\N	\N	2026-01-17 23:13:05.318404+00	2026-01-18 18:41:16.728239+00
239	239	1	16850.00	1.0000	t	\N	\N	2026-01-17 23:21:39.529976+00	2026-01-18 18:41:16.728239+00
240	240	1	13200.00	1.0000	t	\N	\N	2026-01-17 23:23:02.045716+00	2026-01-18 18:41:16.728239+00
241	241	5	4500.00	1.0000	t	\N	\N	2026-01-17 23:29:45.952822+00	2026-01-18 18:41:16.728239+00
242	242	1	4000.00	1.0000	t	\N	\N	2026-01-17 23:31:05.275306+00	2026-01-18 18:41:16.728239+00
243	243	1	800.00	1.0000	t	\N	\N	2026-01-17 23:31:58.067386+00	2026-01-18 18:41:16.728239+00
244	244	1	3850.00	1.0000	t	\N	\N	2026-01-17 23:32:39.799808+00	2026-01-18 18:41:16.728239+00
245	245	1	850.00	1.0000	t	\N	\N	2026-01-17 23:57:58.900473+00	2026-01-18 18:41:16.728239+00
246	246	1	100.00	1.0000	t	\N	\N	2026-01-17 23:58:28.004766+00	2026-01-18 18:41:16.728239+00
248	248	1	350.00	1.0000	t	\N	\N	2026-01-17 23:59:34.070529+00	2026-01-18 18:41:16.728239+00
249	249	1	25.00	1.0000	t	\N	\N	2026-01-18 00:02:12.307642+00	2026-01-18 18:41:16.728239+00
250	250	1	30.00	1.0000	t	\N	\N	2026-01-18 00:02:42.93074+00	2026-01-18 18:41:16.728239+00
251	251	1	40.00	1.0000	t	\N	\N	2026-01-18 00:03:07.504312+00	2026-01-18 18:41:16.728239+00
252	252	1	65.00	1.0000	t	\N	\N	2026-01-18 00:03:36.374022+00	2026-01-18 18:41:16.728239+00
253	253	1	120.00	1.0000	t	\N	\N	2026-01-18 00:04:06.636584+00	2026-01-18 18:41:16.728239+00
254	254	1	25.00	1.0000	t	\N	\N	2026-01-18 00:05:17.858013+00	2026-01-18 18:41:16.728239+00
255	255	1	35000.00	1.0000	t	\N	\N	2026-01-18 12:57:10.159235+00	2026-01-18 18:41:16.728239+00
256	256	1	3550.00	1.0000	t	\N	\N	2026-01-18 12:58:59.657837+00	2026-01-18 18:41:16.728239+00
257	257	1	2100.00	1.0000	t	\N	\N	2026-01-18 13:02:21.956851+00	2026-01-18 18:41:16.728239+00
258	258	9	2100.00	1.0000	t	\N	\N	2026-01-18 13:05:41.954174+00	2026-01-18 18:41:16.728239+00
259	259	1	90.00	1.0000	t	\N	\N	2026-01-18 13:06:48.428532+00	2026-01-18 18:41:16.728239+00
260	260	1	3000.00	1.0000	t	\N	\N	2026-01-18 13:07:39.765675+00	2026-01-18 18:41:16.728239+00
261	261	1	100.00	1.0000	t	\N	\N	2026-01-18 13:12:06.928509+00	2026-01-18 18:41:16.728239+00
262	262	1	1000.00	1.0000	t	\N	\N	2026-01-18 13:12:39.231395+00	2026-01-18 18:41:16.728239+00
263	263	1	45000.00	1.0000	t	\N	\N	2026-01-18 13:16:00.214451+00	2026-01-18 18:41:16.728239+00
264	264	1	1000.00	1.0000	t	\N	\N	2026-01-18 13:16:40.28674+00	2026-01-18 18:41:16.728239+00
265	265	1	25.00	1.0000	t	\N	\N	2026-01-18 13:24:54.757153+00	2026-01-18 18:41:16.728239+00
266	266	1	2000.00	1.0000	t	\N	\N	2026-01-18 13:45:34.815198+00	2026-01-18 18:41:16.728239+00
267	267	1	3000.00	1.0000	t	\N	\N	2026-01-18 13:46:15.909307+00	2026-01-18 18:41:16.728239+00
268	268	1	5000.00	1.0000	t	\N	\N	2026-01-18 13:46:44.097548+00	2026-01-18 18:41:16.728239+00
269	269	1	20.00	1.0000	t	\N	\N	2026-01-18 14:05:11.514349+00	2026-01-18 18:41:16.728239+00
270	270	1	25.00	1.0000	t	\N	\N	2026-01-18 14:07:47.149815+00	2026-01-18 18:41:16.728239+00
271	271	1	30.00	1.0000	t	\N	\N	2026-01-18 14:08:43.24378+00	2026-01-18 18:41:16.728239+00
272	272	1	35.00	1.0000	t	\N	\N	2026-01-18 14:12:28.23871+00	2026-01-18 18:41:16.728239+00
273	273	6	5000.00	1.0000	t	\N	\N	2026-01-18 14:14:29.840705+00	2026-01-18 18:41:16.728239+00
274	274	1	3000.00	1.0000	t	\N	\N	2026-01-18 14:35:24.455309+00	2026-01-18 18:41:16.728239+00
275	275	1	200.00	1.0000	t	\N	\N	2026-01-18 14:45:31.416565+00	2026-01-18 18:41:16.728239+00
276	276	5	200.00	1.0000	t	\N	\N	2026-01-18 14:46:11.875405+00	2026-01-18 18:41:16.728239+00
277	277	1	1750.00	1.0000	t	\N	\N	2026-01-18 14:47:26.281249+00	2026-01-18 18:41:16.728239+00
278	278	1	1750.00	1.0000	t	\N	\N	2026-01-18 14:48:03.322355+00	2026-01-18 18:41:16.728239+00
279	279	1	7500.00	1.0000	t	\N	\N	2026-01-18 14:50:25.320547+00	2026-01-18 18:41:16.728239+00
280	280	1	2500.00	1.0000	t	\N	\N	2026-01-18 14:54:13.597319+00	2026-01-18 18:41:16.728239+00
281	281	1	1750.00	1.0000	t	\N	\N	2026-01-18 15:00:11.727697+00	2026-01-18 18:41:16.728239+00
282	282	1	1700.00	1.0000	t	\N	\N	2026-01-18 15:05:16.783396+00	2026-01-18 18:41:16.728239+00
283	283	1	2000.00	1.0000	t	\N	\N	2026-01-18 15:05:51.660357+00	2026-01-18 18:41:16.728239+00
284	284	1	2700.00	1.0000	t	\N	\N	2026-01-18 15:06:21.370435+00	2026-01-18 18:41:16.728239+00
285	285	1	3300.00	1.0000	t	\N	\N	2026-01-18 15:06:56.927671+00	2026-01-18 18:41:16.728239+00
287	287	1	5250.00	1.0000	t	\N	\N	2026-01-18 15:08:12.494077+00	2026-01-18 18:41:16.728239+00
288	288	1	1920.00	1.0000	t	\N	\N	2026-01-18 15:11:03.029786+00	2026-01-18 18:41:16.728239+00
289	289	1	8850.00	1.0000	t	\N	\N	2026-01-18 15:15:52.749378+00	2026-01-18 18:41:16.728239+00
290	290	1	100.00	1.0000	t	\N	\N	2026-01-18 15:17:11.581385+00	2026-01-18 18:41:16.728239+00
291	291	1	50.00	1.0000	t	\N	\N	2026-01-18 15:18:39.614728+00	2026-01-18 18:41:16.728239+00
292	292	1	75.00	1.0000	t	\N	\N	2026-01-18 15:22:00.161525+00	2026-01-18 18:41:16.728239+00
293	293	1	25.00	1.0000	t	\N	\N	2026-01-18 15:22:30.032677+00	2026-01-18 18:41:16.728239+00
294	294	5	900.00	1.0000	t	\N	\N	2026-01-18 15:30:31.333647+00	2026-01-18 18:41:16.728239+00
295	295	1	5850.00	1.0000	t	\N	\N	2026-01-18 15:33:20.347754+00	2026-01-18 18:41:16.728239+00
296	296	1	100000.00	1.0000	t	\N	\N	2026-01-18 15:46:22.715909+00	2026-01-18 18:41:16.728239+00
297	297	1	63200.00	1.0000	t	\N	\N	2026-01-18 15:46:50.720978+00	2026-01-18 18:41:16.728239+00
298	298	1	38200.00	1.0000	t	\N	\N	2026-01-18 15:47:17.633816+00	2026-01-18 18:41:16.728239+00
299	299	1	8000.00	1.0000	t	\N	\N	2026-01-18 15:52:37.663482+00	2026-01-18 18:41:16.728239+00
300	300	1	3900.00	1.0000	t	\N	\N	2026-01-18 15:53:03.431049+00	2026-01-18 18:41:16.728239+00
301	301	1	40.00	1.0000	t	\N	\N	2026-01-18 15:55:55.353011+00	2026-01-18 18:41:16.728239+00
302	302	1	55.00	1.0000	t	\N	\N	2026-01-18 15:58:53.78607+00	2026-01-18 18:41:16.728239+00
303	303	1	1000.00	1.0000	t	\N	\N	2026-01-18 16:08:48.347244+00	2026-01-18 18:41:16.728239+00
305	304	5	500.00	1.0000	t	\N	\N	2026-01-18 16:09:46.225744+00	2026-01-18 18:41:16.728239+00
306	306	5	200.00	1.0000	t	\N	\N	2026-01-18 16:22:11.20271+00	2026-01-18 18:41:16.728239+00
307	307	1	350.00	1.0000	t	\N	\N	2026-01-18 16:26:18.986446+00	2026-01-18 18:41:16.728239+00
308	308	1	750.00	1.0000	t	\N	\N	2026-01-18 16:26:59.58408+00	2026-01-18 18:41:16.728239+00
309	309	1	170.00	1.0000	t	\N	\N	2026-01-18 16:32:17.59111+00	2026-01-18 18:41:16.728239+00
310	310	1	700.00	1.0000	t	\N	\N	2026-01-18 16:32:52.69915+00	2026-01-18 18:41:16.728239+00
311	311	1	300.00	1.0000	t	\N	\N	2026-01-18 16:35:21.859714+00	2026-01-18 18:41:16.728239+00
312	312	1	300.00	1.0000	t	\N	\N	2026-01-18 16:54:45.028491+00	2026-01-18 18:41:16.728239+00
313	313	1	1500.00	1.0000	t	\N	\N	2026-01-18 16:59:08.003183+00	2026-01-18 18:41:16.728239+00
314	314	1	1000.00	1.0000	t	\N	\N	2026-01-18 17:22:16.533479+00	2026-01-18 18:41:16.728239+00
315	315	1	500.00	1.0000	t	\N	\N	2026-01-18 17:23:22.296229+00	2026-01-18 18:41:16.728239+00
316	316	1	1000.00	1.0000	t	\N	\N	2026-01-18 17:24:10.563477+00	2026-01-18 18:41:16.728239+00
317	317	5	300.00	1.0000	t	\N	\N	2026-01-18 17:25:56.657851+00	2026-01-18 18:41:16.728239+00
318	318	1	4900.00	1.0000	t	\N	\N	2026-01-18 17:45:52.11967+00	2026-01-18 18:41:16.728239+00
319	319	1	1800.00	1.0000	t	\N	\N	2026-01-18 17:50:47.949853+00	2026-01-18 18:41:16.728239+00
320	320	1	8850.00	1.0000	t	\N	\N	2026-01-18 17:51:49.112209+00	2026-01-18 18:41:16.728239+00
321	321	1	10950.00	1.0000	t	\N	\N	2026-01-18 17:53:46.062185+00	2026-01-18 18:41:16.728239+00
322	322	1	15000.00	1.0000	t	\N	\N	2026-01-18 17:55:37.972556+00	2026-01-18 18:41:16.728239+00
323	323	5	800.00	1.0000	t	\N	\N	2026-01-18 17:57:46.284015+00	2026-01-18 18:41:16.728239+00
324	324	1	1500.00	1.0000	t	\N	\N	2026-01-18 18:08:41.160824+00	2026-01-18 18:41:16.728239+00
325	325	1	27560.00	1.0000	t	\N	\N	2026-01-18 18:09:24.682363+00	2026-01-18 18:41:16.728239+00
326	326	1	65.00	1.0000	t	\N	\N	2026-01-18 18:10:29.001387+00	2026-01-18 18:41:16.728239+00
327	327	1	50.00	1.0000	t	\N	\N	2026-01-18 18:11:15.511906+00	2026-01-18 18:41:16.728239+00
328	328	5	2200.00	1.0000	t	\N	\N	2026-01-18 18:18:20.797637+00	2026-01-18 18:41:16.728239+00
329	329	1	870.00	1.0000	t	\N	\N	2026-01-18 18:19:11.745744+00	2026-01-18 18:41:16.728239+00
330	330	1	70.00	1.0000	t	\N	\N	2026-01-18 18:23:21.959587+00	2026-01-18 18:41:16.728239+00
331	331	1	200.00	1.0000	t	\N	\N	2026-01-18 18:35:42.914718+00	2026-01-18 18:41:16.728239+00
340	339	1	660.00	1.0000	t	\N	\N	2026-01-18 19:17:28.751735+00	2026-01-18 19:17:28.751735+00
341	340	1	50.00	1.0000	t	\N	\N	2026-01-18 19:18:30.930783+00	2026-01-18 19:18:30.930783+00
342	341	1	23950.00	1.0000	t	\N	\N	2026-01-19 20:42:02.32059+00	2026-01-19 20:42:02.32059+00
343	201	1	20.00	1.0000	t	\N	\N	2026-01-19 20:52:40.53106+00	2026-01-19 20:52:40.53106+00
344	202	1	40.00	1.0000	t	\N	\N	2026-01-19 20:53:25.935609+00	2026-01-19 20:53:25.935609+00
345	203	1	60.00	1.0000	t	\N	\N	2026-01-19 20:56:08.599947+00	2026-01-19 20:56:08.599947+00
346	342	10	1600.00	1.0000	t	\N	\N	2026-01-19 21:03:10.989752+00	2026-01-19 21:03:10.989752+00
347	343	1	45.00	1.0000	t	\N	\N	2026-01-19 21:06:00.352277+00	2026-01-19 21:06:00.352277+00
348	344	1	1700.00	1.0000	t	\N	\N	2026-01-19 21:12:11.110313+00	2026-01-19 21:12:11.110313+00
349	345	1	3000.00	1.0000	t	\N	\N	2026-01-19 21:15:23.063688+00	2026-01-19 21:15:23.063688+00
350	346	11	300.00	1.0000	t	\N	\N	2026-01-19 21:17:11.063278+00	2026-01-19 21:17:11.063278+00
351	347	1	200.00	1.0000	t	\N	\N	2026-01-19 21:19:42.184226+00	2026-01-19 21:19:42.184226+00
352	348	1	18900.00	1.0000	t	\N	\N	2026-01-19 21:24:14.48267+00	2026-01-19 21:24:14.48267+00
353	349	1	8800.00	1.0000	t	\N	\N	2026-01-19 21:28:03.35482+00	2026-01-19 21:28:03.35482+00
354	350	1	9600.00	1.0000	t	\N	\N	2026-01-19 21:29:26.05895+00	2026-01-19 21:29:26.05895+00
355	351	5	1500.00	1.0000	t	\N	\N	2026-01-19 21:31:08.113315+00	2026-01-19 21:31:08.113315+00
356	352	1	200.00	1.0000	t	\N	\N	2026-01-19 21:32:25.027605+00	2026-01-19 21:32:25.027605+00
358	354	1	5050.00	1.0000	t	\N	\N	2026-01-19 21:39:22.661862+00	2026-01-19 21:39:22.661862+00
360	187	5	1800.00	1.0000	t	\N	\N	2026-01-19 21:54:00.355685+00	2026-01-19 21:54:00.355685+00
361	355	5	500.00	1.0000	t	\N	\N	2026-01-19 22:04:32.662635+00	2026-01-19 22:04:32.662635+00
362	356	5	500.00	1.0000	t	\N	\N	2026-01-19 22:06:04.162966+00	2026-01-19 22:06:04.162966+00
364	357	1	1000.00	1.0000	t	\N	\N	2026-01-19 22:40:05.574491+00	2026-01-19 22:40:05.574491+00
365	358	1	21550.00	1.0000	t	\N	\N	2026-01-19 22:41:18.217777+00	2026-01-19 22:41:18.217777+00
366	153	1	750.00	1.0000	t	\N	\N	2026-01-19 22:43:12.654062+00	2026-01-19 22:43:12.654062+00
367	154	1	2500.00	1.0000	t	\N	\N	2026-01-19 22:43:34.116516+00	2026-01-19 22:43:34.116516+00
368	359	5	200.00	1.0000	t	\N	\N	2026-01-19 22:47:06.828615+00	2026-01-19 22:47:06.828615+00
369	360	5	350.00	1.0000	t	\N	\N	2026-01-19 22:52:15.516565+00	2026-01-19 22:52:15.516565+00
370	361	1	3000.00	1.0000	t	\N	\N	2026-01-19 23:13:22.331745+00	2026-01-19 23:13:22.331745+00
371	362	1	2300.00	1.0000	t	\N	\N	2026-01-19 23:14:08.186378+00	2026-01-19 23:14:08.186378+00
372	363	1	1500.00	1.0000	t	\N	\N	2026-01-19 23:14:44.84882+00	2026-01-19 23:14:44.84882+00
373	364	1	30.00	1.0000	t	\N	\N	2026-01-19 23:18:54.08914+00	2026-01-19 23:18:54.08914+00
374	365	1	22000.00	1.0000	t	\N	\N	2026-01-19 23:21:07.995903+00	2026-01-19 23:21:07.995903+00
375	366	1	3000.00	1.0000	t	\N	\N	2026-01-19 23:29:36.80105+00	2026-01-19 23:29:36.80105+00
376	367	1	4300.00	1.0000	t	\N	\N	2026-01-19 23:31:36.012299+00	2026-01-19 23:31:36.012299+00
377	368	1	3200.00	1.0000	t	\N	\N	2026-01-19 23:33:15.402518+00	2026-01-19 23:33:15.402518+00
378	369	1	8300.00	1.0000	t	\N	\N	2026-01-19 23:34:42.398778+00	2026-01-19 23:34:42.398778+00
379	370	1	8900.00	1.0000	t	\N	\N	2026-01-19 23:39:23.607522+00	2026-01-19 23:39:23.607522+00
380	371	1	3400.00	1.0000	t	\N	\N	2026-01-19 23:40:38.615974+00	2026-01-19 23:40:38.615974+00
381	372	1	6000.00	1.0000	t	\N	\N	2026-01-19 23:41:54.567261+00	2026-01-19 23:41:54.567261+00
382	373	1	6500.00	1.0000	t	\N	\N	2026-01-19 23:44:42.761789+00	2026-01-19 23:44:42.761789+00
383	374	5	800.00	1.0000	t	\N	\N	2026-01-19 23:49:04.285016+00	2026-01-19 23:49:04.285016+00
384	375	1	22000.00	1.0000	t	\N	\N	2026-01-19 23:55:25.296766+00	2026-01-19 23:55:25.296766+00
386	376	1	2500.00	1.0000	t	\N	\N	2026-01-19 23:59:30.96607+00	2026-01-19 23:59:30.96607+00
388	377	1	6600.00	1.0000	t	\N	\N	2026-01-20 00:02:27.843194+00	2026-01-20 00:02:27.843194+00
389	378	1	5400.00	1.0000	t	\N	\N	2026-01-20 00:04:58.708881+00	2026-01-20 00:04:58.708881+00
390	379	1	6100.00	1.0000	t	\N	\N	2026-01-20 00:08:14.979175+00	2026-01-20 00:08:14.979175+00
392	381	1	4900.00	1.0000	t	\N	\N	2026-01-20 00:13:03.108017+00	2026-01-20 00:13:03.108017+00
393	382	1	200.00	1.0000	t	\N	\N	2026-01-20 00:18:24.978532+00	2026-01-20 00:18:24.978532+00
395	383	1	20950.00	1.0000	t	\N	\N	2026-01-20 00:27:25.892725+00	2026-01-20 00:27:25.892725+00
396	384	1	14850.00	1.0000	t	\N	\N	2026-01-20 00:28:55.177641+00	2026-01-20 00:28:55.177641+00
397	385	1	21300.00	1.0000	t	\N	\N	2026-01-20 00:29:50.531859+00	2026-01-20 00:29:50.531859+00
398	386	1	10100.00	1.0000	t	\N	\N	2026-01-20 00:31:55.316265+00	2026-01-20 00:31:55.316265+00
399	387	1	3750.00	1.0000	t	\N	\N	2026-01-20 00:36:25.851445+00	2026-01-20 00:36:25.851445+00
400	388	1	4550.00	1.0000	t	\N	\N	2026-01-20 00:37:49.968781+00	2026-01-20 00:37:49.968781+00
401	389	1	3750.00	1.0000	t	\N	\N	2026-01-20 00:39:10.710943+00	2026-01-20 00:39:10.710943+00
402	390	9	3200.00	1.0000	t	\N	\N	2026-01-20 00:40:50.54684+00	2026-01-20 00:40:50.54684+00
403	391	1	64850.00	1.0000	t	\N	\N	2026-01-20 00:43:59.16502+00	2026-01-20 00:43:59.16502+00
404	392	1	8500.00	1.0000	t	\N	\N	2026-01-20 00:45:12.179791+00	2026-01-20 00:45:12.179791+00
405	393	11	3300.00	1.0000	t	\N	\N	2026-01-20 00:46:45.096108+00	2026-01-20 00:46:45.096108+00
406	394	1	6000.00	1.0000	t	\N	\N	2026-01-20 20:17:44.87062+00	2026-01-20 20:17:44.87062+00
407	395	1	9200.00	1.0000	t	\N	\N	2026-01-20 20:19:38.465487+00	2026-01-20 20:19:38.465487+00
408	193	1	4000.00	1.0000	t	\N	\N	2026-01-20 20:23:04.921235+00	2026-01-20 20:23:04.921235+00
409	396	1	10.00	1.0000	t	\N	\N	2026-01-20 20:26:49.078402+00	2026-01-20 20:26:49.078402+00
410	397	12	4500.00	1.0000	t	\N	\N	2026-01-20 20:34:10.556997+00	2026-01-20 20:34:10.556997+00
411	398	12	4500.00	1.0000	t	\N	\N	2026-01-20 20:35:55.636978+00	2026-01-20 20:35:55.636978+00
412	399	12	3500.00	1.0000	t	\N	\N	2026-01-20 20:37:41.282552+00	2026-01-20 20:37:41.282552+00
413	400	1	9700.00	1.0000	t	\N	\N	2026-01-20 20:42:08.363335+00	2026-01-20 20:42:08.363335+00
414	401	1	12550.00	1.0000	t	\N	\N	2026-01-20 20:45:25.020241+00	2026-01-20 20:45:25.020241+00
415	402	1	3200.00	1.0000	t	\N	\N	2026-01-20 20:49:58.745078+00	2026-01-20 20:49:58.745078+00
416	205	1	100.00	1.0000	t	\N	\N	2026-01-20 20:52:05.367557+00	2026-01-20 20:52:05.367557+00
417	206	1	200.00	1.0000	t	\N	\N	2026-01-20 20:53:12.62769+00	2026-01-20 20:53:12.62769+00
418	184	1	30.00	1.0000	t	\N	\N	2026-01-20 20:55:23.470415+00	2026-01-20 20:55:23.470415+00
419	185	1	20.00	1.0000	t	\N	\N	2026-01-20 20:56:13.304855+00	2026-01-20 20:56:13.304855+00
420	181	1	50.00	1.0000	t	\N	\N	2026-01-20 20:56:58.734449+00	2026-01-20 20:56:58.734449+00
421	403	5	200.00	1.0000	t	\N	\N	2026-01-20 21:16:51.907598+00	2026-01-20 21:16:51.907598+00
422	404	1	1700.00	1.0000	t	\N	\N	2026-01-20 21:22:26.418022+00	2026-01-20 21:22:26.418022+00
423	159	5	2100.00	1.0000	t	\N	\N	2026-01-20 21:23:39.866499+00	2026-01-20 21:23:39.866499+00
425	405	7	19000.00	1.0000	t	\N	\N	2026-01-20 21:25:23.039261+00	2026-01-20 21:25:23.039261+00
426	406	7	10700.00	1.0000	t	\N	\N	2026-01-20 21:26:17.218656+00	2026-01-20 21:26:17.218656+00
427	407	7	6600.00	1.0000	t	\N	\N	2026-01-20 21:27:17.598289+00	2026-01-20 21:27:17.598289+00
428	408	1	30200.00	1.0000	t	\N	\N	2026-01-20 21:42:19.969783+00	2026-01-20 21:42:19.969783+00
429	409	5	6500.00	1.0000	t	\N	\N	2026-01-20 22:55:32.762845+00	2026-01-20 22:55:32.762845+00
430	410	1	3200.00	1.0000	t	\N	\N	2026-01-20 22:55:58.359298+00	2026-01-20 22:55:58.359298+00
431	195	1	2150.00	1.0000	t	\N	\N	2026-01-20 22:57:18.667666+00	2026-01-20 22:57:18.667666+00
432	411	1	89000.00	1.0000	t	\N	\N	2026-01-20 23:03:09.529177+00	2026-01-20 23:03:09.529177+00
434	413	1	4200.00	1.0000	t	\N	\N	2026-01-20 23:11:19.755528+00	2026-01-20 23:11:19.755528+00
435	414	1	11200.00	1.0000	t	\N	\N	2026-01-20 23:12:15.056445+00	2026-01-20 23:12:15.056445+00
437	416	1	15.00	1.0000	t	\N	\N	2026-01-20 23:21:29.209878+00	2026-01-20 23:21:29.209878+00
438	417	12	6650.00	1.0000	t	\N	\N	2026-01-20 23:27:12.358791+00	2026-01-20 23:27:12.358791+00
439	418	1	1700.00	1.0000	t	\N	\N	2026-01-20 23:30:28.367687+00	2026-01-20 23:30:28.367687+00
440	419	1	2800.00	1.0000	t	\N	\N	2026-01-20 23:34:30.78542+00	2026-01-20 23:34:30.78542+00
441	420	1	3500.00	1.0000	t	\N	\N	2026-01-20 23:39:41.469205+00	2026-01-20 23:39:41.469205+00
442	421	1	35.00	1.0000	t	\N	\N	2026-01-20 23:41:47.146306+00	2026-01-20 23:41:47.146306+00
443	422	1	3300.00	1.0000	t	\N	\N	2026-01-20 23:44:29.691547+00	2026-01-20 23:44:29.691547+00
444	423	1	250.00	1.0000	t	\N	\N	2026-01-20 23:49:56.656275+00	2026-01-20 23:49:56.656275+00
445	424	1	250000.00	1.0000	t	\N	\N	2026-01-20 23:52:58.402096+00	2026-01-20 23:52:58.402096+00
446	425	1	5000.00	1.0000	t	\N	\N	2026-01-21 00:04:40.778725+00	2026-01-21 00:04:40.778725+00
447	426	1	43000.00	1.0000	t	\N	\N	2026-01-21 00:06:20.151976+00	2026-01-21 00:06:20.151976+00
448	149	1	5000.00	1.0000	t	\N	\N	2026-01-21 00:10:51.856183+00	2026-01-21 00:10:51.856183+00
449	380	1	5450.00	1.0000	t	\N	\N	2026-01-21 00:14:04.499502+00	2026-01-21 00:14:04.499502+00
450	353	1	1000.00	1.0000	t	\N	\N	2026-01-21 00:17:45.799631+00	2026-01-21 00:17:45.799631+00
451	96	1	6550.00	1.0000	t	\N	\N	2026-01-21 00:19:18.045769+00	2026-01-21 00:19:18.045769+00
452	286	1	4350.00	1.0000	t	\N	\N	2026-01-21 00:19:50.870471+00	2026-01-21 00:19:50.870471+00
453	95	1	117600.00	1.0000	t	\N	\N	2026-01-21 00:20:48.535465+00	2026-01-21 00:20:48.535465+00
454	194	1	2500.00	1.0000	t	\N	\N	2026-01-21 00:21:19.742869+00	2026-01-21 00:21:19.742869+00
456	197	1	1800.00	1.0000	t	\N	\N	2026-01-21 00:22:16.681385+00	2026-01-21 00:22:16.681385+00
457	196	1	2600.00	1.0000	t	\N	\N	2026-01-21 00:22:41.267931+00	2026-01-21 00:22:41.267931+00
458	88	1	2600.00	1.0000	t	\N	\N	2026-01-21 00:23:25.411289+00	2026-01-21 00:23:25.411289+00
459	415	1	700.00	1.0000	t	\N	\N	2026-01-21 00:24:59.783315+00	2026-01-21 00:24:59.783315+00
460	412	1	4600.00	1.0000	t	\N	\N	2026-01-21 00:26:25.504971+00	2026-01-21 00:26:25.504971+00
455	198	1	3400.00	1.0000	t	\N	\N	2026-01-21 00:21:46.212257+00	2026-01-21 00:21:46.212257+00
461	213	5	3000.00	1.0000	t	\N	\N	2026-01-21 00:26:59.296848+00	2026-01-21 00:26:59.296848+00
462	427	1	2500.00	1.0000	t	\N	\N	2026-01-21 12:58:18.691478+00	2026-01-21 12:58:18.691478+00
463	428	1	3300.00	1.0000	t	\N	\N	2026-01-21 20:27:42.270298+00	2026-01-21 20:27:42.270298+00
465	429	1	7100.00	1.0000	t	\N	\N	2026-01-21 21:19:24.281423+00	2026-01-21 21:19:24.281423+00
466	430	1	2400.00	1.0000	t	\N	\N	2026-01-21 21:32:18.873347+00	2026-01-21 21:32:18.873347+00
467	431	1	2800.00	1.0000	t	\N	\N	2026-01-21 21:35:46.82497+00	2026-01-21 21:35:46.82497+00
468	83	1	1500.00	1.0000	t	\N	\N	2026-01-21 21:37:26.833596+00	2026-01-21 21:37:26.833596+00
469	432	1	2500.00	1.0000	t	\N	\N	2026-01-21 21:41:33.264501+00	2026-01-21 21:41:33.264501+00
470	433	1	3950.00	1.0000	t	\N	\N	2026-01-21 21:56:00.683521+00	2026-01-21 21:56:00.683521+00
471	434	1	3500.00	1.0000	t	\N	\N	2026-01-21 22:25:03.093622+00	2026-01-21 22:25:03.093622+00
472	435	1	3000.00	1.0000	t	\N	\N	2026-01-21 22:26:31.265579+00	2026-01-21 22:26:31.265579+00
473	436	1	3650.00	1.0000	t	\N	\N	2026-01-21 22:27:01.95499+00	2026-01-21 22:27:01.95499+00
474	437	1	1850.00	1.0000	t	\N	\N	2026-01-21 22:30:31.635195+00	2026-01-21 22:30:31.635195+00
476	438	1	1000.00	1.0000	t	\N	\N	2026-01-21 22:51:42.481105+00	2026-01-21 22:51:42.481105+00
477	439	1	200.00	1.0000	t	\N	\N	2026-01-21 22:55:43.589641+00	2026-01-21 22:55:43.589641+00
478	440	1	2500.00	1.0000	t	\N	\N	2026-01-21 22:59:22.152394+00	2026-01-21 22:59:22.152394+00
479	441	1	700.00	1.0000	t	\N	\N	2026-01-21 23:10:48.419911+00	2026-01-21 23:10:48.419911+00
480	442	1	550.00	1.0000	t	\N	\N	2026-01-21 23:12:46.882908+00	2026-01-21 23:12:46.882908+00
481	204	1	75.00	1.0000	t	\N	\N	2026-01-21 23:21:14.819503+00	2026-01-21 23:21:14.819503+00
482	443	1	1250.00	1.0000	t	\N	\N	2026-01-21 23:32:24.347819+00	2026-01-21 23:32:24.347819+00
483	444	1	9500.00	1.0000	t	\N	\N	2026-01-21 23:46:23.609033+00	2026-01-21 23:46:23.609033+00
484	61	1	1850.00	1.0000	t	\N	\N	2026-01-21 23:48:10.427302+00	2026-01-21 23:48:10.427302+00
485	45	1	2500.00	1.0000	t	\N	\N	2026-01-21 23:53:53.373075+00	2026-01-21 23:53:53.373075+00
486	445	1	1000.00	1.0000	t	\N	\N	2026-01-22 00:07:48.332246+00	2026-01-22 00:07:48.332246+00
487	446	1	25000.00	1.0000	t	\N	\N	2026-01-22 00:12:09.025012+00	2026-01-22 00:12:09.025012+00
489	448	1	2000.00	1.0000	t	\N	\N	2026-01-22 00:18:08.401339+00	2026-01-22 00:18:08.401339+00
490	447	1	3550.00	1.0000	t	\N	\N	2026-01-22 00:23:35.517171+00	2026-01-22 00:23:35.517171+00
491	449	1	4000.00	1.0000	t	\N	\N	2026-01-22 00:27:02.521998+00	2026-01-22 00:27:02.521998+00
492	450	1	3200.00	1.0000	t	\N	\N	2026-01-22 00:32:25.212369+00	2026-01-22 00:32:25.212369+00
493	451	1	9200.00	1.0000	t	\N	\N	2026-01-22 00:34:40.362214+00	2026-01-22 00:34:40.362214+00
495	452	1	10600.00	1.0000	t	\N	\N	2026-01-22 00:38:37.576926+00	2026-01-22 00:38:37.576926+00
496	453	1	10260.00	1.0000	t	\N	\N	2026-01-22 00:40:24.840415+00	2026-01-22 00:40:24.840415+00
497	454	1	19500.00	1.0000	t	\N	\N	2026-01-22 00:42:53.943816+00	2026-01-22 00:42:53.943816+00
498	455	1	21300.00	1.0000	t	\N	\N	2026-01-22 00:45:43.692759+00	2026-01-22 00:45:43.692759+00
499	456	1	1250.00	1.0000	t	\N	\N	2026-01-22 00:52:14.983488+00	2026-01-22 00:52:14.983488+00
500	457	1	4000.00	1.0000	t	\N	\N	2026-01-22 00:53:51.426765+00	2026-01-22 00:53:51.426765+00
501	212	5	2350.00	1.0000	t	\N	\N	2026-01-22 03:05:10.888132+00	2026-01-22 03:05:10.888132+00
502	21	1	3600.00	1.0000	t	\N	\N	2026-01-22 03:06:18.993908+00	2026-01-22 03:06:18.993908+00
503	214	5	1000.00	1.0000	t	\N	\N	2026-01-22 03:07:34.175247+00	2026-01-22 03:07:34.175247+00
504	220	5	1500.00	1.0000	t	\N	\N	2026-01-22 03:08:24.186978+00	2026-01-22 03:08:24.186978+00
505	458	1	5650.00	1.0000	t	\N	\N	2026-01-22 10:34:19.822286+00	2026-01-22 10:34:19.822286+00
506	459	1	200.00	1.0000	t	\N	\N	2026-01-22 20:03:28.256742+00	2026-01-22 20:03:28.256742+00
508	461	1	1000.00	1.0000	t	\N	\N	2026-01-22 21:13:50.619147+00	2026-01-22 21:13:50.619147+00
513	462	1	1000.00	1.0000	t	\N	\N	2026-01-22 21:43:38.40935+00	2026-01-22 21:43:38.40935+00
514	463	1	300.00	1.0000	t	\N	\N	2026-01-22 21:47:07.135704+00	2026-01-22 21:47:07.135704+00
515	464	1	55.00	1.0000	t	\N	\N	2026-01-22 22:35:24.756548+00	2026-01-22 22:35:24.756548+00
517	466	1	5500.00	1.0000	t	\N	\N	2026-01-22 22:41:03.008329+00	2026-01-22 22:41:03.008329+00
518	465	1	5500.00	1.0000	t	\N	\N	2026-01-22 22:41:29.422787+00	2026-01-22 22:41:29.422787+00
519	467	1	750.00	1.0000	t	\N	\N	2026-01-22 22:47:54.609067+00	2026-01-22 22:47:54.609067+00
521	469	5	4500.00	1.0000	t	\N	\N	2026-01-22 22:53:21.004976+00	2026-01-22 22:53:21.004976+00
522	468	5	4500.00	1.0000	t	\N	\N	2026-01-22 22:54:17.957505+00	2026-01-22 22:54:17.957505+00
523	470	5	8650.00	1.0000	t	\N	\N	2026-01-22 22:55:18.484007+00	2026-01-22 22:55:18.484007+00
524	471	1	2000.00	1.0000	t	\N	\N	2026-01-22 22:57:14.331218+00	2026-01-22 22:57:14.331218+00
525	472	1	11550.00	1.0000	t	\N	\N	2026-01-22 22:58:19.184766+00	2026-01-22 22:58:19.184766+00
526	460	1	3650.00	1.0000	t	\N	\N	2026-01-22 23:35:10.249808+00	2026-01-22 23:35:10.249808+00
527	473	1	19550.00	1.0000	t	\N	\N	2026-01-22 23:41:19.822883+00	2026-01-22 23:41:19.822883+00
528	474	1	5000.00	1.0000	t	\N	\N	2026-01-22 23:51:38.308828+00	2026-01-22 23:51:38.308828+00
530	475	1	3400.00	1.0000	t	\N	\N	2026-01-22 23:53:24.324578+00	2026-01-22 23:53:24.324578+00
531	476	1	14500.00	1.0000	t	\N	\N	2026-01-22 23:54:16.220423+00	2026-01-22 23:54:16.220423+00
532	477	1	4600.00	1.0000	t	\N	\N	2026-01-23 00:00:09.324962+00	2026-01-23 00:00:09.324962+00
533	478	1	5700.00	1.0000	t	\N	\N	2026-01-23 00:03:43.536107+00	2026-01-23 00:03:43.536107+00
534	479	1	7850.00	1.0000	t	\N	\N	2026-01-23 00:04:55.429712+00	2026-01-23 00:04:55.429712+00
535	305	1	250.00	1.0000	t	\N	\N	2026-01-23 00:07:52.016824+00	2026-01-23 00:07:52.016824+00
536	247	1	300.00	1.0000	t	\N	\N	2026-01-23 00:10:38.034771+00	2026-01-23 00:10:38.034771+00
537	480	1	3800.00	1.0000	t	\N	\N	2026-01-23 00:14:16.746789+00	2026-01-23 00:14:16.746789+00
538	481	1	4300.00	1.0000	t	\N	\N	2026-01-23 00:15:11.554371+00	2026-01-23 00:15:11.554371+00
539	482	1	4600.00	1.0000	t	\N	\N	2026-01-23 00:18:55.556308+00	2026-01-23 00:18:55.556308+00
540	160	5	5400.00	1.0000	t	\N	\N	2026-01-23 01:00:11.810527+00	2026-01-23 01:00:11.810527+00
541	483	1	7500.00	1.0000	t	\N	\N	2026-01-23 01:01:44.848987+00	2026-01-23 01:01:44.848987+00
\.


--
-- Data for Name: purchase_invoice; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.purchase_invoice (id, supplier_id, invoice_number, invoice_date, due_date, total_amount, status, paid_at, created_at) FROM stdin;
1	1	54979	2026-01-08	2026-02-08	127290.00	PENDING	\N	2026-01-13 21:25:10.351255+00
2	1	54918	2026-01-07	2026-02-07	298258.00	PENDING	\N	2026-01-13 23:35:17.970419+00
3	2	13194	2025-12-18	2026-01-18	869533.00	PAID	2026-01-14	2026-01-14 00:57:45.636678+00
4	3	325193	2026-01-10	2026-02-10	123235.00	PENDING	\N	2026-01-14 22:56:07.974939+00
5	3	168694	2026-01-10	2026-02-10	10068.00	PENDING	\N	2026-01-14 22:59:27.158177+00
6	3	40321	2026-01-10	2026-02-10	125087.00	PENDING	\N	2026-01-14 23:09:57.721525+00
7	3	325199	2026-01-10	2026-02-10	154824.00	PENDING	\N	2026-01-14 23:12:43.46236+00
9	5	4773	2026-01-10	2026-02-10	410439.00	PENDING	\N	2026-01-16 00:24:50.584374+00
10	3	325138	2026-01-09	2026-02-09	50154.00	PENDING	\N	2026-01-16 20:40:11.325213+00
11	6	12522	2026-12-26	2026-01-26	22770.00	PENDING	\N	2026-01-16 21:35:06.800789+00
12	6	12614	2026-01-14	2026-02-14	42336.00	PENDING	\N	2026-01-17 00:18:17.022072+00
13	6	12610	2026-01-13	2026-02-13	585700.00	PENDING	\N	2026-01-17 16:46:35.009566+00
14	7	2909	2026-01-17	2026-01-17	13860.00	PAID	2026-01-17	2026-01-17 20:54:29.073089+00
15	4	3464	2026-01-05	2026-02-05	294142.00	PENDING	\N	2026-01-17 23:23:39.796193+00
16	4	3496	2026-01-16	2026-02-16	475840.00	PENDING	\N	2026-01-20 00:47:35.896751+00
17	8	4620	2026-01-20	2026-02-20	332878.00	PENDING	\N	2026-01-21 00:07:06.00775+00
19	2	13456	2026-01-19	2026-02-19	410025.00	PENDING	\N	2026-01-22 00:46:12.793663+00
8	4	3349	2025-11-29	2025-12-29	316449.00	PAID	2026-01-22	2026-01-15 00:35:02.448922+00
18	4	3361	2025-12-04	2026-01-04	38988.00	PAID	2026-01-22	2026-01-21 00:31:07.301897+00
20	7	2921	2026-01-22	2026-01-22	109248.00	PAID	2026-01-23	2026-01-23 00:24:44.584644+00
\.


--
-- Data for Name: purchase_invoice_line; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.purchase_invoice_line (id, invoice_id, product_id, qty, unit_cost, line_total) FROM stdin;
1	1	4	2.000	4254.0000	8508.00
2	1	6	2.000	7576.0000	15152.00
3	1	5	2.000	8916.0000	17832.00
4	1	3	2.000	5373.0000	10746.00
5	1	2	1.000	75052.0000	75052.00
135	3	22	6.000	1049.0000	6294.00
136	3	21	1779.000	20.0000	35580.00
137	3	23	20.000	1415.0000	28300.00
138	3	24	5.000	5778.0000	28890.00
139	3	25	5.000	5950.0000	29750.00
140	3	26	60.000	486.0000	29160.00
141	3	27	20.000	278.0000	5560.00
142	3	28	20.000	126.0000	2520.00
143	3	29	10.000	93.0000	930.00
144	3	30	10.000	1091.0000	10910.00
145	3	31	2.000	6066.0000	12132.00
146	3	32	5.000	357.0000	1785.00
147	3	33	50.000	243.0000	12150.00
148	3	34	25.000	364.0000	9100.00
149	3	35	10.000	228.0000	2280.00
150	3	36	20.000	223.0000	4460.00
151	3	37	20.000	294.0000	5880.00
152	3	38	20.000	294.0000	5880.00
153	3	39	20.000	98.0000	1960.00
154	3	40	20.000	871.0000	17420.00
155	3	41	3.000	21533.0000	64599.00
156	3	42	1.000	14656.0000	14656.00
157	3	43	100.000	253.0000	25300.00
158	3	44	20.000	1404.0000	28080.00
159	3	45	10.000	841.0000	8410.00
160	3	46	2.000	2430.0000	4860.00
161	3	47	2.000	5283.0000	10566.00
162	3	48	5.000	5158.0000	25790.00
163	3	49	5.000	6389.0000	31945.00
164	3	50	20.000	2983.0000	59660.00
165	3	51	20.000	3460.0000	69200.00
166	3	52	20.000	1072.0000	21440.00
167	3	53	120.000	135.0000	16200.00
168	3	54	20.000	739.0000	14780.00
169	3	55	10.000	2406.0000	24060.00
170	3	56	10.000	512.0000	5120.00
171	3	57	2.000	17078.0000	34156.00
172	3	58	40.000	563.0000	22520.00
173	3	60	10.000	2834.0000	28340.00
174	3	61	60.000	1001.0000	60060.00
175	3	62	20.000	611.0000	12220.00
176	3	63	10.000	1595.0000	15950.00
177	3	59	10.000	2068.0000	20680.00
186	5	71	6.000	1678.0000	10068.00
187	6	66	1.000	40163.0000	40163.00
188	6	68	12.000	4137.0000	49644.00
189	6	67	12.000	2940.0000	35280.00
210	9	94	6.000	3730.0000	22380.00
211	9	97	4.000	12725.0000	50900.00
212	9	98	3.000	29997.0000	89991.00
213	9	99	6.000	2690.0000	16140.00
214	9	100	6.000	3169.0000	19014.00
215	9	101	24.000	1498.0000	35952.00
216	9	102	24.000	1871.0000	44904.00
217	9	103	24.000	2822.0000	67728.00
218	9	104	24.000	747.0000	17928.00
219	9	106	10.000	1480.0000	14800.00
220	9	105	7.000	4386.0000	30702.00
223	11	112	5.000	1500.0000	7500.00
224	11	111	10.000	500.0000	5000.00
225	11	110	10.000	1000.0000	10000.00
226	11	63	10.000	27.0000	270.00
235	13	199	25.000	700.0000	17500.00
236	13	82	25.000	700.0000	17500.00
237	13	115	1.000	7000.0000	7000.00
238	13	114	1.000	2500.0000	2500.00
239	13	116	1.000	7000.0000	7000.00
240	13	117	1.000	7000.0000	7000.00
241	13	118	1.000	20000.0000	20000.00
242	13	138	10.000	300.0000	3000.00
243	13	137	10.000	300.0000	3000.00
244	13	142	10.000	300.0000	3000.00
78	2	8	600.000	4.0000	2400.00
79	2	9	600.000	5.0000	3000.00
80	2	1	200.000	5.0000	1000.00
81	2	10	200.000	85.0000	17000.00
82	2	11	100.000	143.0000	14300.00
83	2	12	200.000	216.0000	43200.00
84	2	13	12.000	5260.0000	63120.00
85	2	14	2.000	4429.0000	8858.00
86	2	15	2.000	4796.0000	9592.00
87	2	16	2.000	4274.0000	8548.00
88	2	17	48.000	980.0000	47040.00
89	2	18	500.000	45.0000	22500.00
90	2	19	500.000	47.0000	23500.00
91	2	20	500.000	60.0000	30000.00
92	2	7	200.000	21.0000	4200.00
245	13	141	10.000	3000.0000	30000.00
246	13	140	10.000	3000.0000	30000.00
247	13	125	1.000	5000.0000	5000.00
248	13	120	1.000	5000.0000	5000.00
249	13	124	1.000	5000.0000	5000.00
250	13	119	1.000	5000.0000	5000.00
251	13	123	1.000	5000.0000	5000.00
252	13	122	1.000	7000.0000	7000.00
253	13	121	1.000	5000.0000	5000.00
254	13	128	1.000	5000.0000	5000.00
255	13	127	1.000	5000.0000	5000.00
256	13	126	1.000	5000.0000	5000.00
257	13	143	1.000	17000.0000	17000.00
258	13	144	1.000	3000.0000	3000.00
259	13	45	20.000	500.0000	10000.00
260	13	113	50.000	500.0000	25000.00
261	13	64	20.000	500.0000	10000.00
262	13	188	10.000	2000.0000	20000.00
263	13	190	7.000	2000.0000	14000.00
182	4	64	20.000	887.0000	17740.00
183	4	65	25.000	233.0000	5825.00
184	4	69	50.000	1500.0000	75000.00
185	4	70	5.000	4934.0000	24670.00
190	7	72	4.000	9012.0000	36048.00
191	7	73	2.000	8614.0000	17228.00
192	7	74	4.000	10870.0000	43480.00
193	7	75	4.000	14517.0000	58068.00
194	8	78	4.000	1774.0000	7096.00
195	8	79	15.000	669.0000	10035.00
196	8	80	15.000	669.0000	10035.00
197	8	81	15.000	669.0000	10035.00
198	8	82	15.000	669.0000	10035.00
199	8	83	15.000	669.0000	10035.00
200	8	84	1.000	5277.0000	5277.00
201	8	85	6.000	4731.0000	28386.00
202	8	86	30.000	1534.0000	46020.00
203	8	87	4.000	2395.0000	9580.00
204	8	89	1.000	5575.0000	5575.00
205	8	91	5.000	3856.0000	19280.00
206	8	93	5.000	11942.0000	59710.00
207	8	92	50.000	216.0000	10800.00
208	8	90	50.000	699.0000	34950.00
209	8	77	40.000	990.0000	39600.00
221	10	107	3.000	6938.0000	20814.00
222	10	108	2.000	14670.0000	29340.00
227	12	133	1.000	4062.0000	4062.00
228	12	132	1.000	4116.0000	4116.00
229	12	129	1.000	4276.0000	4276.00
230	12	131	1.000	4332.0000	4332.00
231	12	130	1.000	5550.0000	5550.00
232	12	136	2.000	3000.0000	6000.00
233	12	134	5.000	2000.0000	10000.00
234	12	135	4.000	1000.0000	4000.00
264	13	109	10.000	2000.0000	20000.00
265	13	72	7.000	4000.0000	28000.00
266	13	177	6.000	3700.0000	22200.00
267	13	175	6.000	3000.0000	18000.00
268	13	176	7.000	2000.0000	14000.00
269	13	174	2.000	5000.0000	10000.00
270	13	90	50.000	500.0000	25000.00
271	13	157	6.000	3000.0000	18000.00
272	13	150	6.000	2000.0000	12000.00
273	13	147	2.000	10000.0000	20000.00
274	13	151	2.000	3000.0000	6000.00
275	13	152	2.000	5000.0000	10000.00
276	13	148	1.000	1000.0000	1000.00
277	13	71	6.000	1000.0000	6000.00
278	13	191	1.000	10000.0000	10000.00
279	13	163	1.000	10000.0000	10000.00
280	13	164	1.000	10000.0000	10000.00
281	13	145	50.000	100.0000	5000.00
282	13	146	50.000	100.0000	5000.00
283	13	170	10.000	100.0000	1000.00
284	13	171	10.000	100.0000	1000.00
285	13	172	10.000	100.0000	1000.00
286	13	173	10.000	100.0000	1000.00
287	13	166	10.000	100.0000	1000.00
288	13	167	10.000	100.0000	1000.00
289	13	168	10.000	100.0000	1000.00
290	13	180	2.000	1000.0000	2000.00
291	13	179	2.000	2500.0000	5000.00
292	13	161	7.000	1000.0000	7000.00
293	13	162	6.000	1000.0000	6000.00
294	13	207	2.000	5000.0000	10000.00
295	14	208	5.000	1000.0000	5000.00
296	14	209	3.000	1000.0000	3000.00
297	14	156	1.000	1000.0000	1000.00
298	14	155	1.000	1000.0000	1000.00
299	14	210	2.000	1000.0000	2000.00
300	14	211	4.000	465.0000	1860.00
301	15	221	2.000	4600.0000	9200.00
302	15	222	3.000	2896.0000	8688.00
303	15	186	6.000	539.0000	3234.00
304	15	223	3.000	953.0000	2859.00
305	15	227	5.000	8747.0000	43735.00
306	15	229	5.000	1057.0000	5285.00
307	15	77	5.000	1057.0000	5285.00
308	15	236	40.000	1592.0000	63680.00
309	15	212	100.000	1175.0000	117500.00
310	15	237	2.000	2990.0000	5980.00
311	15	238	2.000	2990.0000	5980.00
312	15	239	2.000	8423.0000	16846.00
313	15	240	2.000	2935.0000	5870.00
314	16	344	20.000	830.0000	16600.00
315	16	375	5.000	3695.0000	18475.00
316	16	377	3.000	3306.0000	9918.00
317	16	378	4.000	2692.0000	10768.00
318	16	379	5.000	3033.0000	15165.00
319	16	282	24.000	845.0000	20280.00
320	16	383	4.000	10485.0000	41940.00
321	16	384	2.000	7409.0000	14818.00
322	16	386	2.000	5031.0000	10062.00
323	16	199	15.000	713.0000	10695.00
324	16	83	15.000	713.0000	10695.00
325	16	82	15.000	713.0000	10695.00
326	16	81	15.000	713.0000	10695.00
327	16	387	5.000	1875.0000	9375.00
328	16	388	5.000	2260.0000	11300.00
329	16	389	5.000	1875.0000	9375.00
330	16	85	12.000	5299.0000	63588.00
331	16	390	18.000	1597.0000	28746.00
332	16	391	2.000	50000.0000	100000.00
333	16	392	21.000	2000.0000	42000.00
334	16	393	10.000	1065.0000	10650.00
335	17	411	2.000	44520.0000	89040.00
336	17	408	2.000	15085.0000	30170.00
337	17	382	100.000	374.0000	37400.00
338	17	416	1000.000	6.0000	6000.00
339	17	417	2.000	3460.0000	6920.00
340	17	419	5.000	1376.0000	6880.00
341	17	424	1.000	126000.0000	126000.00
342	17	425	5.000	2535.0000	12675.00
343	17	426	3.000	5931.0000	17793.00
344	18	85	12.000	3249.0000	38988.00
345	19	437	20.000	537.0000	10740.00
346	19	438	20.000	516.0000	10320.00
347	19	439	200.000	83.0000	16600.00
348	19	58	50.000	563.0000	28150.00
349	19	432	50.000	933.0000	46650.00
350	19	203	1000.000	28.0000	28000.00
351	19	204	1000.000	36.0000	36000.00
352	19	61	50.000	814.0000	40700.00
353	19	45	10.000	1138.0000	11380.00
354	19	445	20.000	516.0000	10320.00
355	19	447	10.000	1772.0000	17720.00
356	19	448	10.000	1027.0000	10270.00
357	19	449	10.000	2007.0000	20070.00
358	19	450	10.000	1603.0000	16030.00
359	19	451	10.000	4592.0000	45920.00
360	19	452	4.000	10900.0000	43600.00
361	19	453	1.000	5555.0000	5555.00
362	19	454	4.000	1500.0000	6000.00
363	19	455	1.000	6000.0000	6000.00
364	20	477	7.000	2295.0000	16065.00
365	20	478	10.000	2837.0000	28370.00
366	20	479	3.000	3921.0000	11763.00
367	20	305	50.000	111.0000	5550.00
368	20	247	50.000	134.0000	6700.00
369	20	347	20.000	40.0000	800.00
370	20	482	10.000	2000.0000	20000.00
371	20	460	10.000	1000.0000	10000.00
372	20	480	10.000	1000.0000	10000.00
\.


--
-- Data for Name: purchase_invoice_payment; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.purchase_invoice_payment (id, invoice_id, paid_at, amount, notes, created_at) FROM stdin;
1	3	2026-01-14	869533.00	Pago migrado desde sistema anterior	2026-01-14 00:00:00+00
2	14	2026-01-17	13860.00	Pago migrado desde sistema anterior	2026-01-17 00:00:00+00
\.


--
-- Data for Name: quote; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.quote (id, quote_number, status, issued_at, valid_until, notes, payment_method, total_amount, sale_id, created_at, updated_at, customer_name, customer_phone) FROM stdin;
1	PRES-20260113-213207-0001	SENT	2026-01-13 21:32:07.785339+00	2026-01-20	\N	CASH	8500.00	\N	2026-01-13 21:32:07.781626+00	2026-01-13 21:32:57.60915+00	Juan perez	\N
\.


--
-- Data for Name: quote_line; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.quote_line (id, quote_id, product_id, product_name_snapshot, uom_snapshot, qty, unit_price, line_total) FROM stdin;
1	1	4	MARTILLO BOLITA 113GRS MANGO MADERA	unidad	1.000	8500.00	8500.00
\.


--
-- Data for Name: sale; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.sale (id, datetime, total, status, created_at) FROM stdin;
6	2026-01-14 14:29:40.822786+00	8500.00	CONFIRMED	2026-01-14 14:29:40.821218+00
7	2026-01-14 21:50:08.920167+00	41400.00	CONFIRMED	2026-01-14 21:50:08.918209+00
8	2026-01-15 21:35:09.619283+00	2000.00	CONFIRMED	2026-01-15 21:35:09.618074+00
9	2026-01-16 23:51:53.79224+00	3000.00	CONFIRMED	2026-01-16 23:51:53.791195+00
10	2026-01-16 23:51:53.919358+00	3000.00	CONFIRMED	2026-01-16 23:51:53.918349+00
11	2026-01-17 14:26:39.940668+00	3000.00	CONFIRMED	2026-01-17 14:26:39.939682+00
12	2026-01-17 15:07:22.314248+00	18000.00	CONFIRMED	2026-01-17 15:07:22.312768+00
13	2026-01-17 15:25:15.701597+00	3700.00	CONFIRMED	2026-01-17 15:25:15.700518+00
14	2026-01-17 18:21:03.409105+00	8000.00	CONFIRMED	2026-01-17 18:21:03.408048+00
15	2026-01-17 21:47:01.694953+00	3400.00	CONFIRMED	2026-01-17 21:47:01.693812+00
16	2026-01-17 21:56:03.658259+00	3440.00	CONFIRMED	2026-01-17 21:56:03.656708+00
17	2026-01-17 22:01:59.01625+00	5300.00	CONFIRMED	2026-01-17 22:01:59.014698+00
18	2026-01-17 22:14:09.841938+00	3860.00	CONFIRMED	2026-01-17 22:14:09.840403+00
19	2026-01-17 22:31:37.454168+00	1020.00	CONFIRMED	2026-01-17 22:31:37.452771+00
20	2026-01-17 22:32:49.350795+00	1300.00	CONFIRMED	2026-01-17 22:32:49.349875+00
21	2026-01-17 22:53:41.595418+00	2000.00	CONFIRMED	2026-01-17 22:53:41.594359+00
22	2026-01-17 22:58:26.627402+00	19000.00	CONFIRMED	2026-01-17 22:58:26.625766+00
23	2026-01-17 22:59:48.070623+00	7000.00	CONFIRMED	2026-01-17 22:59:48.068778+00
24	2026-01-17 23:30:05.068206+00	9000.00	CONFIRMED	2026-01-17 23:30:05.066245+00
25	2026-01-17 23:34:41.854657+00	8650.00	CONFIRMED	2026-01-17 23:34:41.852742+00
26	2026-01-17 23:40:35.654779+00	8000.00	CONFIRMED	2026-01-17 23:40:35.653745+00
27	2026-01-18 00:08:29.347656+00	4100.00	CONFIRMED	2026-01-18 00:08:29.345335+00
28	2026-01-18 13:04:23.617564+00	5650.00	CONFIRMED	2026-01-18 13:04:23.616115+00
29	2026-01-18 13:13:39.194321+00	1500.00	CONFIRMED	2026-01-18 13:13:39.192369+00
30	2026-01-18 13:14:32.272739+00	1500.00	CONFIRMED	2026-01-18 13:14:32.271711+00
31	2026-01-18 13:19:19.873088+00	6700.00	CONFIRMED	2026-01-18 13:19:19.871257+00
32	2026-01-18 13:25:44.543989+00	750.00	CONFIRMED	2026-01-18 13:25:44.542617+00
33	2026-01-18 13:48:08.350592+00	16000.00	CONFIRMED	2026-01-18 13:48:08.348295+00
34	2026-01-18 13:50:03.928469+00	5650.00	CONFIRMED	2026-01-18 13:50:03.927388+00
35	2026-01-18 13:58:30.834625+00	1800.00	CONFIRMED	2026-01-18 13:58:30.833648+00
36	2026-01-18 14:05:44.799667+00	120.00	CONFIRMED	2026-01-18 14:05:44.798684+00
37	2026-01-18 14:09:51.988492+00	22850.00	CONFIRMED	2026-01-18 14:09:51.985688+00
38	2026-01-18 14:15:00.473341+00	6500.00	CONFIRMED	2026-01-18 14:15:00.471676+00
39	2026-01-18 14:35:40.916608+00	3000.00	CONFIRMED	2026-01-18 14:35:40.915415+00
40	2026-01-18 14:40:53.237931+00	3000.00	CONFIRMED	2026-01-18 14:40:53.236353+00
41	2026-01-18 14:46:35.939555+00	2000.00	CONFIRMED	2026-01-18 14:46:35.938505+00
42	2026-01-18 14:52:27.744853+00	7800.00	CONFIRMED	2026-01-18 14:52:27.742809+00
43	2026-01-18 14:56:00.457127+00	4500.00	CONFIRMED	2026-01-18 14:56:00.454543+00
44	2026-01-18 15:08:35.571993+00	5250.00	CONFIRMED	2026-01-18 15:08:35.569402+00
45	2026-01-18 15:08:57.019969+00	200.00	CONFIRMED	2026-01-18 15:08:57.018875+00
46	2026-01-18 15:10:05.035613+00	16000.00	CONFIRMED	2026-01-18 15:10:05.033336+00
47	2026-01-18 15:19:26.532484+00	9000.00	CONFIRMED	2026-01-18 15:19:26.530621+00
48	2026-01-18 15:24:36.715677+00	4240.00	CONFIRMED	2026-01-18 15:24:36.713874+00
49	2026-01-18 15:30:56.950266+00	1350.00	CONFIRMED	2026-01-18 15:30:56.949236+00
50	2026-01-18 15:33:45.896541+00	5850.00	CONFIRMED	2026-01-18 15:33:45.895639+00
51	2026-01-18 15:56:52.109396+00	12875.00	CONFIRMED	2026-01-18 15:56:52.107039+00
52	2026-01-18 15:59:36.907695+00	380.00	CONFIRMED	2026-01-18 15:59:36.906298+00
53	2026-01-18 16:13:35.77127+00	3100.00	CONFIRMED	2026-01-18 16:13:35.769403+00
54	2026-01-18 16:22:33.443243+00	2000.00	CONFIRMED	2026-01-18 16:22:33.442223+00
55	2026-01-18 16:31:25.670988+00	1500.00	CONFIRMED	2026-01-18 16:31:25.669458+00
56	2026-01-18 16:34:24.604925+00	4150.00	CONFIRMED	2026-01-18 16:34:24.602888+00
57	2026-01-18 16:36:02.128423+00	2150.00	CONFIRMED	2026-01-18 16:36:02.127492+00
58	2026-01-18 16:58:16.208637+00	4200.00	CONFIRMED	2026-01-18 16:58:16.20752+00
59	2026-01-18 16:59:28.214544+00	9500.00	CONFIRMED	2026-01-18 16:59:28.213109+00
60	2026-01-18 17:24:37.930903+00	17700.00	CONFIRMED	2026-01-18 17:24:37.92835+00
61	2026-01-18 17:26:15.310744+00	2100.00	CONFIRMED	2026-01-18 17:26:15.309733+00
62	2026-01-18 17:40:00.702044+00	300.00	CONFIRMED	2026-01-18 17:40:00.700895+00
63	2026-01-18 17:41:39.42205+00	3700.00	CONFIRMED	2026-01-18 17:41:39.421178+00
64	2026-01-18 17:43:27.590876+00	34900.00	CONFIRMED	2026-01-18 17:43:27.589002+00
65	2026-01-18 17:47:16.411347+00	15300.00	CONFIRMED	2026-01-18 17:47:16.409425+00
66	2026-01-18 17:54:12.451968+00	16300.00	CONFIRMED	2026-01-18 17:54:12.449403+00
67	2026-01-18 17:54:26.519171+00	10950.00	CONFIRMED	2026-01-18 17:54:26.518223+00
68	2026-01-18 17:57:12.074454+00	22150.00	CONFIRMED	2026-01-18 17:57:12.072589+00
69	2026-01-18 18:06:50.090703+00	2500.00	CONFIRMED	2026-01-18 18:06:50.089462+00
70	2026-01-18 18:20:59.498603+00	3480.00	CONFIRMED	2026-01-18 18:20:59.497078+00
71	2026-01-18 18:24:11.052165+00	29870.00	CONFIRMED	2026-01-18 18:24:11.049667+00
72	2026-01-18 18:46:02.038257+00	3000.00	CONFIRMED	2026-01-18 18:46:02.037131+00
73	2026-01-18 18:51:01.544179+00	200.00	CONFIRMED	2026-01-18 18:51:01.542916+00
74	2026-01-18 18:51:17.608779+00	1500.00	CONFIRMED	2026-01-18 18:51:17.607836+00
75	2026-01-18 19:17:54.56745+00	760.00	CONFIRMED	2026-01-18 19:17:54.566008+00
76	2026-01-18 19:19:05.921254+00	200.00	CONFIRMED	2026-01-18 19:19:05.91948+00
77	2026-01-19 20:50:08.68891+00	43450.00	CONFIRMED	2026-01-19 20:50:08.686538+00
78	2026-01-19 20:50:41.602748+00	3000.00	CONFIRMED	2026-01-19 20:50:41.601287+00
79	2026-01-19 20:54:52.837739+00	4160.00	CONFIRMED	2026-01-19 20:54:52.836313+00
80	2026-01-19 20:58:38.313766+00	36500.00	CONFIRMED	2026-01-19 20:58:38.311545+00
81	2026-01-19 20:59:13.68224+00	600.00	CONFIRMED	2026-01-19 20:59:13.681185+00
82	2026-01-19 21:03:47.719136+00	1600.00	CONFIRMED	2026-01-19 21:03:47.717993+00
83	2026-01-19 21:06:30.593455+00	2160.00	CONFIRMED	2026-01-19 21:06:30.591529+00
84	2026-01-19 21:17:43.155051+00	3600.00	CONFIRMED	2026-01-19 21:17:43.153592+00
85	2026-01-19 21:18:27.249209+00	1000.00	CONFIRMED	2026-01-19 21:18:27.248284+00
86	2026-01-19 21:23:39.051298+00	200.00	CONFIRMED	2026-01-19 21:23:39.050262+00
87	2026-01-19 21:28:45.105202+00	8800.00	CONFIRMED	2026-01-19 21:28:45.104264+00
88	2026-01-19 21:29:44.543486+00	9600.00	CONFIRMED	2026-01-19 21:29:44.542393+00
89	2026-01-19 21:33:43.396135+00	13400.00	CONFIRMED	2026-01-19 21:33:43.394326+00
90	2026-01-19 21:38:14.989065+00	1020.00	CONFIRMED	2026-01-19 21:38:14.987581+00
91	2026-01-19 21:43:30.796315+00	3300.00	CONFIRMED	2026-01-19 21:43:30.793981+00
92	2026-01-19 21:55:30.711366+00	56500.00	CONFIRMED	2026-01-19 21:55:30.70997+00
93	2026-01-19 22:38:28.065329+00	7000.00	CONFIRMED	2026-01-19 22:38:28.063591+00
94	2026-01-19 22:39:07.304307+00	1500.00	CONFIRMED	2026-01-19 22:39:07.303297+00
95	2026-01-19 22:40:27.076792+00	2000.00	CONFIRMED	2026-01-19 22:40:27.075913+00
96	2026-01-19 22:41:36.453384+00	21550.00	CONFIRMED	2026-01-19 22:41:36.452468+00
97	2026-01-19 22:44:49.569596+00	8100.00	CONFIRMED	2026-01-19 22:44:49.568234+00
98	2026-01-19 22:46:24.278029+00	7500.00	CONFIRMED	2026-01-19 22:46:24.277126+00
99	2026-01-19 22:47:23.554805+00	800.00	CONFIRMED	2026-01-19 22:47:23.553689+00
100	2026-01-19 22:47:40.188146+00	600.00	CONFIRMED	2026-01-19 22:47:40.18728+00
101	2026-01-19 23:06:31.304342+00	3400.00	CONFIRMED	2026-01-19 23:06:31.302669+00
102	2026-01-19 23:11:06.181156+00	6000.00	CONFIRMED	2026-01-19 23:11:06.179045+00
103	2026-01-19 23:19:24.278379+00	240.00	CONFIRMED	2026-01-19 23:19:24.277311+00
104	2026-01-19 23:25:13.103818+00	1500.00	CONFIRMED	2026-01-19 23:25:13.102867+00
105	2026-01-19 23:30:04.246043+00	9000.00	CONFIRMED	2026-01-19 23:30:04.245025+00
106	2026-01-19 23:33:35.794822+00	6400.00	CONFIRMED	2026-01-19 23:33:35.793391+00
107	2026-01-19 23:41:09.434022+00	12300.00	CONFIRMED	2026-01-19 23:41:09.432564+00
108	2026-01-19 23:44:58.850293+00	6500.00	CONFIRMED	2026-01-19 23:44:58.849188+00
109	2026-01-19 23:59:50.975396+00	5000.00	CONFIRMED	2026-01-19 23:59:50.974285+00
110	2026-01-20 19:08:24.038437+00	6350.00	CONFIRMED	2026-01-20 19:08:24.037212+00
111	2026-01-20 20:15:23.278974+00	2700.00	CONFIRMED	2026-01-20 20:15:23.277816+00
112	2026-01-20 20:18:19.01117+00	6000.00	CONFIRMED	2026-01-20 20:18:19.010077+00
113	2026-01-20 20:21:14.540234+00	4400.00	CONFIRMED	2026-01-20 20:21:14.538696+00
114	2026-01-20 20:23:46.49217+00	10000.00	CONFIRMED	2026-01-20 20:23:46.490857+00
115	2026-01-20 20:38:25.795006+00	4600.00	CONFIRMED	2026-01-20 20:38:25.793468+00
116	2026-01-20 20:43:29.764812+00	53950.00	CONFIRMED	2026-01-20 20:43:29.762588+00
117	2026-01-20 20:47:22.227456+00	15050.00	CONFIRMED	2026-01-20 20:47:22.225802+00
118	2026-01-20 20:50:34.992285+00	3200.00	CONFIRMED	2026-01-20 20:50:34.991351+00
119	2026-01-20 20:53:50.632711+00	200.00	CONFIRMED	2026-01-20 20:53:50.631808+00
120	2026-01-20 21:14:52.987371+00	330.00	CONFIRMED	2026-01-20 21:14:52.985746+00
121	2026-01-20 21:15:28.643448+00	2000.00	CONFIRMED	2026-01-20 21:15:28.642458+00
122	2026-01-20 21:15:54.664025+00	1000.00	CONFIRMED	2026-01-20 21:15:54.663176+00
123	2026-01-20 21:17:23.37858+00	1000.00	CONFIRMED	2026-01-20 21:17:23.37761+00
124	2026-01-20 21:22:49.247128+00	3400.00	CONFIRMED	2026-01-20 21:22:49.246225+00
125	2026-01-20 21:27:37.089606+00	6600.00	CONFIRMED	2026-01-20 21:27:37.088201+00
126	2026-01-20 21:42:38.021+00	30200.00	CONFIRMED	2026-01-20 21:42:38.019979+00
127	2026-01-20 22:56:36.20961+00	16200.00	CONFIRMED	2026-01-20 22:56:36.208188+00
128	2026-01-20 22:58:16.030425+00	2630.00	CONFIRMED	2026-01-20 22:58:16.028503+00
129	2026-01-20 23:15:38.59942+00	3400.00	CONFIRMED	2026-01-20 23:15:38.598285+00
130	2026-01-20 23:31:20.85508+00	3400.00	CONFIRMED	2026-01-20 23:31:20.854089+00
131	2026-01-20 23:43:20.166045+00	7260.00	CONFIRMED	2026-01-20 23:43:20.164143+00
132	2026-01-20 23:51:05.056073+00	1480.00	CONFIRMED	2026-01-20 23:51:05.054496+00
133	2026-01-21 00:25:19.639134+00	6000.00	CONFIRMED	2026-01-21 00:25:19.638035+00
134	2026-01-21 12:58:52.886008+00	2500.00	CONFIRMED	2026-01-21 12:58:52.884963+00
135	2026-01-21 12:59:14.395263+00	2000.00	CONFIRMED	2026-01-21 12:59:14.393891+00
136	2026-01-21 13:04:16.767117+00	10000.00	CONFIRMED	2026-01-21 13:04:16.766148+00
137	2026-01-21 13:40:59.639245+00	6300.00	CONFIRMED	2026-01-21 13:40:59.638286+00
138	2026-01-21 19:32:58.287633+00	1750.00	CONFIRMED	2026-01-21 19:32:58.28665+00
139	2026-01-21 20:28:06.886495+00	3300.00	CONFIRMED	2026-01-21 20:28:06.885271+00
140	2026-01-21 20:42:34.378198+00	3000.00	CONFIRMED	2026-01-21 20:42:34.376392+00
141	2026-01-21 20:50:57.409332+00	1250.00	CONFIRMED	2026-01-21 20:50:57.407784+00
142	2026-01-21 21:29:40.416775+00	17900.00	CONFIRMED	2026-01-21 21:29:40.413629+00
143	2026-01-21 21:30:21.275322+00	4400.00	CONFIRMED	2026-01-21 21:30:21.27387+00
144	2026-01-21 21:30:44.442073+00	4500.00	CONFIRMED	2026-01-21 21:30:44.44111+00
145	2026-01-21 21:32:44.473772+00	2400.00	CONFIRMED	2026-01-21 21:32:44.472738+00
146	2026-01-21 21:37:54.432538+00	7500.00	CONFIRMED	2026-01-21 21:37:54.431634+00
147	2026-01-21 21:38:14.588175+00	2800.00	CONFIRMED	2026-01-21 21:38:14.587217+00
148	2026-01-21 21:38:51.48112+00	200.00	CONFIRMED	2026-01-21 21:38:51.480108+00
149	2026-01-21 21:39:29.796982+00	4750.00	CONFIRMED	2026-01-21 21:39:29.795607+00
150	2026-01-21 21:40:01.844596+00	12600.00	CONFIRMED	2026-01-21 21:40:01.843651+00
151	2026-01-21 21:40:46.949944+00	6000.00	CONFIRMED	2026-01-21 21:40:46.948356+00
152	2026-01-21 21:41:58.351647+00	2500.00	CONFIRMED	2026-01-21 21:41:58.350744+00
153	2026-01-21 21:42:37.424823+00	11600.00	CONFIRMED	2026-01-21 21:42:37.423897+00
154	2026-01-21 21:48:44.321061+00	16160.00	CONFIRMED	2026-01-21 21:48:44.319355+00
155	2026-01-21 22:04:03.301464+00	7000.00	CONFIRMED	2026-01-21 22:04:03.3004+00
156	2026-01-21 22:09:40.2952+00	5600.00	CONFIRMED	2026-01-21 22:09:40.29315+00
157	2026-01-21 22:10:23.765374+00	4240.00	CONFIRMED	2026-01-21 22:10:23.763988+00
158	2026-01-21 22:59:39.772623+00	5000.00	CONFIRMED	2026-01-21 22:59:39.771687+00
159	2026-01-21 22:59:50.07374+00	1500.00	CONFIRMED	2026-01-21 22:59:50.072643+00
160	2026-01-21 23:13:04.129875+00	2650.00	CONFIRMED	2026-01-21 23:13:04.128087+00
161	2026-01-21 23:13:39.445641+00	8000.00	CONFIRMED	2026-01-21 23:13:39.444266+00
162	2026-01-21 23:32:38.409597+00	1250.00	CONFIRMED	2026-01-21 23:32:38.408456+00
163	2026-01-21 23:44:02.484733+00	14650.00	CONFIRMED	2026-01-21 23:44:02.482873+00
164	2026-01-21 23:44:33.344514+00	3300.00	CONFIRMED	2026-01-21 23:44:33.343626+00
165	2026-01-21 23:46:41.078767+00	9500.00	CONFIRMED	2026-01-21 23:46:41.07761+00
166	2026-01-22 00:12:47.638072+00	25000.00	CONFIRMED	2026-01-22 00:12:47.637026+00
167	2026-01-22 00:52:50.564218+00	13750.00	CONFIRMED	2026-01-22 00:52:50.562763+00
168	2026-01-22 00:54:06.077456+00	4000.00	CONFIRMED	2026-01-22 00:54:06.076454+00
169	2026-01-22 19:59:22.000643+00	21600.00	CONFIRMED	2026-01-22 19:59:21.999549+00
170	2026-01-22 19:59:50.829337+00	2100.00	CONFIRMED	2026-01-22 19:59:50.828353+00
171	2026-01-22 20:01:04.96329+00	5000.00	CONFIRMED	2026-01-22 20:01:04.962422+00
172	2026-01-22 20:04:04.062525+00	600.00	CONFIRMED	2026-01-22 20:04:04.06156+00
173	2026-01-22 20:14:42.727657+00	1400.00	CONFIRMED	2026-01-22 20:14:42.726585+00
174	2026-01-22 20:15:27.835271+00	3750.00	CONFIRMED	2026-01-22 20:15:27.834077+00
175	2026-01-22 20:17:29.365091+00	6000.00	CONFIRMED	2026-01-22 20:17:29.364183+00
176	2026-01-22 21:45:16.980865+00	4650.00	CONFIRMED	2026-01-22 21:45:16.979092+00
177	2026-01-22 21:47:59.731599+00	600.00	CONFIRMED	2026-01-22 21:47:59.730371+00
178	2026-01-22 22:09:19.093477+00	17300.00	CONFIRMED	2026-01-22 22:09:19.091053+00
179	2026-01-22 22:29:32.394801+00	400.00	CONFIRMED	2026-01-22 22:29:32.393724+00
180	2026-01-22 22:32:20.242407+00	2000.00	CONFIRMED	2026-01-22 22:32:20.240768+00
181	2026-01-22 22:36:54.835039+00	8035.00	CONFIRMED	2026-01-22 22:36:54.833599+00
182	2026-01-22 22:42:15.475681+00	6500.00	CONFIRMED	2026-01-22 22:42:15.474268+00
183	2026-01-22 22:43:22.699565+00	6000.00	CONFIRMED	2026-01-22 22:43:22.698637+00
184	2026-01-22 22:43:45.550386+00	400.00	CONFIRMED	2026-01-22 22:43:45.54926+00
185	2026-01-22 22:44:09.912137+00	6000.00	CONFIRMED	2026-01-22 22:44:09.91115+00
186	2026-01-22 22:44:35.628163+00	3750.00	CONFIRMED	2026-01-22 22:44:35.627136+00
187	2026-01-22 22:45:06.616001+00	2000.00	CONFIRMED	2026-01-22 22:45:06.615136+00
188	2026-01-22 22:46:02.492722+00	15150.00	CONFIRMED	2026-01-22 22:46:02.491227+00
189	2026-01-22 22:46:31.020336+00	6000.00	CONFIRMED	2026-01-22 22:46:31.019458+00
190	2026-01-22 22:50:59.470395+00	1875.00	CONFIRMED	2026-01-22 22:50:59.469066+00
191	2026-01-22 22:56:33.584045+00	4500.00	CONFIRMED	2026-01-22 22:56:33.583024+00
192	2026-01-22 22:59:19.814889+00	2000.00	CONFIRMED	2026-01-22 22:59:19.813378+00
193	2026-01-22 23:28:28.848564+00	4800.00	CONFIRMED	2026-01-22 23:28:28.847199+00
194	2026-01-22 23:41:47.628497+00	19550.00	CONFIRMED	2026-01-22 23:41:47.627661+00
195	2026-01-22 23:52:02.630684+00	5000.00	CONFIRMED	2026-01-22 23:52:02.629793+00
196	2026-01-23 00:26:44.878791+00	1500.00	CONFIRMED	2026-01-23 00:26:44.877653+00
197	2026-01-23 01:00:28.901069+00	21600.00	CONFIRMED	2026-01-23 01:00:28.89996+00
198	2026-01-23 01:02:08.86685+00	27500.00	CONFIRMED	2026-01-23 01:02:08.86483+00
199	2026-01-23 01:03:06.90023+00	3200.00	CONFIRMED	2026-01-23 01:03:06.899361+00
200	2026-01-23 01:03:53.143378+00	7650.00	CONFIRMED	2026-01-23 01:03:53.14178+00
\.


--
-- Data for Name: sale_line; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.sale_line (id, sale_id, product_id, qty, unit_price, line_total, uom_id) FROM stdin;
132	72	1	2.000	1500.00	3000.00	1
134	74	1	1.000	1500.00	1500.00	1
135	75	215	1.000	100.00	100.00	1
136	75	339	1.000	660.00	660.00	1
142	78	113	2.000	1500.00	3000.00	1
143	79	202	4.000	40.00	160.00	1
144	79	303	4.000	1000.00	4000.00	1
149	81	305	3.000	200.00	600.00	1
151	83	11	6.000	290.00	1740.00	1
152	83	293	6.000	25.00	150.00	1
153	83	343	6.000	45.00	270.00	1
156	85	186	1.000	1000.00	1000.00	1
157	86	347	1.000	200.00	200.00	1
160	89	351	7.000	1500.00	10500.00	5
161	89	352	7.000	200.00	1400.00	1
162	89	58	1.000	1500.00	1500.00	1
165	91	71	1.000	3300.00	3300.00	1
166	92	187	30.000	1800.00	54000.00	5
167	92	280	1.000	2500.00	2500.00	1
169	94	113	1.000	1500.00	1500.00	1
170	95	357	2.000	1000.00	2000.00	1
172	97	153	5.000	750.00	3750.00	1
173	97	286	1.000	4350.00	4350.00	1
175	99	359	4.000	200.00	800.00	5
176	100	276	3.000	200.00	600.00	5
177	101	314	2.000	1000.00	2000.00	1
178	101	360	4.000	350.00	1400.00	5
182	103	364	8.000	30.00	240.00	1
185	106	368	2.000	3200.00	6400.00	1
186	107	370	1.000	8900.00	8900.00	1
187	107	371	1.000	3400.00	3400.00	1
188	108	373	1.000	6500.00	6500.00	1
189	109	376	2.000	2500.00	5000.00	1
191	111	284	1.000	2700.00	2700.00	1
193	113	303	4.000	1000.00	4000.00	1
194	113	305	2.000	200.00	400.00	1
197	115	396	10.000	10.00	100.00	1
198	115	397	1.000	4500.00	4500.00	12
203	117	280	1.000	2500.00	2500.00	1
204	117	401	1.000	12550.00	12550.00	1
205	118	402	1.000	3200.00	3200.00	1
206	119	206	1.000	200.00	200.00	1
209	121	359	10.000	200.00	2000.00	5
210	122	205	10.000	100.00	1000.00	1
214	126	408	1.000	30200.00	30200.00	1
220	129	371	1.000	3400.00	3400.00	1
222	131	250	4.000	30.00	120.00	1
223	131	420	2.000	3500.00	7000.00	1
224	131	421	4.000	35.00	140.00	1
225	132	253	4.000	120.00	480.00	1
226	132	423	4.000	250.00	1000.00	1
228	134	427	1.000	2500.00	2500.00	1
230	136	154	4.000	2500.00	10000.00	1
231	137	146	3.500	1800.00	6300.00	5
232	138	272	50.000	35.00	1750.00	1
233	139	428	1.000	3300.00	3300.00	1
234	140	113	1.000	1500.00	1500.00	1
235	140	90	1.000	1500.00	1500.00	1
237	142	142	1.000	4400.00	4400.00	1
238	142	181	20.000	50.00	1000.00	1
239	142	211	1.000	2500.00	2500.00	1
240	142	302	20.000	55.00	1100.00	1
241	142	317	6.000	300.00	1800.00	5
242	142	429	1.000	7100.00	7100.00	1
245	144	90	3.000	1500.00	4500.00	1
248	147	431	1.000	2800.00	2800.00	1
249	148	205	2.000	100.00	200.00	1
252	150	187	7.000	1800.00	12600.00	5
253	151	199	2.000	1500.00	3000.00	1
254	151	313	2.000	1500.00	3000.00	1
259	155	157	1.000	7000.00	7000.00	6
260	156	17	1.000	2000.00	2000.00	1
261	156	1	2.000	1500.00	3000.00	1
262	156	305	3.000	200.00	600.00	1
263	157	216	3.000	880.00	2640.00	1
264	157	342	1.000	1600.00	1600.00	10
266	159	104	1.000	1500.00	1500.00	1
267	160	248	2.000	350.00	700.00	1
268	160	441	2.000	700.00	1400.00	1
269	160	442	1.000	550.00	550.00	1
270	161	158	1.000	5000.00	5000.00	1
271	161	22	1.000	3000.00	3000.00	1
273	163	153	3.000	750.00	2250.00	1
274	163	156	1.000	10500.00	10500.00	8
275	163	223	1.000	1900.00	1900.00	1
276	164	393	1.000	3300.00	3300.00	11
279	167	154	5.000	2500.00	12500.00	1
280	167	456	1.000	1250.00	1250.00	1
282	169	160	4.000	5400.00	21600.00	5
286	173	441	2.000	700.00	1400.00	1
289	176	460	1.000	3650.00	3650.00	1
290	176	461	1.000	1000.00	1000.00	1
292	178	101	1.000	3000.00	3000.00	1
293	178	184	15.000	30.00	450.00	1
294	178	188	1.000	5550.00	5550.00	6
295	178	205	83.000	100.00	8300.00	1
297	180	200	1.000	2000.00	2000.00	1
300	182	357	1.000	1000.00	1000.00	1
301	182	465	1.000	5500.00	5500.00	1
302	183	50	1.000	6000.00	6000.00	1
303	184	276	2.000	200.00	400.00	5
304	185	113	4.000	1500.00	6000.00	1
305	186	102	1.000	3750.00	3750.00	1
306	187	303	2.000	1000.00	2000.00	1
307	188	286	1.000	4350.00	4350.00	1
308	188	378	2.000	5400.00	10800.00	1
133	73	331	1.000	200.00	200.00	1
137	76	340	4.000	50.00	200.00	1
168	93	204	100.000	70.00	7000.00	1
171	96	358	1.000	21550.00	21550.00	1
174	98	153	10.000	750.00	7500.00	1
179	102	17	1.000	2000.00	2000.00	1
180	102	314	2.000	1000.00	2000.00	1
181	102	82	2.000	1000.00	2000.00	1
183	104	58	1.000	1500.00	1500.00	1
184	105	366	3.000	3000.00	9000.00	1
192	112	394	1.000	6000.00	6000.00	1
7	6	4	1.000	8500.00	8500.00	1
8	7	23	1.000	2900.00	2900.00	1
9	7	4	1.000	8500.00	8500.00	1
10	7	63	10.000	3000.00	30000.00	1
11	8	82	2.000	1000.00	2000.00	1
12	9	101	1.000	3000.00	3000.00	1
13	10	101	1.000	3000.00	3000.00	1
14	11	101	1.000	3000.00	3000.00	1
15	12	50	3.000	6000.00	18000.00	1
16	13	61	2.000	1850.00	3700.00	1
17	14	85	1.000	8000.00	8000.00	1
18	15	44	1.000	3400.00	3400.00	1
19	16	215	8.000	100.00	800.00	1
20	16	216	3.000	880.00	2640.00	1
21	17	217	1.000	5300.00	5300.00	7
22	18	218	2.000	550.00	1100.00	1
23	18	219	4.000	690.00	2760.00	1
24	19	224	2.000	100.00	200.00	5
25	19	225	1.000	820.00	820.00	1
26	20	226	1.000	1300.00	1300.00	1
27	21	230	1.000	2000.00	2000.00	1
28	22	227	1.000	17500.00	17500.00	1
29	22	231	1.000	1500.00	1500.00	1
30	23	232	1.000	7000.00	7000.00	1
31	24	241	2.000	4500.00	9000.00	5
32	25	242	1.000	4000.00	4000.00	1
33	25	243	1.000	800.00	800.00	1
34	25	244	1.000	3850.00	3850.00	1
35	26	85	1.000	8000.00	8000.00	1
36	27	245	1.000	850.00	850.00	1
37	27	247	2.000	270.00	540.00	1
38	27	250	2.000	30.00	60.00	1
39	27	254	106.000	25.00	2650.00	1
40	28	256	1.000	3550.00	3550.00	1
41	28	257	1.000	2100.00	2100.00	1
42	29	261	5.000	100.00	500.00	1
43	29	262	1.000	1000.00	1000.00	1
44	30	58	1.000	1500.00	1500.00	1
45	31	259	30.000	90.00	2700.00	1
46	31	260	1.000	3000.00	3000.00	1
47	31	264	1.000	1000.00	1000.00	1
48	32	254	20.000	25.00	500.00	1
49	32	265	10.000	25.00	250.00	1
50	33	162	1.000	6000.00	6000.00	6
51	33	266	1.000	2000.00	2000.00	1
52	33	267	1.000	3000.00	3000.00	1
53	33	268	1.000	5000.00	5000.00	1
54	34	103	1.000	5650.00	5650.00	1
55	35	15	2.000	900.00	1800.00	3
56	36	269	6.000	20.00	120.00	1
57	37	109	1.000	9100.00	9100.00	1
58	37	270	20.000	25.00	500.00	1
59	37	271	20.000	30.00	600.00	1
60	37	58	1.000	1500.00	1500.00	1
61	37	84	1.000	11150.00	11150.00	1
62	38	273	1.000	5000.00	5000.00	6
63	38	58	1.000	1500.00	1500.00	1
64	39	274	1.000	3000.00	3000.00	1
65	40	267	1.000	3000.00	3000.00	1
66	41	276	10.000	200.00	2000.00	5
67	42	182	2.000	60.00	120.00	1
68	42	183	2.000	90.00	180.00	1
69	42	279	1.000	7500.00	7500.00	1
70	43	17	1.000	2000.00	2000.00	1
71	43	280	1.000	2500.00	2500.00	1
72	44	277	2.000	1750.00	3500.00	1
73	44	278	1.000	1750.00	1750.00	1
74	45	275	1.000	200.00	200.00	1
75	46	103	1.000	5650.00	5650.00	1
76	46	284	1.000	2700.00	2700.00	1
77	46	285	1.000	3300.00	3300.00	1
78	46	286	1.000	4350.00	4350.00	1
79	47	289	1.000	8850.00	8850.00	1
80	47	290	1.000	100.00	100.00	1
81	47	291	1.000	50.00	50.00	1
82	48	288	2.000	1920.00	3840.00	1
83	48	292	4.000	75.00	300.00	1
84	48	293	4.000	25.00	100.00	1
85	49	294	1.500	900.00	1350.00	5
86	50	295	1.000	5850.00	5850.00	1
87	51	293	15.000	25.00	375.00	1
88	51	299	1.000	8000.00	8000.00	1
89	51	300	1.000	3900.00	3900.00	1
90	51	301	15.000	40.00	600.00	1
91	52	251	4.000	40.00	160.00	1
92	52	302	4.000	55.00	220.00	1
93	53	303	2.000	1000.00	2000.00	1
94	53	304	1.000	500.00	500.00	5
95	53	305	3.000	200.00	600.00	1
96	54	306	10.000	200.00	2000.00	5
97	55	58	1.000	1500.00	1500.00	1
98	56	309	15.000	170.00	2550.00	1
99	56	310	2.000	700.00	1400.00	1
100	56	9	20.000	10.00	200.00	1
101	57	52	1.000	2150.00	2150.00	1
102	58	312	14.000	300.00	4200.00	1
103	59	200	4.000	2000.00	8000.00	1
104	59	313	1.000	1500.00	1500.00	1
105	60	199	1.000	1500.00	1500.00	1
106	60	240	1.000	13200.00	13200.00	1
107	60	314	1.000	1000.00	1000.00	1
108	60	315	2.000	500.00	1000.00	1
109	60	81	1.000	1000.00	1000.00	1
110	61	317	7.000	300.00	2100.00	5
111	62	8	30.000	10.00	300.00	1
112	63	61	2.000	1850.00	3700.00	1
113	64	273	1.000	5000.00	5000.00	6
114	64	50	1.000	6000.00	6000.00	1
115	64	93	1.000	23900.00	23900.00	1
116	65	318	1.000	4900.00	4900.00	1
117	65	82	5.000	1000.00	5000.00	1
118	65	99	1.000	5400.00	5400.00	1
119	66	103	1.000	5650.00	5650.00	1
120	66	319	1.000	1800.00	1800.00	1
121	66	320	1.000	8850.00	8850.00	1
122	67	321	1.000	10950.00	10950.00	1
123	68	103	1.000	5650.00	5650.00	1
124	68	322	1.000	15000.00	15000.00	1
125	68	58	1.000	1500.00	1500.00	1
126	69	306	12.500	200.00	2500.00	5
127	70	329	4.000	870.00	3480.00	1
128	71	324	1.000	1500.00	1500.00	1
129	71	325	1.000	27560.00	27560.00	1
130	71	326	6.000	65.00	390.00	1
131	71	330	6.000	70.00	420.00	1
138	77	17	1.000	2000.00	2000.00	1
139	77	212	7.000	2350.00	16450.00	5
140	77	280	1.000	2500.00	2500.00	1
141	77	294	25.000	900.00	22500.00	5
145	80	200	2.000	2000.00	4000.00	1
146	80	203	100.000	60.00	6000.00	1
147	80	212	10.000	2350.00	23500.00	5
148	80	69	1.000	3000.00	3000.00	1
150	82	342	1.000	1600.00	1600.00	10
154	84	345	1.000	3000.00	3000.00	1
155	84	346	2.000	300.00	600.00	11
158	87	349	1.000	8800.00	8800.00	1
159	88	350	1.000	9600.00	9600.00	1
163	90	269	1.000	20.00	20.00	1
164	90	353	1.000	1000.00	1000.00	1
190	110	100	1.000	6350.00	6350.00	1
195	114	193	1.000	4000.00	4000.00	1
196	114	50	1.000	6000.00	6000.00	1
199	116	200	2.000	2000.00	4000.00	1
200	116	212	15.000	2350.00	35250.00	5
201	116	273	1.000	5000.00	5000.00	6
202	116	400	1.000	9700.00	9700.00	1
207	120	184	6.000	30.00	180.00	1
208	120	254	6.000	25.00	150.00	1
211	123	403	5.000	200.00	1000.00	5
212	124	404	2.000	1700.00	3400.00	1
213	125	407	1.000	6600.00	6600.00	7
215	127	409	2.000	6500.00	13000.00	5
216	127	410	1.000	3200.00	3200.00	1
217	128	185	4.000	20.00	80.00	1
218	128	195	1.000	2150.00	2150.00	1
219	128	306	2.000	200.00	400.00	5
221	130	418	2.000	1700.00	3400.00	1
227	133	174	1.000	6000.00	6000.00	6
229	135	283	1.000	2000.00	2000.00	1
236	141	62	1.000	1250.00	1250.00	1
243	143	346	3.000	300.00	900.00	11
244	143	76	1.000	3500.00	3500.00	1
246	145	430	1.000	2400.00	2400.00	1
247	146	83	5.000	1500.00	7500.00	1
250	149	102	1.000	3750.00	3750.00	1
251	149	82	1.000	1000.00	1000.00	1
255	152	432	1.000	2500.00	2500.00	1
256	153	24	1.000	11600.00	11600.00	1
257	154	202	4.000	40.00	160.00	1
258	154	85	2.000	8000.00	16000.00	1
265	158	440	2.000	2500.00	5000.00	1
272	162	443	1.000	1250.00	1250.00	1
277	165	444	1.000	9500.00	9500.00	1
278	166	446	1.000	25000.00	25000.00	1
281	168	457	1.000	4000.00	4000.00	1
283	170	159	1.000	2100.00	2100.00	5
284	171	154	2.000	2500.00	5000.00	1
285	172	459	3.000	200.00	600.00	1
287	174	102	1.000	3750.00	3750.00	1
288	175	353	6.000	1000.00	6000.00	1
291	177	463	2.000	300.00	600.00	1
296	179	251	10.000	40.00	400.00	1
298	181	181	43.000	50.00	2150.00	1
299	181	464	107.000	55.00	5885.00	1
309	189	69	2.000	3000.00	6000.00	1
310	190	254	15.000	25.00	375.00	1
311	190	467	2.000	750.00	1500.00	1
312	191	469	1.000	4500.00	4500.00	5
313	192	471	1.000	2000.00	2000.00	1
314	193	313	1.000	1500.00	1500.00	1
315	193	393	1.000	3300.00	3300.00	11
316	194	473	1.000	19550.00	19550.00	1
317	195	474	1.000	5000.00	5000.00	1
318	196	153	2.000	750.00	1500.00	1
319	197	160	4.000	5400.00	21600.00	5
320	198	374	25.000	800.00	20000.00	5
321	198	483	1.000	7500.00	7500.00	1
322	199	390	1.000	3200.00	3200.00	9
323	200	200	2.000	2000.00	4000.00	1
324	200	460	1.000	3650.00	3650.00	1
\.


--
-- Data for Name: stock_move; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.stock_move (id, date, type, reference_type, reference_id, notes) FROM stdin;
1	2026-01-13 21:25:10.357105+00	IN	INVOICE	1	Compra - Boleta #54979
4	2026-01-13 23:35:17.981682+00	IN	INVOICE	2	Compra - Boleta #54918
5	2026-01-14 00:57:45.65758+00	IN	INVOICE	3	Compra - Boleta #13194
9	2026-01-14 14:29:40.825309+00	OUT	SALE	6	Venta #6
10	2026-01-14 21:50:08.92373+00	OUT	SALE	7	Venta #7
11	2026-01-14 22:15:12.406443+00	ADJUST	MANUAL	\N	Ajuste por edición de Boleta #13194
12	2026-01-14 22:17:35.822381+00	ADJUST	MANUAL	\N	Ajuste por edición de Boleta #13194
13	2026-01-14 22:56:07.983307+00	IN	INVOICE	4	Compra - Boleta #325193
14	2026-01-14 22:59:27.163524+00	IN	INVOICE	5	Compra - Boleta #168694
15	2026-01-14 23:09:57.725789+00	IN	INVOICE	6	Compra - Boleta #40321
16	2026-01-14 23:12:43.466522+00	IN	INVOICE	7	Compra - Boleta #325199
17	2026-01-15 00:35:02.460404+00	IN	INVOICE	8	Compra - Boleta #3349
18	2026-01-15 21:35:09.622256+00	OUT	SALE	8	Venta #8
19	2026-01-16 00:24:50.592968+00	IN	INVOICE	9	Compra - Boleta #4773
20	2026-01-16 20:40:11.330378+00	IN	INVOICE	10	Compra - Boleta #325138
21	2026-01-16 21:35:06.806474+00	IN	INVOICE	11	Compra - Boleta #12522
22	2026-01-16 23:51:53.794082+00	OUT	SALE	9	Venta #9
23	2026-01-16 23:51:53.921352+00	OUT	SALE	10	Venta #10
24	2026-01-17 00:18:17.029333+00	IN	INVOICE	12	Compra - Boleta #12614
25	2026-01-17 14:26:39.942596+00	OUT	SALE	11	Venta #11
26	2026-01-17 15:07:22.318505+00	OUT	SALE	12	Venta #12
27	2026-01-17 15:25:15.70366+00	OUT	SALE	13	Venta #13
28	2026-01-17 16:46:35.036704+00	IN	INVOICE	13	Compra - Boleta #12610
29	2026-01-17 18:21:03.411675+00	OUT	SALE	14	Venta #14
30	2026-01-17 20:54:29.078922+00	IN	INVOICE	14	Compra - Boleta #2909
31	2026-01-17 21:47:01.697741+00	OUT	SALE	15	Venta #15
32	2026-01-17 21:54:46.353473+00	ADJUST	MANUAL	\N	Stock inicial
33	2026-01-17 21:55:21.538989+00	ADJUST	MANUAL	\N	Stock inicial
34	2026-01-17 21:56:03.659821+00	OUT	SALE	16	Venta #16
35	2026-01-17 21:57:51.603885+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
36	2026-01-17 22:01:40.422159+00	ADJUST	MANUAL	\N	Stock inicial
37	2026-01-17 22:01:59.017597+00	OUT	SALE	17	Venta #17
38	2026-01-17 22:10:28.648699+00	ADJUST	MANUAL	\N	Stock inicial
39	2026-01-17 22:13:28.768414+00	ADJUST	MANUAL	\N	Stock inicial
40	2026-01-17 22:14:09.843131+00	OUT	SALE	18	Venta #18
41	2026-01-17 22:16:20.064913+00	ADJUST	MANUAL	\N	Stock inicial
42	2026-01-17 22:20:22.862169+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
43	2026-01-17 22:30:11.721312+00	ADJUST	MANUAL	\N	Stock inicial
44	2026-01-17 22:31:01.726548+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
45	2026-01-17 22:31:37.455001+00	OUT	SALE	19	Venta #19
46	2026-01-17 22:32:27.027573+00	ADJUST	MANUAL	\N	Stock inicial
47	2026-01-17 22:32:49.351517+00	OUT	SALE	20	Venta #20
48	2026-01-17 22:40:09.685243+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
49	2026-01-17 22:45:57.766703+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
50	2026-01-17 22:49:36.996883+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
51	2026-01-17 22:53:20.68624+00	ADJUST	MANUAL	\N	Stock inicial
52	2026-01-17 22:53:41.597859+00	OUT	SALE	21	Venta #21
53	2026-01-17 22:55:32.966554+00	ADJUST	MANUAL	\N	Stock inicial
54	2026-01-17 22:56:25.062929+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
55	2026-01-17 22:57:01.643401+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
56	2026-01-17 22:58:26.628987+00	OUT	SALE	22	Venta #22
57	2026-01-17 22:59:32.261561+00	ADJUST	MANUAL	\N	Stock inicial
58	2026-01-17 22:59:48.072753+00	OUT	SALE	23	Venta #23
59	2026-01-17 23:05:30.467536+00	ADJUST	MANUAL	\N	Stock inicial
60	2026-01-17 23:06:21.723803+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
61	2026-01-17 23:08:18.091014+00	ADJUST	MANUAL	\N	Stock inicial
62	2026-01-17 23:08:18.701155+00	ADJUST	MANUAL	\N	Stock inicial
63	2026-01-17 23:23:39.805532+00	IN	INVOICE	15	Compra - Boleta #3464
64	2026-01-17 23:29:45.964051+00	ADJUST	MANUAL	\N	Stock inicial
65	2026-01-17 23:30:05.071201+00	OUT	SALE	24	Venta #24
66	2026-01-17 23:31:05.281333+00	ADJUST	MANUAL	\N	Stock inicial
67	2026-01-17 23:31:58.077717+00	ADJUST	MANUAL	\N	Stock inicial
68	2026-01-17 23:32:39.811279+00	ADJUST	MANUAL	\N	Stock inicial
69	2026-01-17 23:34:41.856848+00	OUT	SALE	25	Venta #25
70	2026-01-17 23:37:03.700879+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
71	2026-01-17 23:37:56.884757+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
72	2026-01-17 23:40:35.65631+00	OUT	SALE	26	Venta #26
73	2026-01-17 23:57:58.913495+00	ADJUST	MANUAL	\N	Stock inicial
74	2026-01-17 23:58:28.008956+00	ADJUST	MANUAL	\N	Stock inicial
75	2026-01-17 23:59:06.245682+00	ADJUST	MANUAL	\N	Stock inicial
76	2026-01-17 23:59:34.078187+00	ADJUST	MANUAL	\N	Stock inicial
77	2026-01-18 00:02:12.321571+00	ADJUST	MANUAL	\N	Stock inicial
78	2026-01-18 00:02:42.935194+00	ADJUST	MANUAL	\N	Stock inicial
79	2026-01-18 00:03:07.508281+00	ADJUST	MANUAL	\N	Stock inicial
80	2026-01-18 00:03:36.378144+00	ADJUST	MANUAL	\N	Stock inicial
81	2026-01-18 00:04:06.640861+00	ADJUST	MANUAL	\N	Stock inicial
82	2026-01-18 00:05:17.864139+00	ADJUST	MANUAL	\N	Stock inicial
83	2026-01-18 00:06:42.371664+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
84	2026-01-18 00:08:29.349174+00	OUT	SALE	27	Venta #27
85	2026-01-18 12:57:10.166571+00	ADJUST	MANUAL	\N	Stock inicial
86	2026-01-18 12:58:59.664283+00	ADJUST	MANUAL	\N	Stock inicial
87	2026-01-18 13:02:21.964553+00	ADJUST	MANUAL	\N	Stock inicial
88	2026-01-18 13:04:23.619222+00	OUT	SALE	28	Venta #28
89	2026-01-18 13:05:41.958872+00	ADJUST	MANUAL	\N	Stock inicial
90	2026-01-18 13:06:48.438338+00	ADJUST	MANUAL	\N	Stock inicial
91	2026-01-18 13:07:39.771376+00	ADJUST	MANUAL	\N	Stock inicial
92	2026-01-18 13:12:06.935775+00	ADJUST	MANUAL	\N	Stock inicial
93	2026-01-18 13:12:39.236493+00	ADJUST	MANUAL	\N	Stock inicial
94	2026-01-18 13:13:39.195357+00	OUT	SALE	29	Venta #29
95	2026-01-18 13:14:32.273508+00	OUT	SALE	30	Venta #30
96	2026-01-18 13:16:00.219916+00	ADJUST	MANUAL	\N	Stock inicial
97	2026-01-18 13:16:40.291368+00	ADJUST	MANUAL	\N	Stock inicial
98	2026-01-18 13:19:19.873882+00	OUT	SALE	31	Venta #31
99	2026-01-18 13:24:54.763952+00	ADJUST	MANUAL	\N	Stock inicial
100	2026-01-18 13:25:44.544816+00	OUT	SALE	32	Venta #32
101	2026-01-18 13:45:34.822405+00	ADJUST	MANUAL	\N	Stock inicial
102	2026-01-18 13:46:15.915737+00	ADJUST	MANUAL	\N	Stock inicial
103	2026-01-18 13:46:44.101601+00	ADJUST	MANUAL	\N	Stock inicial
104	2026-01-18 13:48:08.351933+00	OUT	SALE	33	Venta #33
105	2026-01-18 13:50:03.929837+00	OUT	SALE	34	Venta #34
106	2026-01-18 13:58:30.835887+00	OUT	SALE	35	Venta #35
107	2026-01-18 14:05:11.527267+00	ADJUST	MANUAL	\N	Stock inicial
108	2026-01-18 14:05:44.800449+00	OUT	SALE	36	Venta #36
109	2026-01-18 14:07:47.159504+00	ADJUST	MANUAL	\N	Stock inicial
110	2026-01-18 14:08:43.248569+00	ADJUST	MANUAL	\N	Stock inicial
111	2026-01-18 14:09:51.989715+00	OUT	SALE	37	Venta #37
112	2026-01-18 14:12:28.251646+00	ADJUST	MANUAL	\N	Stock inicial
113	2026-01-18 14:14:29.848759+00	ADJUST	MANUAL	\N	Stock inicial
114	2026-01-18 14:15:00.476184+00	OUT	SALE	38	Venta #38
115	2026-01-18 14:35:24.462215+00	ADJUST	MANUAL	\N	Stock inicial
116	2026-01-18 14:35:40.91825+00	OUT	SALE	39	Venta #39
117	2026-01-18 14:40:53.241942+00	OUT	SALE	40	Venta #40
118	2026-01-18 14:45:31.424088+00	ADJUST	MANUAL	\N	Stock inicial
119	2026-01-18 14:46:11.886674+00	ADJUST	MANUAL	\N	Stock inicial
120	2026-01-18 14:46:35.941111+00	OUT	SALE	41	Venta #41
121	2026-01-18 14:47:26.286375+00	ADJUST	MANUAL	\N	Stock inicial
122	2026-01-18 14:48:03.326777+00	ADJUST	MANUAL	\N	Stock inicial
123	2026-01-18 14:50:25.324711+00	ADJUST	MANUAL	\N	Stock inicial
124	2026-01-18 14:51:17.767844+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
125	2026-01-18 14:51:46.864315+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
126	2026-01-18 14:52:27.746144+00	OUT	SALE	42	Venta #42
127	2026-01-18 14:54:13.603209+00	ADJUST	MANUAL	\N	Stock inicial
128	2026-01-18 14:56:00.460288+00	OUT	SALE	43	Venta #43
129	2026-01-18 15:00:11.735469+00	ADJUST	MANUAL	\N	Stock inicial
130	2026-01-18 15:05:16.789199+00	ADJUST	MANUAL	\N	Stock inicial
131	2026-01-18 15:05:51.664832+00	ADJUST	MANUAL	\N	Stock inicial
132	2026-01-18 15:06:21.380937+00	ADJUST	MANUAL	\N	Stock inicial
133	2026-01-18 15:06:56.938556+00	ADJUST	MANUAL	\N	Stock inicial
134	2026-01-18 15:07:28.156594+00	ADJUST	MANUAL	\N	Stock inicial
135	2026-01-18 15:08:12.50776+00	ADJUST	MANUAL	\N	Stock inicial
136	2026-01-18 15:08:35.574836+00	OUT	SALE	44	Venta #44
137	2026-01-18 15:08:57.022478+00	OUT	SALE	45	Venta #45
138	2026-01-18 15:10:05.036463+00	OUT	SALE	46	Venta #46
139	2026-01-18 15:11:03.034585+00	ADJUST	MANUAL	\N	Stock inicial
140	2026-01-18 15:15:52.756717+00	ADJUST	MANUAL	\N	Stock inicial
141	2026-01-18 15:17:11.587933+00	ADJUST	MANUAL	\N	Stock inicial
142	2026-01-18 15:18:39.630828+00	ADJUST	MANUAL	\N	Stock inicial
143	2026-01-18 15:19:26.533989+00	OUT	SALE	47	Venta #47
144	2026-01-18 15:22:00.167933+00	ADJUST	MANUAL	\N	Stock inicial
145	2026-01-18 15:22:30.040801+00	ADJUST	MANUAL	\N	Stock inicial
146	2026-01-18 15:24:36.717032+00	OUT	SALE	48	Venta #48
147	2026-01-18 15:30:31.345842+00	ADJUST	MANUAL	\N	Stock inicial
148	2026-01-18 15:30:56.95186+00	OUT	SALE	49	Venta #49
149	2026-01-18 15:33:20.352185+00	ADJUST	MANUAL	\N	Stock inicial
150	2026-01-18 15:33:45.897313+00	OUT	SALE	50	Venta #50
151	2026-01-18 15:46:22.735629+00	ADJUST	MANUAL	\N	Stock inicial
152	2026-01-18 15:46:50.728755+00	ADJUST	MANUAL	\N	Stock inicial
153	2026-01-18 15:47:17.639175+00	ADJUST	MANUAL	\N	Stock inicial
154	2026-01-18 15:52:37.674649+00	ADJUST	MANUAL	\N	Stock inicial
155	2026-01-18 15:53:03.435967+00	ADJUST	MANUAL	\N	Stock inicial
156	2026-01-18 15:55:55.357086+00	ADJUST	MANUAL	\N	Stock inicial
157	2026-01-18 15:56:52.111371+00	OUT	SALE	51	Venta #51
158	2026-01-18 15:58:53.792004+00	ADJUST	MANUAL	\N	Stock inicial
159	2026-01-18 15:59:36.908667+00	OUT	SALE	52	Venta #52
160	2026-01-18 16:01:33.874331+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
161	2026-01-18 16:08:48.35314+00	ADJUST	MANUAL	\N	Stock inicial
162	2026-01-18 16:09:46.230395+00	ADJUST	MANUAL	\N	Stock inicial
163	2026-01-18 16:10:28.597373+00	ADJUST	MANUAL	\N	Stock inicial
164	2026-01-18 16:13:35.772422+00	OUT	SALE	53	Venta #53
165	2026-01-18 16:19:47.184483+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
166	2026-01-18 16:20:29.829762+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
167	2026-01-18 16:21:08.370282+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
168	2026-01-18 16:22:11.208736+00	ADJUST	MANUAL	\N	Stock inicial
169	2026-01-18 16:22:33.445201+00	OUT	SALE	54	Venta #54
170	2026-01-18 16:26:18.996497+00	ADJUST	MANUAL	\N	Stock inicial
171	2026-01-18 16:26:59.593144+00	ADJUST	MANUAL	\N	Stock inicial
172	2026-01-18 16:31:25.674505+00	OUT	SALE	55	Venta #55
173	2026-01-18 16:32:17.596951+00	ADJUST	MANUAL	\N	Stock inicial
174	2026-01-18 16:32:52.712068+00	ADJUST	MANUAL	\N	Stock inicial
175	2026-01-18 16:34:24.606458+00	OUT	SALE	56	Venta #56
176	2026-01-18 16:35:21.866925+00	ADJUST	MANUAL	\N	Stock inicial
177	2026-01-18 16:36:02.129159+00	OUT	SALE	57	Venta #57
178	2026-01-18 16:54:45.040029+00	ADJUST	MANUAL	\N	Stock inicial
179	2026-01-18 16:58:16.210868+00	OUT	SALE	58	Venta #58
180	2026-01-18 16:59:08.01335+00	ADJUST	MANUAL	\N	Stock inicial
181	2026-01-18 16:59:28.215294+00	OUT	SALE	59	Venta #59
182	2026-01-18 17:22:16.53912+00	ADJUST	MANUAL	\N	Stock inicial
183	2026-01-18 17:23:22.305662+00	ADJUST	MANUAL	\N	Stock inicial
184	2026-01-18 17:24:10.574099+00	ADJUST	MANUAL	\N	Stock inicial
185	2026-01-18 17:24:37.932311+00	OUT	SALE	60	Venta #60
186	2026-01-18 17:25:56.665229+00	ADJUST	MANUAL	\N	Stock inicial
187	2026-01-18 17:26:15.311488+00	OUT	SALE	61	Venta #61
188	2026-01-18 17:40:00.704278+00	OUT	SALE	62	Venta #62
189	2026-01-18 17:41:39.423214+00	OUT	SALE	63	Venta #63
190	2026-01-18 17:43:27.592066+00	OUT	SALE	64	Venta #64
191	2026-01-18 17:45:52.130158+00	ADJUST	MANUAL	\N	Stock inicial
192	2026-01-18 17:47:16.412225+00	OUT	SALE	65	Venta #65
193	2026-01-18 17:50:47.955342+00	ADJUST	MANUAL	\N	Stock inicial
194	2026-01-18 17:51:49.120772+00	ADJUST	MANUAL	\N	Stock inicial
195	2026-01-18 17:53:46.07072+00	ADJUST	MANUAL	\N	Stock inicial
196	2026-01-18 17:54:12.454424+00	OUT	SALE	66	Venta #66
197	2026-01-18 17:54:26.519899+00	OUT	SALE	67	Venta #67
198	2026-01-18 17:55:37.980342+00	ADJUST	MANUAL	\N	Stock inicial
199	2026-01-18 17:57:12.075334+00	OUT	SALE	68	Venta #68
200	2026-01-18 17:57:46.289064+00	ADJUST	MANUAL	\N	Stock inicial
201	2026-01-18 18:06:50.091988+00	OUT	SALE	69	Venta #69
202	2026-01-18 18:08:41.165475+00	ADJUST	MANUAL	\N	Stock inicial
203	2026-01-18 18:09:24.696368+00	ADJUST	MANUAL	\N	Stock inicial
204	2026-01-18 18:10:29.010348+00	ADJUST	MANUAL	\N	Stock inicial
205	2026-01-18 18:11:15.519534+00	ADJUST	MANUAL	\N	Stock inicial
206	2026-01-18 18:18:20.803694+00	ADJUST	MANUAL	\N	Stock inicial
207	2026-01-18 18:19:11.751804+00	ADJUST	MANUAL	\N	Stock inicial
208	2026-01-18 18:20:25.773437+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
209	2026-01-18 18:20:59.500392+00	OUT	SALE	70	Venta #70
210	2026-01-18 18:23:21.964754+00	ADJUST	MANUAL	\N	Stock inicial
211	2026-01-18 18:24:11.054546+00	OUT	SALE	71	Venta #71
212	2026-01-18 18:35:42.921476+00	ADJUST	MANUAL	\N	Stock inicial
213	2026-01-18 18:46:02.041376+00	OUT	SALE	72	Venta #72
214	2026-01-18 18:51:01.546996+00	OUT	SALE	73	Venta #73
215	2026-01-18 18:51:17.60968+00	OUT	SALE	74	Venta #74
428	2026-01-22 00:42:53.954773+00	ADJUST	MANUAL	\N	Stock inicial
216	2026-01-18 19:17:13.598413+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
217	2026-01-18 19:17:54.568997+00	OUT	SALE	75	Venta #75
218	2026-01-18 19:18:30.937922+00	ADJUST	MANUAL	\N	Stock inicial
219	2026-01-18 19:19:05.925451+00	OUT	SALE	76	Venta #76
220	2026-01-19 20:42:02.338404+00	ADJUST	MANUAL	\N	Stock inicial
221	2026-01-19 20:50:08.69147+00	OUT	SALE	77	Venta #77
222	2026-01-19 20:50:41.606472+00	OUT	SALE	78	Venta #78
223	2026-01-19 20:52:31.825947+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
224	2026-01-19 20:53:18.638527+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
225	2026-01-19 20:54:52.838676+00	OUT	SALE	79	Venta #79
226	2026-01-19 20:56:02.321496+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
227	2026-01-19 20:58:38.31579+00	OUT	SALE	80	Venta #80
228	2026-01-19 20:59:13.683539+00	OUT	SALE	81	Venta #81
229	2026-01-19 21:03:11.001933+00	ADJUST	MANUAL	\N	Stock inicial
230	2026-01-19 21:03:47.720063+00	OUT	SALE	82	Venta #82
231	2026-01-19 21:06:00.360073+00	ADJUST	MANUAL	\N	Stock inicial
232	2026-01-19 21:06:30.594322+00	OUT	SALE	83	Venta #83
233	2026-01-19 21:15:23.072594+00	ADJUST	MANUAL	\N	Stock inicial
234	2026-01-19 21:17:11.069912+00	ADJUST	MANUAL	\N	Stock inicial
235	2026-01-19 21:17:43.155846+00	OUT	SALE	84	Venta #84
236	2026-01-19 21:18:27.249983+00	OUT	SALE	85	Venta #85
237	2026-01-19 21:19:42.191847+00	ADJUST	MANUAL	\N	Stock inicial
238	2026-01-19 21:23:39.052438+00	OUT	SALE	86	Venta #86
239	2026-01-19 21:24:14.493548+00	ADJUST	MANUAL	\N	Stock inicial
240	2026-01-19 21:28:03.362437+00	ADJUST	MANUAL	\N	Stock inicial
241	2026-01-19 21:28:45.106083+00	OUT	SALE	87	Venta #87
242	2026-01-19 21:29:26.06799+00	ADJUST	MANUAL	\N	Stock inicial
243	2026-01-19 21:29:44.545137+00	OUT	SALE	88	Venta #88
244	2026-01-19 21:31:08.126594+00	ADJUST	MANUAL	\N	Stock inicial
245	2026-01-19 21:32:25.034554+00	ADJUST	MANUAL	\N	Stock inicial
246	2026-01-19 21:33:43.397428+00	OUT	SALE	89	Venta #89
247	2026-01-19 21:37:28.920546+00	ADJUST	MANUAL	\N	Stock inicial
248	2026-01-19 21:38:14.990242+00	OUT	SALE	90	Venta #90
249	2026-01-19 21:39:22.669206+00	ADJUST	MANUAL	\N	Stock inicial
250	2026-01-19 21:43:30.79799+00	OUT	SALE	91	Venta #91
251	2026-01-19 21:53:49.5909+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
252	2026-01-19 21:55:30.712204+00	OUT	SALE	92	Venta #92
253	2026-01-19 22:04:32.67351+00	ADJUST	MANUAL	\N	Stock inicial
254	2026-01-19 22:06:04.169261+00	ADJUST	MANUAL	\N	Stock inicial
255	2026-01-19 22:36:54.830677+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
256	2026-01-19 22:38:28.069878+00	OUT	SALE	93	Venta #93
257	2026-01-19 22:39:07.305624+00	OUT	SALE	94	Venta #94
258	2026-01-19 22:40:05.580557+00	ADJUST	MANUAL	\N	Stock inicial
259	2026-01-19 22:40:27.077504+00	OUT	SALE	95	Venta #95
260	2026-01-19 22:41:18.224897+00	ADJUST	MANUAL	\N	Stock inicial
261	2026-01-19 22:41:36.454161+00	OUT	SALE	96	Venta #96
262	2026-01-19 22:43:04.612547+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
263	2026-01-19 22:43:27.428459+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
264	2026-01-19 22:44:49.570438+00	OUT	SALE	97	Venta #97
265	2026-01-19 22:46:24.278847+00	OUT	SALE	98	Venta #98
266	2026-01-19 22:47:06.836427+00	ADJUST	MANUAL	\N	Stock inicial
267	2026-01-19 22:47:23.556129+00	OUT	SALE	99	Venta #99
268	2026-01-19 22:47:40.188891+00	OUT	SALE	100	Venta #100
269	2026-01-19 22:52:15.524367+00	ADJUST	MANUAL	\N	Stock inicial
270	2026-01-19 23:06:31.305996+00	OUT	SALE	101	Venta #101
271	2026-01-19 23:11:06.183108+00	OUT	SALE	102	Venta #102
272	2026-01-19 23:13:22.342394+00	ADJUST	MANUAL	\N	Stock inicial
273	2026-01-19 23:14:08.192242+00	ADJUST	MANUAL	\N	Stock inicial
274	2026-01-19 23:14:44.855042+00	ADJUST	MANUAL	\N	Stock inicial
275	2026-01-19 23:18:54.097012+00	ADJUST	MANUAL	\N	Stock inicial
276	2026-01-19 23:19:24.27989+00	OUT	SALE	103	Venta #103
277	2026-01-19 23:21:08.00467+00	ADJUST	MANUAL	\N	Stock inicial
278	2026-01-19 23:25:13.104896+00	OUT	SALE	104	Venta #104
279	2026-01-19 23:29:36.818264+00	ADJUST	MANUAL	\N	Stock inicial
280	2026-01-19 23:30:04.247189+00	OUT	SALE	105	Venta #105
281	2026-01-19 23:31:36.021817+00	ADJUST	MANUAL	\N	Stock inicial
282	2026-01-19 23:33:15.408492+00	ADJUST	MANUAL	\N	Stock inicial
283	2026-01-19 23:33:35.795921+00	OUT	SALE	106	Venta #106
284	2026-01-19 23:34:42.407695+00	ADJUST	MANUAL	\N	Stock inicial
285	2026-01-19 23:39:23.615118+00	ADJUST	MANUAL	\N	Stock inicial
286	2026-01-19 23:40:38.62198+00	ADJUST	MANUAL	\N	Stock inicial
287	2026-01-19 23:41:09.435344+00	OUT	SALE	107	Venta #107
288	2026-01-19 23:41:54.576276+00	ADJUST	MANUAL	\N	Stock inicial
289	2026-01-19 23:44:42.771209+00	ADJUST	MANUAL	\N	Stock inicial
290	2026-01-19 23:44:58.851217+00	OUT	SALE	108	Venta #108
291	2026-01-19 23:49:04.294319+00	ADJUST	MANUAL	\N	Stock inicial
292	2026-01-19 23:58:47.493596+00	ADJUST	MANUAL	\N	Stock inicial
293	2026-01-19 23:59:50.976959+00	OUT	SALE	109	Venta #109
294	2026-01-20 00:02:15.678055+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
295	2026-01-20 00:04:58.714757+00	ADJUST	MANUAL	\N	Stock inicial
296	2026-01-20 00:13:03.119465+00	ADJUST	MANUAL	\N	Stock inicial
297	2026-01-20 00:18:24.994958+00	ADJUST	MANUAL	\N	Stock inicial
298	2026-01-20 00:27:18.784114+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
299	2026-01-20 00:29:50.5397+00	ADJUST	MANUAL	\N	Stock inicial
300	2026-01-20 00:47:35.913861+00	IN	INVOICE	16	Compra - Boleta #3496
301	2026-01-20 19:08:24.041968+00	OUT	SALE	110	Venta #110
302	2026-01-20 20:15:23.281848+00	OUT	SALE	111	Venta #111
303	2026-01-20 20:17:44.884608+00	ADJUST	MANUAL	\N	Stock inicial
304	2026-01-20 20:18:19.012733+00	OUT	SALE	112	Venta #112
305	2026-01-20 20:19:38.472876+00	ADJUST	MANUAL	\N	Stock inicial
306	2026-01-20 20:21:14.541596+00	OUT	SALE	113	Venta #113
307	2026-01-20 20:22:45.594863+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
308	2026-01-20 20:23:46.492947+00	OUT	SALE	114	Venta #114
309	2026-01-20 20:26:49.092802+00	ADJUST	MANUAL	\N	Stock inicial
310	2026-01-20 20:34:10.575762+00	ADJUST	MANUAL	\N	Stock inicial
311	2026-01-20 20:35:55.652596+00	ADJUST	MANUAL	\N	Stock inicial
312	2026-01-20 20:37:41.295498+00	ADJUST	MANUAL	\N	Stock inicial
313	2026-01-20 20:38:25.79639+00	OUT	SALE	115	Venta #115
314	2026-01-20 20:42:08.371129+00	ADJUST	MANUAL	\N	Stock inicial
315	2026-01-20 20:43:29.766841+00	OUT	SALE	116	Venta #116
316	2026-01-20 20:45:25.027823+00	ADJUST	MANUAL	\N	Stock inicial
317	2026-01-20 20:47:22.230105+00	OUT	SALE	117	Venta #117
318	2026-01-20 20:49:58.758628+00	ADJUST	MANUAL	\N	Stock inicial
319	2026-01-20 20:50:34.993055+00	OUT	SALE	118	Venta #118
320	2026-01-20 20:51:45.018071+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
321	2026-01-20 20:53:02.106509+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
322	2026-01-20 20:53:50.633569+00	OUT	SALE	119	Venta #119
323	2026-01-20 20:55:10.442501+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
324	2026-01-20 20:55:54.718554+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
325	2026-01-20 20:56:45.573831+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
326	2026-01-20 21:14:52.989581+00	OUT	SALE	120	Venta #120
327	2026-01-20 21:15:28.646021+00	OUT	SALE	121	Venta #121
328	2026-01-20 21:15:54.664812+00	OUT	SALE	122	Venta #122
329	2026-01-20 21:16:51.914403+00	ADJUST	MANUAL	\N	Stock inicial
330	2026-01-20 21:17:23.379581+00	OUT	SALE	123	Venta #123
331	2026-01-20 21:22:26.426379+00	ADJUST	MANUAL	\N	Stock inicial
332	2026-01-20 21:22:49.247895+00	OUT	SALE	124	Venta #124
333	2026-01-20 21:23:32.928423+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
334	2026-01-20 21:23:56.132002+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
335	2026-01-20 21:25:23.053382+00	ADJUST	MANUAL	\N	Stock inicial
336	2026-01-20 21:26:17.233365+00	ADJUST	MANUAL	\N	Stock inicial
337	2026-01-20 21:27:17.60588+00	ADJUST	MANUAL	\N	Stock inicial
338	2026-01-20 21:27:37.091761+00	OUT	SALE	125	Venta #125
339	2026-01-20 21:42:19.985943+00	ADJUST	MANUAL	\N	Stock inicial
340	2026-01-20 21:42:38.022464+00	OUT	SALE	126	Venta #126
341	2026-01-20 22:55:32.778207+00	ADJUST	MANUAL	\N	Stock inicial
342	2026-01-20 22:55:58.365059+00	ADJUST	MANUAL	\N	Stock inicial
343	2026-01-20 22:56:36.210988+00	OUT	SALE	127	Venta #127
344	2026-01-20 22:57:10.57428+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
345	2026-01-20 22:58:16.031785+00	OUT	SALE	128	Venta #128
346	2026-01-20 23:11:19.769942+00	ADJUST	MANUAL	\N	Stock inicial
347	2026-01-20 23:12:15.065486+00	ADJUST	MANUAL	\N	Stock inicial
348	2026-01-20 23:15:38.60162+00	OUT	SALE	129	Venta #129
349	2026-01-20 23:30:28.373986+00	ADJUST	MANUAL	\N	Stock inicial
350	2026-01-20 23:31:20.857201+00	OUT	SALE	130	Venta #130
351	2026-01-20 23:39:41.487064+00	ADJUST	MANUAL	\N	Stock inicial
352	2026-01-20 23:41:47.160905+00	ADJUST	MANUAL	\N	Stock inicial
353	2026-01-20 23:43:20.167452+00	OUT	SALE	131	Venta #131
354	2026-01-20 23:44:29.710976+00	ADJUST	MANUAL	\N	Stock inicial
355	2026-01-20 23:49:56.670589+00	ADJUST	MANUAL	\N	Stock inicial
356	2026-01-20 23:51:05.057337+00	OUT	SALE	132	Venta #132
357	2026-01-21 00:07:06.015119+00	IN	INVOICE	17	Compra - Boleta #4620
358	2026-01-21 00:10:44.702372+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
359	2026-01-21 00:13:56.677403+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
360	2026-01-21 00:17:38.025671+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
361	2026-01-21 00:19:10.228796+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
362	2026-01-21 00:19:42.606559+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
363	2026-01-21 00:20:41.973244+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
364	2026-01-21 00:21:12.538396+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
365	2026-01-21 00:21:39.649058+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
366	2026-01-21 00:22:09.213687+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
367	2026-01-21 00:22:33.744962+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
368	2026-01-21 00:23:16.177731+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
369	2026-01-21 00:24:53.754989+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
370	2026-01-21 00:25:19.640651+00	OUT	SALE	133	Venta #133
371	2026-01-21 00:26:17.810465+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
372	2026-01-21 00:26:51.759494+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
373	2026-01-21 00:31:07.307692+00	IN	INVOICE	18	Compra - Boleta #3361
374	2026-01-21 12:58:18.705289+00	ADJUST	MANUAL	\N	Stock inicial
375	2026-01-21 12:58:52.887847+00	OUT	SALE	134	Venta #134
376	2026-01-21 12:59:14.398198+00	OUT	SALE	135	Venta #135
377	2026-01-21 13:04:16.768373+00	OUT	SALE	136	Venta #136
378	2026-01-21 13:40:59.640493+00	OUT	SALE	137	Venta #137
379	2026-01-21 19:32:58.289071+00	OUT	SALE	138	Venta #138
380	2026-01-21 20:27:42.284442+00	ADJUST	MANUAL	\N	Stock inicial
381	2026-01-21 20:28:06.887897+00	OUT	SALE	139	Venta #139
382	2026-01-21 20:42:34.380502+00	OUT	SALE	140	Venta #140
383	2026-01-21 20:50:57.412375+00	OUT	SALE	141	Venta #141
384	2026-01-21 21:15:55.358202+00	ADJUST	MANUAL	\N	Stock inicial
385	2026-01-21 21:29:40.419821+00	OUT	SALE	142	Venta #142
386	2026-01-21 21:30:21.277528+00	OUT	SALE	143	Venta #143
387	2026-01-21 21:30:44.442894+00	OUT	SALE	144	Venta #144
388	2026-01-21 21:32:18.885286+00	ADJUST	MANUAL	\N	Stock inicial
389	2026-01-21 21:32:44.474731+00	OUT	SALE	145	Venta #145
390	2026-01-21 21:35:46.832004+00	ADJUST	MANUAL	\N	Stock inicial
391	2026-01-21 21:37:54.433271+00	OUT	SALE	146	Venta #146
392	2026-01-21 21:38:14.59002+00	OUT	SALE	147	Venta #147
393	2026-01-21 21:38:51.482041+00	OUT	SALE	148	Venta #148
394	2026-01-21 21:39:29.797868+00	OUT	SALE	149	Venta #149
395	2026-01-21 21:40:01.845822+00	OUT	SALE	150	Venta #150
396	2026-01-21 21:40:46.950719+00	OUT	SALE	151	Venta #151
397	2026-01-21 21:41:33.270808+00	ADJUST	MANUAL	\N	Stock inicial
398	2026-01-21 21:41:58.352469+00	OUT	SALE	152	Venta #152
399	2026-01-21 21:42:37.425612+00	OUT	SALE	153	Venta #153
400	2026-01-21 21:48:44.323242+00	OUT	SALE	154	Venta #154
401	2026-01-21 21:56:00.697279+00	ADJUST	MANUAL	\N	Stock inicial
402	2026-01-21 22:04:03.304012+00	OUT	SALE	155	Venta #155
403	2026-01-21 22:09:40.296749+00	OUT	SALE	156	Venta #156
404	2026-01-21 22:10:23.766169+00	OUT	SALE	157	Venta #157
405	2026-01-21 22:25:03.104699+00	ADJUST	MANUAL	\N	Stock inicial
406	2026-01-21 22:26:31.279015+00	ADJUST	MANUAL	\N	Stock inicial
407	2026-01-21 22:27:01.965927+00	ADJUST	MANUAL	\N	Stock inicial
408	2026-01-21 22:30:31.650675+00	ADJUST	MANUAL	\N	Stock inicial
409	2026-01-21 22:51:35.28891+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
410	2026-01-21 22:55:43.604648+00	ADJUST	MANUAL	\N	Stock inicial
411	2026-01-21 22:59:22.164151+00	ADJUST	MANUAL	\N	Stock inicial
412	2026-01-21 22:59:39.773991+00	OUT	SALE	158	Venta #158
413	2026-01-21 22:59:50.075627+00	OUT	SALE	159	Venta #159
414	2026-01-21 23:10:48.434356+00	ADJUST	MANUAL	\N	Stock inicial
415	2026-01-21 23:12:46.89244+00	ADJUST	MANUAL	\N	Stock inicial
416	2026-01-21 23:13:04.130785+00	OUT	SALE	160	Venta #160
417	2026-01-21 23:13:39.446438+00	OUT	SALE	161	Venta #161
418	2026-01-21 23:32:24.361263+00	ADJUST	MANUAL	\N	Stock inicial
419	2026-01-21 23:32:38.411424+00	OUT	SALE	162	Venta #162
420	2026-01-21 23:44:02.487347+00	OUT	SALE	163	Venta #163
421	2026-01-21 23:44:33.345296+00	OUT	SALE	164	Venta #164
422	2026-01-21 23:46:23.618311+00	ADJUST	MANUAL	\N	Stock inicial
423	2026-01-21 23:46:41.079952+00	OUT	SALE	165	Venta #165
424	2026-01-22 00:12:09.039102+00	ADJUST	MANUAL	\N	Stock inicial
425	2026-01-22 00:12:47.640294+00	OUT	SALE	166	Venta #166
426	2026-01-22 00:18:08.408041+00	ADJUST	MANUAL	\N	Stock inicial
427	2026-01-22 00:23:26.979119+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
429	2026-01-22 00:46:12.804782+00	IN	INVOICE	19	Compra - Boleta #13456
430	2026-01-22 00:52:14.997537+00	ADJUST	MANUAL	\N	Stock inicial
431	2026-01-22 00:52:50.565602+00	OUT	SALE	167	Venta #167
432	2026-01-22 00:53:51.4355+00	ADJUST	MANUAL	\N	Stock inicial
433	2026-01-22 00:54:06.0796+00	OUT	SALE	168	Venta #168
434	2026-01-22 03:06:03.592373+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
435	2026-01-22 10:34:19.837944+00	ADJUST	MANUAL	\N	Stock inicial
436	2026-01-22 19:59:22.003148+00	OUT	SALE	169	Venta #169
437	2026-01-22 19:59:50.831199+00	OUT	SALE	170	Venta #170
438	2026-01-22 20:01:04.964063+00	OUT	SALE	171	Venta #171
439	2026-01-22 20:03:28.269913+00	ADJUST	MANUAL	\N	Stock inicial
440	2026-01-22 20:04:04.063324+00	OUT	SALE	172	Venta #172
441	2026-01-22 20:14:42.730875+00	OUT	SALE	173	Venta #173
442	2026-01-22 20:15:27.839319+00	OUT	SALE	174	Venta #174
443	2026-01-22 20:17:29.366298+00	OUT	SALE	175	Venta #175
444	2026-01-22 21:08:58.675648+00	ADJUST	MANUAL	\N	Stock inicial
445	2026-01-22 21:13:50.632181+00	ADJUST	MANUAL	\N	Stock inicial
446	2026-01-22 21:13:50.955492+00	ADJUST	MANUAL	\N	Stock inicial
447	2026-01-22 21:43:17.073142+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
448	2026-01-22 21:45:16.983337+00	OUT	SALE	176	Venta #176
449	2026-01-22 21:47:07.148126+00	ADJUST	MANUAL	\N	Stock inicial
450	2026-01-22 21:47:59.734158+00	OUT	SALE	177	Venta #177
451	2026-01-22 22:09:19.095949+00	OUT	SALE	178	Venta #178
452	2026-01-22 22:29:32.397014+00	OUT	SALE	179	Venta #179
453	2026-01-22 22:32:20.245103+00	OUT	SALE	180	Venta #180
454	2026-01-22 22:35:24.770025+00	ADJUST	MANUAL	\N	Stock inicial
455	2026-01-22 22:36:54.83641+00	OUT	SALE	181	Venta #181
456	2026-01-22 22:40:29.642733+00	ADJUST	MANUAL	\N	Stock inicial
457	2026-01-22 22:41:03.014098+00	ADJUST	MANUAL	\N	Stock inicial
458	2026-01-22 22:41:21.361052+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
459	2026-01-22 22:42:15.476525+00	OUT	SALE	182	Venta #182
460	2026-01-22 22:43:22.700384+00	OUT	SALE	183	Venta #183
461	2026-01-22 22:43:45.551922+00	OUT	SALE	184	Venta #184
462	2026-01-22 22:44:09.913005+00	OUT	SALE	185	Venta #185
463	2026-01-22 22:44:35.629445+00	OUT	SALE	186	Venta #186
464	2026-01-22 22:45:06.6167+00	OUT	SALE	187	Venta #187
465	2026-01-22 22:46:02.494016+00	OUT	SALE	188	Venta #188
466	2026-01-22 22:46:31.021046+00	OUT	SALE	189	Venta #189
467	2026-01-22 22:47:54.616058+00	ADJUST	MANUAL	\N	Stock inicial
468	2026-01-22 22:50:59.471137+00	OUT	SALE	190	Venta #190
469	2026-01-22 22:52:29.477025+00	ADJUST	MANUAL	\N	Stock inicial
470	2026-01-22 22:53:21.01078+00	ADJUST	MANUAL	\N	Stock inicial
471	2026-01-22 22:55:18.489789+00	ADJUST	MANUAL	\N	Stock inicial
472	2026-01-22 22:56:33.585256+00	OUT	SALE	191	Venta #191
473	2026-01-22 22:57:14.3391+00	ADJUST	MANUAL	\N	Stock inicial
474	2026-01-22 22:58:19.19117+00	ADJUST	MANUAL	\N	Stock inicial
475	2026-01-22 22:59:19.816934+00	OUT	SALE	192	Venta #192
476	2026-01-22 23:28:28.85046+00	OUT	SALE	193	Venta #193
477	2026-01-22 23:34:46.795017+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
478	2026-01-22 23:41:19.828448+00	ADJUST	MANUAL	\N	Stock inicial
479	2026-01-22 23:41:47.629202+00	OUT	SALE	194	Venta #194
480	2026-01-22 23:51:38.32168+00	ADJUST	MANUAL	\N	Stock inicial
481	2026-01-22 23:52:02.632174+00	OUT	SALE	195	Venta #195
482	2026-01-22 23:52:46.507062+00	ADJUST	MANUAL	\N	Stock inicial
483	2026-01-22 23:53:16.009415+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
484	2026-01-22 23:54:16.226069+00	ADJUST	MANUAL	\N	Stock inicial
485	2026-01-23 00:15:11.569924+00	ADJUST	MANUAL	\N	Stock inicial
486	2026-01-23 00:24:44.591287+00	IN	INVOICE	20	Compra - Boleta #2921
487	2026-01-23 00:26:44.880348+00	OUT	SALE	196	Venta #196
488	2026-01-23 01:00:04.60986+00	ADJUST	MANUAL	\N	Ajuste manual desde edición de producto
489	2026-01-23 01:00:28.902724+00	OUT	SALE	197	Venta #197
490	2026-01-23 01:01:44.855661+00	ADJUST	MANUAL	\N	Stock inicial
491	2026-01-23 01:02:08.868516+00	OUT	SALE	198	Venta #198
492	2026-01-23 01:03:06.901009+00	OUT	SALE	199	Venta #199
493	2026-01-23 01:03:53.144154+00	OUT	SALE	200	Venta #200
\.


--
-- Data for Name: stock_move_line; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.stock_move_line (id, stock_move_id, product_id, qty, uom_id, unit_cost) FROM stdin;
1	1	4	2.000	1	4254.0000
2	1	6	2.000	1	7576.0000
3	1	5	2.000	1	8916.0000
4	1	3	2.000	1	5373.0000
5	1	2	1.000	1	75052.0000
6	4	8	600.000	1	4.0000
7	4	9	600.000	1	5.0000
8	4	1	200.000	1	5.0000
9	4	10	200.000	1	85.0000
10	4	11	100.000	1	143.0000
11	4	12	200.000	1	216.0000
12	4	13	12.000	1	5260.0000
13	4	14	2.000	3	4429.0000
14	4	15	2.000	3	4796.0000
15	4	16	2.000	3	4274.0000
16	4	17	48.000	1	980.0000
17	4	18	500.000	1	45.0000
18	4	19	500.000	1	47.0000
19	4	20	500.000	1	60.0000
20	4	7	200.000	1	21.0000
21	5	22	6.000	1	1049.0000
22	5	21	1779.000	1	20.0000
23	5	23	20.000	1	1415.0000
24	5	24	5.000	1	5778.0000
25	5	25	5.000	1	5950.0000
26	5	26	60.000	1	486.0000
27	5	27	20.000	1	278.0000
28	5	28	20.000	1	126.0000
29	5	29	10.000	1	93.0000
30	5	30	10.000	5	1091.0000
31	5	31	2.000	5	6066.0000
32	5	32	5.000	1	357.0000
33	5	33	50.000	5	243.0000
34	5	34	25.000	5	364.0000
35	5	35	10.000	1	228.0000
36	5	36	20.000	1	223.0000
37	5	37	20.000	1	294.0000
38	5	38	20.000	1	294.0000
39	5	39	20.000	1	98.0000
40	5	40	20.000	1	871.0000
41	5	41	3.000	1	21533.0000
42	5	42	1.000	5	14656.0000
43	5	43	100.000	5	253.0000
44	5	44	20.000	1	1404.0000
45	5	45	10.000	1	841.0000
46	5	46	2.000	1	2430.0000
47	5	47	2.000	1	5283.0000
48	5	48	5.000	1	5158.0000
49	5	49	5.000	1	6389.0000
50	5	50	120.000	1	2983.0000
51	5	51	120.000	1	3460.0000
52	5	52	20.000	1	1072.0000
53	5	53	120.000	1	135.0000
54	5	54	20.000	1	739.0000
55	5	55	10.000	1	2406.0000
56	5	56	10.000	1	512.0000
57	5	57	2.000	1	17078.0000
58	5	58	40.000	1	563.0000
59	5	60	10.000	1	2834.0000
60	5	61	60.000	1	1001.0000
61	5	62	40.000	1	611.0000
62	5	63	10.000	1	1595.0000
63	9	4	1.000	1	\N
64	10	23	1.000	1	\N
65	10	4	1.000	1	\N
66	10	63	10.000	1	\N
67	11	61	-30.000	1	0.0000
68	11	62	-20.000	1	0.0000
69	12	50	-100.000	1	0.0000
70	12	51	-100.000	1	0.0000
71	12	61	30.000	1	0.0000
72	12	59	10.000	1	0.0000
73	13	64	20.000	1	887.0000
74	13	65	25.000	1	233.0000
75	13	69	50.000	1	1500.0000
76	13	70	5.000	1	4500.0000
77	14	71	6.000	1	1678.0000
78	15	66	1.000	1	40163.0000
79	15	68	12.000	1	4137.0000
80	15	67	12.000	1	2940.0000
81	16	72	4.000	1	9012.0000
82	16	73	2.000	1	8614.0000
83	16	74	4.000	1	10870.0000
84	16	75	4.000	1	14517.0000
85	17	78	4.000	1	1774.0000
86	17	79	15.000	1	669.0000
87	17	80	15.000	1	669.0000
88	17	81	15.000	1	669.0000
89	17	82	15.000	1	669.0000
90	17	83	15.000	1	669.0000
91	17	84	1.000	1	5277.0000
92	17	85	6.000	1	4731.0000
93	17	86	30.000	1	1534.0000
94	17	87	4.000	1	2395.0000
95	17	89	1.000	1	5575.0000
96	17	91	5.000	1	3856.0000
97	17	93	5.000	1	11942.0000
98	17	92	50.000	1	216.0000
99	17	90	50.000	1	699.0000
100	17	77	40.000	1	990.0000
101	18	82	2.000	1	\N
102	19	94	6.000	1	3730.0000
103	19	97	4.000	1	12725.0000
104	19	98	3.000	1	29997.0000
105	19	99	6.000	1	2690.0000
106	19	100	6.000	1	3169.0000
107	19	101	24.000	1	1498.0000
108	19	102	24.000	1	1871.0000
109	19	103	24.000	1	2822.0000
110	19	104	24.000	1	747.0000
111	19	106	10.000	1	1480.0000
112	19	105	7.000	1	4386.0000
113	20	107	3.000	1	6938.0000
114	20	108	2.000	1	14670.0000
115	21	112	5.000	1	1500.0000
116	21	111	10.000	1	500.0000
117	21	110	10.000	1	1000.0000
118	21	63	10.000	1	27.0000
119	22	101	1.000	1	\N
120	23	101	1.000	1	\N
121	24	133	1.000	1	4062.0000
122	24	132	1.000	1	4116.0000
123	24	129	1.000	1	4276.0000
124	24	131	1.000	1	4332.0000
125	24	130	1.000	1	5550.0000
126	24	136	2.000	6	3000.0000
127	24	134	5.000	6	2000.0000
128	24	135	4.000	6	1000.0000
129	25	101	1.000	1	\N
130	26	50	3.000	1	\N
131	27	61	2.000	1	\N
132	28	199	25.000	1	700.0000
133	28	82	25.000	1	700.0000
134	28	115	1.000	1	7000.0000
135	28	114	1.000	1	2500.0000
136	28	116	1.000	1	7000.0000
137	28	117	1.000	1	7000.0000
138	28	118	1.000	1	20000.0000
139	28	138	10.000	1	300.0000
140	28	137	10.000	1	300.0000
141	28	142	10.000	1	300.0000
142	28	141	10.000	1	3000.0000
143	28	140	10.000	1	3000.0000
144	28	125	1.000	1	5000.0000
145	28	120	1.000	1	5000.0000
146	28	124	1.000	1	5000.0000
147	28	119	1.000	1	5000.0000
148	28	123	1.000	1	5000.0000
149	28	122	1.000	1	7000.0000
150	28	121	1.000	1	5000.0000
151	28	128	1.000	1	5000.0000
152	28	127	1.000	1	5000.0000
153	28	126	1.000	1	5000.0000
154	28	143	1.000	1	17000.0000
155	28	144	1.000	1	3000.0000
156	28	45	20.000	1	500.0000
157	28	113	50.000	1	500.0000
158	28	64	20.000	1	500.0000
159	28	188	10.000	6	2000.0000
160	28	190	7.000	6	2000.0000
161	28	109	10.000	1	2000.0000
162	28	72	7.000	1	4000.0000
163	28	177	6.000	6	3700.0000
164	28	175	6.000	6	3000.0000
165	28	176	7.000	6	2000.0000
166	28	174	2.000	6	5000.0000
167	28	90	50.000	1	500.0000
168	28	157	6.000	6	3000.0000
169	28	150	6.000	6	2000.0000
170	28	147	2.000	7	10000.0000
171	28	151	2.000	6	3000.0000
172	28	152	2.000	6	5000.0000
173	28	148	1.000	7	1000.0000
174	28	71	6.000	1	1000.0000
175	28	191	1.000	1	10000.0000
176	28	163	1.000	1	10000.0000
177	28	164	1.000	1	10000.0000
178	28	145	50.000	5	100.0000
179	28	146	50.000	5	100.0000
180	28	170	10.000	1	100.0000
181	28	171	10.000	1	100.0000
182	28	172	10.000	1	100.0000
183	28	173	10.000	1	100.0000
184	28	166	10.000	1	100.0000
185	28	167	10.000	1	100.0000
186	28	168	10.000	1	100.0000
187	28	180	2.000	6	1000.0000
188	28	179	2.000	1	2500.0000
189	28	161	7.000	6	1000.0000
190	28	162	6.000	6	1000.0000
191	28	207	2.000	1	5000.0000
192	29	85	1.000	1	\N
193	30	208	5.000	1	1000.0000
194	30	209	3.000	1	1000.0000
195	30	156	1.000	8	1000.0000
196	30	155	1.000	7	1000.0000
197	30	210	2.000	1	1000.0000
198	30	211	4.000	1	465.0000
199	31	44	1.000	1	\N
200	32	215	50.000	1	0.0000
201	33	216	20.000	1	0.0000
202	34	215	8.000	1	\N
203	34	216	3.000	1	\N
204	35	214	50.000	5	0.0000
205	36	217	10.000	7	0.0000
206	37	217	1.000	7	\N
207	38	218	5.000	1	0.0000
208	39	219	50.000	1	0.0000
209	40	218	2.000	1	\N
210	40	219	4.000	1	\N
211	41	220	90.000	5	0.0000
212	42	200	50.000	1	0.0000
213	43	225	15.000	1	0.0000
214	44	224	100.000	5	0.0000
215	45	224	2.000	5	\N
216	45	225	1.000	1	\N
448	211	330	6.000	1	\N
217	46	226	5.000	1	0.0000
218	47	226	1.000	1	\N
219	48	77	-35.000	1	0.0000
220	49	228	5.000	1	0.0000
221	50	77	-5.000	1	0.0000
222	51	230	10.000	1	0.0000
223	52	230	1.000	1	\N
224	53	231	5.000	1	0.0000
225	54	189	2.000	1	0.0000
226	55	227	5.000	1	0.0000
227	56	227	1.000	1	\N
228	56	231	1.000	1	\N
229	57	232	4.000	1	0.0000
230	58	232	1.000	1	\N
231	59	233	10.000	1	0.0000
232	60	226	6.000	1	0.0000
233	61	234	5.000	1	0.0000
234	62	235	5.000	1	0.0000
235	63	221	2.000	1	4600.0000
236	63	222	3.000	1	2896.0000
237	63	186	6.000	1	539.0000
238	63	223	3.000	1	953.0000
239	63	227	5.000	1	8747.0000
240	63	229	5.000	1	1057.0000
241	63	77	5.000	1	1057.0000
242	63	236	40.000	5	1592.0000
243	63	212	100.000	5	1175.0000
244	63	237	2.000	1	2990.0000
245	63	238	2.000	1	2990.0000
246	63	239	2.000	1	8423.0000
247	63	240	2.000	1	2935.0000
248	64	241	20.000	5	0.0000
249	65	241	2.000	5	\N
250	66	242	7.000	1	0.0000
251	67	243	10.000	1	0.0000
252	68	244	20.000	1	0.0000
253	69	242	1.000	1	\N
254	69	243	1.000	1	\N
255	69	244	1.000	1	\N
256	70	158	26.000	1	0.0000
257	71	76	2.000	1	0.0000
258	72	85	1.000	1	\N
259	73	245	5.000	1	0.0000
260	74	246	5.000	1	0.0000
261	75	247	2.000	1	0.0000
262	76	248	5.000	1	0.0000
263	77	249	100.000	1	0.0000
264	78	250	100.000	1	0.0000
265	79	251	100.000	1	0.0000
266	80	252	100.000	1	0.0000
267	81	253	100.000	1	0.0000
268	82	254	50.000	1	0.0000
269	83	254	100.000	1	0.0000
270	84	245	1.000	1	\N
271	84	247	2.000	1	\N
272	84	250	2.000	1	\N
273	84	254	106.000	1	\N
274	85	255	1.000	1	0.0000
275	86	256	4.000	1	0.0000
276	87	257	20.000	1	0.0000
277	88	256	1.000	1	\N
278	88	257	1.000	1	\N
279	89	258	30.000	9	0.0000
280	90	259	200.000	1	0.0000
281	91	260	5.000	1	0.0000
282	92	261	100.000	1	0.0000
283	93	262	15.000	1	0.0000
284	94	261	5.000	1	\N
285	94	262	1.000	1	\N
286	95	58	1.000	1	\N
287	96	263	1.000	1	0.0000
288	97	264	15.000	1	0.0000
289	98	259	30.000	1	\N
290	98	260	1.000	1	\N
291	98	264	1.000	1	\N
292	99	265	100.000	1	0.0000
293	100	254	20.000	1	\N
294	100	265	10.000	1	\N
295	101	266	17.000	1	0.0000
296	102	267	10.000	1	0.0000
297	103	268	25.000	1	0.0000
298	104	162	1.000	6	\N
299	104	266	1.000	1	\N
300	104	267	1.000	1	\N
301	104	268	1.000	1	\N
302	105	103	1.000	1	\N
303	106	15	2.000	3	\N
304	107	269	500.000	1	0.0000
305	108	269	6.000	1	\N
306	109	270	300.000	1	0.0000
307	110	271	500.000	1	0.0000
308	111	109	1.000	1	\N
309	111	270	20.000	1	\N
310	111	271	20.000	1	\N
311	111	58	1.000	1	\N
312	111	84	1.000	1	\N
313	112	272	800.000	1	0.0000
314	113	273	8.000	6	0.0000
315	114	273	1.000	6	\N
316	114	58	1.000	1	\N
317	115	274	6.000	1	0.0000
318	116	274	1.000	1	\N
319	117	267	1.000	1	\N
320	118	275	10.000	1	0.0000
321	119	276	1000.000	5	0.0000
322	120	276	10.000	5	\N
323	121	277	25.000	1	0.0000
324	122	278	20.000	1	0.0000
325	123	279	1.000	1	0.0000
326	124	183	100.000	1	0.0000
327	125	182	100.000	1	0.0000
328	126	182	2.000	1	\N
329	126	183	2.000	1	\N
330	126	279	1.000	1	\N
331	127	280	6.000	1	0.0000
332	128	17	1.000	1	\N
333	128	280	1.000	1	\N
334	129	281	25.000	1	0.0000
335	130	282	1.000	1	0.0000
336	131	283	5.000	1	0.0000
337	132	284	3.000	1	0.0000
338	133	285	3.000	1	0.0000
339	134	286	2.000	1	0.0000
340	135	287	12.000	1	0.0000
341	136	277	2.000	1	\N
342	136	278	1.000	1	\N
343	137	275	1.000	1	\N
344	138	103	1.000	1	\N
345	138	284	1.000	1	\N
346	138	285	1.000	1	\N
347	138	286	1.000	1	\N
348	139	288	10.000	1	0.0000
349	140	289	1.000	1	0.0000
350	141	290	50.000	1	0.0000
351	142	291	100.000	1	0.0000
352	143	289	1.000	1	\N
353	143	290	1.000	1	\N
354	143	291	1.000	1	\N
355	144	292	50.000	1	0.0000
356	145	293	1000.000	1	0.0000
357	146	288	2.000	1	\N
358	146	292	4.000	1	\N
359	146	293	4.000	1	\N
360	147	294	50.000	5	0.0000
361	148	294	1.500	5	\N
362	149	295	6.000	1	0.0000
363	150	295	1.000	1	\N
364	151	296	1.000	1	0.0000
365	152	297	1.000	1	0.0000
366	153	298	1.000	1	0.0000
367	154	299	2.000	1	0.0000
368	155	300	5.000	1	0.0000
369	156	301	1000.000	1	0.0000
370	157	293	15.000	1	\N
371	157	299	1.000	1	\N
372	157	300	1.000	1	\N
373	157	301	15.000	1	\N
374	158	302	25.000	1	0.0000
375	159	251	4.000	1	\N
376	159	302	4.000	1	\N
377	160	165	3.000	1	0.0000
378	161	303	500.000	1	0.0000
379	162	304	50.000	5	0.0000
380	163	305	20.000	1	0.0000
381	164	303	2.000	1	\N
382	164	304	1.000	5	\N
383	164	305	3.000	1	\N
384	165	15	1100.000	3	0.0000
385	166	178	5.000	1	0.0000
386	167	192	5.000	1	0.0000
387	168	306	50.000	5	0.0000
388	169	306	10.000	5	\N
389	170	307	10.000	1	0.0000
390	171	308	10.000	1	0.0000
391	172	58	1.000	1	\N
392	173	309	90.000	1	0.0000
393	174	310	50.000	1	0.0000
394	175	309	15.000	1	\N
395	175	310	2.000	1	\N
396	175	9	20.000	1	\N
397	176	311	50.000	1	0.0000
398	177	52	1.000	1	\N
399	178	312	50.000	1	0.0000
400	179	312	14.000	1	\N
401	180	313	50.000	1	0.0000
402	181	200	4.000	1	\N
403	181	313	1.000	1	\N
404	182	314	25.000	1	0.0000
405	183	315	20.000	1	0.0000
406	184	316	20.000	1	0.0000
407	185	199	1.000	1	\N
408	185	240	1.000	1	\N
409	185	314	1.000	1	\N
410	185	315	2.000	1	\N
411	185	81	1.000	1	\N
412	186	317	100.000	5	0.0000
413	187	317	7.000	5	\N
414	188	8	30.000	1	\N
415	189	61	2.000	1	\N
416	190	273	1.000	6	\N
417	190	50	1.000	1	\N
418	190	93	1.000	1	\N
419	191	318	5.000	1	0.0000
420	192	318	1.000	1	\N
421	192	82	5.000	1	\N
422	192	99	1.000	1	\N
423	193	319	2.000	1	0.0000
424	194	320	10.000	1	0.0000
425	195	321	4.000	1	0.0000
426	196	103	1.000	1	\N
427	196	319	1.000	1	\N
428	196	320	1.000	1	\N
429	197	321	1.000	1	\N
430	198	322	20.000	1	0.0000
431	199	103	1.000	1	\N
432	199	322	1.000	1	\N
433	199	58	1.000	1	\N
434	200	323	50.000	5	0.0000
435	201	306	12.500	5	\N
436	202	324	10.000	1	0.0000
437	203	325	3.000	1	0.0000
438	204	326	50.000	1	0.0000
439	205	327	100.000	1	0.0000
440	206	328	4.000	5	0.0000
441	207	329	10.000	1	0.0000
442	208	329	-5.000	1	0.0000
443	209	329	4.000	1	\N
444	210	330	100.000	1	0.0000
445	211	324	1.000	1	\N
446	211	325	1.000	1	\N
447	211	326	6.000	1	\N
449	212	331	10.000	1	0.0000
450	213	1	2.000	1	\N
451	214	331	1.000	1	\N
452	215	1	1.000	1	\N
453	216	339	5.000	1	0.0000
454	217	215	1.000	1	\N
455	217	339	1.000	1	\N
456	218	340	100.000	1	0.0000
457	219	340	4.000	1	\N
458	220	341	9.000	1	0.0000
459	221	17	1.000	1	\N
460	221	212	7.000	5	\N
461	221	280	1.000	1	\N
462	221	294	25.000	5	\N
463	222	113	2.000	1	\N
464	223	201	1000.000	1	0.0000
465	224	202	350.000	1	0.0000
466	225	202	4.000	1	\N
467	225	303	4.000	1	\N
468	226	203	150.000	1	0.0000
469	227	200	2.000	1	\N
470	227	203	100.000	1	\N
471	227	212	10.000	5	\N
472	227	69	1.000	1	\N
473	228	305	3.000	1	\N
474	229	342	4.000	10	0.0000
475	230	342	1.000	10	\N
476	231	343	100.000	1	0.0000
477	232	11	6.000	1	\N
478	232	293	6.000	1	\N
479	232	343	6.000	1	\N
480	233	345	3.000	1	0.0000
481	234	346	20.000	11	0.0000
482	235	345	1.000	1	\N
483	235	346	2.000	11	\N
484	236	186	1.000	1	\N
485	237	347	1.000	1	0.0000
486	238	347	1.000	1	\N
487	239	348	1.000	1	0.0000
488	240	349	1.000	1	0.0000
489	241	349	1.000	1	\N
490	242	350	2.000	1	0.0000
491	243	350	1.000	1	\N
492	244	351	1000.000	5	0.0000
493	245	352	50.000	1	0.0000
494	246	351	7.000	5	\N
495	246	352	7.000	1	\N
496	246	58	1.000	1	\N
497	247	353	1.000	1	0.0000
498	248	269	1.000	1	\N
499	248	353	1.000	1	\N
500	249	354	5.000	1	0.0000
501	250	71	1.000	1	\N
502	251	187	50.000	5	0.0000
503	252	187	30.000	5	\N
504	252	280	1.000	1	\N
505	253	355	100.000	5	0.0000
506	254	356	100.000	5	0.0000
507	255	204	330.000	1	0.0000
508	256	204	100.000	1	\N
509	257	113	1.000	1	\N
510	258	357	15.000	1	0.0000
511	259	357	2.000	1	\N
512	260	358	5.000	1	0.0000
513	261	358	1.000	1	\N
514	262	153	100.000	1	0.0000
515	263	154	100.000	1	0.0000
516	264	153	5.000	1	\N
517	264	286	1.000	1	\N
518	265	153	10.000	1	\N
519	266	359	100.000	5	0.0000
520	267	359	4.000	5	\N
521	268	276	3.000	5	\N
522	269	360	100.000	5	0.0000
523	270	314	2.000	1	\N
524	270	360	4.000	5	\N
525	271	17	1.000	1	\N
526	271	314	2.000	1	\N
527	271	82	2.000	1	\N
528	272	361	4.000	1	0.0000
529	273	362	1.000	1	0.0000
530	274	363	3.000	1	0.0000
531	275	364	100.000	1	0.0000
532	276	364	8.000	1	\N
533	277	365	2.000	1	0.0000
534	278	58	1.000	1	\N
535	279	366	100.000	1	0.0000
536	280	366	3.000	1	\N
537	281	367	5.000	1	0.0000
538	282	368	4.000	1	0.0000
539	283	368	2.000	1	\N
540	284	369	1.000	1	0.0000
541	285	370	4.000	1	0.0000
542	286	371	7.000	1	0.0000
543	287	370	1.000	1	\N
544	287	371	1.000	1	\N
545	288	372	4.000	1	0.0000
546	289	373	11.000	1	0.0000
547	290	373	1.000	1	\N
548	291	374	150.000	5	0.0000
549	292	376	6.000	1	0.0000
550	293	376	2.000	1	\N
551	294	377	2.000	1	0.0000
552	295	378	1.000	1	0.0000
553	296	381	1.000	1	0.0000
554	297	382	50.000	1	0.0000
555	298	383	1.000	1	0.0000
556	299	385	1.000	1	0.0000
557	300	344	20.000	1	830.0000
558	300	375	5.000	1	3695.0000
559	300	377	3.000	1	3306.0000
560	300	378	4.000	1	2692.0000
561	300	379	5.000	1	3033.0000
562	300	282	24.000	1	845.0000
563	300	383	4.000	1	10485.0000
564	300	384	2.000	1	7409.0000
565	300	386	2.000	1	5031.0000
566	300	199	15.000	1	713.0000
567	300	83	15.000	1	713.0000
568	300	82	15.000	1	713.0000
569	300	81	15.000	1	713.0000
570	300	387	5.000	1	1875.0000
571	300	388	5.000	1	2260.0000
572	300	389	5.000	1	1875.0000
573	300	85	12.000	1	5299.0000
574	300	390	18.000	9	1597.0000
575	300	391	2.000	1	50000.0000
576	300	392	21.000	1	2000.0000
577	300	393	10.000	11	1065.0000
578	301	100	1.000	1	\N
579	302	284	1.000	1	\N
580	303	394	6.000	1	0.0000
581	304	394	1.000	1	\N
582	305	395	5.000	1	0.0000
583	306	303	4.000	1	\N
584	306	305	2.000	1	\N
585	307	193	10.000	1	0.0000
586	308	193	1.000	1	\N
587	308	50	1.000	1	\N
588	309	396	1000.000	1	0.0000
589	310	397	4.000	12	0.0000
590	311	398	8.000	12	0.0000
591	312	399	7.000	12	0.0000
592	313	396	10.000	1	\N
593	313	397	1.000	12	\N
594	314	400	1.000	1	0.0000
595	315	200	2.000	1	\N
596	315	212	15.000	5	\N
597	315	273	1.000	6	\N
598	315	400	1.000	1	\N
599	316	401	1.000	1	0.0000
600	317	280	1.000	1	\N
601	317	401	1.000	1	\N
602	318	402	4.000	1	0.0000
603	319	402	1.000	1	\N
604	320	205	850.000	1	0.0000
605	321	206	1500.000	1	0.0000
606	322	206	1.000	1	\N
607	323	184	100.000	1	0.0000
608	324	185	100.000	1	0.0000
609	325	181	100.000	1	0.0000
610	326	184	6.000	1	\N
611	326	254	6.000	1	\N
612	327	359	10.000	5	\N
613	328	205	10.000	1	\N
614	329	403	100.000	5	0.0000
615	330	403	5.000	5	\N
616	331	404	2.000	1	0.0000
617	332	404	2.000	1	\N
618	333	159	7.000	5	0.0000
619	334	160	5.000	5	0.0000
620	335	405	2.000	7	0.0000
621	336	406	3.000	7	0.0000
622	337	407	2.000	7	0.0000
623	338	407	1.000	7	\N
624	339	408	2.000	1	0.0000
625	340	408	1.000	1	\N
626	341	409	3.000	5	0.0000
627	342	410	4.000	1	0.0000
628	343	409	2.000	5	\N
629	343	410	1.000	1	\N
630	344	195	10.000	1	0.0000
631	345	185	4.000	1	\N
632	345	195	1.000	1	\N
633	345	306	2.000	5	\N
634	346	413	7.000	1	0.0000
635	347	414	1.000	1	0.0000
636	348	371	1.000	1	\N
637	349	418	2.000	1	0.0000
638	350	418	2.000	1	\N
639	351	420	9.000	1	0.0000
640	352	421	200.000	1	0.0000
641	353	250	4.000	1	\N
642	353	420	2.000	1	\N
643	353	421	4.000	1	\N
644	354	422	15.000	1	0.0000
645	355	423	500.000	1	0.0000
646	356	253	4.000	1	\N
647	356	423	4.000	1	\N
648	357	411	2.000	1	44520.0000
649	357	408	2.000	1	15085.0000
650	357	382	100.000	1	374.0000
651	357	416	1000.000	1	6.0000
652	357	417	2.000	12	3460.0000
653	357	419	5.000	1	1376.0000
654	357	424	1.000	1	126000.0000
655	357	425	5.000	1	2535.0000
656	357	426	3.000	1	5931.0000
657	358	149	2.000	1	0.0000
658	359	380	5.000	1	0.0000
659	360	353	20.000	1	0.0000
660	361	96	1.000	1	0.0000
661	362	286	2.000	1	0.0000
662	363	95	2.000	1	0.0000
663	364	194	10.000	1	0.0000
664	365	198	10.000	1	0.0000
665	366	197	10.000	1	0.0000
666	367	196	10.000	1	0.0000
667	368	88	3.000	1	0.0000
668	369	415	100.000	1	0.0000
669	370	174	1.000	6	\N
670	371	412	5.000	1	0.0000
671	372	213	50.000	5	0.0000
672	373	85	12.000	1	3249.0000
673	374	427	10.000	1	0.0000
674	375	427	1.000	1	\N
675	376	283	1.000	1	\N
676	377	154	4.000	1	\N
677	378	146	3.500	5	\N
678	379	272	50.000	1	\N
679	380	428	13.000	1	0.0000
680	381	428	1.000	1	\N
681	382	113	1.000	1	\N
682	382	90	1.000	1	\N
683	383	62	1.000	1	\N
684	384	429	1.000	1	0.0000
685	385	142	1.000	1	\N
686	385	181	20.000	1	\N
687	385	211	1.000	1	\N
688	385	302	20.000	1	\N
689	385	317	6.000	5	\N
690	385	429	1.000	1	\N
691	386	346	3.000	11	\N
692	386	76	1.000	1	\N
693	387	90	3.000	1	\N
694	388	430	4.000	1	0.0000
695	389	430	1.000	1	\N
696	390	431	10.000	1	0.0000
697	391	83	5.000	1	\N
698	392	431	1.000	1	\N
699	393	205	2.000	1	\N
700	394	102	1.000	1	\N
701	394	82	1.000	1	\N
702	395	187	7.000	5	\N
703	396	199	2.000	1	\N
704	396	313	2.000	1	\N
705	397	432	10.000	1	0.0000
706	398	432	1.000	1	\N
707	399	24	1.000	1	\N
708	400	202	4.000	1	\N
709	400	85	2.000	1	\N
710	401	433	9.000	1	0.0000
711	402	157	1.000	6	\N
712	403	17	1.000	1	\N
713	403	1	2.000	1	\N
714	403	305	3.000	1	\N
715	404	216	3.000	1	\N
716	404	342	1.000	10	\N
717	405	434	7.000	1	0.0000
718	406	435	2.000	1	0.0000
719	407	436	6.000	1	0.0000
720	408	437	8.000	1	0.0000
721	409	438	30.000	1	0.0000
722	410	439	50.000	1	0.0000
723	411	440	20.000	1	0.0000
724	412	440	2.000	1	\N
725	413	104	1.000	1	\N
726	414	441	50.000	1	0.0000
727	415	442	14.000	1	0.0000
728	416	248	2.000	1	\N
729	416	441	2.000	1	\N
730	416	442	1.000	1	\N
731	417	158	1.000	1	\N
732	417	22	1.000	1	\N
733	418	443	10.000	1	0.0000
734	419	443	1.000	1	\N
735	420	153	3.000	1	\N
736	420	156	1.000	8	\N
737	420	223	1.000	1	\N
738	421	393	1.000	11	\N
739	422	444	4.000	1	0.0000
740	423	444	1.000	1	\N
741	424	446	1.000	1	0.0000
742	425	446	1.000	1	\N
743	426	448	2.000	1	0.0000
744	427	447	1.000	1	0.0000
745	428	454	9.000	1	0.0000
746	429	437	20.000	1	537.0000
747	429	438	20.000	1	516.0000
748	429	439	200.000	1	83.0000
749	429	58	50.000	1	563.0000
750	429	432	50.000	1	933.0000
751	429	203	1000.000	1	28.0000
752	429	204	1000.000	1	36.0000
753	429	61	50.000	1	814.0000
754	429	45	10.000	1	1138.0000
755	429	445	20.000	1	516.0000
756	429	447	10.000	1	1772.0000
757	429	448	10.000	1	1027.0000
758	429	449	10.000	1	2007.0000
759	429	450	10.000	1	1603.0000
760	429	451	10.000	1	4592.0000
761	429	452	4.000	1	10900.0000
762	429	453	1.000	1	5555.0000
763	429	454	4.000	1	1500.0000
764	429	455	1.000	1	6000.0000
765	430	456	7.000	1	0.0000
766	431	154	5.000	1	\N
767	431	456	1.000	1	\N
768	432	457	7.000	1	0.0000
769	433	457	1.000	1	\N
770	434	21	-1769.000	1	0.0000
771	435	458	22.000	1	0.0000
772	436	160	4.000	5	\N
773	437	159	1.000	5	\N
774	438	154	2.000	1	\N
775	439	459	10.000	1	0.0000
776	440	459	3.000	1	\N
777	441	441	2.000	1	\N
778	442	102	1.000	1	\N
779	443	353	6.000	1	\N
780	444	460	9.000	1	0.0000
781	445	461	10.000	1	0.0000
782	446	462	10.000	1	0.0000
783	447	462	-10.000	1	0.0000
784	448	460	1.000	1	\N
785	448	461	1.000	1	\N
786	449	463	10.000	1	0.0000
787	450	463	2.000	1	\N
788	451	101	1.000	1	\N
789	451	184	15.000	1	\N
790	451	188	1.000	6	\N
791	451	205	83.000	1	\N
792	452	251	10.000	1	\N
793	453	200	1.000	1	\N
794	454	464	150.000	1	0.0000
795	455	181	43.000	1	\N
796	455	464	107.000	1	\N
797	456	465	2.000	1	0.0000
798	457	466	2.000	1	0.0000
799	458	465	1.000	1	0.0000
800	459	357	1.000	1	\N
801	459	465	1.000	1	\N
802	460	50	1.000	1	\N
803	461	276	2.000	5	\N
804	462	113	4.000	1	\N
805	463	102	1.000	1	\N
806	464	303	2.000	1	\N
807	465	286	1.000	1	\N
808	465	378	2.000	1	\N
809	466	69	2.000	1	\N
810	467	467	50.000	1	0.0000
811	468	254	15.000	1	\N
812	468	467	2.000	1	\N
813	469	468	10.000	5	0.0000
814	470	469	10.000	5	0.0000
815	471	470	10.000	5	0.0000
816	472	469	1.000	5	\N
817	473	471	10.000	1	0.0000
818	474	472	1.000	1	0.0000
819	475	471	1.000	1	\N
820	476	313	1.000	1	\N
821	476	393	1.000	11	\N
822	477	460	-8.000	1	0.0000
823	478	473	1.000	1	0.0000
824	479	473	1.000	1	\N
825	480	474	9.000	1	0.0000
826	481	474	1.000	1	\N
827	482	475	3.000	1	0.0000
828	483	475	1.000	1	0.0000
829	484	476	1.000	1	0.0000
830	485	481	5.000	1	0.0000
831	486	477	7.000	1	2295.0000
832	486	478	10.000	1	2837.0000
833	486	479	3.000	1	3921.0000
834	486	305	50.000	1	111.0000
835	486	247	50.000	1	134.0000
836	486	347	20.000	1	40.0000
837	486	482	10.000	1	2000.0000
838	486	460	10.000	1	1000.0000
839	486	480	10.000	1	1000.0000
840	487	153	2.000	1	\N
841	488	160	3.000	5	0.0000
842	489	160	4.000	5	\N
843	490	483	10.000	1	0.0000
844	491	374	25.000	5	\N
845	491	483	1.000	1	\N
846	492	390	1.000	9	\N
847	493	200	2.000	1	\N
848	493	460	1.000	1	\N
\.


--
-- Data for Name: supplier; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.supplier (id, name, tax_id, phone, email, notes, created_at) FROM stdin;
1	Figueroa 533 S. A. (Abramaq)	30-71464381-5	2494382306	info@abramaq.com.ar	\N	2026-01-13 21:16:17.761349+00
2	MATELEC	\N	\N	\N	\N	2026-01-13 23:37:35.068751+00
3	UNIPEL	\N	\N	\N	\N	2026-01-14 22:19:08.288001+00
4	LA ROSA	20-29549156-7	2494327122	\N	\N	2026-01-14 23:24:24.052753+00
5	ACUARELLA	23-251470049	2227537955	ariel.marion@hotmail.com	\N	2026-01-16 00:11:32.84064+00
6	DE PILATO	\N	\N	\N	\N	2026-01-16 21:31:41.633708+00
7	PAULO OLGUIN	\N	2494616670	\N	\N	2026-01-17 20:49:05.581307+00
8	VELOZ CRISTIAN	20-22933168-0	2494282055	ferreline_tandil@hotmail.com	\N	2026-01-20 23:05:44.160391+00
\.


--
-- Data for Name: uom; Type: TABLE DATA; Schema: public; Owner: ferreteria
--

COPY public.uom (id, name, symbol, created_at) FROM stdin;
1	Unidad	unidad	2026-01-13 21:08:51.603407+00
2	kilogramo	kg	2026-01-13 23:14:31.450078+00
3	gramos	100 grs	2026-01-13 23:16:14.177082+00
5	METRO	M	2026-01-13 23:49:19.605459+00
6	CAJA	CJ	2026-01-16 23:20:40.69139+00
7	LATA	LT	2026-01-17 13:13:57.011007+00
8	BIDON	B	2026-01-17 13:33:05.60827+00
9	SOBRE	S	2026-01-18 13:05:09.620134+00
10	BOLSA DE 1/2	1/2 KG	2026-01-19 21:02:21.806551+00
11	PAR	X2	2026-01-19 21:16:19.097521+00
12	BLISTER	BL	2026-01-20 20:32:22.937249+00
\.


--
-- Name: category_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.category_id_seq', 12, true);


--
-- Name: finance_ledger_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.finance_ledger_id_seq', 200, true);


--
-- Name: missing_product_request_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.missing_product_request_id_seq', 1, true);


--
-- Name: product_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.product_id_seq', 483, true);


--
-- Name: product_uom_price_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.product_uom_price_id_seq', 541, true);


--
-- Name: purchase_invoice_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.purchase_invoice_id_seq', 20, true);


--
-- Name: purchase_invoice_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.purchase_invoice_line_id_seq', 372, true);


--
-- Name: purchase_invoice_payment_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.purchase_invoice_payment_id_seq', 2, true);


--
-- Name: quote_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.quote_id_seq', 1, true);


--
-- Name: quote_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.quote_line_id_seq', 1, true);


--
-- Name: sale_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.sale_id_seq', 200, true);


--
-- Name: sale_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.sale_line_id_seq', 324, true);


--
-- Name: stock_move_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.stock_move_id_seq', 493, true);


--
-- Name: stock_move_line_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.stock_move_line_id_seq', 848, true);


--
-- Name: supplier_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.supplier_id_seq', 8, true);


--
-- Name: uom_id_seq; Type: SEQUENCE SET; Schema: public; Owner: ferreteria
--

SELECT pg_catalog.setval('public.uom_id_seq', 12, true);


--
-- Name: category category_name_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_name_key UNIQUE (name);


--
-- Name: category category_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.category
    ADD CONSTRAINT category_pkey PRIMARY KEY (id);


--
-- Name: finance_ledger finance_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.finance_ledger
    ADD CONSTRAINT finance_ledger_pkey PRIMARY KEY (id);


--
-- Name: missing_product_request missing_product_request_normalized_name_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.missing_product_request
    ADD CONSTRAINT missing_product_request_normalized_name_key UNIQUE (normalized_name);


--
-- Name: missing_product_request missing_product_request_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.missing_product_request
    ADD CONSTRAINT missing_product_request_pkey PRIMARY KEY (id);


--
-- Name: product product_barcode_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_barcode_key UNIQUE (barcode);


--
-- Name: product product_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_pkey PRIMARY KEY (id);


--
-- Name: product product_sku_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_sku_key UNIQUE (sku);


--
-- Name: product_stock product_stock_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_stock
    ADD CONSTRAINT product_stock_pkey PRIMARY KEY (product_id);


--
-- Name: product_uom_price product_uom_price_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_uom_price
    ADD CONSTRAINT product_uom_price_pkey PRIMARY KEY (id);


--
-- Name: purchase_invoice_line purchase_invoice_line_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_line
    ADD CONSTRAINT purchase_invoice_line_pkey PRIMARY KEY (id);


--
-- Name: purchase_invoice_payment purchase_invoice_payment_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_payment
    ADD CONSTRAINT purchase_invoice_payment_pkey PRIMARY KEY (id);


--
-- Name: purchase_invoice purchase_invoice_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice
    ADD CONSTRAINT purchase_invoice_pkey PRIMARY KEY (id);


--
-- Name: quote_line quote_line_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote_line
    ADD CONSTRAINT quote_line_pkey PRIMARY KEY (id);


--
-- Name: quote quote_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote
    ADD CONSTRAINT quote_pkey PRIMARY KEY (id);


--
-- Name: quote quote_quote_number_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote
    ADD CONSTRAINT quote_quote_number_key UNIQUE (quote_number);


--
-- Name: quote quote_sale_id_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote
    ADD CONSTRAINT quote_sale_id_key UNIQUE (sale_id);


--
-- Name: sale_line sale_line_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale_line
    ADD CONSTRAINT sale_line_pkey PRIMARY KEY (id);


--
-- Name: sale sale_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale
    ADD CONSTRAINT sale_pkey PRIMARY KEY (id);


--
-- Name: stock_move_line stock_move_line_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move_line
    ADD CONSTRAINT stock_move_line_pkey PRIMARY KEY (id);


--
-- Name: stock_move stock_move_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move
    ADD CONSTRAINT stock_move_pkey PRIMARY KEY (id);


--
-- Name: purchase_invoice supplier_invoice_number_uniq; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice
    ADD CONSTRAINT supplier_invoice_number_uniq UNIQUE (supplier_id, invoice_number);


--
-- Name: supplier supplier_name_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.supplier
    ADD CONSTRAINT supplier_name_key UNIQUE (name);


--
-- Name: supplier supplier_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.supplier
    ADD CONSTRAINT supplier_pkey PRIMARY KEY (id);


--
-- Name: uom uom_name_key; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.uom
    ADD CONSTRAINT uom_name_key UNIQUE (name);


--
-- Name: uom uom_pkey; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.uom
    ADD CONSTRAINT uom_pkey PRIMARY KEY (id);


--
-- Name: product_uom_price uq_product_uom; Type: CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_uom_price
    ADD CONSTRAINT uq_product_uom UNIQUE (product_id, uom_id);


--
-- Name: idx_finance_ledger_payment_method; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_finance_ledger_payment_method ON public.finance_ledger USING btree (payment_method);


--
-- Name: idx_invoice_date; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_date ON public.purchase_invoice USING btree (invoice_date);


--
-- Name: idx_invoice_due_date; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_due_date ON public.purchase_invoice USING btree (due_date);


--
-- Name: idx_invoice_line_invoice; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_line_invoice ON public.purchase_invoice_line USING btree (invoice_id);


--
-- Name: idx_invoice_line_product; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_line_product ON public.purchase_invoice_line USING btree (product_id);


--
-- Name: idx_invoice_payment_invoice_id; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_payment_invoice_id ON public.purchase_invoice_payment USING btree (invoice_id);


--
-- Name: idx_invoice_payment_paid_at; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_payment_paid_at ON public.purchase_invoice_payment USING btree (paid_at);


--
-- Name: idx_invoice_pending_supplier; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_pending_supplier ON public.purchase_invoice USING btree (supplier_id) WHERE (status = 'PENDING'::public.invoice_status);


--
-- Name: idx_invoice_status; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_status ON public.purchase_invoice USING btree (status);


--
-- Name: idx_invoice_supplier; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_invoice_supplier ON public.purchase_invoice USING btree (supplier_id);


--
-- Name: idx_ledger_datetime; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_ledger_datetime ON public.finance_ledger USING btree (datetime DESC);


--
-- Name: idx_ledger_ref; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_ledger_ref ON public.finance_ledger USING btree (reference_type, reference_id);


--
-- Name: idx_ledger_type; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_ledger_type ON public.finance_ledger USING btree (type);


--
-- Name: idx_missing_product_count_desc; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_missing_product_count_desc ON public.missing_product_request USING btree (request_count DESC);


--
-- Name: idx_missing_product_last_requested_at; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_missing_product_last_requested_at ON public.missing_product_request USING btree (last_requested_at DESC);


--
-- Name: idx_missing_product_status; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_missing_product_status ON public.missing_product_request USING btree (status);


--
-- Name: idx_product_active; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_active ON public.product USING btree (active);


--
-- Name: idx_product_category; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_category ON public.product USING btree (category_id);


--
-- Name: idx_product_min_stock_qty; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_min_stock_qty ON public.product USING btree (min_stock_qty);


--
-- Name: idx_product_name; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_name ON public.product USING btree (name);


--
-- Name: idx_product_uom; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_uom ON public.product USING btree (uom_id);


--
-- Name: idx_product_uom_price_is_base; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_uom_price_is_base ON public.product_uom_price USING btree (product_id, is_base) WHERE (is_base = true);


--
-- Name: idx_product_uom_price_product_id; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_uom_price_product_id ON public.product_uom_price USING btree (product_id);


--
-- Name: idx_product_uom_price_uom_id; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_product_uom_price_uom_id ON public.product_uom_price USING btree (uom_id);


--
-- Name: idx_quote_customer_name; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_customer_name ON public.quote USING btree (customer_name);


--
-- Name: idx_quote_customer_phone; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_customer_phone ON public.quote USING btree (customer_phone);


--
-- Name: idx_quote_line_product_id; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_line_product_id ON public.quote_line USING btree (product_id);


--
-- Name: idx_quote_line_quote_id; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_line_quote_id ON public.quote_line USING btree (quote_id);


--
-- Name: idx_quote_number; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_number ON public.quote USING btree (quote_number);


--
-- Name: idx_quote_sale_id; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_sale_id ON public.quote USING btree (sale_id);


--
-- Name: idx_quote_status_issued; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_status_issued ON public.quote USING btree (status, issued_at DESC);


--
-- Name: idx_quote_valid_until; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_quote_valid_until ON public.quote USING btree (valid_until);


--
-- Name: idx_sale_datetime; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_sale_datetime ON public.sale USING btree (datetime DESC);


--
-- Name: idx_sale_line_product; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_sale_line_product ON public.sale_line USING btree (product_id);


--
-- Name: idx_sale_line_sale; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_sale_line_sale ON public.sale_line USING btree (sale_id);


--
-- Name: idx_sale_status; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_sale_status ON public.sale USING btree (status);


--
-- Name: idx_stock_move_date; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_stock_move_date ON public.stock_move USING btree (date DESC);


--
-- Name: idx_stock_move_line_move; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_stock_move_line_move ON public.stock_move_line USING btree (stock_move_id);


--
-- Name: idx_stock_move_line_prod; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_stock_move_line_prod ON public.stock_move_line USING btree (product_id);


--
-- Name: idx_stock_move_ref; Type: INDEX; Schema: public; Owner: ferreteria
--

CREATE INDEX idx_stock_move_ref ON public.stock_move USING btree (reference_type, reference_id);


--
-- Name: missing_product_request missing_product_set_updated_at; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER missing_product_set_updated_at BEFORE UPDATE ON public.missing_product_request FOR EACH ROW EXECUTE FUNCTION public.trg_missing_product_set_updated_at();


--
-- Name: product product_init_stock; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER product_init_stock AFTER INSERT ON public.product FOR EACH ROW EXECUTE FUNCTION public.trg_product_init_stock();


--
-- Name: product product_set_updated_at; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER product_set_updated_at BEFORE UPDATE ON public.product FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: quote quote_set_updated_at; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER quote_set_updated_at BEFORE UPDATE ON public.quote FOR EACH ROW EXECUTE FUNCTION public.trg_quote_set_updated_at();


--
-- Name: stock_move_line stock_move_line_after_del; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER stock_move_line_after_del AFTER DELETE ON public.stock_move_line FOR EACH ROW EXECUTE FUNCTION public.trg_stock_move_line_after_del();


--
-- Name: stock_move_line stock_move_line_after_ins; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER stock_move_line_after_ins AFTER INSERT ON public.stock_move_line FOR EACH ROW EXECUTE FUNCTION public.trg_stock_move_line_after_ins();


--
-- Name: product_uom_price trg_check_single_base_uom; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE TRIGGER trg_check_single_base_uom BEFORE INSERT OR UPDATE ON public.product_uom_price FOR EACH ROW EXECUTE FUNCTION public.check_single_base_uom();


--
-- Name: purchase_invoice trg_invoice_has_lines; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE CONSTRAINT TRIGGER trg_invoice_has_lines AFTER INSERT OR UPDATE ON public.purchase_invoice DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.chk_invoice_has_lines();


--
-- Name: purchase_invoice trg_invoice_total_matches_lines; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE CONSTRAINT TRIGGER trg_invoice_total_matches_lines AFTER INSERT OR UPDATE ON public.purchase_invoice DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.chk_invoice_total_matches_lines();


--
-- Name: sale trg_sale_has_lines; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE CONSTRAINT TRIGGER trg_sale_has_lines AFTER INSERT OR UPDATE ON public.sale DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.chk_sale_has_lines();


--
-- Name: sale trg_sale_total_matches_lines; Type: TRIGGER; Schema: public; Owner: ferreteria
--

CREATE CONSTRAINT TRIGGER trg_sale_total_matches_lines AFTER INSERT OR UPDATE ON public.sale DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION public.chk_sale_total_matches_lines();


--
-- Name: purchase_invoice_payment fk_invoice_payment_invoice; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_payment
    ADD CONSTRAINT fk_invoice_payment_invoice FOREIGN KEY (invoice_id) REFERENCES public.purchase_invoice(id) ON DELETE CASCADE;


--
-- Name: product_uom_price fk_product_uom_price_product; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_uom_price
    ADD CONSTRAINT fk_product_uom_price_product FOREIGN KEY (product_id) REFERENCES public.product(id) ON DELETE CASCADE;


--
-- Name: product_uom_price fk_product_uom_price_uom; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_uom_price
    ADD CONSTRAINT fk_product_uom_price_uom FOREIGN KEY (uom_id) REFERENCES public.uom(id);


--
-- Name: sale_line fk_sale_line_uom; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale_line
    ADD CONSTRAINT fk_sale_line_uom FOREIGN KEY (uom_id) REFERENCES public.uom(id);


--
-- Name: product product_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.category(id) ON UPDATE RESTRICT ON DELETE SET NULL;


--
-- Name: product_stock product_stock_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product_stock
    ADD CONSTRAINT product_stock_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id) ON DELETE CASCADE;


--
-- Name: product product_uom_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_uom_id_fkey FOREIGN KEY (uom_id) REFERENCES public.uom(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: purchase_invoice_line purchase_invoice_line_invoice_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_line
    ADD CONSTRAINT purchase_invoice_line_invoice_id_fkey FOREIGN KEY (invoice_id) REFERENCES public.purchase_invoice(id) ON UPDATE RESTRICT ON DELETE CASCADE;


--
-- Name: purchase_invoice_line purchase_invoice_line_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice_line
    ADD CONSTRAINT purchase_invoice_line_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: purchase_invoice purchase_invoice_supplier_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.purchase_invoice
    ADD CONSTRAINT purchase_invoice_supplier_id_fkey FOREIGN KEY (supplier_id) REFERENCES public.supplier(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: quote_line quote_line_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote_line
    ADD CONSTRAINT quote_line_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: quote_line quote_line_quote_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote_line
    ADD CONSTRAINT quote_line_quote_id_fkey FOREIGN KEY (quote_id) REFERENCES public.quote(id) ON UPDATE RESTRICT ON DELETE CASCADE;


--
-- Name: quote quote_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.quote
    ADD CONSTRAINT quote_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sale(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: sale_line sale_line_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale_line
    ADD CONSTRAINT sale_line_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: sale_line sale_line_sale_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.sale_line
    ADD CONSTRAINT sale_line_sale_id_fkey FOREIGN KEY (sale_id) REFERENCES public.sale(id) ON UPDATE RESTRICT ON DELETE CASCADE;


--
-- Name: stock_move_line stock_move_line_product_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move_line
    ADD CONSTRAINT stock_move_line_product_id_fkey FOREIGN KEY (product_id) REFERENCES public.product(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- Name: stock_move_line stock_move_line_stock_move_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move_line
    ADD CONSTRAINT stock_move_line_stock_move_id_fkey FOREIGN KEY (stock_move_id) REFERENCES public.stock_move(id) ON UPDATE RESTRICT ON DELETE CASCADE;


--
-- Name: stock_move_line stock_move_line_uom_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: ferreteria
--

ALTER TABLE ONLY public.stock_move_line
    ADD CONSTRAINT stock_move_line_uom_id_fkey FOREIGN KEY (uom_id) REFERENCES public.uom(id) ON UPDATE RESTRICT ON DELETE RESTRICT;


--
-- PostgreSQL database dump complete
--

\unrestrict kCxIb5M6MRz2SQm1OrbSOXPQwsDNJrg7WINa6vup8D8nWUUw3u6VdrJCcFWbswb

