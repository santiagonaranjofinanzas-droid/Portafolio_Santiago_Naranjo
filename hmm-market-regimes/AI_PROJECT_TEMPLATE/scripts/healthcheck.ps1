# Project Health Check Script
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $workspaceDir

Write-Output "--- Project Health Check ---"
Write-Output "Workspace: $workspaceDir"

$allPassed = $true

# 1. Serena Health Check
if (Get-Command serena -ErrorAction SilentlyContinue) {
    Write-Output "Checking Serena status..."
    try {
        & serena project health-check
        if ($LASTEXITCODE -eq 0) {
            Write-Output "[SUCCESS] Serena health check passed."
        } else {
            Write-Output "[ERROR] Serena health check failed."
            $allPassed = $false
        }
    } catch {
        Write-Output "[ERROR] Serena error: $_"
        $allPassed = $false
    }
} else {
    Write-Output "[WARNING] Serena is not installed or not in PATH."
}

# 2. Graphify Status
$graphJson = Join-Path $workspaceDir "graphify-out\graph.json"
if (Test-Path $graphJson) {
    Write-Output "[SUCCESS] Graphify index exists ($((Get-Item $graphJson).Length) bytes)."
} else {
    Write-Output "[WARNING] Graphify index does not exist at graphify-out/graph.json."
}

# 3. Antigravity Configuration
$mcpConfig = Join-Path $workspaceDir ".agents\mcp_config.json"
if (Test-Path $mcpConfig) {
    Write-Output "[SUCCESS] Antigravity MCP configuration exists."
} else {
    Write-Output "[ERROR] Antigravity MCP configuration is missing."
    $allPassed = $false
}

if ($allPassed) {
    Write-Output "----------------------------"
    Write-Output "[SUCCESS] Project environment is healthy."
    exit 0
} else {
    Write-Output "----------------------------"
    Write-Output "[ERROR] Project has health check failures."
    exit 1
}
