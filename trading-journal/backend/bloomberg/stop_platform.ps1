# Detiene todos los servicios del ecosistema
Write-Host "--- DETENIENDO ECOSISTEMA ---" -ForegroundColor Red

# Detener procesos lanzados por launch_platform.ps1
$PidsPath = Join-Path $PSScriptRoot "run_pids.json"
if (Test-Path $PidsPath) {
	Write-Host "Cerrando servicios registrados..."
	$pids = Get-Content $PidsPath | ConvertFrom-Json
	foreach ($name in $pids.PSObject.Properties.Name) {
		$pid = $pids.$name
		if ($pid) {
			Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
		}
	}
	Remove-Item $PidsPath -ErrorAction SilentlyContinue
} else {
	Write-Host "No se encontro archivo de PIDs. Omitiendo cierre de procesos." -ForegroundColor Yellow
}

# Detener Docker
Write-Host "Bajando contenedores Docker (Redis)..."
docker-compose down

Write-Host "--- SISTEMA DETENIDO ---" -ForegroundColor Green
