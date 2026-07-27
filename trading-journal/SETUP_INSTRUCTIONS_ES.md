# GUÍA DE ACTIVACIÓN: MT5 ↔ DASHBOARD

##Estado Actual 

-  EA corregido y copiado a tu carpeta de MT5
-  Carpetas de outbox creadas
-  Dashboard preparado con indicador MT5
-  Scripts de monitoreo listos

---

## PROCESO DE CONFIGURACIÓN (5 minutos)

###Paso 1: COMPILAR el EA en MT5 (2 minutos)

```
1. Abre MT5 Terminal
2. Presiona: Ctrl+E (o Tools > MetaEditor)
3. En el panel lateral izquierdo, encuentra:
   → Experts > Black_Knight_Quant_Reporter.mq5
4. Presiona: F5 (Compile)
5. Esperas "Compilation completed successfully" (sin errores)
```

**Resultado esperado:**
```
Compiling 'Black_Knight_Quant_Reporter.mq5'...
Compilation completed successfully.
```

---

###Paso 2: CARGAR el EA en un Gráfico (1 minuto)

```
1. En MT5, abre cualquier gráfico (Ej: EURUSD M1)
2. Insert > Advisors > Advisors (o arrastra el EA al gráfico)
3. Se abre ventana "Advisor Settings"
4. Pestaña "Common":
    Allow automated trading
    Allow DLL imports  
    Allow Web Requests
5. Click "OK"
6. En el gráfico debería aparecer un rectángulo verde con "Black Knight Quant Reporter"
```

**Resultado esperado:**
```
[2026.04.14 14:23:45] Black Knight: EA initialized successfully. Listening for trades...
```

---

###Paso 3: INICIAR EL AGENTE (1 minuto)

Ejecuta desde tu carpeta del proyecto:

```powershell
#Opción A: Simple (recomendada)
.\Dashboard.bat

#Opción B: Manual (con más control)
.\RUN_MT5_OUTBOX.bat

#Opción C: Terminal (debug)
.\scratch\run_phase2_outbox_from_md.ps1
```

**Resultado esperado:**
```
[INFO] Outbox agent started - polling every 30s...
[INFO] Listening for JSON files in: _journal_data/outbox_queue
```

---

###Paso 4: VERIFICAR EN DASHBOARD (2 minutos)

Abre en navegador:
```
https://black-knight-saas.vercel.app
```

Busca en la sección **Overview**:
- **MT5 Status Indicator** (arriba, nuevo)
- Estado debería ser:  "MT5 Listening" o 🟣 "MT5 Idle"

---

## FLUJO EN TIEMPO REAL

Una vez configurado, cuando cierres un trade en MT5:

```
1. MT5 EA detecta operación cerrada
   ↓
2. Escribe JSON a: _journal_data/outbox_queue/trade_XXXXX.json
   ↓
3. Agente lee archivo (cada 30s)
   ↓ 
4. Firma con HMAC SHA256
   ↓
5. Envía a: https://bk-quant-api.onrender.com/api/v1/ingest/trade
   ↓
6. Backend valida y almacena en PostgreSQL
   ↓
7. Dashboard actualiza en ~30 segundos
   ↓
8. Ves:  "MT5 Connected" + "Last trade 5s ago"
```

**Latencia esperada:**
- MT5 → JSON: 1s
- Agente read/sign: 2s
- Backend: 0.5s
- Dashboard refresh: 30s (configurable)
- **Total: ~34 segundos**

---

## CHECKLIST DE VERIFICACIÓN

Ejecuta antes de confiar en el sistema:

```powershell
#Terminal PowerShell
.\CHECK_MT5_STATUS.ps1
```

Verifica que  todo esté GREEN:
- [] EA in MT5 folder
- [] Outbox folders exist
- [] Credentials file present
- [] Outbox agent script available
- [] Cloud backend responding

---

## MONITOREO EN TIEMPO REAL

Para ver qué está pasando mientras tradeas:

