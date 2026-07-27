@echo off
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
powershell -ExecutionPolicy Bypass -File "%~dp0\startup.ps1"
