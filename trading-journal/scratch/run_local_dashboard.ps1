# Run Local Dashboard (Backend + Frontend + MT5 Outbox Agent)
# Uses WMI to create fully detached processes that survive after the launcher exits.
# PIDs are saved so STOP_TERMINAL.bat can shut them down cleanly.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

$pidDir  = Join-Path $projectRoot '_journal_data\pids'
$logDir  = Join-Path $projectRoot '_journal_data\logs'
New-Item -ItemType Directory -Force $pidDir | Out-Null
New-Item -ItemType Directory -Force $logDir | Out-Null

Write-Host "Iniciando Black Knight local..." -ForegroundColor Cyan

# Resolve absolute paths
$pythonPath      = (Resolve-Path ".\.venv\Scripts\python.exe").Path
$agentScriptPath = (Resolve-Path ".\scratch\run_phase2_outbox_from_md.ps1").Path
$frontendDir     = (Resolve-Path ".\frontend").Path
$npmPath         = (Get-Command npm.cmd -ErrorAction SilentlyContinue).Source
if (-not $npmPath) { $npmPath = "npm.cmd" }

# ── Helper: launch a fully detached process via WMI ──────────────────────
function Start-DetachedProcess {
    param(
        [string]$FilePath,
        [string]$Arguments,
        [string]$WorkDir
    )
    $commandLine = "`"$FilePath`" $Arguments"
    $startInfo   = ([wmiclass]"Win32_ProcessStartup").CreateInstance()
    $startInfo.ShowWindow = 0  # SW_HIDE
    $result = Invoke-WmiMethod -Class Win32_Process -Name Create `
        -ArgumentList @($commandLine, $WorkDir, $startInfo)
    if ($result.ReturnValue -ne 0) {
        throw "WMI Create failed (code $($result.ReturnValue)) for: $commandLine"
    }
    return $result.ProcessId
}

# ── 1. FastAPI Backend (Port 8080) ───────────────────────────────────────
Write-Host "[1/3] Iniciando Backend (FastAPI) en puerto 8080..." -ForegroundColor Yellow
$backendPid = Start-DetachedProcess `
    -FilePath $pythonPath `
    -Arguments "-m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080" `
    -WorkDir $projectRoot
$backendPid | Out-File -FilePath (Join-Path $pidDir 'backend.pid') -Encoding ascii
Write-Host "  PID Backend: $backendPid" -ForegroundColor Gray

# ── 2. Next.js Frontend (Port 3000) ─────────────────────────────────────
Write-Host "[2/3] Iniciando Frontend (Next.js) en puerto 3000..." -ForegroundColor Yellow
$frontendPid = Start-DetachedProcess `
    -FilePath $npmPath `
    -Arguments "run dev" `
    -WorkDir $frontendDir
$frontendPid | Out-File -FilePath (Join-Path $pidDir 'frontend.pid') -Encoding ascii
Write-Host "  PID Frontend: $frontendPid" -ForegroundColor Gray

# ── 3. MT5 Outbox Agent ─────────────────────────────────────────────────
Write-Host "[3/3] Iniciando Agente MT5 Outbox..." -ForegroundColor Yellow
Start-DetachedProcess `
    -FilePath "powershell.exe" `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$agentScriptPath`"" `
    -WorkDir $projectRoot | Out-Null

# ── Wait and verify ─────────────────────────────────────────────────────
Write-Host "`nEsperando que los servicios inicialicen (5s)..." -ForegroundColor Gray
Start-Sleep -Seconds 5

$backendAlive  = $null -ne (Get-Process -Id $backendPid -ErrorAction SilentlyContinue)
$frontendAlive = $null -ne (Get-Process -Id $frontendPid -ErrorAction SilentlyContinue)

if ($backendAlive) {
    Write-Host "[OK] Backend activo (PID $backendPid)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Backend no esta corriendo." -ForegroundColor Red
}

if ($frontendAlive) {
    Write-Host "[OK] Frontend activo (PID $frontendPid)" -ForegroundColor Green
} else {
    Write-Host "[FAIL] Frontend no esta corriendo." -ForegroundColor Red
}

# Open dashboard in browser
Start-Process "http://localhost:3000"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Black Knight corriendo localmente!" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  Backend:  http://127.0.0.1:8080" -ForegroundColor White
Write-Host "  Stop:     .\STOP_TERMINAL.bat" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan
