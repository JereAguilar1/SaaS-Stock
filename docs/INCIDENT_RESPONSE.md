# Incident Response Guide

## Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| **P1 - Critical** | Complete outage, data loss | Immediate | Notify all stakeholders |
| **P2 - High** | Major feature broken, performance degraded | < 30 min | Notify on-call engineer |
| **P3 - Medium** | Minor feature issue, workaround available | < 2 hours | Can wait for business hours |
| **P4 - Low** | Cosmetic issue, no impact | Next sprint | Log for backlog |

---

## P1 - Critical Incidents

### Complete Site Down

**Symptoms:**
- `https://tandil.site` returns 502/503/504
- Health check fails
- No response from server

**Immediate Actions:**

1. **Verify the issue:**
   ```bash
   curl -I https://tandil.site
   curl https://tandil.site/health
   ```

2. **SSH to VPS:**
   ```bash
   ssh root@tandil.site
   cd /root/ferreteria
   ```

3. **Check all services:**
   ```bash
   docker compose -f docker-compose.prod.yml ps
   ```

4. **Check logs:**
   ```bash
   docker compose -f docker-compose.prod.yml logs --tail=100 web
   docker compose -f docker-compose.prod.yml logs --tail=100 db
   docker compose -f docker-compose.prod.yml logs --tail=100 nginx
   ```

5. **Quick fix - Restart all services:**
   ```bash
   docker compose -f docker-compose.prod.yml restart
   ```

6. **If restart doesn't work:**
   ```bash
   # Check disk space
   df -h
   
   # Check memory
   free -h
   
   # If out of resources, clean up
   docker system prune -f
   ```

7. **Last resort - Full reboot:**
   ```bash
   reboot
   ```

**Post-Incident:**
- Document what happened in `incidents/YYYY-MM-DD-incident-summary.md`
- Schedule post-mortem meeting
- Create tickets for preventive measures

---

### Database Connection Lost

**Symptoms:**
- App returns 500 errors
- Logs show "database connection error"
- Health check reports database disconnected

**Immediate Actions:**

1. **Check database container:**
   ```bash
   docker compose -f docker-compose.prod.yml ps db
   docker compose -f docker-compose.prod.yml logs db --tail=100
   ```

2. **Restart database:**
   ```bash
   docker compose -f docker-compose.prod.yml restart db
   ```

3. **If database won't start, check logs:**
   ```bash
   docker compose -f docker-compose.prod.yml logs db
   ```

4. **Common issues:**
   - **Out of disk space:** Free up space, restart
   - **Corrupted data:** Restore from backup (see below)
   - **Wrong permissions:** Check volume permissions

5. **Restore from backup if database is corrupted:**
   ```bash
   docker compose -f docker-compose.prod.yml stop web
   cd /root/ferreteria
   ./infra/backups/restore_db.sh /var/backups/ferreteria/daily/[latest-backup].sql.gz
   docker compose -f docker-compose.prod.yml start web
   ```

---

### Data Loss / Corruption

**Symptoms:**
- Users report missing data
- Database queries return unexpected results
- Data integrity violations

**Immediate Actions:**

1. **STOP ALL WRITES IMMEDIATELY:**
   ```bash
   docker compose -f docker-compose.prod.yml stop web
   ```

