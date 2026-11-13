<#
.SYNOPSIS
    Starts the SmartRoute backend (FastAPI + Uvicorn) with the .venv interpreter.

.DESCRIPTION
    The process working directory is backend\, so that:
      - the "app" package is importable,
      - the backend\.env file is loaded,
      - the default SQLite database (sqlite:///./smartroute.db) is created in backend\smartroute.db.
    Tables are created automatically when the application starts.

.PARAMETER Port
    HTTP port (default 8000).

.PARAMETER BindHost
    Listen address (default 127.0.0.1 - local only).

.PARAMETER NoReload
    Disables automatic reload on code changes.

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

Write-Host "SmartRoute backend:     http://${BindHost}:$Port" -ForegroundColor Cyan
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
