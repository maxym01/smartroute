<#
.SYNOPSIS
    Imports the GTFS Static timetable (by default the official ZTM Gdańsk feed) into backend\gtfs.db.

.DESCRIPTION
    Runs "python -m app.cli.gtfs import" with the .venv interpreter from the backend\ directory
    (where .env and the relative database path are resolved). Running it again replaces the
    whole timetable in one transaction; on error the previous timetable stays unchanged.

.PARAMETER Source
    URL (http/https) or path to a local ZIP file. Defaults to GTFS_FEED_URL from the settings.

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
    # A relative path is resolved from where the script was called, not from backend\.
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
