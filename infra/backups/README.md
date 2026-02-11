# Database Backup & Restore

Este directorio contiene scripts para backup y restauración de la base de datos PostgreSQL del SaaS Comercial.

## 📁 Estructura

```
infra/backups/
├── backup_db.sh         # Script de backup diario
├── restore_db.sh        # Script de restauración
├── README.md           # Este archivo
└── crontab.example     # Ejemplo de crontab para backups automáticos
```

## 🔧 Configuración

### Variables de Entorno

Los scripts usan las siguientes variables de entorno (definidas en `.env.prod`):

```bash
BACKUP_PATH=/var/backups/ferreteria
BACKUP_RETENTION_DAYS=30
POSTGRES_DB=ferreteria_db
POSTGRES_USER=ferreteria_user
```

### Permisos

Los scripts deben ser ejecutables:

```bash
chmod +x infra/backups/backup_db.sh
chmod +x infra/backups/restore_db.sh
```

---

## 📦 Backup Manual

### Ejecutar Backup

```bash
# Desde el directorio raíz del proyecto
./infra/backups/backup_db.sh
```

El script:
1. Crea un backup comprimido en `/var/backups/ferreteria/daily/`
2. Aplica política de retención (elimina backups > 30 días)
3. Muestra los 5 backups más recientes

### Salida Esperada

```
[2026-01-14 03:00:01] Starting PostgreSQL backup...
[2026-01-14 03:00:01] Backup file: /var/backups/ferreteria/daily/ferreteria_2026-01-14_030001.sql.gz
[2026-01-14 03:00:01] Database: ferreteria_db, User: ferreteria_user
[2026-01-14 03:00:15] Backup completed successfully! Size: 1.2M
[2026-01-14 03:00:15] Backup file created: /var/backups/ferreteria/daily/ferreteria_2026-01-14_030001.sql.gz
[2026-01-14 03:00:15] Applying retention policy (keeping last 30 days)...
[2026-01-14 03:00:15] No old backups to delete
[2026-01-14 03:00:15] Total backups in /var/backups/ferreteria/daily: 15
[2026-01-14 03:00:15] Most recent backups:
[2026-01-14 03:00:15]   ferreteria_2026-01-14_030001.sql.gz (1.2M, 2026-01-14 03:00:01)
[2026-01-14 03:00:15]   ferreteria_2026-01-13_030000.sql.gz (1.1M, 2026-01-13 03:00:00)
[2026-01-14 03:00:15]   ferreteria_2026-01-12_030000.sql.gz (1.1M, 2026-01-12 03:00:00)
[2026-01-14 03:00:15] Backup process completed successfully!
```

### Listar Backups Disponibles

```bash
ls -lh /var/backups/ferreteria/daily/
```

---

## 🔄 Restauración de Backup

### ⚠️ ADVERTENCIA

La restauración **ELIMINARÁ** todos los datos actuales de la base de datos y los reemplazará con el backup.

### Ejecutar Restauración

```bash
# Desde el directorio raíz del proyecto
./infra/backups/restore_db.sh /var/backups/ferreteria/daily/ferreteria_2026-01-14_030001.sql.gz
```

### Proceso de Restauración

El script:
1. Solicita confirmación (debes escribir `YES`)
2. Detiene el servicio web para evitar conexiones activas
3. Restaura la base de datos desde el backup
4. Reinicia el servicio web
5. Verifica la conexión a la base de datos

### Salida Esperada

```
[2026-01-14 10:15:01] ============================================
[2026-01-14 10:15:01] PostgreSQL Database Restore
[2026-01-14 10:15:01] ============================================
[2026-01-14 10:15:01] Backup file: /var/backups/ferreteria/daily/ferreteria_2026-01-14_030001.sql.gz
[2026-01-14 10:15:01] Database: ferreteria_db
[2026-01-14 10:15:01] User: ferreteria_user
[2026-01-14 10:15:01] ============================================
[2026-01-14 10:15:01] WARNING: This will DROP and RECREATE the database!
[2026-01-14 10:15:01] WARNING: All current data will be LOST!

Are you sure you want to continue? Type 'YES' to confirm: YES
[2026-01-14 10:15:05] Starting database restore...
[2026-01-14 10:15:05] Stopping web service...
[2026-01-14 10:15:07] Web service stopped
[2026-01-14 10:15:09] Restoring database from backup...
[2026-01-14 10:15:25] Database restored successfully!
[2026-01-14 10:15:25] Restarting web service...
[2026-01-14 10:15:28] Web service restarted
[2026-01-14 10:15:28] Verifying database connection...
[2026-01-14 10:15:31] Database connection verified!
[2026-01-14 10:15:31] ============================================
[2026-01-14 10:15:31] Restore process completed successfully!
[2026-01-14 10:15:31] ============================================
[2026-01-14 10:15:31] Please verify your application is working correctly.
```

