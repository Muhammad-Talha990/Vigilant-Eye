# VigilantEye — recommended FYP demo startup (Windows PowerShell)
# Usage (from repo root):
#   .\start-dev.ps1
#   .\start-dev.ps1 -Detach
#   .\start-dev.ps1 -Status
#   .\start-dev.ps1 -Stop
#
# Does NOT:
#   - touch Windows PostgreSQL services
#   - modify pg_hba.conf
#   - print secrets
#   - run docker compose down -v

[CmdletBinding()]
param(
    [switch]$Detach,
    [switch]$Stop,
    [switch]$Status,
    [switch]$Build
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Ensure-EnvFile {
    $envPath = Join-Path $Root ".env"
    $example = Join-Path $Root ".env.example"
    if (-not (Test-Path $envPath)) {
        if (-not (Test-Path $example)) {
            throw ".env.example is missing; cannot create .env"
        }
        Copy-Item $example $envPath
        Write-Host "Created .env from .env.example (edit secrets if you wish; defaults are local-dev only)."
    }
    else {
        Write-Host ".env present (values not displayed)."
    }
}

function Assert-Docker {
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        $candidate = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
        if (Test-Path $candidate) {
            $binDir = Split-Path $candidate -Parent
            if ($env:Path -notlike "*$binDir*") {
                $env:Path = "$binDir;$env:Path"
            }
            $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
        }
    }
    if (-not $dockerCmd) {
        Write-Host ""
        Write-Host "Docker: NOT READY" -ForegroundColor Red
        Write-Host "Reason: 'docker' was not found on PATH."
        Write-Host "Install Docker Desktop, start it, then re-run .\start-dev.ps1"
        Write-Host "Winget: winget install -e --id Docker.DockerDesktop"
        exit 1
    }
    try {
        docker info 1>$null 2>$null
        if ($LASTEXITCODE -ne 0) { throw "docker info failed" }
    }
    catch {
        Write-Host ""
        Write-Host "Docker: NOT READY" -ForegroundColor Red
        Write-Host "Reason: Docker Engine is not running."
        Write-Host "Open Docker Desktop, wait until it says Running, then re-run .\start-dev.ps1"
        exit 1
    }
    Write-Host "Docker: READY"
}

function Wait-Http([string]$Url, [string]$Label, [int]$Attempts = 60, [int]$DelaySec = 3) {
    for ($i = 1; $i -le $Attempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 300) {
                Write-Host "$Label`: READY"
                return $true
            }
        }
        catch {
            # keep waiting
        }
        Write-Host "$Label`: waiting ($i/$Attempts)…"
        Start-Sleep -Seconds $DelaySec
    }
    Write-Host "$Label`: NOT READY" -ForegroundColor Red
    Write-Host "Reason: $Url did not become healthy in time."
    return $false
}

if ($Stop) {
    Assert-Docker
    Write-Step "Stopping Compose stack (volumes preserved)"
    docker compose down
    Write-Host "Stopped. Database volume ve_pg was preserved."
    exit 0
}

if ($Status) {
    Assert-Docker
    Write-Step "Compose status"
    docker compose ps
    Write-Host ""
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 5
        Write-Host "Backend /health: READY ($($h.StatusCode))"
    }
    catch { Write-Host "Backend /health: NOT READY" }
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:8000/ready" -UseBasicParsing -TimeoutSec 5
        Write-Host "Backend /ready: READY ($($r.StatusCode))"
    }
    catch { Write-Host "Backend /ready: NOT READY" }
    try {
        $f = Invoke-WebRequest -Uri "http://127.0.0.1:5173/" -UseBasicParsing -TimeoutSec 5
        Write-Host "Frontend: READY ($($f.StatusCode))"
    }
    catch { Write-Host "Frontend: NOT READY" }
    exit 0
}

Write-Step "Environment"
Ensure-EnvFile
Assert-Docker

Write-Step "Validating Compose file"
docker compose config 1>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker config: NOT READY" -ForegroundColor Red
    exit 1
}
Write-Host "Docker config: READY"

Write-Step "Starting stack"
$upArgs = @("compose", "up")
if ($Build -or -not (docker images -q vigilant-eye-api 2>$null)) {
    $upArgs += "--build"
}
# Always build on first explicit request; default include --build for reliability
if ($Build) { }
$upArgs = @("compose", "up", "--build")
if ($Detach) { $upArgs += "-d" }

& docker @upArgs
if ($LASTEXITCODE -ne 0 -and $Detach) {
    Write-Host "Startup: NOT READY" -ForegroundColor Red
    exit $LASTEXITCODE
}

if ($Detach) {
    Write-Step "Waiting for health endpoints"
    $dbOk = $true
    $pg = docker compose ps --format json 2>$null
    # Prefer API readiness (implies DB)
    $apiOk = Wait-Http "http://127.0.0.1:8000/ready" "Backend"
    $frontOk = Wait-Http "http://127.0.0.1:5173/" "Frontend"

    Write-Host ""
    Write-Host "========== VigilantEye ==========" -ForegroundColor Green
    Write-Host "PostgreSQL:  managed by Compose (host port from .env POSTGRES_HOST_PORT, default 15432)"
    if ($apiOk) { Write-Host "Backend:     READY" } else { Write-Host "Backend:     NOT READY" -ForegroundColor Red }
    if ($frontOk) { Write-Host "Frontend:    READY" } else { Write-Host "Frontend:    NOT READY" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Frontend:  http://localhost:5173"
    Write-Host "Backend:   http://127.0.0.1:8000"
    Write-Host "API Docs:  http://127.0.0.1:8000/docs"
    Write-Host "Health:    http://127.0.0.1:8000/health"
    Write-Host "Ready:     http://127.0.0.1:8000/ready"
    Write-Host ""
    Write-Host "Demo accounts: see README.md (password not printed here)."
    Write-Host "Stop:    .\start-dev.ps1 -Stop"
    Write-Host "Status:  .\start-dev.ps1 -Status"
    Write-Host "=================================" -ForegroundColor Green

    if (-not ($apiOk -and $frontOk)) { exit 1 }
}
else {
    Write-Host "Foreground mode: press Ctrl+C to stop (volumes preserved)."
}
