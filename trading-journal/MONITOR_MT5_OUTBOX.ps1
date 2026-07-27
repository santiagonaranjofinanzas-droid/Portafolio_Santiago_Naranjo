#!/usr/bin/env pwsh
# BLACK KNIGHT - MT5 OUTBOX MONITOR
# Clean version to avoid encoding issues

param(
    [switch]$Watch = $false
)

$projectPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$localCredentialsPath = Join-Path $projectPath 'PHASE2_CREDENTIALS.local.md'
$templateCredentialsPath = Join-Path $projectPath 'PHASE2_CREDENTIALS.md'
$credentialsPath = $null

if (Test-Path $localCredentialsPath) {
    $credentialsPath = $localCredentialsPath
} elseif (Test-Path $templateCredentialsPath) {
    $credentialsPath = $templateCredentialsPath
}

function Get-CredentialValue {
    param([string]$Key)
    if (-not $credentialsPath) { return $null }
    $pattern = [regex]::Escape($Key) + '=([^`\r\n]+)'
    foreach ($line in Get-Content -Path $credentialsPath) {
        $match = [regex]::Match($line, $pattern)
        if ($match.Success) { return $match.Groups[1].Value.Trim() }
    }
    return $null
}

function Show-Status {
    Clear-Host
    Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "     BLACK KNIGHT - MT5 OUTBOX MONITOR (Real-time)            " -ForegroundColor Cyan
    Write-Host "-----------------------------------------------------------------" -ForegroundColor Cyan

    $outboxPath = Get-CredentialValue -Key 'BK_AGENT_QUEUE_DIR'
    if (-not $outboxPath) { $outboxPath = Join-Path $projectPath "_journal_data\outbox_queue" }
    if (-not [System.IO.Path]::IsPathRooted($outboxPath)) { $outboxPath = Join-Path $projectPath $outboxPath }

    Write-Host "`n--- OUTBOX FOLDER ---" -ForegroundColor Yellow
    Write-Host "Path: $outboxPath" -ForegroundColor Gray
    if (Test-Path $outboxPath) {
        $files = Get-ChildItem -Path $outboxPath -Filter "*.json" -ErrorAction SilentlyContinue
        $count = if ($files) { $files.Count } else { 0 }
        Write-Host "Status: Ready" -ForegroundColor Green
        Write-Host "Pending files: $count" -ForegroundColor Cyan
        
        if ($count -gt 0) {
            Write-Host "Recent exports:" -ForegroundColor White
            $files | Sort-Object CreationTime -Descending | Select-Object -First 5 | ForEach-Object {
                $ago = [datetime]::Now - $_.CreationTime
                $agoStr = "$([int]$ago.TotalSeconds)s"
                if ($ago.TotalMinutes -ge 1) { $agoStr = "$([int]$ago.TotalMinutes)m" }
                Write-Host "  - $($_.Name) ($($_.Length) bytes, $agoStr ago)" -ForegroundColor Green
            }
        }
    } else {
        Write-Host "Status: NOT FOUND" -ForegroundColor Red
    }

    Write-Host "`n--- AGENT STATUS ---" -ForegroundColor Yellow
    $pythonProc = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { 
        try { $_.CommandLine -match "run_phase2_outbox" } catch { $false }
    }
    
    if ($pythonProc) {
        Write-Host "Status: RUNNING" -ForegroundColor Green
        Write-Host "PID: $($pythonProc.Id)" -ForegroundColor Gray
    } else {
        Write-Host "Status: NOT RUNNING" -ForegroundColor Yellow
    }

    Write-Host "`n--- QUICK COMMANDS ---" -ForegroundColor Cyan
    Write-Host "Start Agent: RUN_MT5_OUTBOX.bat" -ForegroundColor Gray
    Write-Host "Stop Agent:  STOP_TERMINAL.bat" -ForegroundColor Gray
    
    Write-Host "`n-----------------------------------------------------------------" -ForegroundColor Cyan
    Write-Host "Timestamp: $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Gray
}

if ($Watch) {
    while ($true) {
        Show-Status
        Start-Sleep -Seconds 5
    }
} else {
    Show-Status
}
