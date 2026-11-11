<#
.SYNOPSIS
    Uruchamia backend SmartRoute AI (FastAPI + Uvicorn) z interpretera w .venv.

.DESCRIPTION
    Katalogiem roboczym procesu jest backend\, dzięki czemu:
      - pakiet "app" jest importowalny,
      - wczytywany jest plik backend\.env,
      - domyślna baza SQLite (sqlite:///./smartroute.db) powstaje w backend\smartroute.db.
    Tabele są tworzone automatycznie przy starcie aplikacji.

.PARAMETER Port
    Port HTTP (domyślnie 8000).

.PARAMETER BindHost
    Adres nasłuchu (domyślnie 127.0.0.1 - tylko lokalnie).

.PARAMETER NoReload
    Wyłącza automatyczne przeładowanie po zmianie kodu.

.EXAMPLE
    .\run.ps1
    .\run.ps1 -Port 8080 -NoReload
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [string]$BindHost = '127.0.0.1',
    [switch]$NoReload
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'

function Stop-WithError([string]$Message) {
    Write-Host "BŁĄD: $Message" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $VenvPython)) {
    Stop-WithError "Brak środowiska .venv. Najpierw uruchom:  powershell -ExecutionPolicy Bypass -File .\setup.ps1"
}

& $VenvPython -c 'import uvicorn' 2>$null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Uvicorn nie jest zainstalowany w .venv. Uruchom ponownie .\setup.ps1"
}

$uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$Port")
if (-not $NoReload) {
    $uvicornArgs += @('--reload', '--reload-dir', 'app')
}

Write-Host "SmartRoute AI backend:  http://${BindHost}:$Port" -ForegroundColor Cyan
Write-Host "Swagger UI:             http://${BindHost}:$Port/docs" -ForegroundColor Cyan
Write-Host 'Zatrzymanie: Ctrl+C' -ForegroundColor DarkGray

Push-Location $BackendDir
try {
    & $VenvPython @uvicornArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $exitCode
