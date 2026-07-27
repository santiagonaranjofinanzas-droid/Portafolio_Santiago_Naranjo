# Lanza el ecosistema Bloomberg-Palantir completo
Write-Host "--- INICIANDO DESPLIEGUE AUTOMATIZADO ---" -ForegroundColor Cyan

$PidsPath = Join-Path $PSScriptRoot "run_pids.json"
$pids = @{}

# 1. Verificar Redis (Docker)
Write-Host "[1/5] Verificando Redis..." -ForegroundColor Yellow
docker-compose up -d

# 2. Iniciar Quant Service (Puerto 8001)
Write-Host "[2/5] Lanzando Quant Service en segundo plano..." -ForegroundColor Yellow
$quantProc = Start-Process -FilePath "uvicorn" -ArgumentList "app.main:app --port 8001" -WorkingDirectory (Join-Path $PSScriptRoot "quant-service") -WindowStyle Hidden -PassThru
$pids["quant"] = $quantProc.Id

# 3. Iniciar Decision Engine (Puerto 8002)
Write-Host "[3/5] Lanzando Decision Engine en segundo plano..." -ForegroundColor Yellow
$decisionProc = Start-Process -FilePath "uvicorn" -ArgumentList "app.main:app --port 8002" -WorkingDirectory (Join-Path $PSScriptRoot "decision-engine") -WindowStyle Hidden -PassThru
$pids["decision"] = $decisionProc.Id

# 4. Iniciar Dashboard (Puerto 3000)
Write-Host "[4/5] Lanzando Dashboard Next.js en segundo plano..." -ForegroundColor Yellow
$dashboardProc = Start-Process -FilePath "npm" -ArgumentList "run dev" -WorkingDirectory (Join-Path $PSScriptRoot "dashboard") -WindowStyle Hidden -PassThru
$pids["dashboard"] = $dashboardProc.Id

# 5. Iniciar Orquestador Maestro (El Pulso)
Write-Host "[5/5] Activando el Orquestador Maestro en segundo plano..." -ForegroundColor Yellow
$orchestratorProc = Start-Process -FilePath "python" -ArgumentList "master_orchestrator.py" -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
$pids["orchestrator"] = $orchestratorProc.Id

$pids | ConvertTo-Json | Set-Content -Path $PidsPath

Write-Host "--- SISTEMA DESPLEGADO EXITOSAMENTE ---" -ForegroundColor Green
Write-Host "Los servicios están operando en segundo plano (Modo Silencioso)."
Write-Host "Usa 'stop_platform.ps1' para cerrar todo cuando termines."
