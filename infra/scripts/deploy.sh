#!/bin/bash
# ============================================
# Production Deployment Script
# ============================================
# This script handles zero-downtime deployment to production

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

log "=== Starting Deployment ==="

# Step 1: Pull latest code
log "Pulling latest code..."
git fetch --all --tags
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
log "Current branch: $CURRENT_BRANCH"

if [ -n "${1:-}" ]; then
    log "Checking out: $1"
    git checkout "$1"
else
    log "Pulling latest changes for $CURRENT_BRANCH"
    git pull origin "$CURRENT_BRANCH"
fi

# Step 2: Check for database migrations
log "Checking for database migrations..."
if [ -d "alembic/versions" ] && [ "$(ls -A alembic/versions/*.py 2>/dev/null | wc -l)" -gt 0 ]; then
    log "Running database migrations..."
    docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" alembic upgrade head || {
        warning "Migration failed or not configured yet. Continuing..."
    }
else
    log "No Alembic migrations found, skipping..."
fi

# Step 3: Build new Docker image
log "Building Docker image..."
docker compose -f "$COMPOSE_FILE" build "$SERVICE_NAME" || {
    error "Docker build failed"
    exit 1
}

# Step 4: Zero-downtime restart
log "Restarting service with zero downtime..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps --build "$SERVICE_NAME" || {
    error "Service restart failed"
    exit 1
}

# Step 5: Wait for service to be ready
log "Waiting for service to stabilize..."
sleep 10

# Step 6: Health check
log "Running health check..."
MAX_RETRIES=5
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker compose -f "$COMPOSE_FILE" exec -T "$SERVICE_NAME" wget --spider --quiet http://localhost:5000/health; then
        log "✓ Health check passed!"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        warning "Health check failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
        
        if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
            error "Health check failed after $MAX_RETRIES attempts"
            log "Rolling back..."
            ./infra/scripts/rollback.sh
            exit 1
        fi
        
        sleep 5
    fi
done

# Step 7: Cleanup old images
log "Cleaning up old Docker images..."
docker image prune -f || warning "Failed to prune images"

log "=== Deployment Completed Successfully ==="
log "Application is running and healthy"

# Display running containers
log "Running containers:"
docker compose -f "$COMPOSE_FILE" ps

exit 0
