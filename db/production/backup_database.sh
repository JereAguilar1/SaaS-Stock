#!/bin/bash
# ============================================================================
# Sistema Ferretería - Script de Backup de Base de Datos
# ============================================================================
# Versión: 1.0
# Fecha: Enero 2026
# Uso: ./backup_database.sh
# ============================================================================

# Configuración
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-ferreteria}"
DB_USER="${DB_USER:-ferreteria}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/ferreteria_backup_${DATE}.sql"
BACKUP_FILE_COMPRESSED="${BACKUP_FILE}.gz"

# Crear directorio de backups si no existe
mkdir -p "$BACKUP_DIR"

echo "============================================"
echo "Backup de Base de Datos - Sistema Ferretería"
echo "============================================"
echo "Fecha: $(date)"
echo "Base de datos: ${DB_NAME}"
echo "Host: ${DB_HOST}:${DB_PORT}"
echo "Usuario: ${DB_USER}"
echo "Archivo: ${BACKUP_FILE_COMPRESSED}"
echo "============================================"
echo ""

# Realizar backup
echo "Iniciando backup..."
PGPASSWORD="${DB_PASSWORD}" pg_dump \
  -h "$DB_HOST" \
  -p "$DB_PORT" \
  -U "$DB_USER" \
  -d "$DB_NAME" \
  --format=plain \
  --no-owner \
  --no-acl \
  --verbose \
  > "$BACKUP_FILE" 2>&1

# Verificar si el backup fue exitoso
if [ $? -eq 0 ]; then
  echo ""
  echo "✓ Backup completado exitosamente"
  
  # Comprimir backup
  echo "Comprimiendo backup..."
  gzip "$BACKUP_FILE"
  
  if [ $? -eq 0 ]; then
    echo "✓ Backup comprimido: ${BACKUP_FILE_COMPRESSED}"
    
    # Mostrar tamaño
    SIZE=$(du -h "$BACKUP_FILE_COMPRESSED" | cut -f1)
    echo "Tamaño: $SIZE"
    
    # Limpiar backups antiguos (mantener últimos 30 días)
    echo ""
    echo "Limpiando backups antiguos (>30 días)..."
    find "$BACKUP_DIR" -name "ferreteria_backup_*.sql.gz" -mtime +30 -delete
    
    # Contar backups restantes
    BACKUP_COUNT=$(find "$BACKUP_DIR" -name "ferreteria_backup_*.sql.gz" | wc -l)
    echo "Backups disponibles: $BACKUP_COUNT"
    
  else
    echo "✗ Error al comprimir backup"
    exit 1
  fi
else
  echo ""
  echo "✗ Error al realizar backup"
  exit 1
fi

echo ""
echo "============================================"
echo "Backup completado"
echo "============================================"
