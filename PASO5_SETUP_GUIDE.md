
## ✅ Checklist de Configuración

### 1. Configurar GitHub Secrets

Ve a tu repositorio en GitHub → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Agrega los siguientes secrets:

| Secret Name | Valor | Descripción |
|-------------|-------|-------------|
| `VPS_SSH_KEY` | Tu clave privada SSH completa | Contenido de `~/.ssh/id_rsa` o tu key privada |
| `VPS_HOST` | `tandil.site` | Tu dominio o IP del VPS |
| `VPS_USER` | `saas_stock` | Usuario SSH del VPS |
| `DOCKER_USERNAME` | Tu usuario de Docker Hub | Para push de imágenes |
| `DOCKER_PASSWORD` | Token de Docker Hub | No uses tu password, usa token |

#### Cómo generar SSH Key (si no tienes):

```bash
# En tu máquina local
ssh-keygen -t ed25519 -C "github-actions@saas-stock"
# Guardar en: ~/.ssh/github_actions_key

# Ver la clave privada (esto va en VPS_SSH_KEY)
cat ~/.ssh/github_actions_key

# Ver la clave pública (esto va en el VPS)
cat ~/.ssh/github_actions_key.pub
```

#### Agregar clave pública al VPS:

```bash
# SSH al VPS
ssh saas_stock@tandil.site

# Agregar clave pública
echo "tu-clave-publica-aqui" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

#### Crear Docker Hub Token:

1. Ve a https://hub.docker.com/settings/security
2. Click "New Access Token"
3. Name: "GitHub Actions CI/CD"
4. Permissions: Read & Write
5. Copia el token → Este va en `DOCKER_PASSWORD`

---

### 2. Configurar VPS

```bash
# SSH al VPS
ssh saas_stock@tandil.site

# Crear estructura de directorios para backups
sudo mkdir -p /var/backups/saas_stock/daily
sudo chown -R saas_stock:saas_stock /var/backups/saas_stock

# Dar permisos de ejecución a scripts
cd /home/saas_stock/saas_stock
chmod +x infra/scripts/deploy.sh
chmod +x infra/scripts/rollback.sh
chmod +x infra/backups/backup_db.sh
chmod +x infra/backups/restore_db.sh

# Crear directorio de logs
sudo mkdir -p /var/log/saas_stock
sudo chown saas_stock:saas_stock /var/log/saas_stock
```

---

### 3. Configurar .env.prod en VPS

```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

# Copiar ejemplo
cp .env.prod.example .env.prod

# Editar con valores reales
nano .env.prod
```

**Variables obligatorias en .env.prod:**

```bash
# Domain
DOMAIN=tandil.site
ACME_EMAIL=tu-email@gmail.com

# Database
POSTGRES_DB=saas_stock_db
POSTGRES_USER=saas_stock_user
POSTGRES_PASSWORD=TU_PASSWORD_SEGURO_AQUI_123

# Flask
SECRET_KEY=genera-un-string-random-de-64-caracteres-aqui
FLASK_ENV=production
DATABASE_URL=postgresql://saas_stock_user:TU_PASSWORD_SEGURO_AQUI_123@db:5432/saas_stock_db

# Business
QUOTE_VALID_DAYS=30
MAX_UPLOAD_MB=10

# PASO 5: Sentry (opcional, pero recomendado)
SENTRY_DSN=https://tu-sentry-dsn@sentry.io/project-id
GIT_COMMIT=production
```

#### Generar SECRET_KEY:

```bash
# En tu terminal local o del VPS
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

---

### 4. Configurar Sentry (Opcional pero recomendado)

1. Ve a https://sentry.io y crea cuenta gratis
2. Crea nuevo proyecto → Selecciona "Flask"
3. Copia el DSN
4. Agrégalo a `.env.prod` como `SENTRY_DSN`

---

### 5. Primera Ejecución Manual

```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

# Pull código
git pull origin main

# Levantar servicios
docker compose -f docker-compose.prod.yml up -d

# Ver logs
docker compose -f docker-compose.prod.yml logs -f web

# Verificar health
curl https://tandil.site/health
```

---

### 6. Probar CI/CD

#### Test CI (Continuous Integration):

```bash
# En tu repo local
git add .
git commit -m "test: verify CI pipeline"
git push origin main

# Ve a GitHub Actions y verifica que el workflow "CI" se ejecute
```

#### Test CD (Continuous Deployment):

```bash
# Crear tag de release
git tag -a v1.0.0 -m "Release v1.0.0: First production release"
git push origin v1.0.0

# Ve a GitHub Actions y verifica que el workflow "CD - Deploy to Production" se ejecute
# Esto hará:
# 1. Backup automático
# 2. Deploy al VPS
# 3. Health check
# 4. Rollback si falla
```

---

## 🔄 Flujo de Trabajo Normal

### Desarrollo

```bash
# 1. Crear rama feature
git checkout -b feature/nueva-funcionalidad

# 2. Hacer cambios
# ... editar código ...

# 3. Commit
git add .
git commit -m "feat: agregar nueva funcionalidad"

# 4. Push
git push origin feature/nueva-funcionalidad

# 5. CI se ejecuta automáticamente (tests, linting)
```

### Merge a Main

```bash
# 1. Crear Pull Request en GitHub
# 2. CI verifica todo
# 3. Merge PR

# 4. CI se ejecuta en main
# 5. Docker image se construye y sube a Docker Hub
```

### Deploy a Producción

```bash
# 1. Crear release tag
git checkout main
git pull origin main
git tag -a v1.0.1 -m "Release v1.0.1: Bug fixes"
git push origin v1.0.1

# 2. CD se ejecuta automáticamente:
#    - Backup DB
#    - Deploy
#    - Health check
#    - Rollback si falla
```

