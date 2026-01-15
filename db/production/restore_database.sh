#!/bin/bash
# ============================================================================
# Sistema Ferretería - Script de Restore de Base de Datos
# ============================================================================
# Versión: 1.0
# Fecha: Enero 2026
# Uso: ./restore_database.sh <archivo_backup.sql.gz>
# ============================================================================

# Verificar que se proporcione archivo de backup
if [ -z "$1" ]; then
  echo "Error: Debe proporcionar un archivo de backup"
  echo "Uso: ./restore_database.sh <archivo_backup.sql.gz>"
  echo ""
  echo "Backups disponibles:"
  find ./backups -name "ferreteria_backup_*.sql.gz" -type f | sort -r | head -10
  exit 1
fi

BACKUP_FILE="$1"

# Verificar que el archivo existe
if [ ! -f "$BACKUP_FILE" ]; then
  echo "Error: El archivo $BACKUP_FILE no existe"
  exit 1
fi

# Configuración
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-ferreteria}"
DB_USER="${DB_USER:-ferreteria}"

echo "============================================"
echo "Restore de Base de Datos - Sistema Ferretería"
echo "============================================"
echo "ADVERTENCIA: Esta operación eliminará todos"
echo "los datos actuales de la base de datos"
echo "============================================"
echo "Fecha: $(date)"
echo "Base de datos: ${DB_NAME}"
echo "Host: ${DB_HOST}:${DB_PORT}"
echo "Usuario: ${DB_USER}"
echo "Archivo: ${BACKUP_FILE}"
echo "============================================"
echo ""

# Confirmación
read -p "¿Está seguro de que desea continuar? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
  echo "Operación cancelada"
  exit 0
fi

echo ""
echo "Iniciando restore..."

# Descomprimir si es necesario
if [[ "$BACKUP_FILE" == *.gz ]]; then
  echo "Descomprimiendo backup..."
  TEMP_FILE="${BACKUP_FILE%.gz}"
  gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
  RESTORE_FILE="$TEMP_FILE"
else
  RESTORE_FILE="$BACKUP_FILE"
fi

# Eliminar conexiones activas
echo "Cerrando conexiones activas..."
PGPASSWORD="${DB_PASSWORD}" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '${DB_NAME}' AND pid <> pg_backend_pid();" \
  > /dev/null 2>&1

# Eliminar y recrear base de datos
echo "Recreando base de datos..."
PGPASSWORD="${DB_PASSWORD}" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "DROP DATABASE IF EXISTS ${DB_NAME};" \
  > /dev/null 2>&1

PGPASSWORD="${DB_PASSWORD}" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d postgres \
  -c "CREATE DATABASE ${DB_NAME};" \
  > /dev/null 2>&1

# Restaurar backup
echo "Restaurando datos..."
PGPASSWORD="${DB_PASSWORD}" psql \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --quiet \
  < "$RESTORE_FILE"

# Verificar si el restore fue exitoso
if [ $? -eq 0 ]; then
  echo ""
  echo "✓ Restore completado exitosamente"
  
  # Limpiar archivo temporal si se descomprimió
  if [[ "$BACKUP_FILE" == *.gz ]] && [ -f "$TEMP_FILE" ]; then
    rm "$TEMP_FILE"
  fi
  
  # Verificar datos
  echo ""
  echo "Verificando datos restaurados..."
  PGPASSWORD="${DB_PASSWORD}" psql \
    -h "$DB_HOST" \
    -p "$DB_PORT" \
    -U "$DB_USER" \
    -d "$DB_NAME" \
    -c "SELECT 'Productos:' as tabla, COUNT(*) as registros FROM product UNION ALL SELECT 'Categorías:', COUNT(*) FROM category UNION ALL SELECT 'UOMs:', COUNT(*) FROM uom UNION ALL SELECT 'Ventas:', COUNT(*) FROM sale UNION ALL SELECT 'Boletas:', COUNT(*) FROM purchase_invoice;"
  
else
  echo ""
  echo "✗ Error al restaurar backup"
  
  # Limpiar archivo temporal si se descomprimió
  if [[ "$BACKUP_FILE" == *.gz ]] && [ -f "$TEMP_FILE" ]; then
    rm "$TEMP_FILE"
  fi
  
  exit 1
fi

echo ""
echo "============================================"
echo "Restore completado"
echo "============================================"
