# Scaling Guide

## Current Architecture (PASO 4)

**Capacity:** ~10 concurrent clients  
**Hardware:** VPS 2vCPU, 4GB RAM, 100GB NVMe  
**Stack:** Flask + Gunicorn (4 workers) + PostgreSQL + Nginx + SSL

---

## When to Scale

### Metrics to Monitor

| Metric | Warning Threshold | Critical Threshold | Action |
|--------|-------------------|-------------------|--------|
| CPU Usage | > 70% sustained | > 85% sustained | Upgrade CPU or add workers |
| Memory Usage | > 75% | > 90% | Upgrade RAM or optimize queries |
| Disk Usage | > 75% | > 90% | Clean up or upgrade disk |
| Response Time (p95) | > 500ms | > 1000ms | Optimize queries or scale |
| Active Connections (DB) | > 75 | > 95 | Add PgBouncer or scale DB |
| Concurrent Users | > 50 | > 100 | Move to PASO 8 (Redis + replicas) |

### Signs You Need to Scale

1. **Response times increasing:** p95 > 500ms consistently
2. **Database connection pool exhausted:** Connection errors in logs
3. **Memory swapping:** Check `free -h` shows swap usage
4. **Queue depth growing:** Requests waiting for workers
5. **More than 20 active tenants:** Time to implement PASO 6-7

---

## Scaling Paths

### Path 1: Vertical Scaling (Quick Win)

**When:** CPU/Memory at capacity, < 50 users  
**Downtime:** ~5-10 minutes  
**Cost:** +$10-20/month

**Steps:**

1. **Backup database:**
   ```bash
   ./infra/backups/backup_db.sh
   ```

2. **Upgrade VPS plan** (via provider dashboard)
   - 2vCPU → 4vCPU
   - 4GB RAM → 8GB RAM

3. **Adjust Gunicorn workers:**
   ```yaml
   # docker-compose.prod.yml
   command: gunicorn --bind 0.0.0.0:5000 --workers 8 app:app
   ```

4. **Restart services:**
   ```bash
   docker compose -f docker-compose.prod.yml restart web
   ```

**Expected Capacity:** ~20-30 concurrent clients

---

### Path 2: Database Optimization (No Downtime)

**When:** Slow queries, high DB CPU  
**Downtime:** None  
**Cost:** $0

**Steps:**

1. **Analyze slow queries:**
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
   SELECT query, calls, total_time, mean_time
   FROM pg_stat_statements
   ORDER BY total_time DESC
   LIMIT 10;
   "
   ```

2. **Add missing indexes:**
   ```sql
   -- Example: Add index on frequently queried columns
   CREATE INDEX CONCURRENTLY idx_product_tenant_active 
   ON product(tenant_id, active) WHERE active = true;
   ```

3. **Enable query caching** (see PASO 8 for Redis implementation)

4. **Vacuum and analyze:**
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "VACUUM ANALYZE;"
   ```

**Expected Impact:** 30-50% faster queries

---

### Path 3: Object Storage Migration (PASO 7)

**When:** Disk usage > 50%, many product images  
**Downtime:** None (gradual migration)  
**Cost:** +$5/month (DigitalOcean Spaces)

**Implementation:** See `roadmap_paso_5-9_saas_escalable.md` PASO 7

**Benefits:**
- Unlimited image storage
- CDN for faster loading
- Lower VPS disk usage

**Expected Capacity:** No limit on images

---

### Path 4: Horizontal Scaling (PASO 8)

**When:** > 50 concurrent users, vertical scaling maxed out  
**Downtime:** ~30 minutes  
**Cost:** +$50/month (8vCPU, 16GB RAM VPS)

**Architecture:**

```
                 ┌─────────┐
                 │  Nginx  │ (Load Balancer)
                 └────┬────┘
                      │
          ┌───────────┼───────────┐
          │           │           │
      ┌───▼───┐   ┌───▼───┐   ┌───▼───┐
      │ Web 1 │   │ Web 2 │   │ Web 3 │ (3 Flask replicas)
      └───┬───┘   └───┬───┘   └───┬───┘
          │           │           │
          └───────────┼───────────┘
                      │
              ┌───────▼──────┐
              │  PgBouncer   │ (Connection pooling)
              └───────┬──────┘
                      │
              ┌───────▼──────┐
              │ PostgreSQL   │
              └──────────────┘
                      │
              ┌───────▼──────┐
              │    Redis     │ (Sessions + Cache)
              └──────────────┘
```

**Key Changes:**

1. **Add Redis for sessions:**
   - Stateless app (no sticky sessions needed)
   - Shared session storage

2. **Add PgBouncer:**
   - Connection pooling
   - Handle 1000+ connections

3. **Multiple web replicas:**
   - 3 Flask instances
   - Load balanced by Nginx

**Implementation:** See `roadmap_paso_5-9_saas_escalable.md` PASO 8

**Expected Capacity:** 100-500 concurrent clients

---

### Path 5: Database Scaling

**When:** Database CPU > 80%, queries still slow after optimization  
**Downtime:** ~1 hour  
**Cost:** +$50-100/month

