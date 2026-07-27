param(
    [int]$RetentionDays = 30
)

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Users\NuevoAdmin\Desktop\Trading\Portafolio_HRP_RMT"
$BackupRoot = Join-Path $ProjectRoot "backups\timescaledb"
$LogDir = Join-Path $ProjectRoot "logs\backups"
$ContainerName = "hrp_rmt_timescaledb"
$DbName = "hrp_rmt"
$DbUser = "postgres"

New-Item -ItemType Directory -Force -Path $BackupRoot | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $ProjectRoot

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupFile = Join-Path $BackupRoot "hrp_rmt_${Timestamp}.dump"
$ManifestFile = Join-Path $BackupRoot "backup_manifest.csv"
$LogFile = Join-Path $LogDir "backup_${Timestamp}.log"

"[$(Get-Date -Format o)] Starting TimescaleDB backup" | Tee-Object -FilePath $LogFile

$PreviousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$DockerOutput = cmd.exe /c "docker compose --env-file .env -f docker-compose.timescaledb.yml up -d 2>&1"
$DockerExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
$DockerOutput | Tee-Object -FilePath $LogFile -Append
if ($DockerExitCode -ne 0) {
    "Docker compose failed with exit_code=$DockerExitCode" | Tee-Object -FilePath $LogFile -Append
    exit $DockerExitCode
}

$DumpCommand = "pg_dump -U $DbUser -d $DbName -Fc"
"Running pg_dump from container $ContainerName" | Tee-Object -FilePath $LogFile -Append
$ErrorActionPreference = "Continue"
$DumpOutput = cmd.exe /c "docker exec $ContainerName $DumpCommand > `"$BackupFile`" 2>&1"
$DumpExitCode = $LASTEXITCODE
$ErrorActionPreference = $PreviousErrorActionPreference
$DumpOutput | Tee-Object -FilePath $LogFile -Append
if ($DumpExitCode -ne 0) {
    "pg_dump failed with exit_code=$DumpExitCode" | Tee-Object -FilePath $LogFile -Append
    exit $DumpExitCode
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $BackupFile).Hash
$Size = (Get-Item -LiteralPath $BackupFile).Length

if (!(Test-Path -LiteralPath $ManifestFile)) {
    "timestamp_utc,path,sha256,size_bytes,retention_days" | Out-File -FilePath $ManifestFile -Encoding utf8NoBOM
}
"$((Get-Date).ToUniversalTime().ToString('o')),$BackupFile,$Hash,$Size,$RetentionDays" | Out-File -FilePath $ManifestFile -Encoding utf8NoBOM -Append

$Cutoff = (Get-Date).AddDays(-1 * $RetentionDays)
Get-ChildItem -LiteralPath $BackupRoot -Filter "hrp_rmt_*.dump" |
    Where-Object { $_.LastWriteTime -lt $Cutoff } |
    ForEach-Object {
        "Deleting expired backup $($_.FullName)" | Tee-Object -FilePath $LogFile -Append
        Remove-Item -LiteralPath $_.FullName -Force
    }

"[$(Get-Date -Format o)] Backup complete file=$BackupFile sha256=$Hash size=$Size" | Tee-Object -FilePath $LogFile -Append
exit 0
