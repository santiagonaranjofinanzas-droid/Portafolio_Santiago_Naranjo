# Update Serena Index
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $workspaceDir

Write-Output "Updating Serena symbol index..."
if (Get-Command serena -ErrorAction SilentlyContinue) {
    & serena project index
    if ($LASTEXITCODE -eq 0) {
        Write-Output "[SUCCESS] Serena symbols indexed successfully."
    } else {
        Write-Output "[ERROR] Serena failed with exit code $LASTEXITCODE."
        exit 1
    }
} else {
    Write-Output "[ERROR] serena CLI is not in PATH."
    exit 1
}
