@echo off
cd /d "%~dp0"
echo [%date% %time%] Iniciando Sistema de Automatización (Master Worker)...

:: Iniciar el Master Worker que coordina todos los bots y procesos
:: Se ejecuta en segundo plano y gestiona el ciclo de 3 horas
start /B .venv\Scripts\python.exe master_worker.py > master_log.txt 2>&1

echo Sistema iniciado correctamente. Todo se ejecutará en segundo plano.
exit
