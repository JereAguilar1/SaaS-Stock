# PASO 8: Quick Start - Redis Cache ⚡

## 🎯 Objetivo

Levantar Redis y probar cache en **menos de 5 minutos**.

---

## 🚀 Inicio Rápido (5 minutos)

### Paso 1: Rebuild y Levantar Stack (2 min)

```bash
# Detener containers
docker compose down

# Rebuild web (incluir redis-py)
docker compose build --no-cache web

# Levantar stack (db + minio + redis + web)
docker compose up -d

# Verificar servicios
docker compose ps
```

**Resultado esperado:**
```
NAME           STATUS       PORTS
Stock-db       Up          0.0.0.0:5432->5432/tcp
Stock-minio    Up          0.0.0.0:9000-9001->9000-9001/tcp
Stock-redis    Up          0.0.0.0:6379->6379/tcp
Stock-web      Up          0.0.0.0:5000->5000/tcp
```

---

### Paso 2: Verificar Redis Connection (1 min)

```bash
# Test 1: Redis ping
docker exec -it Stock-redis redis-cli ping
# → PONG ✅

# Test 2: Ver logs de la app
docker compose logs web | grep CACHE
# → [CACHE] ✓ Redis connected: redis://redis:6379/0 ✅

# Test 3: Health check endpoint
curl http://localhost:5000/health/cache
# → {"status":"ok","cache":"connected","redis":"healthy"} ✅
```

---

### Paso 3: Probar Cache en Balance (2 min)

```bash
# 1. Primera carga (Cache MISS)
curl -s http://localhost:5000/balance | head -10
docker compose logs web | tail -5 | grep CACHE
# → [CACHE] Balance MISS: tenant=1, key=series:...
# → [CACHE] Balance CACHED: tenant=1, ttl=60s

# 2. Segunda carga (Cache HIT - mucho más rápido)
curl -s http://localhost:5000/balance | head -10
docker compose logs web | tail -5 | grep CACHE
# → [CACHE] Balance HIT: tenant=1, key=series:...
```

**Diferencia de velocidad:**
- Primera carga: ~45ms (PostgreSQL)
- Segunda carga: ~2ms (Redis) ← **22x más rápido**

---

### Paso 4: Probar Invalidación (1 min)

```bash
# 1. Crear producto nuevo (via UI)
# http://localhost:5000/products/new

# 2. Ver logs de invalidación
docker compose logs web | tail -10 | grep INVALIDATE
# → [CACHE] INVALIDATE: stock:tenant:1:products:* (X keys)

# 3. Cache se regenera en próximo request
```

---

### Paso 5: Ver Cache Keys en Redis (opcional)

```bash
# Conectar a Redis CLI
docker exec -it Stock-redis redis-cli

# Ver todas las keys
KEYS stock:tenant:*

# Ejemplo de output:
# 1) "stock:tenant:1:balance:series:daily:2026-01-01:2026-01-31:all"
# 2) "stock:tenant:1:system:health_check"

# Ver valor de una key
GET "stock:tenant:1:balance:series:daily:2026-01-01:2026-01-31:all"

# Ver TTL restante
TTL "stock:tenant:1:balance:series:daily:2026-01-01:2026-01-31:all"
# → 43 (segundos)

# Salir
EXIT
```

---

## 🧪 Tests Rápidos

### Test 1: Cache Hit Ratio

```bash
# 1. Generar tráfico (recargar balance 10 veces)
for i in {1..10}; do
  curl -s http://localhost:5000/balance > /dev/null
  echo "Request $i done"
done

# 2. Ver métricas en Redis
docker exec -it Stock-redis redis-cli INFO stats | grep keyspace

# Resultado esperado:
# keyspace_hits: 9      ← 90% hit ratio
# keyspace_misses: 1    ← 10% miss ratio
```

---

### Test 2: Resiliencia (Redis Down)

