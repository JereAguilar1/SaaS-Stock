#!/bin/bash
#
# Script de Verificación - PASO 7: Object Storage
# 
# Este script verifica que la implementación de Object Storage
# está correcta y funcionando.
#

set -e

echo "================================================"
echo "PASO 7: Verificación de Object Storage"
echo "================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Counters
PASSED=0
FAILED=0

# Helper functions
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

# 1. Verificar servicios Docker
echo "1️⃣  Verificando servicios Docker..."
echo ""

if docker compose ps | grep -q "Stock-minio.*Up"; then
    check_pass "MinIO está corriendo"
else
    check_fail "MinIO NO está corriendo"
fi

if docker compose ps | grep -q "Stock-web.*Up"; then
    check_pass "Flask Web está corriendo"
else
    check_fail "Flask Web NO está corriendo"
fi

if docker compose ps | grep -q "Stock-db.*Up"; then
    check_pass "PostgreSQL está corriendo"
else
    check_fail "PostgreSQL NO está corriendo"
fi

echo ""

# 2. Verificar puertos
echo "2️⃣  Verificando puertos..."
echo ""

if nc -z localhost 9000 2>/dev/null; then
    check_pass "Puerto 9000 (MinIO API) está abierto"
else
    check_fail "Puerto 9000 (MinIO API) NO está abierto"
fi

if nc -z localhost 9001 2>/dev/null; then
    check_pass "Puerto 9001 (MinIO Console) está abierto"
else
    check_fail "Puerto 9001 (MinIO Console) NO está abierto"
fi

if nc -z localhost 5000 2>/dev/null; then
    check_pass "Puerto 5000 (Flask) está abierto"
else
    check_fail "Puerto 5000 (Flask) NO está abierto"
fi

echo ""

# 3. Verificar variables de entorno
echo "3️⃣  Verificando variables de entorno en Flask..."
echo ""

if docker compose exec -T web printenv | grep -q "S3_ENDPOINT"; then
    check_pass "S3_ENDPOINT está configurado"
else
    check_fail "S3_ENDPOINT NO está configurado"
fi

if docker compose exec -T web printenv | grep -q "S3_BUCKET"; then
    check_pass "S3_BUCKET está configurado"
else
    check_fail "S3_BUCKET NO está configurado"
fi

if docker compose exec -T web printenv | grep -q "S3_ACCESS_KEY"; then
    check_pass "S3_ACCESS_KEY está configurado"
else
    check_fail "S3_ACCESS_KEY NO está configurado"
fi

echo ""

# 4. Verificar archivos Python
echo "4️⃣  Verificando archivos de código..."
echo ""

if docker compose exec -T web test -f /app/app/services/storage_service.py; then
    check_pass "storage_service.py existe"
else
    check_fail "storage_service.py NO existe"
fi

if docker compose exec -T web python -c "from app.services.storage_service import get_storage_service" 2>/dev/null; then
    check_pass "storage_service.py es importable"
else
    check_fail "storage_service.py NO es importable (error de sintaxis?)"
fi

if docker compose exec -T web python -c "import boto3" 2>/dev/null; then
    check_pass "boto3 está instalado"
else
    check_fail "boto3 NO está instalado"
fi

echo ""

# 5. Verificar bucket en MinIO
echo "5️⃣  Verificando bucket en MinIO..."
echo ""

# Test HTTP endpoint (MinIO API)
if curl -s http://localhost:9000/uploads/ -I | grep -q "200 OK\|403 Forbidden"; then
    check_pass "Bucket 'uploads' es accesible"
else
    check_warn "No se pudo verificar bucket via HTTP (puede ser normal si aún no se creó)"
fi

echo ""

# 6. Verificar logs de la app
echo "6️⃣  Verificando logs de la aplicación..."
echo ""

if docker compose logs web 2>/dev/null | grep -q "\[STORAGE\]"; then
    check_pass "Logs de STORAGE encontrados en la app"
else
    check_warn "No se encontraron logs de STORAGE (puede ser normal si no hubo uploads)"
fi

echo ""

# 7. Test de conectividad a MinIO desde Flask
echo "7️⃣  Test de conectividad MinIO desde Flask..."
echo ""

TEST_RESULT=$(docker compose exec -T web python -c "
import os
import boto3
from botocore.client import Config as BotoConfig

endpoint = os.getenv('S3_ENDPOINT', 'http://minio:9000')
access_key = os.getenv('S3_ACCESS_KEY', 'minioadmin')
secret_key = os.getenv('S3_SECRET_KEY', 'minioadmin')
bucket = os.getenv('S3_BUCKET', 'uploads')

try:
    client = boto3.client(
        's3',
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=BotoConfig(signature_version='s3v4')
    )
    client.head_bucket(Bucket=bucket)
    print('SUCCESS')
except Exception as e:
    print(f'ERROR: {e}')
" 2>&1)

if echo "$TEST_RESULT" | grep -q "SUCCESS"; then
    check_pass "Flask puede conectarse a MinIO"
else
    check_fail "Flask NO puede conectarse a MinIO"
    echo "   Error: $TEST_RESULT"
fi

echo ""

# 8. Resumen final
echo "================================================"
echo "RESUMEN DE VERIFICACIÓN"
echo "================================================"
echo ""
echo -e "Tests pasados: ${GREEN}$PASSED${NC}"
echo -e "Tests fallidos: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ PASO 7 VERIFICADO EXITOSAMENTE${NC}"
    echo ""
    echo "Próximos pasos:"
    echo "1. Abrir MinIO Console: http://localhost:9001"
    echo "2. Login: minioadmin / minioadmin"
    echo "3. Verificar bucket 'uploads'"
    echo "4. Crear producto con imagen en: http://localhost:5000/products/new"
    echo "5. Verificar archivo en MinIO Console"
    echo ""
    exit 0
else
    echo -e "${RED}❌ PASO 7 TIENE ERRORES${NC}"
    echo ""
    echo "Acciones recomendadas:"
    echo "1. Verificar que docker-compose.yml tiene servicio 'minio'"
    echo "2. Verificar que requirements.txt tiene 'boto3'"
    echo "3. Rebuild: docker compose build --no-cache web"
    echo "4. Restart: docker compose down && docker compose up -d"
    echo "5. Ver logs: docker compose logs -f web | grep STORAGE"
    echo ""
    exit 1
fi
