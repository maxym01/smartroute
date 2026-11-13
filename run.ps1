<#
.SYNOPSIS
    Starts the SmartRoute backend (FastAPI + Uvicorn) and frontend (Vite) with one command.

.DESCRIPTION
    Runs both development servers in the current console window:
      - backend: Uvicorn with the .venv interpreter, started from backend\ so that the "app"
        package is importable, backend\.env is loaded and the default SQLite database is
        created in backend\smartroute.db,
      - frontend: the Vite dev server, started from frontend\ (it proxies /api to the backend).

    The script works from any current directory. It checks the prerequisites but never installs
    packages: run setup.ps1 and "npm install" in frontend\ once beforehand.

    If a port is already used by a running SmartRoute server, that server is reused and no second
    instance is started. If the port is used by another program, the script stops with an error
    before starting anything.

    Ctrl+C stops both servers started by this script, including their child processes. If one
    server exits on its own, the other one is stopped as well.

.PARAMETER Port
    Backend HTTP port (default 8000).

.PARAMETER FrontendPort
    Frontend (Vite) port (default 5173).

.PARAMETER BindHost
    Backend listen address (default 127.0.0.1 - local only).

.PARAMETER NoReload
    Disables the backend's automatic reload on code changes.

.PARAMETER BackendOnly
    Starts only the backend.

.PARAMETER FrontendOnly
    Starts only the frontend.

.EXAMPLE
    .\run.ps1
    .\run.ps1 -BackendOnly -NoReload
    .\run.ps1 -Port 8001 -FrontendPort 5174
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 65535)]
    [int]$Port = 8000,
    [ValidateRange(1, 65535)]
    [int]$FrontendPort = 5173,
    [string]$BindHost = '127.0.0.1',
    [switch]$NoReload,
    [switch]$BackendOnly,
    [switch]$FrontendOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$RepoRoot = $PSScriptRoot
$BackendDir = Join-Path $RepoRoot 'backend'
$FrontendDir = Join-Path $RepoRoot 'frontend'
$VenvPython = Join-Path $RepoRoot '.venv\Scripts\python.exe'
$ViteScript = 'node_modules\vite\bin\vite.js'   # relative to frontend\
$MinNodeVersion = [version]'22.12.0'
$ReadyTimeoutSeconds = 90

function Write-Info([string]$Message) { Write-Host $Message -ForegroundColor Cyan }
function Write-Note([string]$Message) { Write-Host $Message -ForegroundColor DarkGray }
function Write-Warn([string]$Message) { Write-Host "UWAGA: $Message" -ForegroundColor Yellow }

function Stop-WithError([string]$Message) {
    Write-Host "BŁĄD: $Message" -ForegroundColor Red
    exit 1
}

function Invoke-NativeQuiet([string]$Exe, [string[]]$Arguments) {
    # Windows PowerShell 5.1 turns native stderr output into terminating errors when
    # $ErrorActionPreference is 'Stop', so it is relaxed for the duration of the call.
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & $Exe @Arguments 2>$null
        return [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = @($output) }
    } finally {
        $ErrorActionPreference = $previous
    }
}

function Test-PortInUse([int]$PortNumber) {
    # Something listening on the IPv4 or IPv6 loopback address counts as "in use"
    # (Vite may listen on ::1 only, Uvicorn on 127.0.0.1).
    foreach ($address in @([System.Net.IPAddress]::Loopback, [System.Net.IPAddress]::IPv6Loopback)) {
        $client = New-Object System.Net.Sockets.TcpClient($address.AddressFamily)
        try {
            $attempt = $client.BeginConnect($address, $PortNumber, $null, $null)
            if ($attempt.AsyncWaitHandle.WaitOne(300) -and $client.Connected) { return $true }
        } catch {
            # Connection refused or IPv6 unavailable: nothing is listening on this address.
        } finally {
            $client.Close()
        }
    }
    return $false
}

function Test-HttpContains([string]$Url, [string]$Text) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3
        return ([string]$response.Content).Contains($Text)
    } catch {
        return $false
    }
}

function Stop-ProcessTree([System.Diagnostics.Process]$Process) {
    if ($Process.HasExited) { return }
    # taskkill /T also ends child processes (Uvicorn's reload worker, Vite's esbuild service).
    $null = Invoke-NativeQuiet 'taskkill.exe' @('/PID', "$($Process.Id)", '/T', '/F')
}