---

## 🧪 Testing

### Ejecutar Tests Localmente

```bash
# Instalar dependencias de test
pip install pytest pytest-flask pytest-cov

# Ejecutar todos los tests
pytest tests/ -v

# Con coverage
pytest tests/ --cov=app --cov-report=html

# Ver reporte
open htmlcov/index.html
```

### Tests de Tenant Isolation (CRÍTICO)

```bash
# Ejecutar solo tests de aislamiento
pytest tests/integration/test_tenant_isolation.py -v

# Estos tests verifican que:
# - Tenant 1 no puede ver datos de Tenant 2
# - Queries filtran correctamente por tenant_id
# - Dashboard muestra solo datos del tenant activo
```

---

## 📊 Monitoreo

### Ver Logs en Producción

```bash
# SSH al VPS
ssh saas_stock@tandil.site
cd /home/saas_stock/saas_stock

# Logs de la app
docker compose -f docker-compose.prod.yml logs -f web

# Logs de la DB
docker compose -f docker-compose.prod.yml logs -f db

# Logs de Nginx
docker compose -f docker-compose.prod.yml logs -f nginx
```

### Health Check

```bash
# Desde cualquier lugar
curl https://tandil.site/health

# Respuesta esperada:
# {"status":"healthy","database":"connected","message":"Database connection successful"}
```

### Ver Errores en Sentry

1. Ve a https://sentry.io
2. Selecciona tu proyecto
3. Verás errores en tiempo real con stack traces completos

---

## 🔙 Rollback Manual

```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

# Ejecutar script de rollback
./infra/scripts/rollback.sh

# Esto:
# 1. Encuentra la versión anterior
# 2. Checkout a ese tag/commit
# 3. Rebuild Docker
# 4. Restart servicios
# 5. Health check
```

---

## 💾 Backups

### Ejecutar Backup Manual

```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

./infra/backups/backup_db.sh

# Verificar
ls -lh /var/backups/saas_stock/daily/
```

### Configurar Cron para Backups Automáticos

```bash
# SSH al VPS
crontab -e

# Agregar esta línea (backup diario a las 3 AM)
0 3 * * * cd /home/saas_stock/saas_stock && ./infra/backups/backup_db.sh >> /var/log/saas_stock/backup.log 2>&1
```

### Restaurar Backup

```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

# Listar backups
ls -lht /var/backups/saas_stock/daily/

# Restaurar (¡CUIDADO! Sobreescribe DB actual)
./infra/backups/restore_db.sh /var/backups/saas_stock/daily/saas_stock_2026-01-20_030000.sql.gz
```

---

## 🚨 Troubleshooting

### CI falla en "Run tests"

**Problema:** Tests fallan en GitHub Actions

**Solución:**
```bash
# Ejecutar tests localmente primero
pytest tests/ -v

# Arreglar tests que fallen
# Commit y push
```

### CD falla en "Health check"

**Problema:** Health check devuelve 502 o timeout

**Solución:**
```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

# Ver logs
docker compose -f docker-compose.prod.yml logs --tail=100 web

# Restart manual
docker compose -f docker-compose.prod.yml restart web

# Verificar health
curl https://tandil.site/health
```

### CD falla en "Backup"

**Problema:** No puede crear backup

**Solución:**
```bash
# SSH al VPS
# Verificar permisos
ls -la /var/backups/saas_stock/

# Dar permisos
sudo chown -R saas_stock:saas_stock /var/backups/saas_stock
sudo chmod -R 755 /var/backups/saas_stock
```

### "Permission denied" en scripts

**Solución:**
```bash
# SSH al VPS
cd /home/saas_stock/saas_stock

chmod +x infra/scripts/*.sh
chmod +x infra/backups/*.sh
```

---

## ✅ Verificación Final

### Checklist para confirmar que todo funciona:

- [ ] GitHub Secrets configurados (5 secrets)
- [ ] SSH key agregada al VPS
- [ ] Directorios de backup creados
- [ ] `.env.prod` configurado en VPS
- [ ] Scripts tienen permisos de ejecución
- [ ] Docker Compose levantado en VPS
- [ ] Health check responde 200
- [ ] CI se ejecuta en cada push
- [ ] Docker image se construye en main
- [ ] CD se ejecuta con tags vX.Y.Z
- [ ] Backup manual funciona
- [ ] Rollback manual funciona
- [ ] Sentry recibe errores (si configurado)
- [ ] Tests pasan localmente
- [ ] Tests de tenant isolation pasan

---

## 📚 Documentación Adicional

- **RUNBOOK.md**: Operaciones diarias, troubleshooting
- **INCIDENT_RESPONSE.md**: Qué hacer en emergencias
- **SCALING_GUIDE.md**: Cuándo y cómo escalar

---

## 🎯 Próximos Pasos

Una vez que PASO 5 funcione correctamente:

### PASO 6: Roles Avanzados ✅ (50% completo)
- Sistema de permisos implementado
- Falta: Aplicar a blueprints, email service, audit log

### PASO 7: Object Storage
- Migrar uploads a DigitalOcean Spaces
- Configurar CDN
- Liberar disco del VPS

### PASO 8: Redis + Horizontal Scaling
- Sesiones en Redis
- Múltiples réplicas de web
- PgBouncer para DB

### PASO 9: Observabilidad + Pagos
- Prometheus + Grafana
- Stripe subscriptions
- Admin panel

---

**Última Actualización:** 2026-01-20  
**Estado:** PASO 5 listo para producción  
**Soporte:** Ver RUNBOOK.md para troubleshooting
