# AI Development Framework Bootstrap Script
# Usage: powershell -ExecutionPolicy Bypass -File bootstrap_project.ps1 [-path <project-path>]

param (
    [string]$path = "."
)

# Set UTF-8 encoding
$OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$scriptDir = $PSScriptRoot
. (Join-Path $scriptDir "shared\utils.ps1")

Write-Log "=========================================="
Write-Log "     AI Development Framework Bootstrap   "
Write-Log "=========================================="

# Resolve absolute path of target project
$targetPath = (Resolve-Path $path).Path

# 1. Run detection
$detectScript = Join-Path $scriptDir "bootstrap\detect.ps1"
Write-Log "Running detection phase..."
$detectionResult = & powershell -ExecutionPolicy Bypass -File $detectScript -projectRoot $targetPath

if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrEmpty($detectionResult)) {
    Write-Error "Detection phase failed."
    exit 1
}

# 2. Run configuration
$configureScript = Join-Path $scriptDir "bootstrap\configure.ps1"
Write-Log "Running configuration phase..."
& powershell -ExecutionPolicy Bypass -File $configureScript -projectRoot $targetPath -detectionJson $detectionResult

if ($LASTEXITCODE -ne 0) {
    Write-Error "Configuration phase failed."
    exit 1
}

# 3. Run validation and health check
$healthcheckScript = Join-Path $targetPath ".agents\scripts\healthcheck.ps1"
if (Test-Path $healthcheckScript) {
    Write-Log "Running health validation..."
    & powershell -ExecutionPolicy Bypass -File $healthcheckScript
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Project successfully bootstrapped and verified!"
    } else {
        Write-Warning "Project bootstrapped with warnings/errors in healthcheck."
    }
} else {
    Write-Warning "Healthcheck script not found in target project."
}
Write-Log "=========================================="
