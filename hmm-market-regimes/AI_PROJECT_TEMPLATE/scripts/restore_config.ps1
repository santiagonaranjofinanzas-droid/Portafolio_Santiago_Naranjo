# Restore project configurations from a backup folder
param (
    [string]$backupFolder = ""
)
$OutputEncoding = [System.Text.Encoding]::UTF8
$workspaceDir = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

if ([string]::IsNullOrEmpty($backupFolder) -or !(Test-Path $backupFolder)) {
    Write-Output "[ERROR] Please specify a valid backup folder path."
    exit 1
}

Write-Output "Restoring configurations from $backupFolder into $workspaceDir..."

# Get all files recursively in the backup folder
$files = Get-ChildItem -Path $backupFolder -Recurse -File
$count = 0
foreach ($f in $files) {
    # Compute relative path
    $relative = $f.FullName.Substring($backupFolder.Length).TrimStart("\/")
    $dest = Join-Path $workspaceDir $relative
    
    # Backup current before overwriting
    $destParent = Split-Path $dest -Parent
    if (!(Test-Path $destParent)) {
        New-Item -ItemType Directory -Path $destParent -Force | Out-Null
    }
    
    if (Test-Path $dest) {
        $backupFile = "$dest.before_restore.bak"
        Copy-Item $dest $backupFile -Force
    }
    
    Copy-Item $f.FullName $dest -Force
    Write-Output "Restored: $relative"
    $count++
}

Write-Output "[SUCCESS] Restored $count configuration files."
