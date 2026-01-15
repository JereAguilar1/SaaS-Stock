# ============================================================================
# Sistema Ferretería - Script de Backup de Base de Datos (Windows)
# ============================================================================
# Versión: 1.0
# Fecha: Enero 2026
# Uso: .\backup_database.ps1
# ============================================================================

# Configuración
$DB_HOST = if ($env:DB_HOST) { $env:DB_HOST } else { "localhost" }
$DB_PORT = if ($env:DB_PORT) { $env:DB_PORT } else { "5432" }
$DB_NAME = if ($env:DB_NAME) { $env:DB_NAME } else { "ferreteria" }
$DB_USER = if ($env:DB_USER) { $env:DB_USER } else { "ferreteria" }
$DB_PASSWORD = $env:DB_PASSWORD
$BACKUP_DIR = if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { ".\backups" }
$DATE = Get-Date -Format "yyyyMMdd_HHmmss"
$BACKUP_FILE = "$BACKUP_DIR\ferreteria_backup_$DATE.sql"

# Crear directorio de backups si no existe
if (-not (Test-Path $BACKUP_DIR)) {
    New-Item -ItemType Directory -Path $BACKUP_DIR | Out-Null
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Backup de Base de Datos - Sistema Ferretería" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Fecha: $(Get-Date)"
Write-Host "Base de datos: $DB_NAME"
Write-Host "Host: ${DB_HOST}:${DB_PORT}"
Write-Host "Usuario: $DB_USER"
Write-Host "Archivo: $BACKUP_FILE"
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Configurar variable de entorno para password
$env:PGPASSWORD = $DB_PASSWORD

# Realizar backup
Write-Host "Iniciando backup..." -ForegroundColor Yellow

try {
    & pg_dump `
      -h $DB_HOST `
      -p $DB_PORT `
      -U $DB_USER `
      -d $DB_NAME `
      --format=plain `
      --no-owner `
      --no-acl `
      --verbose `
      --file="$BACKUP_FILE"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Backup completado exitosamente" -ForegroundColor Green
        
        # Comprimir backup usando 7-Zip o Compress-Archive
        Write-Host "Comprimiendo backup..." -ForegroundColor Yellow
        
        $BACKUP_FILE_ZIP = "$BACKUP_FILE.zip"
        Compress-Archive -Path $BACKUP_FILE -DestinationPath $BACKUP_FILE_ZIP -Force
        
        if (Test-Path $BACKUP_FILE_ZIP) {
            Write-Host "✓ Backup comprimido: $BACKUP_FILE_ZIP" -ForegroundColor Green
            
            # Eliminar archivo sin comprimir
            Remove-Item $BACKUP_FILE
            
            # Mostrar tamaño
            $SIZE = (Get-Item $BACKUP_FILE_ZIP).Length / 1MB
            Write-Host "Tamaño: $([math]::Round($SIZE, 2)) MB"
            
            # Limpiar backups antiguos (mantener últimos 30 días)
            Write-Host ""
            Write-Host "Limpiando backups antiguos (>30 días)..." -ForegroundColor Yellow
            $CutoffDate = (Get-Date).AddDays(-30)
            Get-ChildItem -Path $BACKUP_DIR -Filter "ferreteria_backup_*.sql.zip" | 
                Where-Object { $_.LastWriteTime -lt $CutoffDate } | 
                Remove-Item -Force
            
            # Contar backups restantes
            $BACKUP_COUNT = (Get-ChildItem -Path $BACKUP_DIR -Filter "ferreteria_backup_*.sql.zip").Count
            Write-Host "Backups disponibles: $BACKUP_COUNT"
            
        } else {
            Write-Host "✗ Error al comprimir backup" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host ""
        Write-Host "✗ Error al realizar backup" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "✗ Error: $_" -ForegroundColor Red
    exit 1
} finally {
    # Limpiar variable de entorno
    Remove-Item Env:\PGPASSWORD -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "Backup completado" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
