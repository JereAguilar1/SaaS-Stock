# 🚀 Deployment Guide - Production VPS

Guía completa para desplegar **Ferretería SaaS** en un VPS con Docker, Nginx, HTTPS (Let's Encrypt) y backups automáticos.

---

## 📋 Tabla de Contenidos

1. [Requisitos](#requisitos)
2. [Preparación del VPS](#preparación-del-vps)
3. [Configuración de DNS](#configuración-de-dns)
4. [Configuración de Variables de Entorno](#configuración-de-variables-de-entorno)
5. [Despliegue de la Aplicación](#despliegue-de-la-aplicación)
6. [Configuración de SSL/TLS (Let's Encrypt)](#configuración-de-ssltls-lets-encrypt)
7. [Configuración de Backups](#configuración-de-backups)
8. [Monitoreo y Mantenimiento](#monitoreo-y-mantenimiento)
9. [Troubleshooting](#troubleshooting)

---

## 📌 Requisitos

### Hardware Recomendado
- **VPS:** 2 vCPU, 4GB RAM, 100GB NVMe (para ~10 clientes)
- **Proveedor sugerido:** DigitalOcean, Linode, Vultr, Hetzner
- **SO:** Ubuntu 22.04 LTS o Debian 11+

### Software Necesario
- Docker 24.0+
- Docker Compose 2.20+
- Git
- Dominio propio con acceso a DNS

---

## 🔧 Preparación del VPS

### 1. Conectar al VPS vía SSH

```bash
ssh root@YOUR_VPS_IP
```

### 2. Actualizar Sistema

```bash
apt update && apt upgrade -y
```

### 3. Instalar Docker

```bash
# Instalar dependencias
apt install -y ca-certificates curl gnupg lsb-release

# Agregar repositorio oficial de Docker
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

# Instalar Docker
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Verificar instalación
docker --version
docker compose version
```

### 4. Configurar Firewall (UFW)

```bash
# Habilitar UFW
ufw enable

# Permitir SSH (IMPORTANTE: antes de habilitar firewall)
ufw allow 22/tcp

# Permitir HTTP y HTTPS
ufw allow 80/tcp
ufw allow 443/tcp

# Opcional: Uptime Kuma (si se va a acceder externamente)
ufw allow 3001/tcp

# Verificar reglas
ufw status
```

### 5. Crear Usuario para la Aplicación (Opcional pero recomendado)

```bash
# Crear usuario
adduser ferreteria

# Agregar al grupo docker
usermod -aG docker ferreteria

# Cambiar a usuario
su - ferreteria
```

---

## 🌐 Configuración de DNS

### Configurar Registro A

En tu proveedor de DNS (Cloudflare, Namecheap, etc.), crea un registro **A**:

```
Tipo: A
Nombre: ferreteria (o @ para dominio raíz)
Valor: YOUR_VPS_IP
TTL: 300 (5 minutos)
```

**Ejemplo:**
- **Dominio:** `ferreteria.miempresa.com`
- **IP VPS:** `203.0.113.50`

```
A  ferreteria  203.0.113.50  300
```

### Verificar Propagación DNS

```bash
# Desde tu computadora local
dig ferreteria.miempresa.com

# O usar herramienta online
# https://dnschecker.org
```

**Espera unos minutos** para que el DNS se propague globalmente.

---

## 🔐 Configuración de Variables de Entorno

### 1. Clonar Repositorio

```bash
cd /home/ferreteria  # o /root si usas root
git clone https://github.com/tu-usuario/ferreteria-saas.git ferreteria
cd ferreteria
```

### 2. Crear Archivo `.env.prod`

```bash
cp env.prod.example .env.prod
nano .env.prod
```

### 3. Configurar Variables de Entorno

```bash
# ============================================
# DOMAIN & SSL
# ============================================
DOMAIN=ferreteria.miempresa.com
ACME_EMAIL=admin@miempresa.com

# ============================================
# DATABASE
# ============================================
POSTGRES_DB=ferreteria_db
POSTGRES_USER=ferreteria_user
POSTGRES_PASSWORD=TU_PASSWORD_SUPER_SEGURO_AQUI_32_CARACTERES

# ============================================
# FLASK APP
# ============================================
# Generar con: python3 -c 'import secrets; print(secrets.token_urlsafe(64))'
SECRET_KEY=TU_SECRET_KEY_SUPER_SEGURO_AQUI_64_CARACTERES

FLASK_ENV=production

# ============================================
# BUSINESS INFO
# ============================================
BUSINESS_NAME=Ferretería López
BUSINESS_ADDRESS=Av. Principal 123, Ciudad, Provincia
BUSINESS_PHONE=+54 11 1234-5678
BUSINESS_EMAIL=contacto@ferreteria.miempresa.com

# ============================================
# APP CONFIG
# ============================================
QUOTE_VALID_DAYS=7
MAX_UPLOAD_MB=10

# ============================================
# GUNICORN CONFIG (para VPS de 2vCPU + 4GB RAM)
# ============================================
GUNICORN_WORKERS=4
GUNICORN_THREADS=2
GUNICORN_TIMEOUT=120
WEB_CONCURRENCY=4

# ============================================
# SESSION & SECURITY
# ============================================
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
PREFERRED_URL_SCHEME=https

# ============================================
# BACKUP CONFIG
# ============================================
BACKUP_RETENTION_DAYS=30
BACKUP_PATH=/var/backups/ferreteria
```

**Guardar con:** `Ctrl+O`, `Enter`, `Ctrl+X`

### 4. Generar Secret Keys Seguros

```bash
# SECRET_KEY
python3 -c 'import secrets; print(secrets.token_urlsafe(64))'

# POSTGRES_PASSWORD
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

---

## 🐳 Despliegue de la Aplicación

### 1. Configurar Nginx (reemplazar `${DOMAIN}` en configs)

```bash
# Editar archivo de configuración de Nginx
nano infra/nginx/conf.d/app.conf

# Buscar y reemplazar ${DOMAIN} con tu dominio real:
# Línea 34: ssl_certificate /etc/letsencrypt/live/ferreteria.miempresa.com/fullchain.pem;
# Línea 35: ssl_certificate_key /etc/letsencrypt/live/ferreteria.miempresa.com/privkey.pem;

# Guardar: Ctrl+O, Enter, Ctrl+X
```

**O usar sed para automatizar:**

```bash
DOMAIN="ferreteria.miempresa.com"
sed -i "s|\${DOMAIN}|${DOMAIN}|g" infra/nginx/conf.d/app.conf
sed -i "s|\${DOMAIN}|${DOMAIN}|g" infra/nginx/ssl-params.conf
```

### 2. Crear Directorios Necesarios

```bash
# Directorio de backups
sudo mkdir -p /var/backups/ferreteria/daily

# Dar permisos
sudo chown -R $USER:$USER /var/backups/ferreteria

# Permisos de ejecución para scripts
chmod +x infra/backups/backup_db.sh
chmod +x infra/backups/restore_db.sh
```

### 3. Primera Ejecución (SIN SSL, solo HTTP)

Antes de configurar SSL, debemos levantar la app para que Certbot pueda validar el dominio.

**Temporal: Comentar líneas SSL en Nginx:**

```bash
# Editar archivo de Nginx
nano infra/nginx/conf.d/app.conf

# Comentar el bloque "HTTPS Server" (líneas 30-150 aprox)
# O simplemente eliminar temporalmente las líneas 30-150

# Guardar: Ctrl+O, Enter, Ctrl+X
```

**Levantar servicios (sin SSL):**

```bash
docker compose -f docker-compose.prod.yml up -d db web nginx
```

**Verificar que funciona:**

```bash
# Ver logs
docker compose -f docker-compose.prod.yml logs -f

# Verificar health check
curl http://YOUR_VPS_IP/health
# Debe devolver: {"status": "healthy", ...}

# Verificar desde navegador
# http://ferreteria.miempresa.com (debe redirigir o mostrar la app)
```

---

## 🔒 Configuración de SSL/TLS (Let's Encrypt)

### 1. Obtener Certificados

```bash
# Emitir certificado (modo interactivo)
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@miempresa.com \
  --agree-tos \
  --no-eff-email \
  -d ferreteria.miempresa.com
```

**Salida esperada:**

```
Successfully received certificate.
Certificate is saved at: /etc/letsencrypt/live/ferreteria.miempresa.com/fullchain.pem
Key is saved at:         /etc/letsencrypt/live/ferreteria.miempresa.com/privkey.pem
```

### 2. Habilitar HTTPS en Nginx

```bash
# Descomentar o restaurar el bloque HTTPS en app.conf
nano infra/nginx/conf.d/app.conf

# Asegurarse de que las líneas 30-150 estén activas
# Guardar: Ctrl+O, Enter, Ctrl+X
```

### 3. Reiniciar Nginx

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

### 4. Verificar HTTPS

```bash
# Desde navegador: https://ferreteria.miempresa.com
# Debe mostrar candado verde

# Desde terminal:
curl -I https://ferreteria.miempresa.com/health
# HTTP/2 200
```

### 5. Iniciar Renovación Automática

```bash
# El contenedor certbot ya está configurado para renovar cada 12h
docker compose -f docker-compose.prod.yml up -d certbot

# Verificar que está corriendo
docker ps | grep certbot
```

### 6. Forzar Renovación Manual (opcional, para probar)

```bash
docker compose -f docker-compose.prod.yml run --rm certbot renew --dry-run
```

---

## 💾 Configuración de Backups

### 1. Ejecutar Backup Manual (Primera Vez)

```bash
cd /home/ferreteria/ferreteria
./infra/backups/backup_db.sh
```

**Salida esperada:**

```
[2026-01-14 15:30:01] Starting PostgreSQL backup...
[2026-01-14 15:30:15] Backup completed successfully! Size: 1.2M
[2026-01-14 15:30:15] Backup file created: /var/backups/ferreteria/daily/ferreteria_2026-01-14_153001.sql.gz
[2026-01-14 15:30:15] Total backups: 1
[2026-01-14 15:30:15] Backup process completed successfully!
```

### 2. Configurar Cron para Backups Automáticos

```bash
# Editar crontab
sudo crontab -e

# Agregar al final (backup diario a las 3:00 AM):
0 3 * * * cd /home/ferreteria/ferreteria && ./infra/backups/backup_db.sh >> /var/log/ferreteria_backup.log 2>&1

# Guardar: Ctrl+O, Enter, Ctrl+X
```

### 3. Verificar Crontab

```bash
sudo crontab -l
```

### 4. Probar Restauración (Importante!)

```bash
# Listar backups disponibles
ls -lh /var/backups/ferreteria/daily/

# Restaurar backup (CUIDADO: esto borrará datos actuales)
./infra/backups/restore_db.sh /var/backups/ferreteria/daily/ferreteria_2026-01-14_153001.sql.gz
```

**Para más detalles, ver:** [`infra/backups/README.md`](infra/backups/README.md)

---

## 📊 Monitoreo y Mantenimiento

### 1. Acceder a Uptime Kuma (Monitoreo)

```bash
# Uptime Kuma corre en puerto 3001
# Acceder desde navegador:
http://YOUR_VPS_IP:3001

# Primera vez: crear usuario admin
```

**Configurar Monitoreo en Uptime Kuma:**

1. **Health Check:** `https://ferreteria.miempresa.com/health` (cada 60s)
2. **Database Port:** TCP ping a `localhost:5432`
3. **Disk Space:** Script bash para alertar si < 10% libre

### 2. Ver Logs

```bash
# Logs de todos los servicios
docker compose -f docker-compose.prod.yml logs -f

# Logs de un servicio específico
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f db

# Logs de backups
tail -f /var/log/ferreteria_backup.log
```

### 3. Comandos Útiles

```bash
# Ver estado de servicios
docker compose -f docker-compose.prod.yml ps

# Reiniciar un servicio
docker compose -f docker-compose.prod.yml restart web

# Reiniciar todo
docker compose -f docker-compose.prod.yml restart

# Detener todo
docker compose -f docker-compose.prod.yml down

# Levantar todo
docker compose -f docker-compose.prod.yml up -d

# Ver uso de recursos
docker stats

# Limpiar imágenes viejas
docker system prune -a
```

### 4. Actualizar Aplicación

```bash
cd /home/ferreteria/ferreteria

# Hacer backup antes de actualizar
./infra/backups/backup_db.sh

# Pull cambios
git pull origin main

# Rebuild y restart
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d web

# Ver logs para verificar
docker compose -f docker-compose.prod.yml logs -f web
```

### 5. Aplicar Migración de Base de Datos

```bash
# Si hay nueva migración SQL
docker compose -f docker-compose.prod.yml exec -T db psql -U ferreteria_user -d ferreteria_db < db/migrations/nueva_migracion.sql
```

---

## 🔧 Troubleshooting

### Problema 1: "502 Bad Gateway" en Nginx

**Causa:** El servicio `web` no está respondiendo.

**Solución:**

```bash
# Ver logs del servicio web
docker compose -f docker-compose.prod.yml logs web

# Verificar que está corriendo
docker compose -f docker-compose.prod.yml ps web

# Reiniciar web
docker compose -f docker-compose.prod.yml restart web

# Verificar health check
curl http://localhost:5000/health
```

### Problema 2: "Connection refused" a base de datos

**Causa:** PostgreSQL no está listo o no se puede conectar.

**Solución:**

```bash
# Ver logs de DB
docker compose -f docker-compose.prod.yml logs db

# Verificar health check de DB
docker compose -f docker-compose.prod.yml exec db pg_isready -U ferreteria_user

# Reiniciar DB
docker compose -f docker-compose.prod.yml restart db
```

### Problema 3: Certificado SSL no se genera

**Causa:** DNS no está propagado o webroot no es accesible.

**Solución:**

```bash
# Verificar que el dominio apunta al VPS
dig ferreteria.miempresa.com

# Verificar que nginx sirve .well-known/
curl http://ferreteria.miempresa.com/.well-known/test.txt

# Ver logs de certbot
docker compose -f docker-compose.prod.yml logs certbot

# Intentar modo manual
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email admin@miempresa.com \
  --agree-tos \
  --no-eff-email \
  -d ferreteria.miempresa.com \
  --dry-run
```

### Problema 4: Backup falla con "Permission denied"

**Solución:**

```bash
# Dar permisos al directorio de backups
sudo mkdir -p /var/backups/ferreteria/daily
sudo chown -R $USER:$USER /var/backups/ferreteria

# Dar permisos de ejecución a scripts
chmod +x infra/backups/backup_db.sh
chmod +x infra/backups/restore_db.sh

# Verificar que docker compose funciona
docker compose -f docker-compose.prod.yml ps
```

### Problema 5: "Disk space full"

**Solución:**

```bash
# Ver espacio en disco
df -h

# Limpiar imágenes y contenedores viejos
docker system prune -a -f

# Limpiar logs de Docker
sudo truncate -s 0 /var/lib/docker/containers/*/*-json.log

# Limpiar backups viejos manualmente
find /var/backups/ferreteria/daily -name "*.sql.gz" -mtime +60 -delete
```

### Problema 6: "Rate limit exceeded" en Let's Encrypt

**Causa:** Demasiados intentos de emisión de certificados.

**Solución:**

- Let's Encrypt tiene límite de **5 certificados por dominio por semana**
- Esperar 7 días para volver a intentar
- Usar `--dry-run` para probar sin consumir límite
- Considerar usar certificado wildcard

---

## 📈 Escalabilidad (Para > 10 clientes)

Cuando llegues a **10+ clientes** y necesites escalar:

### Opción 1: Escalar Verticalmente
- Aumentar a **4vCPU + 8GB RAM**
- Ajustar `GUNICORN_WORKERS=8`

### Opción 2: Escalar Horizontalmente
- **Base de datos externa:** Migrar PostgreSQL a servicio administrado (AWS RDS, DigitalOcean Managed DB)
- **Redis para sesiones:** Agregar Redis container para sesiones compartidas
- **Load Balancer:** Múltiples instancias de `web` con Nginx como LB
- **Object Storage:** Migrar uploads a S3/Spaces

### Opción 3: Kubernetes (Para > 100 clientes)
- Migrar a Kubernetes (EKS, GKE, k3s)
- Helm charts
- Auto-scaling
- Observabilidad avanzada (Prometheus, Grafana)

---

## 📞 Soporte

Para problemas o consultas:
- **Email:** admin@miempresa.com
- **Documentación:** `/infra/backups/README.md`
- **Health Check:** `https://ferreteria.miempresa.com/health`

---

## ✅ Checklist Final de Despliegue

- [ ] VPS configurado con Docker y Docker Compose
- [ ] Firewall configurado (UFW)
- [ ] DNS apuntando al VPS (registro A)
- [ ] Archivo `.env.prod` configurado con passwords fuertes
- [ ] Nginx configurado con dominio correcto
- [ ] Aplicación corriendo (HTTP primero)
- [ ] Certificado SSL emitido (Let's Encrypt)
- [ ] HTTPS funcionando con candado verde
- [ ] Renovación automática de SSL configurada
- [ ] Backup manual ejecutado exitosamente
- [ ] Cron configurado para backups diarios
- [ ] Restauración probada al menos una vez
- [ ] Uptime Kuma configurado
- [ ] Health checks verificados
- [ ] Logs monitoreados

---

**¡Felicitaciones! Tu aplicación está en producción. 🎉**

**Última actualización:** 2026-01-14