2. **Assess the damage:**
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db
   
   # Check recent data
   SELECT * FROM tenant ORDER BY created_at DESC LIMIT 10;
   SELECT * FROM sale ORDER BY datetime DESC LIMIT 10;
   ```

3. **Identify last known good backup:**
   ```bash
   ls -lht /var/backups/ferreteria/daily/
   ```

4. **Restore from backup:**
   ```bash
   ./infra/backups/restore_db.sh [backup-file]
   ```

5. **Verify restoration:**
   - Check data integrity
   - Contact affected tenants
   - Document data loss

6. **Resume service:**
   ```bash
   docker compose -f docker-compose.prod.yml start web
   ```

---

## P2 - High Severity Incidents

### SSL Certificate Expired

**Symptoms:**
- Browser shows "Your connection is not private"
- SSL error in logs

**Actions:**

1. **Renew certificate:**
   ```bash
   cd /root/ferreteria
   docker compose -f docker-compose.prod.yml run --rm certbot renew --force-renewal
   ```

2. **Reload Nginx:**
   ```bash
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
   ```

3. **Verify:**
   ```bash
   curl -I https://tandil.site
   ```

---

### Deployment Failed

**Symptoms:**
- GitHub Actions deployment workflow failed
- Health check failed after deployment
- 502 errors after deployment

**Actions:**

1. **Check GitHub Actions logs:**
   - Go to repository Actions tab
   - Review failed workflow

2. **If auto-rollback didn't trigger, manual rollback:**
   ```bash
   ssh root@tandil.site
   cd /root/ferreteria
   ./infra/scripts/rollback.sh
   ```

3. **Verify rollback:**
   ```bash
   curl https://tandil.site/health
   ```

4. **Investigate issue:**
   - Review failed tests
   - Check migration errors
   - Review application logs

---

### High Memory/CPU Usage

**Symptoms:**
- Slow response times
- Timeouts
- High resource usage alerts

**Actions:**

1. **Check resource usage:**
   ```bash
   docker stats
   top
   free -h
   ```

2. **Identify problematic container:**
   ```bash
   docker stats --no-stream
   ```

3. **Check for runaway queries:**
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query
   FROM pg_stat_activity
   WHERE state = 'active'
   ORDER BY duration DESC;
   "
   ```

4. **Kill long-running queries if needed:**
   ```bash
   docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "
   SELECT pg_terminate_backend([pid]);
   "
   ```

5. **Restart services:**
   ```bash
   docker compose -f docker-compose.prod.yml restart web
   ```

---

## P3 - Medium Severity Incidents

### Backup Failed

**Actions:**

1. **Check backup logs:**
   ```bash
   tail -100 /var/log/ferreteria_backup.log
   ```

2. **Run manual backup:**
   ```bash
   cd /root/ferreteria
   ./infra/backups/backup_db.sh
   ```

3. **Verify backup:**
   ```bash
   LATEST=$(ls -t /var/backups/ferreteria/daily/*.sql.gz | head -1)
   gunzip -t $LATEST && echo "✓ Backup OK"
   ```

4. **Fix cron if needed:**
   ```bash
   crontab -e
   ```

---

### Email Sending Failed

**Actions:**

1. **Check SMTP configuration:**
   ```bash
   cat .env.prod | grep SMTP
   ```

2. **Test SMTP connection:**
   ```bash
   docker compose -f docker-compose.prod.yml exec web python -c "
   from flask_mail import Mail, Message
   # Test email sending
   "
   ```

3. **Check logs for email errors:**
   ```bash
   docker compose -f docker-compose.prod.yml logs web | grep -i "mail\|smtp"
   ```

---

## Communication Templates

### P1 Incident - Initial Notification

```
INCIDENT ALERT - P1

Status: Investigating
Started: [TIME]
Impact: [Description]
Affected: [All users / Specific tenants]

We are investigating and will provide updates every 15 minutes.
```

### P1 Incident - Update

```
INCIDENT UPDATE - P1

Status: [Investigating / Identified / Fixing / Monitoring]
Duration: [X minutes]
Actions Taken: [List]
ETA Resolution: [TIME or TBD]

Next update in 15 minutes.
```

### P1 Incident - Resolution

```
INCIDENT RESOLVED - P1

Resolved At: [TIME]
Total Duration: [X minutes]
Root Cause: [Brief description]
Impact: [Description]

Post-mortem will be shared within 24 hours.
Thank you for your patience.
```

---

## Post-Incident Checklist

- [ ] Incident documented in `incidents/` folder
- [ ] Root cause analysis completed
- [ ] Post-mortem meeting scheduled
- [ ] Preventive measures identified
- [ ] Tickets created for preventive measures
- [ ] Communication sent to affected users
- [ ] Runbook updated if needed
- [ ] Monitoring/alerts improved

---

## Contact Information

- **Primary On-Call:** [Phone/Email]
- **Secondary On-Call:** [Phone/Email]
- **Sentry Alerts:** [URL]
- **GitHub Repository:** [URL]
- **VPS Access:** `ssh root@tandil.site`

---

**Last Updated:** 2026-01-20  
**Version:** 1.0.0
