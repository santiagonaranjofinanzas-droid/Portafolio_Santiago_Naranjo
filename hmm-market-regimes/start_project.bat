@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

echo [1/3] Actualizando Graphify de forma incremental...
if exist "graphify-out\graph.json" (
    graphify update .
) else (
    graphify extract . --code-only
)
if errorlevel 1 goto :graphify_error

echo [2/3] Verificando entorno AI (Serena + Antigravity)...
call serena project index
if errorlevel 1 goto :serena_error
call serena project health-check
if errorlevel 1 goto :serena_error

if /I "%~1"=="--check" (
    echo [3/3] Validacion completada; Antigravity IDE no se abrira.
    exit /b 0
)

echo [3/3] Abriendo Antigravity IDE...
call antigravity-ide .
exit /b %errorlevel%

:graphify_error
echo ERROR: Graphify no pudo actualizar el indice.
pause
exit /b 1

:serena_error
echo ERROR: Serena no pudo validar o indexar el proyecto.
pause
exit /b 1
