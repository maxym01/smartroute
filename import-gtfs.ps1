<#
.SYNOPSIS
    Importuje rozkład GTFS Static (domyślnie oficjalny feed ZTM Gdańsk) do backend\gtfs.db.

.DESCRIPTION
    Uruchamia "python -m app.cli.gtfs import" z interpretera .venv i z katalogu backend\
    (tam leży .env i względna ścieżka bazy). Ponowne uruchomienie podmienia cały rozkład
    w jednej transakcji; przy błędzie poprzedni rozkład zostaje bez zmian.

.PARAMETER Source
    URL (http/https) albo ścieżka do lokalnego pliku ZIP. Domyślnie GTFS_FEED_URL z konfiguracji.

.EXAMPLE
    .\import-gtfs.ps1
    .\import-gtfs.ps1 -Source C:\dane\gtfsgoogle.zip
#>
[CmdletBinding()]
param(
    [string]$Source
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'

if (-not (Test-Path $VenvPython)) {
    Write-Host "BŁĄD: Brak środowiska .venv. Najpierw uruchom:  powershell -ExecutionPolicy Bypass -File .\setup.ps1" -ForegroundColor Red
    exit 1
}

$cliArgs = @('-m', 'app.cli.gtfs', 'import')
if ($Source) {
    # Ścieżkę względną liczymy od miejsca wywołania skryptu, a nie od backend\.
    if (-not ($Source -match '^https?://') -and (Test-Path $Source)) {
        $Source = (Resolve-Path $Source).Path
    }
    $cliArgs += @('--source', $Source)
}

$env:PYTHONIOENCODING = 'utf-8'
Push-Location $BackendDir
try {
    & $VenvPython @cliArgs
    $exitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $exitCode
