#!/bin/bash
#
# Script de Verificación - PASO 8: Redis Cache
#
# Verifica que Redis está correctamente configurado y funcionando.
#

set -e

echo "================================================"
echo "PASO 8: Verificación de Redis Cache"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASSED=0
FAILED=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASSED++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAILED++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Verificar servicio Redis en Docker
echo "1️⃣  Verificando servicio Redis..."
echo ""

if docker compose ps | grep -q "Stock-redis.*Up"; then
    check_pass "Redis está corriendo"
else
    check_fail "Redis NO está corriendo"
fi

echo ""

# 2. Verificar puerto Redis
echo "2️⃣  Verificando puerto Redis..."
echo ""

if nc -z localhost 6379 2>/dev/null || timeout 1 bash -c 'cat < /dev/null > /dev/tcp/localhost/6379' 2>/dev/null; then
    check_pass "Puerto 6379 (Redis) está abierto"
else
    check_warn "Puerto 6379 NO está abierto (OK en PROD si no se expone)"
fi

echo ""

# 3. Test Redis PING
echo "3️⃣  Test Redis PING..."
echo ""

if docker exec Stock-redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    check_pass "Redis responde a PING"
else
    check_fail "Redis NO responde a PING"
fi

echo ""

# 4. Verificar dependencias Python
echo "4️⃣  Verificando dependencias Python..."
echo ""

if docker compose exec -T web python -c "import redis" 2>/dev/null; then
    check_pass "redis-py está instalado"
else
    check_fail "redis-py NO está instalado"
fi

if docker compose exec -T web python -c "import hiredis" 2>/dev/null; then
    check_pass "hiredis está instalado (performance boost)"
else
    check_warn "hiredis NO está instalado (opcional, pero recomendado)"
fi

echo ""

# 5. Verificar cache_service.py
echo "5️⃣  Verificando cache service..."
echo ""

if docker compose exec -T web test -f /app/app/services/cache_service.py; then
    check_pass "cache_service.py existe"
else
    check_fail "cache_service.py NO existe"
fi

if docker compose exec -T web python -c "from app.services.cache_service import get_cache" 2>/dev/null; then
    check_pass "cache_service.py es importable"
else
    check_fail "cache_service.py NO es importable"
fi

echo ""

# 6. Test conexión Redis desde Flask
echo "6️⃣  Test conexión Redis desde Flask..."
echo ""

REDIS_TEST=$(docker compose exec -T web python -c "
import os
import redis

redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/0')

try:
    client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=3)
    result = client.ping()
    if result:
        print('SUCCESS')
    else:
        print('ERROR: ping returned False')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

if echo "$REDIS_TEST" | grep -q "SUCCESS"; then
    check_pass "Flask puede conectarse a Redis"
else
    check_fail "Flask NO puede conectarse a Redis"
    echo "   Error: $REDIS_TEST"
fi

echo ""

# 7. Test cache set/get
echo "7️⃣  Test cache set/get..."
echo ""

CACHE_TEST=$(docker compose exec -T web python -c "
import sys
sys.path.insert(0, '/app')

try:
    from app import create_app
    from app.services.cache_service import get_cache
    
    app = create_app()
    with app.app_context():
        cache = get_cache()
        
        # Test set
        success = cache.set(999, 'test', 'quickstart', {'hello': 'world'}, ttl=60)
        if not success:
            print('ERROR: cache.set() returned False')
            sys.exit(1)
        
        # Test get
        value = cache.get(999, 'test', 'quickstart')
        if value and value.get('hello') == 'world':
            print('SUCCESS')
        else:
            print(f'ERROR: Expected {{hello: world}}, got {value}')
except Exception as e:
    print(f'ERROR: {e}')
    import traceback
    traceback.print_exc()
" 2>&1)

if echo "$CACHE_TEST" | grep -q "SUCCESS"; then
    check_pass "Cache set/get funciona correctamente"
else
    check_fail "Cache set/get falló"
    echo "   Error: $CACHE_TEST"
fi

echo ""

# 8. Verificar health endpoint
echo "8️⃣  Verificando health endpoint..."
echo ""

HEALTH_RESPONSE=$(curl -s http://localhost:5000/health/cache 2>&1)

if echo "$HEALTH_RESPONSE" | grep -q '"status".*"ok"'; then
    check_pass "Health endpoint responde OK"
elif echo "$HEALTH_RESPONSE" | grep -q '"status".*"degraded"'; then
    check_warn "Health endpoint responde DEGRADED (Redis down pero app funciona)"
else
    check_fail "Health endpoint no responde correctamente"
    echo "   Response: $HEALTH_RESPONSE"
fi

echo ""

# 9. Ver keys en Redis
echo "9️⃣  Verificando keys en Redis..."
echo ""

KEY_COUNT=$(docker exec Stock-redis redis-cli KEYS "stock:tenant:*" 2>/dev/null | wc -l)

if [ "$KEY_COUNT" -gt 0 ]; then
    check_pass "Redis tiene $KEY_COUNT keys cacheadas"
else
    check_warn "Redis no tiene keys aún (normal si no hubo requests)"
fi

echo ""

# 10. Resumen final
echo "================================================"
echo "RESUMEN DE VERIFICACIÓN"
echo "================================================"
echo ""
echo -e "Tests pasados: ${GREEN}$PASSED${NC}"
echo -e "Tests fallidos: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ PASO 8 VERIFICADO EXITOSAMENTE${NC}"
    echo ""
    echo "Próximos pasos para testing:"
    echo "1. Acceder a balance: http://localhost:5000/balance"
    echo "2. Ver logs: docker compose logs -f web | grep CACHE"
    echo "3. Verificar MISS → HIT en segundo request"
    echo "4. Crear producto y verificar INVALIDATE"
    echo "5. Ver keys: docker exec -it Stock-redis redis-cli KEYS 'stock:tenant:*'"
    echo ""
    echo "Monitoreo de cache:"
    echo "  docker exec -it Stock-redis redis-cli INFO stats"
    echo "  docker exec -it Stock-redis redis-cli MONITOR"
    echo ""
    exit 0
else
    echo -e "${RED}❌ PASO 8 TIENE ERRORES${NC}"
    echo ""
    echo "Acciones recomendadas:"
    echo "1. Verificar docker-compose.yml tiene servicio 'redis'"
    echo "2. Verificar requirements.txt tiene 'redis>=5'"
    echo "3. Rebuild: docker compose build --no-cache web"
    echo "4. Restart: docker compose down && docker compose up -d"
    echo "5. Ver logs: docker compose logs -f web | grep CACHE"
    echo "6. Ver logs Redis: docker compose logs redis"
    echo ""
    exit 1
fi
