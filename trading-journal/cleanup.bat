@echo off
echo [*] Iniciando depuracion de entorno...

if not exist _archive\legacy mkdir _archive\legacy

echo [*] Archiving legacy migration scripts...
move migrate_to_supabase.py _archive\legacy\ 2>nul
move migrate_db.py _archive\legacy\ 2>nul

echo [*] Archiving legacy docs...
move PHASE1_SAAS_SETUP.md _archive\legacy\ 2>nul
move PHASE2_OUTBOX_HMAC_SETUP.md _archive\legacy\ 2>nul
move MT5_AUTOMATION_FLOW.md _archive\legacy\ 2>nul
move DEPLOY_REAL_STEP_BY_STEP.md _archive\legacy\ 2>nul

echo [*] Cleaning temporary logs...
del Black_Knight_Quant_Reporter.log 2>nul
del compile_result.log 2>nul

echo [OK] Depuracion completada.
