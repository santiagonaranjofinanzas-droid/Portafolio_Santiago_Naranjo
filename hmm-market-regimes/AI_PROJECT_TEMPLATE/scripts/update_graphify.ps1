# Update Graphify Index
$OutputEncoding = [System.Text.Encoding]::UTF8
$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $workspaceDir

Write-Output "Updating Graphify knowledge graph..."
if (Get-Command graphify -ErrorAction SilentlyContinue) {
    $graphJson = Join-Path $workspaceDir "graphify-out\graph.json"
    if (Test-Path $graphJson) {
        Write-Output "Running incremental update..."
        & graphify update $workspaceDir
    } else {
        Write-Output "Running code-only extraction..."
        & graphify extract $workspaceDir --code-only
    }
    if ($LASTEXITCODE -eq 0) {
        Write-Output "[SUCCESS] Graphify index updated successfully."
    } else {
        Write-Output "[ERROR] Graphify failed with exit code $LASTEXITCODE."
        exit 1
    }
} else {
    Write-Output "[ERROR] graphify CLI is not in PATH."
    exit 1
}
