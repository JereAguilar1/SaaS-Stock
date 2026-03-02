-- ============================================================================
-- Inserción de Productos de Carnicería
-- ============================================================================
-- Fecha: Marzo 2026
-- Usuario objetivo: jeremiasaguilaring@gmail.com
-- Fuente: productos app.xlsx (77 productos)
-- 
-- INSTRUCCIONES:
--   Local:  docker compose exec -T db psql -U stock -d stock < db/migrations/insert_productos_carniceria.sql
--   Prod:   docker compose -f docker-compose.prod.yml exec -T db psql -U stock_user -d stock_db < db/migrations/insert_productos_carniceria.sql
-- ============================================================================

BEGIN;

-- ============================================================================
-- SCRIPT PRINCIPAL
-- ============================================================================
DO $$
DECLARE
  v_user_id BIGINT;
  v_tenant_id BIGINT;
  v_uom_kg_id BIGINT;
  v_cat_cerdo BIGINT;
  v_cat_ternera BIGINT;
  v_cat_embutidos BIGINT;
  v_cat_preparados BIGINT;
  v_cat_achuras BIGINT;
  v_cat_pollo BIGINT;
  v_cat_otros BIGINT;
BEGIN

  -- ============================================================================
  -- 1. RESOLVER TENANT_ID del usuario
  -- ============================================================================
  SELECT id INTO v_user_id
  FROM app_user
  WHERE email = 'jeremiasaguilaring@gmail.com';

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Usuario jeremiasaguilaring@gmail.com no encontrado';
  END IF;

  SELECT tenant_id INTO v_tenant_id
  FROM user_tenant
  WHERE user_id = v_user_id AND active = TRUE
  ORDER BY id LIMIT 1;

  IF v_tenant_id IS NULL THEN
    RAISE EXCEPTION 'No se encontró un tenant activo para el usuario %', v_user_id;
  END IF;

  RAISE NOTICE '✅ Usuario id=%, tenant_id=%', v_user_id, v_tenant_id;

  -- ============================================================================
  -- 2. RESOLVER UOM "Kilogramo"
  -- ============================================================================
  SELECT id INTO v_uom_kg_id
  FROM uom WHERE tenant_id = v_tenant_id AND LOWER(name) = 'kilogramo';

  IF v_uom_kg_id IS NULL THEN
    INSERT INTO uom (tenant_id, name, symbol)
    VALUES (v_tenant_id, 'Kilogramo', 'kg')
    RETURNING id INTO v_uom_kg_id;
    RAISE NOTICE '✅ UOM "Kilogramo" creada: id=%', v_uom_kg_id;
  ELSE
    RAISE NOTICE '✅ UOM "Kilogramo" existente: id=%', v_uom_kg_id;
  END IF;

  -- ============================================================================
  -- 3. CREAR CATEGORÍAS
  -- ============================================================================
  SELECT id INTO v_cat_cerdo FROM category WHERE tenant_id = v_tenant_id AND name = 'Cerdo';
  IF v_cat_cerdo IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Cerdo') RETURNING id INTO v_cat_cerdo;
  END IF;

  SELECT id INTO v_cat_ternera FROM category WHERE tenant_id = v_tenant_id AND name = 'Ternera';
  IF v_cat_ternera IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Ternera') RETURNING id INTO v_cat_ternera;
  END IF;

  SELECT id INTO v_cat_embutidos FROM category WHERE tenant_id = v_tenant_id AND name = 'Embutidos';
  IF v_cat_embutidos IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Embutidos') RETURNING id INTO v_cat_embutidos;
  END IF;

  SELECT id INTO v_cat_preparados FROM category WHERE tenant_id = v_tenant_id AND name = 'Preparados';
  IF v_cat_preparados IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Preparados') RETURNING id INTO v_cat_preparados;
  END IF;

  SELECT id INTO v_cat_achuras FROM category WHERE tenant_id = v_tenant_id AND name = 'Achuras';
  IF v_cat_achuras IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Achuras') RETURNING id INTO v_cat_achuras;
  END IF;

  SELECT id INTO v_cat_pollo FROM category WHERE tenant_id = v_tenant_id AND name = 'Pollo';
  IF v_cat_pollo IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Pollo') RETURNING id INTO v_cat_pollo;
  END IF;

  SELECT id INTO v_cat_otros FROM category WHERE tenant_id = v_tenant_id AND name = 'Otros';
  IF v_cat_otros IS NULL THEN
    INSERT INTO category (tenant_id, name) VALUES (v_tenant_id, 'Otros') RETURNING id INTO v_cat_otros;
  END IF;

  RAISE NOTICE '✅ Categorías: Cerdo=%, Ternera=%, Embutidos=%, Preparados=%, Achuras=%, Pollo=%, Otros=%',
    v_cat_cerdo, v_cat_ternera, v_cat_embutidos, v_cat_preparados, v_cat_achuras, v_cat_pollo, v_cat_otros;

  -- ============================================================================
  -- 4. INSERTAR PRODUCTOS (ON CONFLICT DO NOTHING = idempotente)
  --    El trigger product_init_stock crea product_stock automáticamente
  -- ============================================================================

  -- CERDO (21 productos: SKU 2001-2021)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2001', 'BIFE DE CERDO', 6000.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2002', 'BONDIOLA DE CERDO', 7810.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2003', 'CARNE PICADA DE CERDO', 5100.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2004', 'CARRE DE CERDO', 6550.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2005', 'CHULETONES DE CERDO', 5780.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2006', 'CHURRASQUITO DE CERDO', 6970.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2007', 'CUADRADA DE CERDO', 6120.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2008', 'CORTE AMERICANO DE CERDO', 5870.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2009', 'ENTRAÑA DE CERDO', 8075.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2010', 'LENGUA DE CERDO', 1700.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2011', 'MATAMBRE DE CERDO', 12310.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2012', 'NALGA DE CERDO', 5510.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2013', 'PANCETA FRESCA', 6970.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2014', 'PATITAS DE CERDO', 1275.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2015', 'PECETO DE CERDO', 6120.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2016', 'PECHITO DE CERDO', 6250.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2017', 'SOLOMILLO DE CERDO', 7650.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2018', 'TAPA DE ASADO DE CERDO', 6970.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2019', 'VACIO DE CERDO', 7570.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2020', 'COSTELETA DE CERDO', 5440.00, v_uom_kg_id, v_cat_cerdo, TRUE),
    (v_tenant_id, '2021', 'PERNIL', 4165.00, v_uom_kg_id, v_cat_cerdo, TRUE)
  ON CONFLICT DO NOTHING;
  RAISE NOTICE '✅ Cerdo: 21 productos';

  -- TERNERA (30 productos: SKU 2100-2129)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2100', 'AGUJA', 16330.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2101', 'ARAÑITA', 18710.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2102', 'ASADO', 20980.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2103', 'BIFE DE CHORIZO', 29990.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2104', 'BOLA DE LOMO', 21950.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2105', 'CARNE PICADA DE TERNERA', 14550.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2106', 'CHULETA', 20740.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2107', 'COLITA DE CUADRIL', 26400.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2108', 'CORTE AMERICANO', 19310.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2109', 'CUADRADA', 19000.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2110', 'CUADRIL', 23900.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2111', 'ENTRAÑA', 23900.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2112', 'FALDA', 13920.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2113', 'FALDA DESHUESADA', 23380.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2114', 'LOMO', 28910.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2115', 'MARUCHA', 23290.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2116', 'MATAMBRE DE TERNERA', 21000.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2117', 'NALGA', 23900.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2118', 'OJO DE BIFE', 25140.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2119', 'OSOBUCO', 13820.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2120', 'PALETA', 18590.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2121', 'PALOMITA', 14450.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2122', 'PECETO', 27590.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2123', 'PICAÑA', 25590.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2124', 'ROAST BEEF', 16330.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2125', 'TAPA DE ASADO', 27690.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2126', 'TAPA DE NALGA', 19890.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2127', 'TAPA DE PALETA', 21470.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2128', 'TORTUGUITA', 18230.00, v_uom_kg_id, v_cat_ternera, TRUE),
    (v_tenant_id, '2129', 'VACIO', 28690.00, v_uom_kg_id, v_cat_ternera, TRUE)
  ON CONFLICT DO NOTHING;
  RAISE NOTICE '✅ Ternera: 30 productos';

  -- EMBUTIDOS (9 productos: SKU 2201-2208 + LONGANIZA sin SKU)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2201', 'CHORIZO PURO CERDO', 7700.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2202', 'SALCHICHA PARRILLERA', 9100.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2203', 'MORCILLA', 5950.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2204', 'MORCILLA BOMBON', 6950.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2205', 'CHORIZO CON QUESO', 7700.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2206', 'MORCILLA VASCA', 6560.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2207', 'CHORIZO BOMBON', 8320.00, v_uom_kg_id, v_cat_embutidos, TRUE),
    (v_tenant_id, '2208', 'CHORIZO ESPECIAL VACUNO', 7920.00, v_uom_kg_id, v_cat_embutidos, TRUE)
  ON CONFLICT DO NOTHING;

  -- LONGANIZA sin código/SKU
  INSERT INTO product (tenant_id, name, sale_price, uom_id, category_id, active)
  SELECT v_tenant_id, 'LONGANIZA', 17900.00, v_uom_kg_id, v_cat_embutidos, TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM product WHERE tenant_id = v_tenant_id AND name = 'LONGANIZA'
  );
  RAISE NOTICE '✅ Embutidos: 9 productos';

  -- PREPARADOS (4 productos: SKU 2209-2212)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2209', 'MILANESA DE CERDO', 6800.00, v_uom_kg_id, v_cat_preparados, TRUE),
    (v_tenant_id, '2210', 'MILANESA DE TERNERA', 15090.00, v_uom_kg_id, v_cat_preparados, TRUE),
    (v_tenant_id, '2211', 'HAMBURGUESA DE CERDO', 6800.00, v_uom_kg_id, v_cat_preparados, TRUE),
    (v_tenant_id, '2212', 'HAMBURGUESA DE TERNERA', 16050.00, v_uom_kg_id, v_cat_preparados, TRUE)
  ON CONFLICT DO NOTHING;
  RAISE NOTICE '✅ Preparados: 4 productos';

  -- ACHURAS (6 productos: SKU 2302-2307)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2302', 'HIGADO', 4750.00, v_uom_kg_id, v_cat_achuras, TRUE),
    (v_tenant_id, '2303', 'MOLLEJA', 36000.00, v_uom_kg_id, v_cat_achuras, TRUE),
    (v_tenant_id, '2304', 'LENGUA', 14500.00, v_uom_kg_id, v_cat_achuras, TRUE),
    (v_tenant_id, '2305', 'CHINCHULIN', 6500.00, v_uom_kg_id, v_cat_achuras, TRUE),
    (v_tenant_id, '2306', 'TRIPA GORDA', 2900.00, v_uom_kg_id, v_cat_achuras, TRUE),
    (v_tenant_id, '2307', 'RIÑON', 5990.00, v_uom_kg_id, v_cat_achuras, TRUE)
  ON CONFLICT DO NOTHING;
  RAISE NOTICE '✅ Achuras: 6 productos';

  -- POLLO (5 productos: SKU 2310, 2400, 2401, 370, 1529)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2310', 'HAMBURGUESA DE POLLO', 9500.00, v_uom_kg_id, v_cat_pollo, TRUE),
    (v_tenant_id, '2400', 'POLLO DE CAMPO ENTERO', 8000.00, v_uom_kg_id, v_cat_pollo, TRUE),
    (v_tenant_id, '2401', 'POLLO DE CAMPO MITAD', 9000.00, v_uom_kg_id, v_cat_pollo, TRUE),
    (v_tenant_id, '370', 'MILANESA DE POLLO', 9050.00, v_uom_kg_id, v_cat_pollo, TRUE),
    (v_tenant_id, '1529', 'HAMBURGUESA DE POLLO', 7500.00, v_uom_kg_id, v_cat_pollo, TRUE)
  ON CONFLICT DO NOTHING;
  RAISE NOTICE '✅ Pollo: 5 productos';

  -- OTROS (2 productos: SKU 2990, 2991)
  INSERT INTO product (tenant_id, sku, name, sale_price, uom_id, category_id, active) VALUES
    (v_tenant_id, '2990', 'BIFE CON HUESO', 5445.00, v_uom_kg_id, v_cat_otros, TRUE),
    (v_tenant_id, '2991', 'CUARTOS', 7744.00, v_uom_kg_id, v_cat_otros, TRUE)
  ON CONFLICT DO NOTHING;
  RAISE NOTICE '✅ Otros: 2 productos';


  -- ============================================================================
  -- 5. INSERTAR CLIENTES (268 clientes desde clientes app.xlsx)
  -- ============================================================================
  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ADRIAN LAVALLEN', 'C0046', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ADRIAN LAVALLEN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALAN DEZEO', 'C0195', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALAN DEZEO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALBANESE CACHO', 'C0094', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALBANESE CACHO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALE DEL VALLE', 'C0144', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALE DEL VALLE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALE DICARLO', 'C0042', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALE DICARLO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALE EL SOLCITO', 'C0066', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALE EL SOLCITO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJANDRA C.', 'C0257', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJANDRA C.'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJANDRA CONFALONIERI', 'C0205', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJANDRA CONFALONIERI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJANDRO ALEWARTS', 'C0105', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJANDRO ALEWARTS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJANDRO', 'C0051', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJANDRO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJANDRO DECO', 'C0150', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJANDRO DECO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJANDRO RUBIO', 'C0265', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJANDRO RUBIO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALEJO DI PAOLA', 'C0154', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALEJO DI PAOLA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ALMACEN SERRANO', 'C0057', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ALMACEN SERRANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ANA LIMACHE', 'C0243', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ANA LIMACHE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ANTO', 'C0245', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ANTO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ARCA', 'C0262', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ARCA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ARIEL DI GIORGIO', 'C0286', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ARIEL DI GIORGIO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ARIEL GUERRERO', 'C0206', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ARIEL GUERRERO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'A. SERRANO', 'C0171', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('A. SERRANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ASIA IJURCO', 'C0250', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ASIA IJURCO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ASIA LUNGHI', 'C0226', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ASIA LUNGHI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ASIA LUNGHI', 'C0107', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ASIA LUNGHI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ASIA PAYRO', 'C0098', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ASIA PAYRO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ASIA RIVADAVIA', 'C0089', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ASIA RIVADAVIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BALBIN CHINO', 'C0078', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BALBIN CHINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BARTEL LUIS', 'C0077', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BARTEL LUIS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BELEN ASINI', 'C0073', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BELEN ASINI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BELLO ABRIL', 'C0273', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BELLO ABRIL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BRAK', 'C0256', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BRAK'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BRAT', 'C0253', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BRAT'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BRIGADIER', 'C0081', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BRIGADIER'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BRUNO', 'C0149', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BRUNO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'BUGNA, JULIETA', 'C0034', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('BUGNA, JULIETA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CABRERA ALEJANDRO - Mayorista Carnico', 'C0104', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CABRERA ALEJANDRO - Mayorista Carnico'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CADEMARTORI, JUAN', 'C0028', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CADEMARTORI, JUAN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CAIO', 'C0204', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CAIO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CAMPERITO', 'C0227', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CAMPERITO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CAMUZZI GAS PAMPEANA', 'C0263', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CAMUZZI GAS PAMPEANA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CANALENSE', 'C0275', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CANALENSE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CAPITANO', 'C0143', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CAPITANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CARLITOS VALLES', 'C0147', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CARLITOS VALLES'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CARLOS CABRERA', 'C0192', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CARLOS CABRERA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CARNICERIA FLECHA DEL PLATA MATIAS', 'C0074', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CARNICERIA FLECHA DEL PLATA MATIAS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CARUSO, RICARDO RAUL', 'C0031', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CARUSO, RICARDO RAUL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHAVO', 'C0101', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHAVO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHEQUES1', 'C0280', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHEQUES1'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHICHO', 'C0246', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHICHO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHINA BING DEL VALLE', 'C0068', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHINA BING DEL VALLE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHINCHU', 'C0163', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHINCHU'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHINO BARK', 'C0261', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHINO BARK'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHINO CORRIENTES', 'C0240', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHINO CORRIENTES'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHINO FIGUEROA', 'C0258', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHINO FIGUEROA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CHINO NACAROTTI', 'C0148', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CHINO NACAROTTI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CIMARRON', 'C0187', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CIMARRON'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CITY BAR', 'C0152', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CITY BAR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CLUB NAHUEL', 'C0172', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CLUB NAHUEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'COLO', 'C0196', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('COLO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CONSTITUCION', 'C0241', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CONSTITUCION'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'Consumidor Final', 'C0001', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('Consumidor Final'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CONTRERAS, MAURO JESUS', 'C0013', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CONTRERAS, MAURO JESUS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CORVALAN', 'C0242', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CORVALAN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CRIS LA MARCA', 'C0234', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CRIS LA MARCA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CRISTIAN CARDELLI BOLIVAR', 'C0076', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CRISTIAN CARDELLI BOLIVAR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'CRISTIAN PARTICULAR', 'C0134', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('CRISTIAN PARTICULAR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DAMIAN CITY', 'C0140', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DAMIAN CITY'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DANIEL ELENO', 'C0131', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DANIEL ELENO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DARIO LORENZO', 'C0161', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DARIO LORENZO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DAVERIO, HECTOR', 'C0018', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DAVERIO, HECTOR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DAVID PRIMERA JUNTA', 'C0224', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DAVID PRIMERA JUNTA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DELFINA FALCONNAT', 'C0281', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DELFINA FALCONNAT'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DE MIGUEL, CLAUDIO ALEJANDRO', 'C0012', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DE MIGUEL, CLAUDIO ALEJANDRO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DEROSE, MAURICIO EDUARDO', 'C0007', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DEROSE, MAURICIO EDUARDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DIEGO', 'C0238', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DIEGO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DON GIULIANO', 'C0216', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DON GIULIANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'DON ROSENDO', 'C0054', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('DON ROSENDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'EDU', 'C0232', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('EDU'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'EDUARDO AYASTU', 'C0268', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('EDUARDO AYASTU'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'EDU PERUANO', 'C0236', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('EDU PERUANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'EL BRETE LUCIANO', 'C0047', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('EL BRETE LUCIANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'EL REFUGIO', 'C0188', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('EL REFUGIO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ETCHEMENDI', 'C0041', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ETCHEMENDI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'EVENTOS ANDRACA', 'C0254', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('EVENTOS ANDRACA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FABIAN 4 ESQUINA', 'C0269', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FABIAN 4 ESQUINA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FABRE SOLE', 'C0158', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FABRE SOLE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FALU LOS CARDOS', 'C0142', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FALU LOS CARDOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FANY', 'C0176', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FANY'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FARIAS MAURICIO BARKER', 'C0072', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FARIAS MAURICIO BARKER'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FAVRE', 'C0117', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FAVRE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FEDE LORENO', 'C0173', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FEDE LORENO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FER ARANDA', 'C0106', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FER ARANDA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FER AVICOLA', 'C0086', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FER AVICOLA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'Fernando Carlos Olivera (Panadero)', 'C0174', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('Fernando Carlos Olivera (Panadero)'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FERNANDO MENA', 'C0203', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FERNANDO MENA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FERNANDO QUEVEDO', 'C0267', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FERNANDO QUEVEDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FEROMONA', 'C0247', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FEROMONA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FEROMONAS', 'C0177', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FEROMONAS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FERREIRO, HEBE CAROLINA ALICIA', 'C0016', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FERREIRO, HEBE CAROLINA ALICIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FINCA TANDIL', 'C0276', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FINCA TANDIL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FINO, DIEGO FERNANDO', 'C0019', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FINO, DIEGO FERNANDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FIRPO', 'C0168', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FIRPO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FONSECA, RAUL ANIBAL', 'C0029', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FONSECA, RAUL ANIBAL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'FRAN TECHOS', 'C0191', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('FRAN TECHOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GABI BALBIN', 'C0277', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GABI BALBIN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GABY SANCHEZ', 'C0248', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GABY SANCHEZ'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GABY SANTINO', 'C0151', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GABY SANTINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GAIADA ORLANDO', 'C0061', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GAIADA ORLANDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GARCIA LUIS FABIAN Y GHELFI RODRIGO DAVID', 'C0032', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GARCIA LUIS FABIAN Y GHELFI RODRIGO DAVID'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GASTON GIANONI', 'C0157', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GASTON GIANONI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GERMAN MELENA', 'C0167', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GERMAN MELENA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GIMENEZ', 'C0213', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GIMENEZ'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GONZALEZ, MATIAS EMANUEL', 'C0033', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GONZALEZ, MATIAS EMANUEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GOYENECHE', 'C0125', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GOYENECHE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GOYO CABRERA', 'C0112', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GOYO CABRERA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GRIERSON HNOS.', 'C0017', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GRIERSON HNOS.'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GUAN GUEMES', 'C0222', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GUAN GUEMES'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GUILER', 'C0122', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GUILER'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'GUILLE CORBETTA', 'C0202', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('GUILLE CORBETTA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'HAMPARSOMIAN, MIRTA SILVIA', 'C0025', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('HAMPARSOMIAN, MIRTA SILVIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'HUELLA', 'C0278', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('HUELLA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'HUELLAS LUCIO', 'C0128', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('HUELLAS LUCIO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'IALEA, PAOLA GISEL', 'C0039', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('IALEA, PAOLA GISEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'IGA', 'C0126', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('IGA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'IGNACIO FUNARO', 'C0266', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('IGNACIO FUNARO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'IRIGOYEN CHINO', 'C0080', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('IRIGOYEN CHINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'IZARRIAGA, LUIS ANTONIO   EL MAGO', 'C0021', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('IZARRIAGA, LUIS ANTONIO   EL MAGO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JANO', 'C0115', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JHON LEGO', 'C0182', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JHON LEGO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JONY CARNES - JONY ZEGA', 'C0189', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JONY CARNES - JONY ZEGA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JORGE CIANO', 'C0180', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JORGE CIANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'Jorge Ismael Ceceri', 'C0050', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('Jorge Ismael Ceceri'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JOSE', 'C0214', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JOSE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JOSE CEJA', 'C0193', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JOSE CEJA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JOSE JIMENEZ', 'C0118', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JOSE JIMENEZ'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JOSE PEPE', 'C0220', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JOSE PEPE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JUANA ASIA', 'C0217', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JUANA ASIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JUAN ACTIS', 'C0185', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JUAN ACTIS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JUAN DE COLECTORA', 'C0260', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JUAN DE COLECTORA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'JUAN LEGUIZAMON', 'C0135', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('JUAN LEGUIZAMON'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'KARINA', 'C0166', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('KARINA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LA FACTORIA', 'C0067', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LA FACTORIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LA PAMPA', 'C0264', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LA PAMPA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LA PIPI', 'C0062', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LA PIPI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LAURA MOVEDIZA', 'C0090', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LAURA MOVEDIZA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LAUTARO LANESTOSA', 'C0040', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LAUTARO LANESTOSA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LEAN CHIDICHIMO', 'C0183', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LEAN CHIDICHIMO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LILIAN ANCHOITA', 'C0097', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LILIAN ANCHOITA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LOPARDO', 'C0165', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LOPARDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LO PEPE', 'C0102', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LO PEPE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LOS 50', 'C0231', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LOS 50'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LOS ALAMOS', 'C0181', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LOS ALAMOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LOS CARDOS', 'C0175', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LOS CARDOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LOS POKEMONES', 'C0212', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LOS POKEMONES'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LOZANO SANCHEZ, PILAR', 'C0003', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LOZANO SANCHEZ, PILAR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LUIS AUROLIMP', 'C0244', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LUIS AUROLIMP'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'LUNGHI CHINO', 'C0111', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('LUNGHI CHINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MAFALDA', 'C0119', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MAFALDA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MANCEDO, DIEGO JAVIER      ALMACEN SERRANO', 'C0038', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MANCEDO, DIEGO JAVIER      ALMACEN SERRANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MA OLAVARRÍA', 'C0225', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MA OLAVARRÍA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARCOS GARRIDO', 'C0043', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARCOS GARRIDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARIANA', 'C0239', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARIANA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARIANO', 'C0229', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARIANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARIELA', 'C0164', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARIELA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARIELA BARKER', 'C0064', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARIELA BARKER'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARK', 'C0270', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARK'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARO PARTICULAR', 'C0133', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARO PARTICULAR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARQUEZ, JULIO SANTOS', 'C0010', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARQUEZ, JULIO SANTOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARTIN CALABRO', 'C0170', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARTIN CALABRO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARTIN CHINO', 'C0052', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARTIN CHINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARTIN CURVA', 'C0215', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARTIN CURVA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARTIN LUBRICENTRO', 'C0120', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARTIN LUBRICENTRO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MARTIN PENA', 'C0113', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MARTIN PENA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MATÍAS', 'C0209', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MATÍAS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MAURO PARTICULAR', 'C0109', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MAURO PARTICULAR'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MELLI CARLOS', 'C0055', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MELLI CARLOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MELLI MARCE', 'C0056', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MELLI MARCE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MERY', 'C0190', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MERY'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MIGUEL FRAIFER', 'C0274', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MIGUEL FRAIFER'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MILI DE 25 MAYO', 'C0129', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MILI DE 25 MAYO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MIRANDA, JOSE HUMBERTO', 'C0020', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MIRANDA, JOSE HUMBERTO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MIRIAM', 'C0235', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MIRIAM'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MIRTA GARRIDO', 'C0087', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MIRTA GARRIDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MORAN, VALERIA AGUSTINA', 'C0005', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MORAN, VALERIA AGUSTINA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MORENO MIGUEL', 'C0153', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MORENO MIGUEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MORTEO, EDUARDO RUBEN ANIBAL', 'C0036', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MORTEO, EDUARDO RUBEN ANIBAL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MOURE ADRIAN', 'C0121', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MOURE ADRIAN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MOURE, CAMILO ROMAN', 'C0014', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MOURE, CAMILO ROMAN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'MUJER IZARRIAGA EL MAGO', 'C0083', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('MUJER IZARRIAGA EL MAGO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NACHO', 'C0251', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NACHO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NACHO ANDRACA', 'C0249', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NACHO ANDRACA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NATY', 'C0198', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NATY'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NELY PARQUE AEREO', 'C0084', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NELY PARQUE AEREO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NICOLAS AMESCUA', 'C0279', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NICOLAS AMESCUA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NICOLAS ELORDI', 'C0139', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NICOLAS ELORDI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'NICO SANTOS', 'C0137', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('NICO SANTOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ORIENTE', 'C0219', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ORIENTE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ORIENTE PRIMERA JUNTA', 'C0223', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ORIENTE PRIMERA JUNTA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'OROSCO, MARIO DANIEL', 'C0035', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('OROSCO, MARIO DANIEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PABLO VALDERREY', 'C0138', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PABLO VALDERREY'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PAME', 'C0197', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PAME'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PAMELA', 'C0287', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PAMELA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PANADERIA LAS DELICIAS', 'C0132', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PANADERIA LAS DELICIAS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PANIFICADORA', 'C0221', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PANIFICADORA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PARAGUAYA', 'C0178', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PARAGUAYA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PARQUERO CHINO', 'C0116', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PARQUERO CHINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PASTITO', 'C0096', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PASTITO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PASTURAS DE CRIA SRL', 'C0004', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PASTURAS DE CRIA SRL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PATRICIA    EL BRETE', 'C0048', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PATRICIA    EL BRETE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PELA', 'C0237', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PELA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PENA, HERNAN EZEQUIEL', 'C0037', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PENA, HERNAN EZEQUIEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PEREZ', 'C0141', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PEREZ'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PICHI EL MAGO', 'C0156', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PICHI EL MAGO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'POCHO ALBANESE', 'C0092', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('POCHO ALBANESE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'POLLERIA PIO', 'C0071', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('POLLERIA PIO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'POLLO', 'C0059', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('POLLO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'POROTO', 'C0160', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('POROTO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PROAVITAND S.R.L', 'C0006', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PROAVITAND S.R.L'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'PUESTO CHICO', 'C0082', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('PUESTO CHICO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RAMONA LA CASA DE DON LUIS', 'C0063', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RAMONA LA CASA DE DON LUIS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RAMONSITO', 'C0218', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RAMONSITO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'REYNA SILVIA MASA', 'C0162', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('REYNA SILVIA MASA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RIVADAVIA CHINO', 'C0093', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RIVADAVIA CHINO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'Roberto Solis Gustavo (Pitu - Zampatti)', 'C0023', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('Roberto Solis Gustavo (Pitu - Zampatti)'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROCIO LUNGHI', 'C0085', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROCIO LUNGHI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RODO', 'C0210', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RODO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RODO - CC', 'C0284', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RODO - CC'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RODO PALACIOS', 'C0285', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RODO PALACIOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROD - PASTURA DE CRIAS', 'C0259', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROD - PASTURA DE CRIAS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROGELIO ALEWEARTS', 'C0207', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROGELIO ALEWEARTS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROMERO, MATIAS EZEQUIEL', 'C0011', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROMERO, MATIAS EZEQUIEL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROMI CLUB 50', 'C0091', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROMI CLUB 50'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROMINA', 'C0272', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROMINA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ROXANA', 'C0136', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ROXANA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'RUBENS ARCO IRIS', 'C0075', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('RUBENS ARCO IRIS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SANDRA MAGO', 'C0130', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SANDRA MAGO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SANDRO NICORA', 'C0271', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SANDRO NICORA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SANSERVINO SEVERO, ALFREDO FACUNDO', 'C0053', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SANSERVINO SEVERO, ALFREDO FACUNDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SANTI', 'C0108', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SANTI'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SANTIAGO VELA', 'C0184', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SANTIAGO VELA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SANTI JIMENEZ', 'C0230', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SANTI JIMENEZ'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SCHONFELD, AGUSTINA', 'C0026', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SCHONFELD, AGUSTINA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SEBA MECÁNICO', 'C0201', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SEBA MECÁNICO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SERAFIN', 'C0228', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SERAFIN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SERGIO ALLENDE', 'C0283', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SERGIO ALLENDE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SHORT, MARIA CECILIA', 'C0009', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SHORT, MARIA CECILIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SILVA LAURA', 'C0169', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SILVA LAURA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'SOFI ROTISERÍA DATE UN GUSTO', 'C0200', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('SOFI ROTISERÍA DATE UN GUSTO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TALLER PROTEGIDO', 'C0194', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TALLER PROTEGIDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TAMARA (HUEVOS)', 'C0199', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TAMARA (HUEVOS)'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TANDIL CARNES', 'C0282', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TANDIL CARNES'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TANDIL EVENTOS', 'C0255', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TANDIL EVENTOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TANO', 'C0208', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TANO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TERILLE', 'C0070', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TERILLE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TERNERO', 'C0079', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TERNERO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'THUOT, DAMIAN GERARDO', 'C0030', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('THUOT, DAMIAN GERARDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TIGRE', 'C0058', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TIGRE'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'TOME NEGRO', 'C0252', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('TOME NEGRO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'URDIROZ, MATIAS EDUARDO', 'C0027', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('URDIROZ, MATIAS EDUARDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'URRUTIA, MARIA BELEN', 'C0008', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('URRUTIA, MARIA BELEN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'URSO, MAURICIO ANDRES', 'C0015', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('URSO, MAURICIO ANDRES'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'VALENTIN', 'C0124', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('VALENTIN'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'VALENTIN PERNIL', 'C0233', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('VALENTIN PERNIL'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'VARIOS', 'C0211', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('VARIOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'VASCO ARAMBURU', 'C0146', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('VASCO ARAMBURU'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'VERO LOS TANITOS', 'C0110', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('VERO LOS TANITOS'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'VICENTE, DAVID FERNANDO EDUARDO', 'C0022', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('VICENTE, DAVID FERNANDO EDUARDO'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'WALTER ASIA', 'C0127', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('WALTER ASIA'))
  );

  INSERT INTO customer (tenant_id, name, notes, active)
  SELECT v_tenant_id, 'ZEGA', 'C0155', TRUE
  WHERE NOT EXISTS (
    SELECT 1 FROM customer WHERE tenant_id = v_tenant_id AND LOWER(TRIM(name)) = LOWER(TRIM('ZEGA'))
  );

  RAISE NOTICE '✅ Clientes: 268 registros procesados';

  RAISE NOTICE '============================================';
  RAISE NOTICE '✅ INSERCIÓN COMPLETADA: 77 productos + 268 clientes';
  RAISE NOTICE '============================================';

END $$;

COMMIT;

-- ============================================================================
-- VERIFICACIÓN
-- ============================================================================
SELECT
  c.name AS categoria,
  COUNT(p.id) AS cantidad
FROM product p
JOIN category c ON p.category_id = c.id
JOIN user_tenant ut ON p.tenant_id = ut.tenant_id
JOIN app_user au ON ut.user_id = au.id
WHERE au.email = 'jeremiasaguilaring@gmail.com'
  AND c.name IN ('Cerdo','Ternera','Embutidos','Preparados','Achuras','Pollo','Otros')
GROUP BY c.name
ORDER BY c.name;

SELECT 'Productos con stock inicializado' AS info, COUNT(*) AS total
FROM product p
JOIN product_stock ps ON ps.product_id = p.id
JOIN user_tenant ut ON p.tenant_id = ut.tenant_id
JOIN app_user au ON ut.user_id = au.id
WHERE au.email = 'jeremiasaguilaring@gmail.com';

-- Verificar clientes insertados
SELECT 'Clientes insertados' AS info, COUNT(*) AS total
FROM customer c
JOIN user_tenant ut ON c.tenant_id = ut.tenant_id
JOIN app_user au ON ut.user_id = au.id
WHERE au.email = 'jeremiasaguilaring@gmail.com';
