#!/bin/bash
# ============================================
# Production Rollback Script
# ============================================
# This script rolls back to the previous version

set -euo pipefail

# Configuration
APP_DIR="${APP_DIR:-/root/ferreteria}"
COMPOSE_FILE="docker-compose.prod.yml"
SERVICE_NAME="web"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0;0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR:${NC} $1" >&2
}

warning() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING:${NC} $1"
}

# Change to app directory
cd "$APP_DIR" || {
    error "Failed to change to app directory: $APP_DIR"
    exit 1
}

log "=== Starting Rollback ==="

# Get current commit/tag
CURRENT_REF=$(git describe --tags --exact-match 2>/dev/null || git rev-parse --short HEAD)
log "Current reference: $CURRENT_REF"

# Get previous tag or commit
PREVIOUS_TAG=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "")

if [ -z "$PREVIOUS_TAG" ]; then
    # No previous tag, go back one commit
    PREVIOUS_REF=$(git rev-parse HEAD^)
    log "No previous tag found, rolling back to commit: $PREVIOUS_REF"
else
    PREVIOUS_REF="$PREVIOUS_TAG"
    log "Rolling back to previous tag: $PREVIOUS_TAG"
fi

# Checkout previous version
log "Checking out: $PREVIOUS_REF"
git checkout "$PREVIOUS_REF" || {
    error "Failed to checkout $PREVIOUS_REF"
    exit 1
}

# Rollback database migrations if Alembic is configured
if [ -d "alembic" ] && [ -f "alembic.ini" ]; then
    warning "Database rollback must be done manually if schema changed"
    warning "Run: docker compose -f $COMPOSE_FILE exec $SERVICE_NAME alembic downgrade -1"
fi

# Rebuild and restart service
log "Rebuilding Docker image..."
docker compose -f "$COMPOSE_FILE" build "$SERVICE_NAME" || {
    error "Docker build failed"
    exit 1
}

log "Restarting service..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps "$SERVICE_NAME" || {
    error "Service restart failed"
    exit 1
}

# Wait for service
log "Waiting for service to stabilize..."
sleep 10

# Health check
log "Running health check..."
if docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" wget --spider --quiet http://localhost:5000/health; then
    log "✓ Rollback successful! Service is healthy."
else
    error "✗ Health check failed after rollback"
    exit 1
fi

log "=== Rollback Completed ==="
log "Rolled back from $CURRENT_REF to $PREVIOUS_REF"

exit 0
