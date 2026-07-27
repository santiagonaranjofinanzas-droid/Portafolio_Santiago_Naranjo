@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "PID_DIR=%ROOT%\_journal_data\pids"
set "LOG_DIR=%ROOT%\_journal_data\logs"
set "QUEUE_DIR=%ROOT%\_journal_data\outbox_queue"
set "BACKEND_PORT=8080"
set "FRONTEND_PORT=3000"
set "BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%"
set "FRONTEND_URL=http://localhost:%FRONTEND_PORT%"
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PID_DIR%" mkdir "%PID_DIR%" >nul 2>nul
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" >nul 2>nul
if not exist "%QUEUE_DIR%" mkdir "%QUEUE_DIR%" >nul 2>nul

if /i "%~1"=="start" goto :start
if /i "%~1"=="stop" goto :stop
if /i "%~1"=="restart" goto :restart
if /i "%~1"=="status" goto :status
if /i "%~1"=="open" goto :open
if /i "%~1"=="shortcut" goto :shortcut
if /i "%~1"=="" goto :menu

echo Uso: %~nx0 [start^|stop^|restart^|status^|open^|shortcut]
exit /b 1

:menu
cls
echo ================================================================
echo   BLACK KNIGHT DASHBOARD
echo ================================================================
echo.
echo   1. Iniciar dashboard completo
echo   2. Detener dashboard
echo   3. Reiniciar dashboard
echo   4. Ver estado
echo   5. Abrir navegador
echo   6. Crear acceso directo en Escritorio
echo   0. Salir
echo.
set /p "CHOICE=Elige una opcion: "
if "%CHOICE%"=="1" goto :start
if "%CHOICE%"=="2" goto :stop
if "%CHOICE%"=="3" goto :restart
if "%CHOICE%"=="4" goto :status
if "%CHOICE%"=="5" goto :open
if "%CHOICE%"=="6" goto :shortcut
if "%CHOICE%"=="0" exit /b 0
goto :menu

:start
call :ensure_tools || exit /b 1
call :stop_silent

echo.
echo ================================================================
echo   Iniciando Black Knight completo
echo ================================================================
echo.

call :start_backend || exit /b 1
call :start_frontend || exit /b 1
call :start_outbox || exit /b 1

echo.
echo Esperando servicios...
timeout /t 6 /nobreak >nul
call :status
call :open
echo.
echo Listo. Dashboard: %FRONTEND_URL%
exit /b 0

:restart
call :stop
goto :start

:stop
echo.
echo Deteniendo Black Knight Dashboard...
call :stop_silent
echo Sistema detenido.
exit /b 0

:stop_silent
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$pidDir='%PID_DIR%';" ^
  "$root='%ROOT%'.Replace('\','\\');" ^
  "$pidFiles=@('backend.pid','frontend.pid','outbox.pid') | ForEach-Object { Join-Path $pidDir $_ };" ^
  "foreach($file in $pidFiles) { if(Test-Path $file) { $text=((Get-Content $file -ErrorAction SilentlyContinue | Select-Object -First 1)+'').Trim(); if($text -match '^\d+$') { Stop-Process -Id ([int]$text) -Force -ErrorAction SilentlyContinue }; Remove-Item $file -Force -ErrorAction SilentlyContinue } };" ^
  "$patterns='uvicorn backend\.app\.main:app|start-server\.js|next-server|run_phase2_outbox|phase2_outbox_agent\.py';" ^
  "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -and $_.CommandLine -match $root -and $_.CommandLine -match $patterns } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue };" ^
  "Get-NetTCPConnection -LocalPort %BACKEND_PORT%,%FRONTEND_PORT% -State Listen -ErrorAction SilentlyContinue | ForEach-Object { if($_.OwningProcess -and $_.OwningProcess -ne $PID) { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
exit /b 0

