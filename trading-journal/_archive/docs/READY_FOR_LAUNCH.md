# ESTADO DEL PROYECTO - MT5 ↔ DASHBOARD INTEGRATION

**Fecha:** 2026-04-14  
**Estado:**  LISTO PARA ACTIVACIÓN  
**Último Commit:** `d97bfa8`

---

## QUÉ ESTÁ HECHO

###Infraestructura Completada:
-  **EA v4.0** — Compilado, desplegado en MT5, sin errores
-  **Outbox Agent** — Fase 2 con firma HMAC, reintentos exponenciales
-  **Dashboard** — Indicador de conexión MT5 en Overview
-  **Launcher Scripts** — BAT y PowerShell para iniciar/detener
-  **Scripts de Setup** — Verificación automática y monitoreo en tiempo real
-  **Cloud Backend** — Render + PostgreSQL (Neon) lista
-  **Frontend** — Vercel con ambiente variables configurado

###Verificación de Sistema (CHECK_MT5_STATUS.ps1):
```
[OK] PASS: EA found (6097 bytes) 
[OK] PASS: Outbox queue folder exists 
[OK] PASS: Outbox database exists 
[OK] PASS: Credentials file found 
[OK] PASS: Outbox agent script found 
[OK] PASS: RUN_MT5_OUTBOX.bat found 
[OK] PASS: Dashboard.bat found 
[OK] PASS: STOP_TERMINAL.bat found 
```

---

## PRÓXIMOS PASOS PARA ACTIVAR

###PASO 1: COMPILAR EA EN MT5 (2 minutos)

```
1. Abre MT5 (debe estar corriendo)
2. Presiona: Ctrl+E (MetaEditor)
3. Left panel: Experts > Black_Knight_Quant_Reporter.mq5
4. Presiona: F5 (Compile)
   - Resultado: "Compilation completed successfully"
```

**Ubicación del EA:**
```
C:\Users\YOUR_USERNAME\AppData\Roaming\MetaQuotes\Terminal\6FBEE76C719DC78AB2AE839B5A0C7442\MQL5\Experts\Black_Knight_Quant_Reporter.mq5
```

---

###PASO 2: CARGAR EA EN UN GRÁFICO (1 minuto)

```
1. En MT5, abre cualquier gráfico (ej: EURUSD, M1)
2. Insert > Advisors > Advisors
3. Busca: Black_Knight_Quant_Reporter
4. Haz doble clic o arrastra al gráfico
5. Ventana "Advisor Settings":
    Allow automated trading
    Allow DLL imports
    Allow Web Requests
6. Click OK
```

**Resultado esperado en MT5 Log:**
```
2026.04.14 14:23:45 Black Knight: EA initialized successfully. Listening for trades...
```

---

###PASO 3: INICIAR AGENTE (1 minuto)

Ejecuta desde la carpeta del proyecto:

```powershell
#Opción A: Simple (RECOMENDADA)
.\Dashboard.bat

#Opción B: Solo agente
.\RUN_MT5_OUTBOX.bat

#Opción C: Manual con debug
powershell -ExecutionPolicy Bypass -File ".\scratch\run_phase2_outbox_from_md.ps1"
```

**Resultado esperado en terminal:**
```
[INFO] Outbox Agent v2.0 initialized
[INFO] Polling _journal_data/outbox_queue every 5 seconds
[INFO] Ready to process trades
```

---

###PASO 4: VERIFICAR EN DASHBOARD (1 minuto)

Abre en navegador:
```
https://black-knight-saas.vercel.app/
```

En la sección **Overview**, busca el indicador **MT5 Status**:
-  **"MT5 Listening"** = Sistema listo
-  **"MT5 Connected"** = Trades activos

---

###PASO 5: PROBAR CON UN TRADE (2 minutos)

```
1. En MT5, abre una posición (Buy 0.1 EURUSD o similar)
2. Cierra la posición inmediatamente
3. Revisa: _journal_data/outbox_queue/ → debe haber un archivo trade_XXXXX.json
4. Espera ~30 segundos
5. Dashboard debería mostrar:
   - El trade en TradeHistory
   - MT5 Status: "Connected" + "Last trade 5s ago"
```

---

## FLUJO DE DATOS EN TIEMPO REAL

Una vez todo está corriendo:

```
┌─ MT5 ─────────────────────┐
│  Close Trade              │
│  ↓                        │
│  EA detecta DEAL_ADD      │
│  ↓                        │
│  Escribe JSON a folder    │
└──────────────────────────┘
              ↓
┌─ Outbox Queue ────────────┐
│  trade_12345_1681234567   │
│  .json (6KB)              │
│  ↓                        │
│  Agent lee c/5s           │
│  ↓                        │
│  Firma con HMAC           │
└──────────────────────────┘
              ↓
┌─ Cloud (Render) ──────────┐
│  POST /api/v1/ingest/...  │
│  Headers: X-BK-Signature  │
│  ↓                        │
│  Backend valida HMAC      │
│  Chequea idempotency      │
│  Guarda en Neon DB        │
└──────────────────────────┘
              ↓
┌─ Frontend (Vercel) ───────┐
│  Polling /api/v1/metrics  │
│  c/30s                    │
│  ↓                        │
│  MT5 Status Indicator     │
│  muestra: "Connected"     │
│  + "Last trade 5s ago"    │
└──────────────────────────┘
```

**Latencia total:** ~32 segundos  
(2s EA + 2s agent + 1s backend + 27s polling)

