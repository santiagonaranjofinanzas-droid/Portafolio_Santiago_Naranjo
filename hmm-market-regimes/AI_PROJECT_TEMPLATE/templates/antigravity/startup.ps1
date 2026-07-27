# Portable Antigravity Startup Script
$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$lockFile = Join-Path $PSScriptRoot "last_run.txt"
$minIntervalMinutes = 5

$runUpdates = $true
if (Test-Path $lockFile) {
    $lastRun = (Get-Item $lockFile).LastWriteTime
    $elapsed = (Get-Date) - $lastRun
    if ($elapsed.TotalMinutes -lt $minIntervalMinutes) {
        $runUpdates = $false
        Write-Output "Antigravity Startup: Skipping updates (last run was $($elapsed.TotalMinutes.ToString('F1')) minutes ago)."
    }
}

if ($runUpdates) {
    Write-Output "Antigravity Startup: Running environment validation and indexing..."
    
    # 1. Update Graphify
    $graphJson = Join-Path $workspaceDir "graphify-out\graph.json"
    if (Test-Path $graphJson) {
        Write-Output "Updating Graphify incrementally..."
        & graphify update $workspaceDir
    } else {
        Write-Output "Extracting Graphify (code-only)..."
        & graphify extract $workspaceDir --code-only
    }
    
    # 2. Update Serena Index
    Write-Output "Indexing Serena symbols..."
    $env:PYTHONUTF8 = "1"
    $env:PYTHONIOENCODING = "utf-8"
    & serena project index
    
    # 3. Health Check Serena
    Write-Output "Running Serena health check..."
    & serena project health-check
    
    # Write lock file
    New-Item -ItemType File -Path $lockFile -Force | Out-Null
    Write-Output "Antigravity Startup: Verification complete."
}
