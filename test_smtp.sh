#!/bin/bash
# Script de testing SMTP - SaaS Stock

echo "======================================================"
echo "   SMTP Testing - SaaS Stock"
echo "======================================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Verificar que el container esté corriendo
echo "1. Verificando estado del container..."
if ! docker compose ps | grep -q "web.*running"; then
    echo -e "${RED}✗ Container 'web' no está corriendo${NC}"
    echo "  Ejecutar: docker compose up -d"
    exit 1
fi
echo -e "${GREEN}✓ Container 'web' está corriendo${NC}"
echo ""

# 2. Verificar variables de entorno
echo "2. Verificando variables SMTP en container..."
echo ""
docker compose exec -T web bash << 'EOF'
echo "SMTP_HOST:     ${SMTP_HOST:-❌ NO CONFIGURADO}"
echo "SMTP_PORT:     ${SMTP_PORT:-❌ NO CONFIGURADO}"
echo "SMTP_USER:     ${SMTP_USER:-❌ NO CONFIGURADO}"
echo "SMTP_PASSWORD: ${SMTP_PASSWORD:+***}"${SMTP_PASSWORD:-❌ NO CONFIGURADO}
echo "SMTP_FROM:     ${SMTP_FROM:-❌ NO CONFIGURADO}"
EOF
echo ""

# 3. Verificar configuración via endpoint
echo "3. Verificando configuración SMTP (endpoint /test-email-config)..."
echo ""
CONFIG_RESPONSE=$(curl -s http://localhost:5000/test-email-config)
CONFIG_STATUS=$(echo "$CONFIG_RESPONSE" | jq -r '.configured // false' 2>/dev/null)

if [ "$CONFIG_STATUS" = "true" ]; then
    echo -e "${GREEN}✓ Configuración SMTP completa${NC}"
    echo "$CONFIG_RESPONSE" | jq '.' 2>/dev/null || echo "$CONFIG_RESPONSE"
else
    echo -e "${RED}✗ Configuración SMTP incompleta${NC}"
    echo "$CONFIG_RESPONSE" | jq '.' 2>/dev/null || echo "$CONFIG_RESPONSE"
    echo ""
    echo -e "${YELLOW}Solución:${NC}"
    echo "1. Editar archivo .env con las variables SMTP"
    echo "2. Ejecutar: docker compose down && docker compose up -d"
    echo "3. Volver a ejecutar este script"
    exit 1
fi
echo ""

# 4. Preguntar si enviar test email
echo "4. ¿Enviar email de prueba?"
echo -e "${YELLOW}   Se enviará a: tandilaitech@gmail.com${NC}"
read -p "   Continuar? (s/n): " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[SsYy]$ ]]; then
    echo "Test cancelado por el usuario."
    exit 0
fi

echo ""
echo "5. Enviando email de prueba..."
echo "   (Ver logs en otra terminal: docker compose logs -f web)"
echo ""

# 5. Enviar test email
TEST_RESPONSE=$(curl -s http://localhost:5000/test-email)
TEST_SUCCESS=$(echo "$TEST_RESPONSE" | jq -r '.success // false' 2>/dev/null)

if [ "$TEST_SUCCESS" = "true" ]; then
    echo -e "${GREEN}✓ Email enviado exitosamente${NC}"
    echo "$TEST_RESPONSE" | jq '.' 2>/dev/null || echo "$TEST_RESPONSE"
    echo ""
    echo -e "${GREEN}Próximos pasos:${NC}"
    echo "1. Revisar logs: docker compose logs --tail=50 web | grep -E 'EMAIL|SMTP'"
    echo "2. Verificar bandeja de entrada de tandilaitech@gmail.com"
    echo "3. Revisar carpeta de spam si no aparece"
else
    echo -e "${RED}✗ Error al enviar email${NC}"
    echo "$TEST_RESPONSE" | jq '.' 2>/dev/null || echo "$TEST_RESPONSE"
    echo ""
    echo -e "${YELLOW}Debugging:${NC}"
    echo "Ver logs completos: docker compose logs --tail=100 web"
    echo "Ver solo SMTP: docker compose logs -f web | grep -E 'send:|reply:|SMTP'"
    exit 1
fi

echo ""
echo "======================================================"
echo "   Test completado"
echo "======================================================"