if ($BackendOnly -and $FrontendOnly) {
    Stop-WithError 'Parametry -BackendOnly i -FrontendOnly wykluczają się.'
}
$runBackend = -not $FrontendOnly
$runFrontend = -not $BackendOnly

# Address used to reach the backend from this machine, also when it listens on all interfaces.
$probeHost = if ($BindHost -in @('0.0.0.0', '::', '*')) { '127.0.0.1' } else { $BindHost }
$backendUrl = "http://${probeHost}:$Port"
$frontendUrl = "http://localhost:$FrontendPort"

# --- Prerequisites (checked only, never installed) ---------------------------------------------
if ($runBackend) {
    if (-not (Test-Path $VenvPython)) {
        Stop-WithError 'Brak środowiska .venv. Najpierw uruchom:  powershell -ExecutionPolicy Bypass -File .\setup.ps1'
    }
    if ((Invoke-NativeQuiet $VenvPython @('-c', 'import fastapi, uvicorn')).ExitCode -ne 0) {
        Stop-WithError 'W .venv brakuje FastAPI lub Uvicorn. Uruchom ponownie .\setup.ps1'
    }
}

$nodeExe = $null
if ($runFrontend) {
    $nodeCommand = Get-Command node -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $nodeCommand) {
        Stop-WithError "Nie znaleziono Node.js (wymagany $MinNodeVersion lub nowszy). Zainstaluj go z https://nodejs.org/ i otwórz nowy terminal. Sam backend uruchomisz poleceniem:  .\run.ps1 -BackendOnly"
    }
    $nodeExe = $nodeCommand.Source
    $nodeVersion = $null
    $versionCheck = Invoke-NativeQuiet $nodeExe @('--version')
    if ($versionCheck.ExitCode -eq 0 -and $versionCheck.Output.Count -gt 0) {
        $null = [version]::TryParse(([string]$versionCheck.Output[0]).Trim().TrimStart('v'), [ref]$nodeVersion)
    }
    if (-not $nodeVersion -or $nodeVersion -lt $MinNodeVersion) {
        Stop-WithError "Wymagany Node.js $MinNodeVersion lub nowszy (wykryto: $(if ($nodeVersion) { $nodeVersion } else { 'nieznana wersja' }))."
    }
    if (-not (Test-Path (Join-Path $FrontendDir $ViteScript))) {
        Stop-WithError 'Brak zależności frontendu (frontend\node_modules). Zainstaluj je raz poleceniem:  cd frontend; npm install'
    }
    if (-not (Test-Path (Join-Path $BackendDir 'gtfs.db'))) {
        Write-Warn 'Nie znaleziono backend\gtfs.db. Wyszukiwarka przystanków w interfejsie wymaga rozkładu: .\import-gtfs.ps1 (pomiń tę uwagę, jeśli GTFS_DATABASE_URL wskazuje inny plik).'
    }
}

# --- Ports: reuse a running SmartRoute server, refuse a foreign one -----------------------------
$startBackend = $false
if ($runBackend) {
    if (Test-PortInUse $Port) {
        if (Test-HttpContains "$backendUrl/api/v1/health" 'SmartRoute') {
            Write-Note "Backend SmartRoute już działa na porcie $Port - nie uruchamiam drugiej instancji."
        } else {
            Stop-WithError "Port $Port jest zajęty przez inny program. Zwolnij go albo wybierz inny port, np.  .\run.ps1 -Port 8001"
        }
    } else {
        $startBackend = $true
    }
}

$startFrontend = $false
if ($runFrontend) {
    if (Test-PortInUse $FrontendPort) {
        if (Test-HttpContains "$frontendUrl/" 'SmartRoute') {
            Write-Note "Frontend SmartRoute już działa na porcie $FrontendPort - nie uruchamiam drugiej instancji."
        } else {
            Stop-WithError "Port $FrontendPort jest zajęty przez inny program. Zwolnij go albo wybierz inny port, np.  .\run.ps1 -FrontendPort 5174"
        }
    } else {
        $startFrontend = $true
    }
}

