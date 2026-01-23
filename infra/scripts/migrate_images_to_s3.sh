#!/bin/bash
#
# PASO 7: Script de Migración de Imágenes (Filesystem → MinIO/S3)
#
# Este script copia todas las imágenes de productos desde el filesystem local
# a MinIO/S3, manteniendo la estructura de directorios por tenant.
#
# PREREQUISITOS:
# 1. MinIO/S3 debe estar corriendo
# 2. aws-cli instalado (o mc - MinIO Client)
# 3. Variables S3_* configuradas en .env
#
# USO:
#   ./infra/scripts/migrate_images_to_s3.sh
#

set -e

echo "================================================"
echo "PASO 7: Migración de Imágenes a S3/MinIO"
echo "================================================"
echo ""

# Configuración (leer de .env o usar defaults)
SOURCE_DIR="${SOURCE_DIR:-app/static/uploads/products}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:9000}"
S3_BUCKET="${S3_BUCKET:-uploads}"
S3_ACCESS_KEY="${S3_ACCESS_KEY:-minioadmin}"
S3_SECRET_KEY="${S3_SECRET_KEY:-minioadmin}"
DEFAULT_TENANT_ID="${DEFAULT_TENANT_ID:-1}"

# Verificar si existe directorio fuente
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Directorio fuente no existe: $SOURCE_DIR"
    echo "   No hay imágenes para migrar (normal si nunca se subieron archivos)."
    exit 0
fi

# Contar archivos
FILE_COUNT=$(find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" \) | wc -l)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "ℹ️  No se encontraron imágenes para migrar."
    exit 0
fi

echo "📁 Directorio fuente: $SOURCE_DIR"
echo "🗂️  Archivos encontrados: $FILE_COUNT"
echo "📦 Bucket destino: $S3_BUCKET"
echo "🌐 Endpoint: $S3_ENDPOINT"
echo ""

# Preguntar confirmación
read -p "¿Continuar con la migración? (y/n): " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Migración cancelada."
    exit 0
fi

# Migración usando AWS CLI (compatible con MinIO)
echo ""
echo "Iniciando migración..."
echo ""

MIGRATED=0
FAILED=0

# Configurar AWS CLI para MinIO
export AWS_ACCESS_KEY_ID="$S3_ACCESS_KEY"
export AWS_SECRET_ACCESS_KEY="$S3_SECRET_KEY"
export AWS_ENDPOINT_URL="$S3_ENDPOINT"

# Migrar cada archivo
find "$SOURCE_DIR" -type f \( -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.png" -o -iname "*.gif" \) | while read filepath; do
    filename=$(basename "$filepath")
    
    # Construir S3 key: products/tenant_1/filename
    s3_key="products/tenant_${DEFAULT_TENANT_ID}/${filename}"
    
    # Detectar content-type
    case "${filepath##*.}" in
        jpg|jpeg|JPG|JPEG)
            content_type="image/jpeg"
            ;;
        png|PNG)
            content_type="image/png"
            ;;
        gif|GIF)
            content_type="image/gif"
            ;;
        *)
            content_type="application/octet-stream"
            ;;
    esac
    
    echo "Migrando: $filename → s3://$S3_BUCKET/$s3_key"
    
    # Upload usando aws s3 cp
    if aws s3 cp "$filepath" "s3://$S3_BUCKET/$s3_key" \
        --endpoint-url="$S3_ENDPOINT" \
        --content-type="$content_type" \
        --acl public-read \
        2>/dev/null; then
        
        echo "  ✓ Migrado exitosamente"
        ((MIGRATED++))
    else
        echo "  ✗ Error al migrar"
        ((FAILED++))
    fi
done

echo ""
echo "================================================"
echo "RESUMEN DE MIGRACIÓN"
echo "================================================"
echo ""
echo "Archivos migrados: $MIGRATED"
echo "Errores: $FAILED"
echo ""

if [ "$FAILED" -eq 0 ]; then
    echo "✅ Migración completada exitosamente"
    echo ""
    echo "Próximos pasos:"
    echo "1. Ejecutar SQL: db/migrations/PASO7_migrate_image_paths.sql"
    echo "2. Verificar imágenes en MinIO Console: http://localhost:9001"
    echo "3. Probar carga de productos con imágenes"
    echo "4. Opcional: Hacer backup de $SOURCE_DIR"
    echo "5. Opcional: Eliminar $SOURCE_DIR después de verificar"
    echo ""
else
    echo "⚠️  Migración completada con errores"
    echo ""
    echo "Revisar archivos fallidos y reintentar."
fi