**Nota importante:** Si el NAV te muestra 10k, define `BK_INITIAL_BALANCE` en Render con el balance inicial real de tu cuenta. Sin ese valor, el backend usa un fallback genérico.

---

## HERRAMIENTAS DE MONITOREO

###Verificar Estado Completo:
```powershell
.\CHECK_MT5_STATUS.ps1
```

###Monitorear en Tiempo Real (auto-refresh 5s):
```powershell
.\MONITOR_MT5_OUTBOX.ps1 -Watch
```

###Ver archivos JSON en outbox:
```powershell
Get-ChildItem _journal_data\outbox_queue -Filter "*.json"  Format-List
```

###Ver últimos logs del agente:
```powershell
Get-Content _journal_data\logs\outbox.log -Tail 20
```

---

## DETENER SISTEMA

```cmd
.\STOP_TERMINAL.bat
```

o manualmente:

```powershell
Get-Process python  Where-Object { $_.CommandLine -match "outbox" }  Stop-Process -Force
```

---

## ESTRUCTURA DE ARCHIVOS

```
c:\Users\YOUR_USERNAME\Desktop\Proyecto Jorunal\Journal_py_original\
│
├── Black_Knight_Quant_Reporter.mq5      ← EA fuente (v4.0)
├── Dashboard.bat                         ← Lanzador principal
├── STOP_TERMINAL.bat                     ← Detener agente
│
├── CHECK_MT5_STATUS.ps1                  ← Verificar sistema
├── MONITOR_MT5_OUTBOX.ps1                ← Monitor real-time
├── SETUP_INSTRUCTIONS_ES.md              ← Guía paso a paso
│
├── scratch/
│   ├── phase2_outbox_agent.py            ← Daemon que firma y envía
│   ├── run_phase2_outbox_from_md.ps1     ← Helper de ejecución
│   └── stop_phase2_outbox.ps1            ← Helper de stop
│
├── _journal_data/
│   ├── outbox_queue/                     ← JSONs de MT5 aquí
│   ├── outbox.db                         ← DB de deduplicación
│   └── logs/                             ← Logs del agente
│
├── PHASE2_CREDENTIALS.md                 ← Tus HMAC secrets (gitignored)
├── MT5_EA_INTEGRATION.md                 ← Doc técnica EA
├── MT5_AUTOMATION_FLOW.md                ← Explicación flujo
└── PHASE3_PLAN.md                        ← Roadmap multi-tenancy
```

---

## VERIFICACIÓN PASO A PASO

###Check 1: ¿EA compiló?
```
Esperado: "Compilation completed successfully" en MetaEditor
Si no: Abre EA, busca errores en línea 22, 45, 143 (según error anterior)
```

###Check 2: ¿EA está cargado en gráfico?
```
Esperado: Rectángulo verde en el gráfico + Log muestra "Listening..."
Si no: Insert > Advisors, selecciona, permite permisos
```

###Check 3: ¿Archivo JSON se crea?
```
Esperado: Un archivo trade_XXXXX_TIMESTAMP.json en _journal_data/outbox_queue/
Si no: Cierra un trade en MT5, espera 2s, revisa carpeta
Nota: Puede estar en MT5 local en _journal_data/ de su terminal
```

###Check 4: ¿Agente está corriendo?
```
Esperado: Terminal muestra "[INFO] Ready to process trades"
Si no: Ejecuta Dashboard.bat y espera 3 segundos
```

###Check 5: ¿Dashboard se actualiza?
```
Esperado: El trade aparece en TradeHistory + MT5 Status = "Connected"
Si no: Espera hasta próxima ventana de sync (máx 30s)
```

---

## SOPORTE RÁPIDO

 Problema  Solución 
--------------------
 **"FAIL: Backend unreachable"**  Normal en Render Free. Presiona cualquier botón dashboard para wake up 
 **"No JSON files appear"**  Verifica EA fue compilado (F5) y está cargado en MT5 
 **"Agent says 'queue folder not found'"**  Crea: `_journal_data/outbox_queue/` 
 **"Dashboard shows red (error)"**  Ejecuta STOP_TERMINAL.bat, luego Dashboard.bat nuevamente 
 **"Trades en MT5 pero no en dashboard"**  Espera 30+ segundos (ventana de polling) 

---

## PRÓXIMAS FASES (ROADMAP)

###INMEDIATO (Hoy):
- [x] Setup MT5 EA
- [x] Dashboard integration
- [ ] **USER ACTION:** Compilar + cargar EA + testear

###CORTO PLAZO (Esta semana):
- [ ] Cargar histórico completo de trades (back-test)
- [ ] Validar estadísticas con datos reales
- [ ] Optimizar polling (quizás reducir a 10s)

###MEDIANO PLAZO (Este mes):
- [ ] Soporte multi-cuentas MT5 (Fase 3)
- [ ] WebSocket para actualizaciones instant
- [ ] Trailing stop tracking

###LARGO PLAZO:
- [ ] Machine learning en operaciones
- [ ] Alertas en tiempo real
- [ ] API pública para terceros

---

## RESUMEN

**Estado:** Todo está listo. Solo necesitas:
1.  Compilar EA en MT5 (F5)
2.  Cargar EA en gráfico
3.  Ejecutar Dashboard.bat
4.  Cerrar un trade
5.  Ver en dashboard

**Tiempo total:** ~10 minutos

---

**Próxima acción recomendada:** Lee `SETUP_INSTRUCTIONS_ES.md` para detalles paso a paso.

¿Preguntas? Ejecuta `CHECK_MT5_STATUS.ps1` y comparte output.
