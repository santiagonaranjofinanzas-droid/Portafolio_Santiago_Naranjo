@echo off
cd /d "%~dp0"
echo [%date% %time%] Iniciando sincronizacion... >> scraper_log.txt
.venv\Scripts\python.exe uni_scraper.py >> scraper_log.txt 2>&1
echo [%date% %time%] Sincronizacion finalizada. >> scraper_log.txt
exit
