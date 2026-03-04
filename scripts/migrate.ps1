# =============================================================================
# migrate.ps1 -- Aplica manualmente las migraciones SQL sobre Stock-db
# Uso:   .\scripts\migrate.ps1
#        .\scripts\migrate.ps1 -File "MEJORA19_product_features.sql"   # solo una
#        .\scripts\migrate.ps1 -DryRun                                  # simula sin ejecutar
# =============================================================================

param(
    [string]$File      = "",
    [switch]$DryRun    = $false,
    [string]$Container = "Stock-db",
    [string]$DbUser    = "stock",
    [string]$DbName    = "stock"
)

$ErrorActionPreference = "Stop"
$MigrationsPath = Join-Path $PSScriptRoot "..\db\migrations"

function Write-Ok   { param($msg) Write-Host "  [OK]   $msg" -ForegroundColor Green    }
function Write-Skip { param($msg) Write-Host "  [---]  $msg" -ForegroundColor DarkGray }
function Write-Fail { param($msg) Write-Host "  [FAIL] $msg" -ForegroundColor Red      }
function Write-Info { param($msg) Write-Host "  [>>]   $msg" -ForegroundColor Cyan     }

Write-Host ""
Write-Host "===================================================" -ForegroundColor DarkCyan
Write-Host "  Migrador SQL -- SaaS-Stock"                        -ForegroundColor Cyan
Write-Host "  Contenedor   : $Container"                         -ForegroundColor Cyan
Write-Host "  Base de datos: $DbName"                            -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "  MODO DRY-RUN (no se ejecutara nada)" -ForegroundColor Yellow
}
Write-Host "===================================================" -ForegroundColor DarkCyan
Write-Host ""

# Verificar que el contenedor este corriendo
$status = docker inspect --format "{{.State.Status}}" $Container 2>&1
if ($LASTEXITCODE -ne 0 -or $status -ne "running") {
    Write-Fail "El contenedor '$Container' no esta corriendo."
    Write-Host "  Inicialo con: docker compose up -d db" -ForegroundColor Yellow
    exit 1
}
Write-Ok "Contenedor '$Container' esta corriendo."

# Obtener lista de archivos
if ($File -ne "") {
    $sqlFiles = @(Get-Item (Join-Path $MigrationsPath $File) -ErrorAction Stop)
} else {
    $sqlFiles = Get-ChildItem -Path $MigrationsPath -Filter "*.sql" | Sort-Object Name
}

if ($sqlFiles.Count -eq 0) {
    Write-Host "  No se encontraron archivos .sql en $MigrationsPath" -ForegroundColor Yellow
    exit 0
}

Write-Info "Se encontraron $($sqlFiles.Count) archivo(s) para procesar."
Write-Host ""

$applied = 0
$failed  = 0
$skipped = 0

foreach ($sqlFile in $sqlFiles) {
    $name = $sqlFile.Name

    # Saltar rollbacks automaticamente salvo que se pidan explicitamente
    if ($File -eq "" -and $name -match "_rollback") {
        Write-Skip "OMITIDO (rollback): $name"
        $skipped++
        continue
    }

    Write-Host "  --> Aplicando: $name" -ForegroundColor White

    if ($DryRun) {
        Write-Skip "[DRY-RUN] Se ejecutaria psql sobre $name"
        $applied++
        continue
    }

    $content = Get-Content -Path $sqlFile.FullName -Raw -Encoding UTF8

    $output = $content | docker exec -i $Container psql -U $DbUser -d $DbName --set ON_ERROR_STOP=1 2>&1

    if ($LASTEXITCODE -eq 0) {
        Write-Ok "$name"
        $output | Where-Object { $_ -match "^(NOTICE|CREATE|ALTER|INSERT|UPDATE|DROP)" } `
                | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
        $applied++
    } else {
        Write-Fail "$name"
        Write-Host ""
        Write-Host $output -ForegroundColor Red
        Write-Host ""
        $failed++

        $resp = Read-Host "  Continuar con la siguiente migracion? (s/N)"
        if ($resp -notmatch "^[sS]$") {
            Write-Host ""
            Write-Host "  Proceso detenido por el usuario." -ForegroundColor Yellow
            break
        }
    }
}

Write-Host ""
Write-Host "===================================================" -ForegroundColor DarkCyan
Write-Host "  Resumen"                                           -ForegroundColor Cyan
Write-Host "  Aplicadas : $applied"                             -ForegroundColor Green
if ($failed -gt 0) {
    Write-Host "  Fallidas  : $failed" -ForegroundColor Red
} else {
    Write-Host "  Fallidas  : $failed" -ForegroundColor Gray
}
Write-Host "  Omitidas  : $skipped"                             -ForegroundColor DarkGray
Write-Host "===================================================" -ForegroundColor DarkCyan
Write-Host ""

if ($failed -gt 0) { exit 1 } else { exit 0 }
