# Clean temporary caches safely
$OutputEncoding = [System.Text.Encoding]::UTF8
$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $workspaceDir

Write-Output "Cleaning temporary caches in $workspaceDir..."

# 1. Clean Python __pycache__
Write-Output "Removing __pycache__ folders..."
Get-ChildItem -Path $workspaceDir -Filter "__pycache__" -Directory -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Output "Deleting: $_"
    Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
}

# 2. Clean Serena Cache (not project.yml or memories)
$serenaCache = Join-Path $workspaceDir ".serena\cache"
if (Test-Path $serenaCache) {
    Write-Output "Cleaning Serena symbol cache..."
    Remove-Item $serenaCache -Recurse -Force -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Path $serenaCache -Force | Out-Null
}

# 3. Clean Pytest Cache
$pytestCache = Join-Path $workspaceDir ".pytest_cache"
if (Test-Path $pytestCache) {
    Write-Output "Cleaning Pytest cache..."
    Remove-Item $pytestCache -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Output "[SUCCESS] Cache cleanup complete."