if ($runFrontend -and -not $runBackend -and -not (Test-PortInUse $Port)) {
    Write-Warn "Backend nie odpowiada na porcie $Port. Interfejs nie pobierze danych, dopóki go nie uruchomisz."
}

Write-Host ''
if ($runBackend) { Write-Info "Backend:     $backendUrl   (Swagger UI: $backendUrl/docs)" }
if ($runFrontend) { Write-Info "Frontend:    $frontendUrl" }

if (-not $startBackend -and -not $startFrontend) {
    Write-Note 'Wszystkie wymagane serwery już działają. Nic nie uruchomiono.'
    exit 0
}
Write-Note 'Zatrzymanie: Ctrl+C (zatrzymuje serwery uruchomione przez ten skrypt).'
Write-Host ''

# --- Start and supervise -------------------------------------------------------------------------
$servers = New-Object System.Collections.Generic.List[object]

function Start-Server([string]$Name, [string]$FilePath, [string[]]$Arguments, [string]$WorkingDirectory, [string]$ReadyUrl) {
    $process = Start-Process -FilePath $FilePath -ArgumentList $Arguments -WorkingDirectory $WorkingDirectory -NoNewWindow -PassThru
    # Reading Handle right away keeps ExitCode available after the process ends.
    $null = $process.Handle
    $servers.Add([pscustomobject]@{ Name = $Name; Process = $process; ReadyUrl = $ReadyUrl; Ready = $false })
}

$exitCode = 0
$previousProxyTarget = $env:VITE_BACKEND_PROXY_TARGET
try {
    if ($startBackend) {
        $uvicornArgs = @('-m', 'uvicorn', 'app.main:app', '--host', $BindHost, '--port', "$Port")
        if (-not $NoReload) { $uvicornArgs += @('--reload', '--reload-dir', 'app') }
        Start-Server 'Backend' $VenvPython $uvicornArgs $BackendDir "$backendUrl/api/v1/health"
    }
    if ($startFrontend) {
        # A non-default backend port has to reach the Vite proxy; the default comes from vite.config.ts.
        if ($Port -ne 8000) { $env:VITE_BACKEND_PROXY_TARGET = $backendUrl }
        try {
            Start-Server 'Frontend' $nodeExe @($ViteScript, '--port', "$FrontendPort", '--strictPort') $FrontendDir "$frontendUrl/"
        } finally {
            $env:VITE_BACKEND_PROXY_TARGET = $previousProxyTarget
        }
    }

    $startedAt = Get-Date
    $timeoutReported = $false
    while ($true) {
        $exited = @($servers | Where-Object { $_.Process.HasExited })
        if ($exited.Count -gt 0) {
            foreach ($server in $exited) {
                Write-Host "BŁĄD: $($server.Name) zakończył działanie (kod $($server.Process.ExitCode)). Zatrzymuję pozostałe serwery." -ForegroundColor Red
            }
            $exitCode = 1
            break
        }

        $pending = @($servers | Where-Object { -not $_.Ready })
        foreach ($server in $pending) {
            if (Test-HttpContains $server.ReadyUrl 'SmartRoute') {
                $server.Ready = $true
                Write-Host "$($server.Name) odpowiada: $($server.ReadyUrl)" -ForegroundColor Green
            }
        }
        if ($pending.Count -gt 0 -and @($servers | Where-Object { -not $_.Ready }).Count -eq 0) {
            Write-Host 'SmartRoute gotowy. Zatrzymanie: Ctrl+C' -ForegroundColor Green
        }
        if (-not $timeoutReported -and @($servers | Where-Object { -not $_.Ready }).Count -gt 0 -and
            ((Get-Date) - $startedAt).TotalSeconds -gt $ReadyTimeoutSeconds) {
            Write-Warn "Serwer nie odpowiada od $ReadyTimeoutSeconds s. Sprawdź komunikaty powyżej."
            $timeoutReported = $true
        }
        Start-Sleep -Milliseconds 500
    }
} finally {
    # Runs on Ctrl+C as well: end every server this script started, with its child processes.
    foreach ($server in $servers) { Stop-ProcessTree $server.Process }
    if ($servers.Count -gt 0) { Write-Note 'Zatrzymano serwery uruchomione przez run.ps1.' }
}
exit $exitCode