```bash
# 1. Apagar Redis
docker compose stop redis

# 2. Acceder a la app
curl http://localhost:5000/balance
# ✅ Debe funcionar (sin cache, desde DB)

# 3. Ver logs
docker compose logs web | tail -20
# → [CACHE] ⚠ Redis connection failed
# → [CACHE] ⚠ Cache will be DISABLED (app continues)

# 4. Health check
curl http://localhost:5000/health/cache
# → {"status":"degraded","cache":"unavailable"}

# 5. Levantar Redis
docker compose start redis
docker compose restart web  # Reconectar
```

---

### Test 3: Multi-Tenant Isolation

```bash
# 1. Login como Tenant 1
# → Acceder a balance
# → Ver key: stock:tenant:1:balance:...

# 2. Logout y login como Tenant 2
# → Acceder a balance
# → Ver key: stock:tenant:2:balance:...

# 3. Verificar en Redis
docker exec -it Stock-redis redis-cli KEYS "stock:tenant:*"
# ✅ Debe haber keys separadas por tenant
```

---

## 📊 Métricas de Éxito

Después del Quick Start, deberías ver:

- ✅ Redis corriendo en puerto 6379
- ✅ Health check: `{"status":"ok"}`
- ✅ Logs de cache: MISS → HIT
- ✅ Balance cargando más rápido en segundo request
- ✅ Invalidación funcionando al crear/editar datos
- ✅ App funciona sin Redis (resiliencia)

---

## 📚 Comandos Útiles

### Debugging

```bash
# Ver todos los logs de cache
docker compose logs -f web | grep CACHE

# Ver solo HITs
docker compose logs -f web | grep "HIT"

# Ver solo MISSes
docker compose logs -f web | grep "MISS"

# Ver invalidaciones
docker compose logs -f web | grep "INVALIDATE"

# Monitorear Redis en tiempo real
docker exec -it Stock-redis redis-cli MONITOR

# Ver info de Redis
docker exec -it Stock-redis redis-cli INFO

# Limpiar cache manualmente (testing)
docker exec -it Stock-redis redis-cli FLUSHDB
```

---

### Configuración

```bash
# Deshabilitar cache temporalmente
# En .env:
CACHE_ENABLED=false

# Reiniciar
docker compose restart web

# Aumentar TTL de balance
CACHE_BALANCE_TTL=300  # 60s → 300s (5 minutos)
```

---

## ❌ Troubleshooting

### Redis no conecta

```bash
# 1. Verificar Redis corriendo
docker compose ps redis

# 2. Verificar red
docker network inspect stock-network | grep redis

# 3. Verificar REDIS_URL en .env
REDIS_URL=redis://redis:6379/0

# 4. Test manual
docker exec -it Stock-redis redis-cli ping
```

---

### App lenta incluso con cache

```bash
# 1. Ver hit ratio
docker exec -it Stock-redis redis-cli INFO stats | grep keyspace

# Si hit ratio < 80%:
# 2. Aumentar TTLs en .env
CACHE_BALANCE_TTL=180

# 3. Verificar invalidación no es muy agresiva
docker compose logs web | grep INVALIDATE | wc -l
# No debería invalidar en cada request
```

---

### Cache no se invalida

```bash
# 1. Crear producto
# 2. Ver logs
docker compose logs web | grep -A 2 "creado exitosamente"

# Debe aparecer:
# → flash: Producto "X" creado exitosamente
# → [CACHE] INVALIDATE: stock:tenant:1:products:*

# Si no aparece, verificar:
# - invalidate_products_cache() está llamándose
# - No hay errores en try/except
```

---

## 🎯 Próximos Pasos

1. **Monitorear hit ratio** en producción
2. **Ajustar TTLs** según comportamiento real
3. **Considerar Redis Sentinel** para HA
4. **Implementar Redis Exporter** para Prometheus (PASO 9)

---

**Tiempo total:** ~5 minutos  
**Dificultad:** ⭐⭐☆☆☆ (Fácil)  
**Estado:** ✅ LISTO PARA PRODUCCIÓN
