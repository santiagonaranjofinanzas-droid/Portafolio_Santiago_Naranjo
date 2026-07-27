# Update all indices
$OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "=== Updating Serena and Graphify indices ==="

$scriptDir = $PSScriptRoot
& (Join-Path $scriptDir "update_graphify.ps1")
& (Join-Path $scriptDir "update_serena.ps1")

Write-Output "All updates completed."