---

## ⏰ Backups Automáticos con Cron

### Configurar Crontab

```bash
# Editar crontab del usuario root o del usuario que ejecuta docker
sudo crontab -e
```

### Agregar Línea de Cron

```cron
# Backup diario a las 3:00 AM (hora del servidor)
0 3 * * * cd /root/ferreteria && ./infra/backups/backup_db.sh >> /var/log/ferreteria_backup.log 2>&1
```

### Verificar Crontab

```bash
sudo crontab -l
```

### Ver Logs de Backup

```bash
tail -f /var/log/ferreteria_backup.log
```

---

## 📊 Monitoreo de Backups

### Verificar Último Backup

```bash
ls -lht /var/backups/ferreteria/daily/ | head -5
```

### Verificar Tamaño de Backups

```bash
du -sh /var/backups/ferreteria/daily/
```

### Verificar Integridad de Backup

```bash
# Descomprimir y verificar archivo SQL
gunzip -t /var/backups/ferreteria/daily/ferreteria_2026-01-14_030001.sql.gz

# Si no hay errores, el archivo es válido
echo $?  # Debe devolver 0
```

---

## 🚨 Troubleshooting

### Problema: "Permission denied"

```bash
# Dar permisos de ejecución
chmod +x infra/backups/backup_db.sh
chmod +x infra/backups/restore_db.sh

# Dar permisos al directorio de backups
sudo mkdir -p /var/backups/ferreteria/daily
sudo chown -R $USER:$USER /var/backups/ferreteria
```

### Problema: "Docker not found"

```bash
# Verificar que Docker está instalado
docker --version

# Verificar que docker compose funciona
docker compose version

# Agregar usuario al grupo docker
sudo usermod -aG docker $USER
newgrp docker
```

### Problema: "Database connection failed"

```bash
# Verificar que el contenedor de DB está corriendo
docker compose -f docker-compose.prod.yml ps db

# Verificar logs del contenedor
docker compose -f docker-compose.prod.yml logs db

# Reiniciar contenedor de DB
docker compose -f docker-compose.prod.yml restart db
```

### Problema: "Backup file is empty"

```bash
# Verificar que el contenedor de DB está saludable
docker compose -f docker-compose.prod.yml exec db pg_isready

# Verificar credenciales en .env.prod
cat .env.prod | grep POSTGRES

# Verificar conectividad manual
docker compose -f docker-compose.prod.yml exec db psql -U ferreteria_user -d ferreteria_db -c "SELECT 1;"
```

---

## 📋 Checklist de Seguridad

- [ ] Backups están en una partición separada o volumen montado
- [ ] Backups tienen permisos restrictivos (chmod 600)
- [ ] Crontab configurado y funcionando
- [ ] Logs de backup monitoreados
- [ ] Política de retención configurada (30 días)
- [ ] Script de restauración probado al menos una vez
- [ ] Backups se copian a un storage externo (opcional pero recomendado)

---

## 🔐 Backups Externos (Recomendado)

Para mayor seguridad, copia los backups a un storage externo:

### Opción 1: rsync a otro servidor

```bash
# Agregar a crontab después del backup
0 4 * * * rsync -avz /var/backups/ferreteria/ user@backup-server:/backups/ferreteria/
```

### Opción 2: S3 / Object Storage

```bash
# Instalar AWS CLI o rclone
apt-get install rclone

# Configurar rclone
rclone config

# Sync a S3
0 4 * * * rclone sync /var/backups/ferreteria/ s3:my-bucket/ferreteria-backups/
```

### Opción 3: Backup local en disco externo

```bash
# Montar disco externo
mount /dev/sdb1 /mnt/backup

# Copiar backups
cp /var/backups/ferreteria/daily/*.sql.gz /mnt/backup/
```

---

## 📞 Soporte

Para problemas o preguntas sobre backups, contactar al administrador del sistema.

**Última actualización:** 2026-01-14