:status
echo.
echo ================================================================
echo   Estado Black Knight
echo ================================================================
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ports=@(%BACKEND_PORT%,%FRONTEND_PORT%);" ^
  "foreach($port in $ports){ $conn=Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1; if($conn){ Write-Host ('Puerto '+$port+': ACTIVO PID '+$conn.OwningProcess) -ForegroundColor Green } else { Write-Host ('Puerto '+$port+': DETENIDO') -ForegroundColor Yellow } };" ^
  "$agent=Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ? { $_.CommandLine -match 'run_phase2_outbox|phase2_outbox_agent\.py' } | Select-Object -First 1;" ^
  "if($agent){ Write-Host ('Agente MT5: ACTIVO PID '+$agent.ProcessId) -ForegroundColor Green } else { Write-Host 'Agente MT5: DETENIDO' -ForegroundColor Yellow };" ^
  "$queue='%QUEUE_DIR%'; if(Test-Path $queue){ $count=(Get-ChildItem $queue -Filter '*.json' -ErrorAction SilentlyContinue | Measure-Object).Count; Write-Host ('Outbox pendiente: '+$count+' archivo(s)') -ForegroundColor Cyan }"
echo.
exit /b 0

:open
start "" "%FRONTEND_URL%"
exit /b 0

:shortcut
set "SHORTCUT=%USERPROFILE%\Desktop\BlackKnight_Dashboard.lnk"
set "ICON=%ROOT%\dashboard.ico"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws=New-Object -ComObject WScript.Shell;" ^
  "$s=$ws.CreateShortcut('%SHORTCUT%');" ^
  "$s.TargetPath='%ROOT%\BlackKnight_Dashboard.bat';" ^
  "$s.WorkingDirectory='%ROOT%';" ^
  "$s.Description='Black Knight Dashboard completo';" ^
  "if(Test-Path '%ICON%'){ $s.IconLocation='%ICON%,0' };" ^
  "$s.Save()"
echo Acceso directo creado: %SHORTCUT%
exit /b 0

:ensure_tools
if not exist "%PYTHON%" (
    echo [ERROR] No encontre Python virtualenv: %PYTHON%
    exit /b 1
)
if not exist "%ROOT%\frontend\package.json" (
    echo [ERROR] No encontre frontend\package.json
    exit /b 1
)
where npm.cmd >nul 2>nul
if errorlevel 1 (
    echo [ERROR] No encontre npm.cmd en PATH.
    exit /b 1
)
if not exist "%ROOT%\scratch\run_phase2_outbox_from_md.ps1" (
    echo [ERROR] No encontre scratch\run_phase2_outbox_from_md.ps1
    exit /b 1
)
exit /b 0

:start_backend
echo [1/3] Backend FastAPI en %BACKEND_URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process -FilePath '%PYTHON%' -ArgumentList '-m uvicorn backend.app.main:app --host 127.0.0.1 --port %BACKEND_PORT%' -WorkingDirectory '%ROOT%' -RedirectStandardOutput '%LOG_DIR%\backend.log' -RedirectStandardError '%LOG_DIR%\backend.err.log' -WindowStyle Hidden -PassThru; $p.Id | Set-Content '%PID_DIR%\backend.pid'"
exit /b %ERRORLEVEL%

:start_frontend
echo [2/3] Frontend Next.js en %FRONTEND_URL%
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$npm=(Get-Command npm.cmd).Source; $p=Start-Process -FilePath $npm -ArgumentList 'run dev' -WorkingDirectory '%ROOT%\frontend' -RedirectStandardOutput '%LOG_DIR%\frontend.log' -RedirectStandardError '%LOG_DIR%\frontend.err.log' -WindowStyle Hidden -PassThru; $p.Id | Set-Content '%PID_DIR%\frontend.pid'"
exit /b %ERRORLEVEL%

:start_outbox
echo [3/3] Agente MT5 outbox
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p=Start-Process -FilePath 'powershell.exe' -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%ROOT%\scratch\run_phase2_outbox_from_md.ps1""' -WorkingDirectory '%ROOT%' -RedirectStandardOutput '%LOG_DIR%\outbox.log' -RedirectStandardError '%LOG_DIR%\outbox.err.log' -WindowStyle Hidden -PassThru; $p.Id | Set-Content '%PID_DIR%\outbox.pid'"
exit /b %ERRORLEVEL%
