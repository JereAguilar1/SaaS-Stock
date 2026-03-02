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

  RAISE NOTICE '============================================';
  RAISE NOTICE '✅ INSERCIÓN COMPLETADA: 77 productos en 7 categorías';
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
