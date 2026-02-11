#!/bin/bash
# ============================================
# PostgreSQL Backup Script for SaaS Comercial
# ============================================
# This script creates a compressed backup of the PostgreSQL database
# and maintains a rolling retention policy.

set -euo pipefail

# Configuration
APP_NAME="${APP_NAME:-ferreteria}"
BACKUP_DIR="${BACKUP_PATH:-/var/backups/${APP_NAME}}"
DAILY_DIR="${BACKUP_DIR}/daily"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")
BACKUP_FILE="${DAILY_DIR}/${APP_NAME}_${TIMESTAMP}.sql.gz"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Create backup directory if it doesn't exist
mkdir -p "${DAILY_DIR}"

# Check if docker-compose is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not in PATH"
    exit 1
fi

log "Starting PostgreSQL backup..."
log "Backup file: ${BACKUP_FILE}"

# Get database credentials from .env.prod or docker-compose
POSTGRES_DB=$(grep POSTGRES_DB .env.prod 2>/dev/null | cut -d '=' -f2 | tr -d ' "' || echo "ferreteria_db")
POSTGRES_USER=$(grep POSTGRES_USER .env.prod 2>/dev/null | cut -d '=' -f2 | tr -d ' "' || echo "ferreteria_user")

log "Database: ${POSTGRES_DB}, User: ${POSTGRES_USER}"

# Perform backup using pg_dump via docker
if docker compose -f "${COMPOSE_FILE}" exec -T db pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --no-owner --no-acl --clean --if-exists | gzip > "${BACKUP_FILE}"; then
    BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
    log "Backup completed successfully! Size: ${BACKUP_SIZE}"
else
    error "Backup failed!"
    # Remove incomplete backup file
    rm -f "${BACKUP_FILE}"
    exit 1
fi

# Verify backup file is not empty
if [ ! -s "${BACKUP_FILE}" ]; then
    error "Backup file is empty!"
    rm -f "${BACKUP_FILE}"
    exit 1
fi

log "Backup file created: ${BACKUP_FILE}"

# Apply retention policy - delete backups older than RETENTION_DAYS
log "Applying retention policy (keeping last ${RETENTION_DAYS} days)..."
DELETED_COUNT=0

find "${DAILY_DIR}" -name "${APP_NAME}_*.sql.gz" -type f -mtime +${RETENTION_DAYS} | while read -r old_backup; do
    log "Deleting old backup: $(basename ${old_backup})"
    rm -f "${old_backup}"
    ((DELETED_COUNT++))
done

if [ ${DELETED_COUNT} -gt 0 ]; then
    log "Deleted ${DELETED_COUNT} old backup(s)"
else
    log "No old backups to delete"
fi

# Count remaining backups
BACKUP_COUNT=$(find "${DAILY_DIR}" -name "${APP_NAME}_*.sql.gz" -type f | wc -l)
log "Total backups in ${DAILY_DIR}: ${BACKUP_COUNT}"

# List 5 most recent backups
log "Most recent backups:"
find "${DAILY_DIR}" -name "${APP_NAME}_*.sql.gz" -type f -printf '%T@ %p\n' | sort -rn | head -5 | while read -r timestamp filepath; do
    filesize=$(du -h "${filepath}" | cut -f1)
    filename=$(basename "${filepath}")
    filedate=$(date -d @"${timestamp%.*}" '+%Y-%m-%d %H:%M:%S')
    log "  ${filename} (${filesize}, ${filedate})"
done

log "Backup process completed successfully!"
exit 0
