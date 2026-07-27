$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Users\NuevoAdmin\Desktop\Trading\Portafolio_HRP_RMT"
Set-Location $ProjectRoot

docker compose --env-file .env -f docker-compose.timescaledb.yml up -d
docker ps --filter name=hrp_rmt_timescaledb --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
