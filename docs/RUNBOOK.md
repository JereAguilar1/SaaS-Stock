# Runbook - Operational Procedures

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Deployment](#deployment)
3. [Rollback](#rollback)
4. [Monitoring & Health Checks](#monitoring--health-checks)
5. [Backup & Restore](#backup--restore)
6. [Troubleshooting](#troubleshooting)
7. [Maintenance](#maintenance)

---

## Daily Operations

### Check System Health

```bash
# SSH to VPS
ssh root@tandil.site

# Check all services
cd /root/ferreteria
docker compose -f docker-compose.prod.yml ps

# Check logs
docker compose -f docker-compose.prod.yml logs --tail=50 web
docker compose -f docker-compose.prod.yml logs --tail=50 db

# Check health endpoint
curl https://tandil.site/health
```

### Monitor Resource Usage

```bash
# Check disk space
df -h

# Check memory usage
free -h

# Check Docker stats
docker stats --no-stream

# Check PostgreSQL connections
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "SELECT count(*) FROM pg_stat_activity;"
```

### View Active Tenants

```bash
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "SELECT id, slug, name, active, created_at FROM tenant ORDER BY created_at DESC LIMIT 10;"
```

---

## Deployment

### Standard Deployment (Automated via GitHub Actions)

1. Create and push a tag:
   ```bash
   git tag -a v1.2.3 -m "Release v1.2.3: Description"
   git push origin v1.2.3
   ```

2. GitHub Actions will automatically:
   - Run CI pipeline (tests, linting)
   - Backup database
   - Deploy to production
   - Run health checks
   - Rollback if health checks fail

3. Monitor deployment:
   - Go to GitHub Actions tab
   - Watch the "Deploy to Production" workflow

### Manual Deployment (Emergency)

```bash
ssh root@tandil.site
cd /root/ferreteria

# Run deployment script
./infra/scripts/deploy.sh [branch/tag]

# Or deploy specific version
git checkout v1.2.3
./infra/scripts/deploy.sh
```

### Deploy with Database Migrations

```bash
# SSH to VPS
cd /root/ferreteria

# Create migration (if needed)
docker compose -f docker-compose.prod.yml exec web alembic revision --autogenerate -m "description"

# Review migration file in alembic/versions/

# Apply migration
docker compose -f docker-compose.prod.yml exec web alembic upgrade head

# Restart services
docker compose -f docker-compose.prod.yml restart web
```

---

## Rollback

### Automatic Rollback

GitHub Actions will automatically rollback if health checks fail after deployment.

### Manual Rollback

```bash
ssh root@tandil.site
cd /root/ferreteria

# Run rollback script
./infra/scripts/rollback.sh

# This will:
# - Checkout previous version
# - Rebuild Docker image
# - Restart services
# - Run health check
```

### Rollback Database Migration

```bash
# Rollback last migration
docker compose -f docker-compose.prod.yml exec web alembic downgrade -1

# Rollback to specific version
docker compose -f docker-compose.prod.yml exec web alembic downgrade <revision_id>
```

---

## Monitoring & Health Checks

### Application Health

```bash
# Check health endpoint
curl https://tandil.site/health

# Expected response:
# {"status":"healthy","database":"connected","message":"Database connection successful"}
```

### Database Health

```bash
docker compose -f docker-compose.prod.yml exec db pg_isready -U ferreteria_user

# Check active connections
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
SELECT 
    count(*) as total,
    count(*) FILTER (WHERE state = 'active') as active,
    count(*) FILTER (WHERE state = 'idle') as idle
FROM pg_stat_activity 
WHERE datname = 'ferreteria_db';
"
```

### Nginx Health

```bash
# Check Nginx status
docker compose -f docker-compose.prod.yml exec nginx nginx -t

# Check access logs
docker compose -f docker-compose.prod.yml logs nginx | tail -100

# Check error logs
docker compose -f docker-compose.prod.yml exec nginx cat /var/log/nginx/error.log | tail -50
```

### SSL Certificate Health

```bash
# Check certificate expiration
echo | openssl s_client -servername tandil.site -connect tandil.site:443 2>/dev/null | openssl x509 -noout -dates

# Renew certificate manually
docker compose -f docker-compose.prod.yml run --rm certbot renew
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Backup & Restore

### Manual Backup

```bash
cd /root/ferreteria
./infra/backups/backup_db.sh
```

### Verify Backups

```bash
# List recent backups
ls -lht /var/backups/ferreteria/daily/*.sql.gz | head -10

# Check latest backup integrity
LATEST=$(ls -t /var/backups/ferreteria/daily/*.sql.gz | head -1)
gunzip -t $LATEST && echo "✓ Backup integrity OK"
```

### Restore from Backup

```bash
cd /root/ferreteria

# IMPORTANT: This will overwrite current database!
# Stop web service first
docker compose -f docker-compose.prod.yml stop web

# Restore
./infra/backups/restore_db.sh /var/backups/ferreteria/daily/ferreteria_YYYY-MM-DD_HHMMSS.sql.gz

# Start web service
docker compose -f docker-compose.prod.yml start web
```

### Backup Rotation

Backups are automatically rotated (30-day retention) by the backup script.

Manual cleanup:
```bash
# Delete backups older than 30 days
find /var/backups/ferreteria/daily -name "*.sql.gz" -mtime +30 -delete
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs --tail=100 web

# Common issues:
# 1. Database connection error -> Check DATABASE_URL in .env.prod
# 2. Port already in use -> Check if old containers running
# 3. Missing environment variables -> Check .env.prod exists

# Restart all services
docker compose -f docker-compose.prod.yml restart
```

### Database Connection Issues

```bash
# Check database is running
docker compose -f docker-compose.prod.yml ps db

# Check database logs
docker compose -f docker-compose.prod.yml logs db --tail=100

# Test connection
docker compose -f docker-compose.prod.yml exec web python -c "
from app.database import get_session
session = get_session()
print('✓ Database connection OK')
"
```

### High Memory Usage

```bash
# Check memory per container
docker stats --no-stream

# Restart services to free memory
docker compose -f docker-compose.prod.yml restart web

# Increase Gunicorn workers if needed
# Edit docker-compose.prod.yml: gunicorn --workers=2 (reduce from 4)
```

### Slow Response Times

```bash
# Check database query performance
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE state = 'active' AND now() - pg_stat_activity.query_start > interval '1 second'
ORDER BY duration DESC;
"

# Check for missing indexes
# Review logs for slow queries
docker compose -f docker-compose.prod.yml logs web | grep "slow"
```

### 502 Bad Gateway

```bash
# Web service is down or not responding
docker compose -f docker-compose.prod.yml ps web

# Restart web service
docker compose -f docker-compose.prod.yml restart web

# Check Nginx can reach web
docker compose -f docker-compose.prod.yml exec nginx ping -c 3 web
```

### SSL Certificate Issues

```bash
# Certificate expired or invalid
docker compose -f docker-compose.prod.yml run --rm certbot renew --dry-run

# Force renewal
docker compose -f docker-compose.prod.yml run --rm certbot renew --force-renewal

# Reload Nginx
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

---

## Maintenance

### Update System Packages

```bash
# Update VPS system packages
apt update && apt upgrade -y

# Reboot if kernel updated
reboot
```

### Update Docker Images

```bash
cd /root/ferreteria

# Pull latest base images
docker compose -f docker-compose.prod.yml pull

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build
```

### Clean Up Docker Resources

```bash
# Remove unused images
docker image prune -a -f

# Remove unused volumes
docker volume prune -f

# Remove unused networks
docker network prune -f

# Full cleanup (use with caution)
docker system prune -a --volumes -f
```

### Database Maintenance

```bash
# Vacuum and analyze
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "VACUUM ANALYZE;"

# Check database size
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
SELECT pg_size_pretty(pg_database_size('ferreteria_db'));
"

# Check table sizes
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"
```

### Rotate Logs

```bash
# Docker logs are automatically rotated by Docker daemon
# Manual cleanup if needed:
docker compose -f docker-compose.prod.yml logs --tail=0 > /dev/null

# Nginx logs
docker compose -f docker-compose.prod.yml exec nginx sh -c "echo '' > /var/log/nginx/access.log"
docker compose -f docker-compose.prod.yml exec nginx sh -c "echo '' > /var/log/nginx/error.log"
```

---

## Emergency Contacts

- **Primary Admin:** [Your Email]
- **On-Call:** [Phone Number]
- **Sentry Alerts:** [Sentry Project URL]
- **GitHub Repository:** [Repository URL]

---

## Quick Reference

| Task | Command |
|------|---------|
| Check health | `curl https://tandil.site/health` |
| View logs | `docker compose -f docker-compose.prod.yml logs -f web` |
| Restart app | `docker compose -f docker-compose.prod.yml restart web` |
| Backup DB | `./infra/backups/backup_db.sh` |
| Restore DB | `./infra/backups/restore_db.sh [file]` |
| Deploy | `./infra/scripts/deploy.sh [tag]` |
| Rollback | `./infra/scripts/rollback.sh` |

---

**Last Updated:** 2026-01-20  
**Version:** 1.0.0
