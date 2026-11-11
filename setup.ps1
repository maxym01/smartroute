<#
.SYNOPSIS
    Przygotowuje lokalne środowisko backendu SmartRoute AI (Windows, Python 3.12).

.DESCRIPTION
    1. Tworzy środowisko wirtualne .venv w katalogu głównym repozytorium (jeśli nie istnieje).
    2. Instaluje backend w trybie edytowalnym wraz z narzędziami dev (pytest, ruff, httpx),
       z wersjami przypiętymi w backend/requirements-lock.txt.
    3. Tworzy backend/.env na podstawie backend/.env.example (jeśli .env jeszcze nie istnieje).

    Skrypt jest idempotentny: można go uruchamiać wielokrotnie. Nie usuwa istniejącego .venv,
    pliku .env ani bazy SQLite.

.PARAMETER NoDev
    Instaluje tylko zależności uruchomieniowe (bez pytest/ruff/httpx).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\setup.ps1
#>
[CmdletBinding()]
param(
    [switch]$NoDev
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RequiredPython = '3.12'
$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$VenvDir = Join-Path $RepoRoot '.venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$LockFile = Join-Path $BackendDir 'requirements-lock.txt'
$EnvExample = Join-Path $BackendDir '.env.example'
$EnvFile = Join-Path $BackendDir '.env'

function Write-Step([string]$Message) { Write-Host "==> $Message" -ForegroundColor Cyan }
function Write-Ok([string]$Message) { Write-Host "    $Message" -ForegroundColor Green }

function Stop-WithError([string]$Message) {
    Write-Host ''
    Write-Host "BŁĄD: $Message" -ForegroundColor Red
    exit 1
}

function Get-PythonVersion([string]$Exe, [string[]]$PrefixArgs = @()) {
    # Zwraca np. "3.12" albo $null, jeśli interpreter nie działa.
    try {
        # Bez cudzysłowów podwójnych: Windows PowerShell 5.1 gubi je przy wywołaniu natywnego exe.
        $out = & $Exe @PrefixArgs -c 'import sys; print(*sys.version_info[:2], sep=chr(46))' 2>$null
        if ($LASTEXITCODE -eq 0 -and $out) { return ($out | Select-Object -First 1).Trim() }
    } catch { }
    return $null
}

function Find-BasePython {
    # Kolejność: launcher "py -3.12", potem "python" z PATH (pomijając alias ze Sklepu Microsoft).
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if ((Get-PythonVersion 'py' @("-$RequiredPython")) -eq $RequiredPython) {
            return @{ Exe = 'py'; Args = @("-$RequiredPython") }
        }
    }
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike '*\WindowsApps\*') {
        if ((Get-PythonVersion $python.Source) -eq $RequiredPython) {
            return @{ Exe = $python.Source; Args = @() }
        }
    }
    return $null
}

if (-not (Test-Path (Join-Path $BackendDir 'pyproject.toml'))) {
    Stop-WithError "Nie znaleziono backend\pyproject.toml. Uruchom skrypt z katalogu głównego repozytorium."
}

# --- 1. Środowisko wirtualne ---------------------------------------------------------------
Write-Step "Środowisko wirtualne (.venv, Python $RequiredPython)"
if (Test-Path $VenvPython) {
    $venvVersion = Get-PythonVersion $VenvPython
    if ($venvVersion -ne $RequiredPython) {
        Stop-WithError ("Istniejące .venv używa Pythona '$venvVersion', wymagany jest $RequiredPython. " +
            "Usuń katalog .venv ręcznie (Remove-Item -Recurse -Force .venv) i uruchom skrypt ponownie.")
    }
    Write-Ok "Używam istniejącego .venv (Python $venvVersion)."
} else {
    $base = Find-BasePython
    if (-not $base) {
        Stop-WithError ("Nie znaleziono Pythona $RequiredPython. Zainstaluj go z https://www.python.org/downloads/ " +
            "(zaznacz 'Add python.exe to PATH' lub użyj launchera 'py') i uruchom skrypt ponownie.")
    }
    & $base.Exe @($base.Args) -m venv $VenvDir
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $VenvPython)) {
        Stop-WithError "Nie udało się utworzyć środowiska .venv."
    }
    Write-Ok "Utworzono .venv."
}

# --- 2. Zależności -------------------------------------------------------------------------
$target = if ($NoDev) { $BackendDir } else { "$BackendDir[dev]" }
Write-Step "Instalacja zależności ($(if ($NoDev) { 'runtime' } else { 'runtime + dev' }))"
$pipArgs = @('-m', 'pip', 'install', '--disable-pip-version-check', '-e', $target)
if (Test-Path $LockFile) {
    $pipArgs += @('-c', $LockFile)
} else {
    Write-Host "    Uwaga: brak $LockFile - wersje nie zostaną przypięte." -ForegroundColor Yellow
}
& $VenvPython @pipArgs
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Instalacja zależności nie powiodła się (pip zwrócił kod $LASTEXITCODE). Sprawdź połączenie z internetem i komunikaty pip powyżej."
}
& $VenvPython -m pip check --disable-pip-version-check
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "pip check wykrył niespójne zależności."
}
Write-Ok "Zależności zainstalowane."

# --- 3. Konfiguracja lokalna ---------------------------------------------------------------
Write-Step "Konfiguracja lokalna (backend\.env)"
if (Test-Path $EnvFile) {
    Write-Ok "backend\.env już istnieje - pozostawiam bez zmian."
} elseif (Test-Path $EnvExample) {
    Copy-Item $EnvExample $EnvFile
    Write-Ok "Utworzono backend\.env z backend\.env.example."
} else {
    Write-Host "    Brak backend\.env.example - aplikacja użyje wartości domyślnych." -ForegroundColor Yellow
}

Write-Host ''
Write-Host 'Gotowe. Uruchom backend poleceniem:  .\run.ps1' -ForegroundColor Green
if (-not $NoDev) {
    Write-Host 'Testy:  cd backend; ..\.venv\Scripts\python.exe -m pytest' -ForegroundColor Green
}
