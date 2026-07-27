@echo off
setlocal
cd /d "%~dp0"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

chcp 65001 >nul 2>&1
powershell -ExecutionPolicy Bypass -File "%~dp0\framework.ps1" %*
exit /b %errorlevel%
