# ⚡ PASO 4 - Deployment Quick Start

Guía rápida de comandos para despliegue en VPS (para usuarios avanzados).

Para guía detallada, ver: [`README_PROD_DEPLOY.md`](README_PROD_DEPLOY.md)

---

## 🚀 Setup Inicial (10 minutos)

```bash
# 1. Conectar a VPS
ssh root@YOUR_VPS_IP

# 2. Instalar Docker
curl -fsSL https://get.docker.com | sh

# 3. Configurar firewall
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable

# 4. Clonar repo
git clone https://github.com/tu-usuario/ferreteria-saas.git ferreteria
cd ferreteria

# 5. Configurar env
cp env.prod.example .env.prod
nano .env.prod  # Editar DOMAIN, passwords, etc.

# 6. Reemplazar ${DOMAIN} en configs Nginx
DOMAIN="ferreteria.example.com"
sed -i "s|\${DOMAIN}|${DOMAIN}|g" infra/nginx/conf.d/app.conf
sed -i "s|\${DOMAIN}|${DOMAIN}|g" infra/nginx/ssl-params.conf

# 7. Crear directorio de backups
mkdir -p /var/backups/ferreteria/daily
chmod +x infra/backups/*.sh
```

---

## 🐳 Despliegue (HTTP primero)

```bash
# Comentar bloque HTTPS en Nginx (temporal)
nano infra/nginx/conf.d/app.conf  # Comentar líneas 30-150

# Levantar servicios
docker compose -f docker-compose.prod.yml up -d db web nginx

# Verificar
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
curl http://YOUR_VPS_IP/health  # Debe devolver {"status": "healthy"}
```

---

## 🔒 Configurar SSL (Let's Encrypt)

```bash
# 1. Emitir certificado
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@example.com \
  --agree-tos \
  --no-eff-email \
  -d ferreteria.example.com

# 2. Descomentar bloque HTTPS en Nginx
nano infra/nginx/conf.d/app.conf  # Descomentar líneas 30-150

# 3. Reiniciar Nginx
docker compose -f docker-compose.prod.yml restart nginx

# 4. Iniciar renovación automática
docker compose -f docker-compose.prod.yml up -d certbot

# 5. Verificar HTTPS
curl -I https://ferreteria.example.com/health
```

---

## 💾 Configurar Backups

```bash
# 1. Backup manual
./infra/backups/backup_db.sh

# 2. Configurar cron
sudo crontab -e
# Agregar: 0 3 * * * cd /root/ferreteria && ./infra/backups/backup_db.sh >> /var/log/ferreteria_backup.log 2>&1

# 3. Verificar
sudo crontab -l

# 4. Probar restauración (CUIDADO: borra datos)
./infra/backups/restore_db.sh /var/backups/ferreteria/daily/ferreteria_2026-01-14_030000.sql.gz
```

---

## 📊 Comandos de Mantenimiento

### Ver Estado
```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f
docker stats
```

### Reiniciar Servicios
```bash
docker compose -f docker-compose.prod.yml restart web
docker compose -f docker-compose.prod.yml restart nginx
docker compose -f docker-compose.prod.yml restart db
docker compose -f docker-compose.prod.yml restart
```

### Detener/Iniciar Todo
```bash
docker compose -f docker-compose.prod.yml down
docker compose -f docker-compose.prod.yml up -d
```

### Actualizar Aplicación
```bash
./infra/backups/backup_db.sh  # Backup primero!
git pull origin main
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d web
docker compose -f docker-compose.prod.yml logs -f web
```

### Aplicar Migración DB
```bash
./infra/backups/backup_db.sh  # Backup primero!
docker compose -f docker-compose.prod.yml exec -T db psql -U ferreteria_user -d ferreteria_db < db/migrations/nueva_migracion.sql
```

### Limpiar Espacio
```bash
docker system prune -a -f
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log
find /var/backups/ferreteria/daily -name "*.sql.gz" -mtime +60 -delete
```

---

## 🔧 Troubleshooting Rápido

### 502 Bad Gateway
```bash
docker compose -f docker-compose.prod.yml logs web
docker compose -f docker-compose.prod.yml restart web
curl http://localhost:5000/health
```

### Connection Refused (DB)
```bash
docker compose -f docker-compose.prod.yml logs db
docker compose -f docker-compose.prod.yml restart db
docker compose -f docker-compose.prod.yml exec db pg_isready -U ferreteria_user
```

### SSL No Funciona
```bash
dig ferreteria.example.com  # Verificar DNS
curl http://ferreteria.example.com/.well-known/test.txt
docker compose -f docker-compose.prod.yml logs certbot
docker compose -f docker-compose.prod.yml run --rm certbot renew --dry-run
```

### Backup Falla
```bash
sudo mkdir -p /var/backups/ferreteria/daily
sudo chown -R $USER:$USER /var/backups/ferreteria
chmod +x infra/backups/*.sh
docker compose -f docker-compose.prod.yml ps
```

---

## 📁 Estructura de Archivos (PASO 4)

```
ferreteria/
├── docker-compose.prod.yml          # Compose para producción
├── .env.prod                        # Variables de entorno (NO en git)
├── env.prod.example                 # Ejemplo de .env.prod
├── infra/
│   ├── nginx/
│   │   ├── nginx.conf              # Configuración global Nginx
│   │   ├── conf.d/
│   │   │   └── app.conf            # Server blocks (HTTP + HTTPS)
│   │   └── ssl-params.conf         # Parámetros SSL/TLS
│   └── backups/
│       ├── backup_db.sh            # Script de backup
│       ├── restore_db.sh           # Script de restauración
│       ├── crontab.example         # Ejemplo de cron
│       └── README.md               # Docs de backups
├── README_PROD_DEPLOY.md           # Guía completa de deploy
└── PASO4_DEPLOYMENT_QUICKSTART.md  # Este archivo
```

---

## ✅ Checklist de Despliegue

- [ ] DNS configurado (registro A)
- [ ] `.env.prod` con passwords fuertes
- [ ] Nginx con dominio correcto
- [ ] Aplicación corriendo (HTTP)
- [ ] SSL configurado (HTTPS)
- [ ] Renovación SSL automática
- [ ] Backup manual exitoso
- [ ] Cron configurado
- [ ] Restauración probada
- [ ] Health checks OK
- [ ] Uptime Kuma configurado

---

## 🔗 Referencias Útiles

- **Guía Completa:** [`README_PROD_DEPLOY.md`](README_PROD_DEPLOY.md)
- **Backups:** [`infra/backups/README.md`](infra/backups/README.md)
- **Health Check:** `https://your-domain.com/health`
- **Uptime Kuma:** `http://YOUR_VPS_IP:3001`

---

**Tiempo estimado de deployment:** 15-20 minutos (primera vez)

**Última actualización:** 2026-01-14
