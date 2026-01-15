#!/bin/bash
# ============================================
# PostgreSQL Restore Script for Ferretería SaaS
# ============================================
# This script restores a PostgreSQL database from a backup file.
# WARNING: This will DROP and RECREATE the database!

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Usage information
usage() {
    echo "Usage: $0 <backup_file.sql.gz>"
    echo ""
    echo "Example:"
    echo "  $0 /var/backups/ferreteria/daily/ferreteria_2026-01-14_030000.sql.gz"
    echo ""
    echo "To list available backups:"
    echo "  ls -lh /var/backups/ferreteria/daily/"
    exit 1
}

# Check if backup file is provided
if [ $# -ne 1 ]; then
    error "Backup file not specified"
    usage
fi

BACKUP_FILE="$1"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"

# Validate backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    error "Backup file does not exist: ${BACKUP_FILE}"
    exit 1
fi

# Validate backup file is not empty
if [ ! -s "${BACKUP_FILE}" ]; then
    error "Backup file is empty: ${BACKUP_FILE}"
    exit 1
fi

# Check if docker-compose is available
if ! command -v docker &> /dev/null; then
    error "Docker is not installed or not in PATH"
    exit 1
fi

# Get database credentials
POSTGRES_DB=$(grep POSTGRES_DB .env.prod 2>/dev/null | cut -d '=' -f2 | tr -d ' "' || echo "ferreteria_db")
POSTGRES_USER=$(grep POSTGRES_USER .env.prod 2>/dev/null | cut -d '=' -f2 | tr -d ' "' || echo "ferreteria_user")

log "============================================"
log "PostgreSQL Database Restore"
log "============================================"
log "Backup file: ${BACKUP_FILE}"
log "Database: ${POSTGRES_DB}"
log "User: ${POSTGRES_USER}"
log "============================================"

warning "This will DROP and RECREATE the database!"
warning "All current data will be LOST!"
echo ""

# Confirmation prompt
read -p "Are you sure you want to continue? Type 'YES' to confirm: " CONFIRM

if [ "${CONFIRM}" != "YES" ]; then
    log "Restore cancelled by user"
    exit 0
fi

log "Starting database restore..."

# Step 1: Stop the web service to prevent connections
log "Stopping web service..."
if docker compose -f "${COMPOSE_FILE}" stop web; then
    log "Web service stopped"
else
    warning "Failed to stop web service (it may not be running)"
fi

# Step 2: Wait a moment for connections to close
sleep 2

# Step 3: Restore the database
log "Restoring database from backup..."

if gunzip -c "${BACKUP_FILE}" | docker compose -f "${COMPOSE_FILE}" exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" > /tmp/restore_output.log 2>&1; then
    log "Database restored successfully!"
else
    error "Database restore failed! Check /tmp/restore_output.log for details"
    log "Restarting web service..."
    docker compose -f "${COMPOSE_FILE}" start web
    exit 1
fi

# Step 4: Restart the web service
log "Restarting web service..."
if docker compose -f "${COMPOSE_FILE}" start web; then
    log "Web service restarted"
else
    error "Failed to restart web service!"
    exit 1
fi

# Step 5: Verify database connection
log "Verifying database connection..."
sleep 3

if docker compose -f "${COMPOSE_FILE}" exec -T db psql -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -c "SELECT COUNT(*) FROM tenant;" > /dev/null 2>&1; then
    log "Database connection verified!"
else
    warning "Could not verify database connection. Please check manually."
fi

log "============================================"
log "Restore process completed successfully!"
log "============================================"
log "Please verify your application is working correctly."
exit 0
