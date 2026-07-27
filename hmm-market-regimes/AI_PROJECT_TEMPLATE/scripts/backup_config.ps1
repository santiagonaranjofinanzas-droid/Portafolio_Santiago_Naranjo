# Backup project configurations
$OutputEncoding = [System.Text.Encoding]::UTF8
$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

$timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
$backupDir = Join-Path $workspaceDir "backup_config_$timestamp"
Write-Output "Creating configuration backup in $backupDir..."

# Ensure backup directory exists
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$itemsToBackup = @(
    ".agents/mcp_config.json",
    ".agents/hooks.json",
    ".agents/startup.bat",
    ".agents/startup.ps1",
    ".serena/project.yml",
    ".serena/project.local.yml",
    "config.toml"
)

$count = 0
foreach ($item in $itemsToBackup) {
    $fullPath = Join-Path $workspaceDir $item
    if (Test-Path $fullPath) {
        $destPath = Join-Path $backupDir $item
        $destParent = Split-Path $destPath -Parent
        if (!(Test-Path $destParent)) {
            New-Item -ItemType Directory -Path $destParent -Force | Out-Null
        }
        Copy-Item $fullPath $destPath -Force
        Write-Output "Backed up: $item"
        $count++
    }
}

if ($count -gt 0) {
    Write-Output "[SUCCESS] Configurations backed up successfully ($count files)."
} else {
    Write-Output "[WARNING] No configuration files found to backup."
    Remove-Item $backupDir -Recurse -Force -ErrorAction SilentlyContinue
}
