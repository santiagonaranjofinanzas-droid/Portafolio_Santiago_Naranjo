$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\NuevoAdmin\Desktop\Trading\Portafolio_HRP_RMT"
$LogDir = Join-Path $ProjectRoot "logs\monitoring"
$LogFile = Join-Path $LogDir "monitoring_api.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

cmd.exe /c "docker compose --env-file .env -f docker-compose.timescaledb.yml up -d 2>&1" | Out-File -FilePath $LogFile -Append

python -m uvicorn production.monitoring_api:app --host 127.0.0.1 --port 8008 | Out-File -FilePath $LogFile -Append