**Options:**

#### Option A: Managed PostgreSQL (Recommended)
- **Provider:** DigitalOcean Managed Database, AWS RDS, etc.
- **Benefits:** Automatic backups, scaling, HA
- **Cost:** $15-100/month depending on size

**Steps:**
1. Provision managed database
2. Migrate data: `pg_dump | pg_restore`
3. Update `DATABASE_URL` in `.env.prod`
4. Restart services

#### Option B: Read Replicas
- **When:** Read-heavy workload
- **Setup:** Primary (writes) + 1-2 replicas (reads)
- **Code changes:** Route read queries to replicas

#### Option C: Separate Database Server
- **Setup:** Move PostgreSQL to dedicated VPS
- **Benefits:** Isolate resources
- **Cost:** +$12-24/month

---

## Scaling Roadmap by Tenant Count

| Tenants | Concurrent Users | Architecture | Monthly Cost | Implementation |
|---------|------------------|--------------|--------------|----------------|
| 1-10 | 5-10 | Current (PASO 4) | $12 | ✓ Done |
| 10-20 | 10-30 | Vertical scale 4vCPU/8GB | $24 | Resize VPS |
| 20-50 | 30-100 | + Object Storage (PASO 7) | $44 | Follow PASO 7 |
| 50-100 | 100-300 | + Redis + Replicas (PASO 8) | $105 | Follow PASO 8 |
| 100-500 | 300-1000 | + Managed DB + CDN | $200 | Follow PASO 9 |
| 500+ | 1000+ | Cloud auto-scaling | $300+ | Kubernetes/Cloud |

---

## Quick Scaling Actions

### Emergency: Site Slow Right Now

1. **Restart services:**
   ```bash
   docker compose -f docker-compose.prod.yml restart web
   ```

2. **Clear old Docker resources:**
   ```bash
   docker system prune -f
   ```

3. **Check for long-running queries:**
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
   SELECT pg_terminate_backend(pid)
   FROM pg_stat_activity
   WHERE state = 'active' AND now() - query_start > interval '1 minute';
   "
   ```

4. **Reduce Gunicorn workers temporarily:**
   ```yaml
   # docker-compose.prod.yml
   command: gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
   ```

### This Week: Planning to Add 10 New Tenants

1. **Verify current capacity:**
   ```bash
   docker stats --no-stream
   free -h
   df -h
   ```

2. **If CPU > 60% or RAM > 70%:**
   - Upgrade VPS plan

3. **If Disk > 60%:**
   - Clean up old backups
   - Or implement PASO 7 (Object Storage)

4. **Load test before onboarding:**
   ```bash
   # Use Apache Bench or similar
   ab -n 1000 -c 10 https://tandil.site/
   ```

---

## Cost Optimization

### When You're Under-Utilized

**Signs:**
- CPU < 30% consistently
- RAM < 50% consistently
- < 5 active tenants

**Actions:**
1. **Downgrade VPS plan** (save $10-20/month)
2. **Reduce Gunicorn workers:**
   ```yaml
   command: gunicorn --bind 0.0.0.0:5000 --workers 2 app:app
   ```

### When You're Over-Provisioned

- **Object Storage:** Only pay for what you use
- **Managed DB:** Pause development instances
- **CDN:** Caching reduces bandwidth costs

---

## Monitoring for Scaling Decisions

### Key Metrics to Track

```bash
# CPU/Memory/Disk (run daily)
docker stats --no-stream
free -h
df -h

# Database stats
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
SELECT count(*) as connections, state
FROM pg_stat_activity
GROUP BY state;
"

# Response times (from logs)
docker compose -f docker-compose.prod.yml logs web | grep "ms" | tail -100
```

### Set Up Alerts (PASO 9)

When implementing PASO 9 (Observability), set up alerts for:
- CPU > 80% for 5 minutes
- Memory > 85%
- Disk > 90%
- Response time p95 > 1000ms
- Error rate > 1%

---

## Decision Tree

```
Start: Performance issue?
│
├─ Yes → What's the bottleneck?
│   │
│   ├─ CPU → Vertical scale (4vCPU) or add workers
│   ├─ Memory → Vertical scale (8GB) or optimize code
│   ├─ Disk → Clean up or Object Storage (PASO 7)
│   ├─ Database → Optimize queries or Managed DB
│   └─ All good but slow → Horizontal scale (PASO 8)
│
└─ No → Planning for growth?
    │
    ├─ < 20 tenants → Stay on current setup
    ├─ 20-50 tenants → Implement PASO 7 (Object Storage)
    ├─ 50-100 tenants → Implement PASO 8 (Redis + Replicas)
    └─ 100+ tenants → Implement PASO 9 (Full observability + managed services)
```

---

## Next Steps

1. **Track your metrics** (CPU, Memory, Disk, Response Time)
2. **Set a growth target** (e.g., "We want to support 30 tenants")
3. **Follow the scaling path** that matches your target
4. **Test before production** (load test, staging environment)
5. **Monitor after scaling** (verify improvements)

---

**Last Updated:** 2026-01-20  
**Version:** 1.0.0