```powershell
#Auto-refresh cada 5 segundos
.\MONITOR_MT5_OUTBOX.ps1 -Watch
```

Muestra:
-  Archivos JSON en outbox
-  Tamaño de base de datos
-  Estado del agente (running/stopped)
-  Ubicación del EA

---

##🆘 SOLUCIÓN DE PROBLEMAS

### "MT5 Status = Rojo (Error)"

```
Causas posibles:
1. EA no compiló → Compila de nuevo (F5 en MetaEditor)
2. EA no está cargado → Carga en gráfico (Insert > Advisors)
3. Agente detenido → Inicia Dashboard.bat
4. Backend offline → Verifica: https://bk-quant-api.onrender.com/health
```

**Solución rápida:**
```powershell
#Detén todo
.\STOP_TERMINAL.bat

#Y reinicia
.\Dashboard.bat
```

---

### "No hay archivos en outbox_queue"

```
Problema: MT5 no está escribiendo archivos
```

**Solución:**
```
1. Cierra un trade en MT5 (real o fake)
2. Mira en: _journal_data/outbox_queue/
3. Debería haber un archivo: trade_XXXXX_TIMESTAMP.json
4. Si no aparece: EA podría no estar compilado correctamente
```

---

### "Archivos en outbox pero Dashboard no actualiza"

```
Problema: Agente no está procesando
```

**Solución:**
```powershell
#Verifica agente está corriendo
Get-Process python  Where-Object { $_.CommandLine -match "outbox" }

#Si no aparece, lanza:
.\Dashboard.bat

#Mira los logs:
Get-Content _journal_data/logs/outbox.log -Tail 20
```

---

## COMANDOS PRINCIPALES

 Comando  Propósito 
--------------------
 `Dashboard.bat`   Inicia agente + abre dashboard 
 `RUN_MT5_OUTBOX.bat`   Solo agente (sin browser) 
 `STOP_TERMINAL.bat`   Detiene agente 
 `CHECK_MT5_STATUS.ps1`   Verifica sistema 
 `MONITOR_MT5_OUTBOX.ps1 -Watch`   Monitoreo real-time 

---

## PRÓXIMOS PASOS

1.  **Hoy**: Compila EA + carga gráfico + verifica status rojo→verde
2.  **Mañana**: Tradea en vivo, verifica sync automático
3.  **Esta semana**: Conecta histórico de trades (full history)
4.  **Próximo**: Multi-tenancy (múltiples cuentas MT5)

---

## INFORMACIÓN TÉCNICA

**Rutas importantes:**
```
MT5 Experts:     C:\Users\<YourUsername>\AppData\Roaming\MetaQuotes\Terminal\<TerminalID>\MQL5\Experts
Outbox JSON:     <ProjectRoot>\_journal_data\outbox_queue
Outbox DB:       <ProjectRoot>\_journal_data\outbox.db
Backend URL:     https://bk-quant-api.onrender.com/api/v1/ingest/trade
Dashboard URL:   https://black-knight-saas.vercel.app
```

**Archivos de configuración:**
```
PHASE2_CREDENTIALS.local.md   ← Tu HMAC secret (no compartir)
Black_Knight_Quant_Reporter.mq5  ← EA compilado
phase2_outbox_agent.py        ← Daemon de sincronización
```

---

## FAQ

**P: ¿Cada cuánto chequea el agente la carpeta?**
R: Cada 30 segundos (configurable). Por eso la latencia es ~30s.

**P: ¿Qué pasa si cierro más de 1 trade a la vez?**
R: Todos se encolan. El agente procesa secuencialmente, pero rápido.

**P: ¿El HMAC secret está protegido?**
R: Sí. Está en PHASE2_CREDENTIALS.md en .gitignore (no se sube a Git).

**P: ¿Funciona offline?**
R: No. Necesita conexión a Render + Vercel. Local solo funciona pruebas.

---

**Versión:** 1.0  
**Última actualización:** 2026-04-14  
**Estado:** Production Ready 
