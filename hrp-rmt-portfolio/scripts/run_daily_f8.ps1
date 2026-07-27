param(
    [string]$RunDate = (Get-Date -Format "yyyy-MM-dd"),
    [switch]$SkipFetch
)

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\NuevoAdmin\Desktop\Trading\Portafolio_HRP_RMT"
$LogDir = Join-Path $ProjectRoot "logs\f8"
$PythonExe = "python"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path $LogDir "f8_daily_${RunDate}_${Timestamp}.log"

$ArgsList = @("production\run_daily_pipeline.py", "--date", $RunDate)
if ($SkipFetch) {
    $ArgsList += "--skip-fetch"
}

"[$(Get-Date -Format o)] Starting F8 daily pipeline for $RunDate" | Tee-Object -FilePath $LogFile
"ProjectRoot=$ProjectRoot" | Tee-Object -FilePath $LogFile -Append
"Starting/verifying TimescaleDB container" | Tee-Object -FilePath $LogFile -Append
$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$DockerOutput = cmd.exe /c "docker compose --env-file .env -f docker-compose.timescaledb.yml up -d" 2>&1
$DockerExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
$DockerOutput | Tee-Object -FilePath $LogFile -Append
if ($DockerExitCode -ne 0) {
    "Docker compose failed with exit_code=$DockerExitCode" | Tee-Object -FilePath $LogFile -Append
    exit $DockerExitCode
}
"Command=$PythonExe $($ArgsList -join ' ')" | Tee-Object -FilePath $LogFile -Append

& $PythonExe @ArgsList 2>&1 | Tee-Object -FilePath $LogFile -Append
$ExitCode = $LASTEXITCODE

"[$(Get-Date -Format o)] Finished with exit_code=$ExitCode" | Tee-Object -FilePath $LogFile -Append
exit $ExitCode
