# 🚀 Guía de Despliegue en Producción - Sistema Ferretería

## 📋 Índice

1. [Requisitos Previos](#requisitos-previos)
2. [Instalación de Base de Datos](#instalación-de-base-de-datos)
3. [Configuración de la Aplicación](#configuración-de-la-aplicación)
4. [Despliegue con Docker](#despliegue-con-docker)
5. [Backup y Restore](#backup-y-restore)
6. [Monitoreo y Mantenimiento](#monitoreo-y-mantenimiento)
7. [Troubleshooting](#troubleshooting)

---

## 📦 Requisitos Previos

### **Hardware Mínimo Recomendado:**
- **CPU:** 2 cores
- **RAM:** 4 GB
- **Disco:** 20 GB SSD
- **Red:** Conexión estable a internet (para actualizaciones)

### **Software Requerido:**

#### **Opción A: Docker (Recomendado)**
- Docker Engine 20+
- Docker Compose V2
- Sistema operativo: Linux (Ubuntu 20.04+), Windows Server 2019+, o macOS

#### **Opción B: Instalación Nativa**
- PostgreSQL 16
- Python 3.11+
- Nginx o Apache (para proxy reverso)
- Sistema operativo: Linux (Ubuntu 20.04+) o Windows Server

---

## 🗄️ Instalación de Base de Datos

### **Método 1: Con Docker (Recomendado)**

```bash
cd /ruta/a/ferreteria-app

# 1. Copiar archivo de configuración
cp env.example .env

# 2. Editar .env y configurar variables (ver sección Configuración)
nano .env

# 3. Iniciar servicios
docker compose up -d

# 4. Verificar que los contenedores están corriendo
docker compose ps

# 5. Aplicar schema de base de datos (se aplica automáticamente en primer inicio)
# Si necesitas aplicarlo manualmente:
docker compose exec db psql -U ferreteria -d ferreteria -f /docker-entrypoint-initdb.d/001_schema.sql
```

### **Método 2: PostgreSQL Nativo**

#### **1. Instalar PostgreSQL 16**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql-16 postgresql-contrib
```

**Windows:**
- Descargar instalador desde: https://www.postgresql.org/download/windows/

#### **2. Crear Base de Datos**

```bash
# Conectar como superusuario
sudo -u postgres psql

# Crear usuario
CREATE USER ferreteria WITH PASSWORD 'tu_password_seguro';

# Crear base de datos
CREATE DATABASE ferreteria OWNER ferreteria;

# Otorgar privilegios
GRANT ALL PRIVILEGES ON DATABASE ferreteria TO ferreteria;

# Salir
\q
```

#### **3. Aplicar Schema**

```bash
# Copiar archivos SQL al servidor
cd /ruta/a/ferreteria-app/db/production

# Aplicar schema
psql -U ferreteria -d ferreteria -f schema_production.sql

# Cargar datos iniciales
psql -U ferreteria -d ferreteria -f initial_data.sql
```

#### **4. Verificar Instalación**

```bash
psql -U ferreteria -d ferreteria -c "\dt"
```

**Salida esperada:**
```
                 List of relations
 Schema |         Name          | Type  |   Owner    
--------+-----------------------+-------+------------
 public | category              | table | ferreteria
 public | finance_ledger        | table | ferreteria
 public | product               | table | ferreteria
 public | product_stock         | table | ferreteria
 public | purchase_invoice      | table | ferreteria
 public | purchase_invoice_line | table | ferreteria
 public | sale                  | table | ferreteria
 public | sale_line             | table | ferreteria
 public | stock_move            | table | ferreteria
 public | stock_move_line       | table | ferreteria
 public | supplier              | table | ferreteria
 public | uom                   | table | ferreteria
```

---

## ⚙️ Configuración de la Aplicación

### **Variables de Entorno Críticas**

Editar archivo `.env`:

```env
# ============================================================================
# CONFIGURACIÓN OBLIGATORIA PARA PRODUCCIÓN
# ============================================================================

# Autenticación (MEJORA 8 - REQUERIDO)
APP_PASSWORD=tu_password_super_seguro_aqui_123456

# Flask (REQUERIDO)
SECRET_KEY=genera_una_clave_aleatoria_de_50_caracteres_minimo
FLASK_DEBUG=0

# Base de Datos
DB_HOST=db                 # Si usas Docker, dejar 'db'
DB_PORT=5432
DB_NAME=ferreteria
DB_USER=ferreteria
DB_PASSWORD=tu_password_db_seguro

# ============================================================================
# NOTAS DE SEGURIDAD
# ============================================================================
# 1. APP_PASSWORD: Contraseña para acceder a la aplicación web
#    - Mínimo 12 caracteres
#    - Combinar letras, números y símbolos
#    - NO usar contraseñas comunes
#
# 2. SECRET_KEY: Clave secreta para firmar sesiones Flask
#    - Generar con: python -c "import secrets; print(secrets.token_hex(32))"
#    - Cambiar en cada instalación
#
# 3. DB_PASSWORD: Contraseña de la base de datos
#    - Mínimo 16 caracteres
#    - NO usar la contraseña por defecto
# ============================================================================
```

### **Generar Claves Seguras**

```bash
# SECRET_KEY (64 caracteres hex)
python -c "import secrets; print(secrets.token_hex(32))"

# APP_PASSWORD (sugerencia: usar generador de contraseñas)
# Ejemplo: openssl rand -base64 32
```

---

## 🐳 Despliegue con Docker

### **Arquitectura de Contenedores**

```
┌─────────────────────────────────────┐
│          Docker Compose             │
├─────────────────────────────────────┤
│                                     │
│  ┌──────────────┐  ┌─────────────┐ │
│  │   Web        │  │     DB      │ │
│  │  (Gunicorn)  │→ │ (Postgres)  │ │
│  │  Port: 5000  │  │ Port: 5432  │ │
│  └──────────────┘  └─────────────┘ │
│         ↓                           │
│   ┌──────────────┐                 │
│   │   Volumes    │                 │
│   │  postgres_data│                │
│   │  uploads/    │                 │
│   └──────────────┘                 │
└─────────────────────────────────────┘
```

### **Paso a Paso**

#### **1. Preparar Archivos**

```bash
# Clonar o copiar proyecto
cd /opt
git clone https://tu-repo/ferreteria-app.git
cd ferreteria-app

# O copiar archivos manualmente
scp -r ferreteria-app/* usuario@servidor:/opt/ferreteria-app/
```

#### **2. Configurar .env**

```bash
cp env.example .env
nano .env  # Editar variables (ver sección anterior)
```

#### **3. Construir e Iniciar**

```bash
# Construir imágenes
docker compose build

# Iniciar servicios
docker compose up -d

# Ver logs
docker compose logs -f web

# Verificar estado
docker compose ps
```

**Salida esperada:**
```
NAME              STATUS         PORTS
ferreteria-db     healthy        5432/tcp
ferreteria-web    healthy        0.0.0.0:5000->5000/tcp
```

#### **4. Verificar Instalación**

```bash
# Health check
curl http://localhost:5000/health

# Salida esperada:
# {"database":"connected","message":"Database connection successful","status":"healthy"}

# Acceder a la aplicación
curl -I http://localhost:5000
# Debe redirigir a /login (HTTP 302)
```

#### **5. Acceder a la Aplicación**

Abrir navegador: `http://tu-servidor:5000`

- Ingresar contraseña configurada en `APP_PASSWORD`
- Verificar acceso a todas las secciones

---

### **Configurar Proxy Reverso (Nginx)**

Para exponer la aplicación en puerto 80/443:

```nginx
# /etc/nginx/sites-available/ferreteria

server {
    listen 80;
    server_name ferreteria.tudominio.com;

    # Redirigir HTTP a HTTPS (recomendado)
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name ferreteria.tudominio.com;

    # Certificados SSL (usar Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/ferreteria.tudominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/ferreteria.tudominio.com/privkey.pem;

    # Proxy a Docker
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Archivos estáticos (opcional, para mejor performance)
    location /static/ {
        proxy_pass http://localhost:5000/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # Logs
    access_log /var/log/nginx/ferreteria_access.log;
    error_log /var/log/nginx/ferreteria_error.log;
}
```

**Activar configuración:**
```bash
sudo ln -s /etc/nginx/sites-available/ferreteria /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

---

## 💾 Backup y Restore

### **Configurar Backups Automáticos**

#### **Linux (Cron)**

```bash
# Dar permisos de ejecución
chmod +x db/production/backup_database.sh

# Editar crontab
crontab -e

# Agregar: Backup diario a las 2:00 AM
0 2 * * * cd /opt/ferreteria-app/db/production && ./backup_database.sh >> /var/log/ferreteria_backup.log 2>&1
```

#### **Windows (Task Scheduler)**

1. Abrir Task Scheduler
2. Crear tarea básica:
   - Nombre: "Ferretería Backup Diario"
   - Disparador: Diario a las 2:00 AM
   - Acción: Ejecutar `backup_database.ps1`

### **Backup Manual**

```bash
# Linux
cd db/production
./backup_database.sh

# Windows
.\backup_database.ps1
```

### **Restore desde Backup**

```bash
# Linux
cd db/production
./restore_database.sh ./backups/ferreteria_backup_20260110_020000.sql.gz

# Windows
# Descomprimir manualmente y usar:
psql -U ferreteria -d ferreteria -f backup.sql
```

### **Ubicación de Backups**

- **Por defecto:** `db/production/backups/`
- **Retención:** Últimos 30 días
- **Formato:** `ferreteria_backup_YYYYMMDD_HHMMSS.sql.gz`

---

## 📊 Monitoreo y Mantenimiento

### **Health Checks**

```bash
# Aplicación
curl http://localhost:5000/health

# Base de datos
docker compose exec db pg_isready -U ferreteria

# Logs en tiempo real
docker compose logs -f web
docker compose logs -f db
```

### **Métricas Clave**

```sql
-- Conectar a la base de datos
psql -U ferreteria -d ferreteria

-- Total de productos
SELECT COUNT(*) as total_productos FROM product WHERE active = TRUE;

-- Ventas del mes actual
SELECT COUNT(*) as ventas_mes, SUM(total) as total_vendido 
FROM sale 
WHERE datetime >= date_trunc('month', CURRENT_DATE) 
  AND status = 'CONFIRMED';

-- Boletas pendientes
SELECT COUNT(*) as boletas_pendientes, SUM(total_amount) as monto_pendiente
FROM purchase_invoice
WHERE status = 'PENDING';

-- Tamaño de la base de datos
SELECT pg_size_pretty(pg_database_size('ferreteria')) as tamaño_db;
```

### **Mantenimiento Regular**

#### **Semanal:**
- Revisar logs de errores
- Verificar espacio en disco
- Comprobar backups exitosos

#### **Mensual:**
- Actualizar dependencias de seguridad
- Revisar performance de consultas lentas
- Limpiar logs antiguos

#### **Trimestral:**
- Auditoría de seguridad
- Revisión de usuarios y permisos
- Actualización de sistema operativo

---

## 🐛 Troubleshooting

### **Problema: No se puede acceder a la aplicación**

```bash
# Verificar que los contenedores están corriendo
docker compose ps

# Ver logs del contenedor web
docker compose logs web --tail=50

# Verificar conectividad
curl http://localhost:5000/health
```

### **Problema: Error de base de datos**

```bash
# Verificar conexión a PostgreSQL
docker compose exec db psql -U ferreteria -d ferreteria -c "SELECT 1;"

# Ver logs de PostgreSQL
docker compose logs db --tail=50

# Reiniciar base de datos
docker compose restart db
```

### **Problema: "APP_PASSWORD no está definida"**

```bash
# Verificar que .env tiene APP_PASSWORD
cat .env | grep APP_PASSWORD

# Verificar que Docker Compose carga el .env
docker compose config | grep APP_PASSWORD

# Recrear contenedores
docker compose down
docker compose up -d
```

### **Problema: Sesión expiró**

- La sesión expira si se reinicia el contenedor web
- Solución: hacer login nuevamente
- Para sesiones persistentes: usar volumen para `/app/instance`

### **Problema: Espacio en disco lleno**

```bash
# Ver uso de disco
df -h

# Limpiar logs de Docker
docker system prune -a --volumes

# Limpiar backups antiguos (>30 días)
find db/production/backups -name "*.sql.gz" -mtime +30 -delete
```

---

## 📞 Soporte

Para problemas adicionales:

1. Revisar logs: `docker compose logs -f`
2. Consultar documentación en `README.md`
3. Verificar configuración en `.env`

---

## ✅ Checklist de Despliegue

- [ ] PostgreSQL instalado y configurado
- [ ] Base de datos creada con schema correcto
- [ ] Datos iniciales cargados (UOM, categorías)
- [ ] Variables de entorno configuradas (`.env`)
- [ ] `APP_PASSWORD` configurado (seguro)
- [ ] `SECRET_KEY` generado (único)
- [ ] Docker Compose corriendo
- [ ] Health check exitoso (`/health`)
- [ ] Login funcional
- [ ] Backups automáticos configurados
- [ ] Nginx/proxy reverso configurado (opcional)
- [ ] SSL/HTTPS configurado (recomendado)
- [ ] Monitoreo básico implementado

---

**Última actualización:** Enero 2026  
**Versión:** 1.0
