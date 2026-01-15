# 📁 Archivos de Producción - Sistema Ferretería

Este directorio contiene todos los archivos necesarios para desplegar el sistema en producción.

---

## 📋 Contenido

### **1. Schema de Base de Datos**

#### **`schema_production.sql`**
- Schema completo de la base de datos
- Incluye todas las tablas, índices, triggers y constraints
- Incluye todas las mejoras implementadas (1-8)
- **Uso:** Primera instalación o recreación completa de la BD

```bash
psql -U ferreteria -d ferreteria -f schema_production.sql
```

---

### **2. Datos Iniciales**

#### **`initial_data.sql`**
- Datos maestros mínimos necesarios
- UOMs (Unidad, Metro, Litro, Kilogramo, etc.)
- Categorías básicas (Herramientas, Pintura, Electricidad, etc.)
- **Uso:** Después de aplicar el schema en instalación nueva

```bash
psql -U ferreteria -d ferreteria -f initial_data.sql
```

---

### **3. Scripts de Backup**

#### **`backup_database.sh`** (Linux/macOS)
- Script de backup automático
- Crea archivo comprimido `.sql.gz`
- Limpia backups antiguos (>30 días)
- **Uso manual:**

```bash
chmod +x backup_database.sh
./backup_database.sh
```

**Configurar backup automático (cron):**
```bash
crontab -e
# Agregar: Backup diario a las 2:00 AM
0 2 * * * cd /ruta/a/db/production && ./backup_database.sh >> /var/log/ferreteria_backup.log 2>&1
```

#### **`backup_database.ps1`** (Windows)
- Script de backup para Windows PowerShell
- Funcionalidad equivalente a la versión Linux
- **Uso manual:**

```powershell
.\backup_database.ps1
```

**Variables de entorno requeridas:**
- `DB_HOST` (default: localhost)
- `DB_PORT` (default: 5432)
- `DB_NAME` (default: ferreteria)
- `DB_USER` (default: ferreteria)
- `DB_PASSWORD` (requerido)

---

### **4. Scripts de Restore**

#### **`restore_database.sh`** (Linux/macOS)
- Restaura base de datos desde backup
- Solicita confirmación antes de proceder
- Elimina y recrea la base de datos
- **Uso:**

```bash
chmod +x restore_database.sh
./restore_database.sh ./backups/ferreteria_backup_20260110_020000.sql.gz
```

**⚠️ ADVERTENCIA:** Esta operación elimina todos los datos actuales.

---

### **5. Guía de Despliegue**

#### **`DEPLOYMENT_GUIDE.md`**
- Guía completa de despliegue en producción
- Instrucciones paso a paso
- Configuración de Docker, Nginx, SSL
- Troubleshooting común
- **Lectura obligatoria antes de desplegar**

---

## 🚀 Quick Start

### **Instalación Nueva (con Docker)**

```bash
# 1. Ir al directorio del proyecto
cd /ruta/a/ferreteria-app

# 2. Configurar variables de entorno
cp env.example .env
nano .env  # Editar APP_PASSWORD, SECRET_KEY, etc.

# 3. Iniciar servicios
docker compose up -d

# 4. Verificar
curl http://localhost:5000/health

# 5. Acceder
# Abrir navegador: http://localhost:5000
# Ingresar contraseña configurada en APP_PASSWORD
```

El schema y datos iniciales se aplican automáticamente en el primer inicio.

---

### **Instalación Nueva (sin Docker)**

```bash
# 1. Crear base de datos
sudo -u postgres psql -c "CREATE USER ferreteria WITH PASSWORD 'tu_password';"
sudo -u postgres psql -c "CREATE DATABASE ferreteria OWNER ferreteria;"

# 2. Aplicar schema
cd /ruta/a/ferreteria-app/db/production
psql -U ferreteria -d ferreteria -f schema_production.sql

# 3. Cargar datos iniciales
psql -U ferreteria -d ferreteria -f initial_data.sql

# 4. Configurar aplicación
cd /ruta/a/ferreteria-app
cp env.example .env
nano .env  # Editar variables

# 5. Instalar dependencias Python
pip install -r requirements.txt

# 6. Iniciar aplicación
python app.py
```

---

## 💾 Mantenimiento

### **Backup Regular**

**Recomendado:** Configurar backup automático diario.

**Linux/macOS (cron):**
```bash
0 2 * * * cd /ruta/a/db/production && ./backup_database.sh
```

**Windows (Task Scheduler):**
- Crear tarea programada para ejecutar `backup_database.ps1` diariamente

---

### **Monitoreo**

**Verificar salud de la aplicación:**
```bash
curl http://localhost:5000/health
```

**Verificar salud de PostgreSQL:**
```bash
docker compose exec db pg_isready -U ferreteria
# O sin Docker:
psql -U ferreteria -d ferreteria -c "SELECT 1;"
```

**Ver logs:**
```bash
# Con Docker:
docker compose logs -f web
docker compose logs -f db

# Sin Docker:
tail -f /var/log/ferreteria.log
```

---

## 📦 Estructura de Backups

```
db/production/backups/
├── ferreteria_backup_20260101_020000.sql.gz
├── ferreteria_backup_20260102_020000.sql.gz
├── ferreteria_backup_20260103_020000.sql.gz
└── ...
```

- **Formato:** `ferreteria_backup_YYYYMMDD_HHMMSS.sql.gz`
- **Retención:** Últimos 30 días (configurable)
- **Compresión:** gzip (Linux/macOS) o zip (Windows)

---

## 🔐 Seguridad

### **Variables Críticas en `.env`**

```env
# ⚠️ CAMBIAR EN PRODUCCIÓN
APP_PASSWORD=tu_password_super_seguro_aqui
SECRET_KEY=genera_clave_aleatoria_64_caracteres_hex
DB_PASSWORD=tu_password_db_seguro

# Generar SECRET_KEY:
# python -c "import secrets; print(secrets.token_hex(32))"
```

### **Checklist de Seguridad**

- [ ] `APP_PASSWORD` fuerte (12+ caracteres)
- [ ] `SECRET_KEY` único (64 caracteres hex)
- [ ] `DB_PASSWORD` fuerte (16+ caracteres)
- [ ] `FLASK_DEBUG=0` en producción
- [ ] Backups automáticos configurados
- [ ] PostgreSQL solo accesible desde localhost (o red interna)
- [ ] Nginx/proxy reverso con HTTPS configurado
- [ ] Firewall configurado (solo puertos 80, 443 expuestos)

---

## 📚 Documentación Adicional

- **Guía completa:** `DEPLOYMENT_GUIDE.md`
- **README principal:** `../../README.md`
- **Mejoras implementadas:** `../../MEJORA*_RESUMEN.md`

---

## ❓ FAQ

### **¿Cómo migro desde desarrollo a producción?**

1. Hacer backup de desarrollo:
   ```bash
   ./backup_database.sh
   ```

2. Copiar backup al servidor de producción

3. Aplicar schema en producción:
   ```bash
   psql -U ferreteria -d ferreteria -f schema_production.sql
   ```

4. Restaurar datos de desarrollo:
   ```bash
   ./restore_database.sh backup_desarrollo.sql.gz
   ```

---

### **¿Cómo actualizo la base de datos después de cambios en el código?**

Si hay cambios en modelos (nuevas columnas, tablas, etc.):

1. Crear script de migración SQL manualmente
2. Aplicar con:
   ```bash
   psql -U ferreteria -d ferreteria -f migration_001.sql
   ```

**Recomendación:** Usar Alembic para migraciones automáticas en el futuro.

---

### **¿Dónde se almacenan las imágenes de productos?**

- **Ruta:** `app/static/uploads/products/`
- **Persistencia con Docker:** Configurar volumen en `docker-compose.yml`
- **Backup:** Incluir en respaldo de archivos (no solo BD)

```yaml
# Agregar en docker-compose.yml:
volumes:
  - ./app/static/uploads:/app/app/static/uploads
```

---

### **¿Cómo cambio la contraseña de acceso (APP_PASSWORD)?**

1. Editar `.env`:
   ```env
   APP_PASSWORD=nueva_contraseña_segura
   ```

2. Reiniciar aplicación:
   ```bash
   # Con Docker:
   docker compose restart web
   
   # Sin Docker:
   systemctl restart ferreteria
   ```

3. Hacer logout y login con nueva contraseña

---

**Última actualización:** Enero 2026  
**Versión:** 1.0
