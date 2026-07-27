param(
    [Parameter(Mandatory=$true)]
    [string]$BackupFile
)

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\NuevoAdmin\Desktop\Trading\Portafolio_HRP_RMT"
$ContainerName = "hrp_rmt_timescaledb"
$DbName = "hrp_rmt"
$DbUser = "postgres"
$ContainerBackup = "/tmp/restore.dump"

Set-Location $ProjectRoot

if (!(Test-Path -LiteralPath $BackupFile)) {
    throw "Backup file not found: $BackupFile"
}

docker compose --env-file .env -f docker-compose.timescaledb.yml up -d
docker cp $BackupFile "${ContainerName}:$ContainerBackup"
docker exec $ContainerName pg_restore -U $DbUser -d $DbName --clean --if-exists $ContainerBackup
docker exec $ContainerName rm -f $ContainerBackup
