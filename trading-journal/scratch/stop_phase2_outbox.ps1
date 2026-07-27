Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$pidDir = Join-Path $projectRoot '_journal_data\pids'
$pidFiles = @(
    (Join-Path $pidDir 'backend.pid'),
    (Join-Path $pidDir 'frontend.pid')
)

Write-Host "Deteniendo procesos por PID..." -ForegroundColor Yellow
foreach ($pidFile in $pidFiles) {
    if (Test-Path $pidFile) {
        $pidText = ((Get-Content $pidFile -ErrorAction SilentlyContinue | Select-Object -First 1) + '').Trim()
        if ($pidText -match '^\d+$') {
            Stop-Process -Id ([int]$pidText) -Force -ErrorAction SilentlyContinue
        }

        Remove-Item $pidFile -Force -ErrorAction SilentlyContinue
    }
}

Write-Host "Deteniendo agentes por patron de comando..." -ForegroundColor Yellow
$patterns = 'phase2_outbox_agent\.py|run_phase2_outbox\.ps1|run_phase2_outbox_from_md\.ps1|run_local_dashboard\.ps1'
Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -match $patterns } |
    ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Write-Host "Liberando puertos 8080 y 3000..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 8080,3000 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    $processIdToKill = $_.OwningProcess
    if ($processIdToKill -and $processIdToKill -ne $PID) {
        Write-Host "Killed process $processIdToKill holding port $($_.LocalPort)" -ForegroundColor Yellow
        Stop-Process -Id $processIdToKill -Force -ErrorAction SilentlyContinue
    }
}

Write-Host 'Sistema detenido con éxito.' -ForegroundColor Green
