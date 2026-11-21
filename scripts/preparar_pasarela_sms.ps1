# Prepara la pasarela SMS de Dacora con un celular Android por USB (docs/pasarela_sms.md).
#
# Uso, desde la raíz del repositorio en PowerShell:
#   powershell -ExecutionPolicy Bypass -File scripts\preparar_pasarela_sms.ps1
#
# Hace, en orden: verifica Docker, crea la clave de firma en .env si falta (y la muestra para
# escribirla en el celular), reconstruye la API, comprueba la pasarela, instala adb si falta,
# espera el celular por USB y lo conecta. Se puede repetir sin problema.

param(
    [string]$Usuario = "",
    [string]$Clave = ""
)

# Continue: Docker escribe su progreso en stderr y no debe tomarse como error.
$ErrorActionPreference = "Continue"
$Repo = Split-Path -Parent $PSScriptRoot
Set-Location $Repo

function Paso($n, $texto) { Write-Host "`n[$n] $texto" -ForegroundColor Cyan }
function Ok($texto) { Write-Host "    OK  $texto" -ForegroundColor Green }
function Falla($texto) { Write-Host "    !!  $texto" -ForegroundColor Red; exit 1 }

# 1. Docker ------------------------------------------------------------------------------------
Paso 1 "Docker"
try { docker info *> $null } catch { Falla "Docker no responde: abra Docker Desktop y espere a que inicie." }
if ($LASTEXITCODE -ne 0) { Falla "Docker no responde: abra Docker Desktop y espere a que inicie." }
# Proyecto de Compose de ESTE repositorio con más contenedores corriendo (la demo en uso).
$proyecto = $null
try {
    $proyectos = docker compose ls --format json | ConvertFrom-Json
    $mio = $proyectos | Where-Object { $_.ConfigFiles -like "*$(Split-Path $Repo -Leaf)*docker-compose.yml*" -and $_.Status -like "running*" } |
        Sort-Object { [int]($_.Status -replace '\D', '') } -Descending | Select-Object -First 1
    if ($mio) { $proyecto = $mio.Name }
} catch { }
if (-not $proyecto) { $proyecto = "dacora" }  # nada corriendo: el nombre por defecto del compose
Ok "Docker activo · proyecto de Compose: $proyecto"

# 2. Clave de firma ----------------------------------------------------------------------------
Paso 2 "Clave de firma de la pasarela (.env)"
$envFile = Join-Path $Repo ".env"
$lineas = if (Test-Path $envFile) { @(Get-Content $envFile) } else { @() }
$actual = $lineas | Where-Object { $_ -match '^SMS_GATEWAY_SIGNING_KEY=(.+)$' } | Select-Object -First 1
if ($actual) {
    $clave = ($actual -split '=', 2)[1].Trim()
    Ok "Ya existe una clave en .env"
} else {
    $bytes = New-Object byte[] 16
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $clave = -join ($bytes | ForEach-Object { $_.ToString("x2") })
    $lineas = @($lineas | Where-Object { $_ -notmatch '^SMS_GATEWAY_SIGNING_KEY=' }) + "SMS_GATEWAY_SIGNING_KEY=$clave"
    Set-Content -Path $envFile -Value $lineas -Encoding ascii
    Ok "Clave nueva creada en .env (no se sube a git)"
}
Write-Host "`n    Escriba esta clave en el celular, en Ajustes > Webhooks > Signing Key (sin espacios):" -ForegroundColor Yellow
Write-Host "        $clave`n" -ForegroundColor Yellow

# 3. API ---------------------------------------------------------------------------------------
Paso 3 "API de Dacora con la pasarela"
docker compose -p $proyecto up -d --build api
if ($LASTEXITCODE -ne 0) { Falla "No se pudo levantar la API (docker compose)." }
$sana = $false
for ($i = 0; $i -lt 40 -and -not $sana; $i++) {
    try { $sana = (Invoke-RestMethod http://localhost:8000/api/v1/health -TimeoutSec 3).status -eq "ok" } catch { Start-Sleep 3 }
}
if (-not $sana) { Falla "La API no respondió en http://localhost:8000. Revise: docker compose -p $proyecto logs api" }
try {
    Invoke-WebRequest http://localhost:8000/api/v1/ingest/sms-gateway -Method Post -Body "{}" `
        -Headers @{ "X-Timestamp" = "1"; "X-Signature" = "x" } -UseBasicParsing -TimeoutSec 5 | Out-Null
    $codigo = 200
} catch { $codigo = [int]$_.Exception.Response.StatusCode }
switch ($codigo) {
    401 { Ok "Pasarela activa y protegida por la clave" }
    503 { Falla "La API no tomó la clave. Revise que .env tenga SMS_GATEWAY_SIGNING_KEY y repita." }
    404 { Falla "Esta versión de la API no tiene la pasarela: use la rama feat/sms-gateway-android o main actualizado." }
    default { Falla "Respuesta inesperada de la pasarela: HTTP $codigo" }
}

# 4. adb ---------------------------------------------------------------------------------------
Paso 4 "adb (Android Platform-Tools)"
$adb = (Get-Command adb -ErrorAction SilentlyContinue).Source
if (-not $adb) {
    $adb = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter adb.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $adb) {
    Write-Host "    Instalando adb con winget..."
    winget install --id Google.PlatformTools -e --accept-source-agreements --accept-package-agreements --disable-interactivity | Out-Null
    $adb = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages" -Recurse -Filter adb.exe -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $adb) { Falla "No se pudo instalar adb. Instálelo a mano: winget install --id Google.PlatformTools -e" }
$env:Path = (Split-Path $adb) + ";" + $env:Path
Ok "adb: $adb"

# 5. Celular por USB ---------------------------------------------------------------------------
Paso 5 "Celular conectado por USB con depuración USB"
Write-Host "    Conecte el celular con un cable de datos y acepte 'Permitir depuración USB' en la pantalla."
$listo = $false
for ($i = 0; $i -lt 60 -and -not $listo; $i++) {
    $estado = & $adb devices | Select-Object -Skip 1 | Where-Object { $_.Trim() }
    if ($estado -match "\tdevice$") { $listo = $true; break }
    if ($estado -match "unauthorized" -and $i % 5 -eq 0) { Write-Host "    El celular pide autorización: acepte en su pantalla." }
    Start-Sleep 2
}
if (-not $listo) { Falla "No se detectó el celular en 2 minutos. Revise el cable y la depuración USB, y repita." }
Ok "Celular detectado"

# 6. Conectar la pasarela ----------------------------------------------------------------------
Paso 6 "Conectar la app del celular con Dacora"
if (-not $Usuario) { $Usuario = Read-Host "    Usuario del 'Local Server' de la app" }
if (-not $Clave) { $Clave = Read-Host "    Clave del 'Local Server' de la app" }
uv run --project services/api python scripts/conectar_pasarela_sms.py --usuario $Usuario --clave $Clave
if ($LASTEXITCODE -ne 0) {
    Write-Host "`n    Si el registro automático falló, agregue el webhook a mano en la app:" -ForegroundColor Yellow
    Write-Host "      evento sms:received · URL http://127.0.0.1:9876/api/v1/ingest/sms-gateway" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nListo. Envíe un SMS al número de la SIM y mírelo en http://localhost:8080/pmu/" -ForegroundColor Green
