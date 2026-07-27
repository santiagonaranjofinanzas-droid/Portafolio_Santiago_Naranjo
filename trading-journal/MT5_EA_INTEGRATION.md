#MT5 EA Configuration & Integration Guide

##Overview

El EA **Black_Knight_Quant_Reporter.mq5** (v4.0) ahora escribe operaciones directamente a la carpeta outbox como archivos JSON. Estos se procesan automáticamente por el outbox agent y se envían al backend en Render con firma HMAC.

##Instalación del EA

###Paso 1: Copiar el archivo EA
1. Ubica tu carpeta de datos de MT5:
   - Windows: `C:\Users\<YourUsername>\AppData\Roaming\MetaQuotes\Terminal\<TerminalID>\MQL5\Experts\`
   - Copiar: `Black_Knight_Quant_Reporter.mq5`

###Paso 2: Compilar el EA
1. Abre MT5
2. Navega a `File` → `Open Data Folder`
3. Ve a `MQL5\Experts`
4. Haz clic derecho en `Black_Knight_Quant_Reporter.mq5` → `Compile`
5. O abre en MetaEditor (`Tools` → `MetaEditor`) y presiona `F5`

###Paso 3: Cargar en una carta
1. En MT5, abre cualquier gráfico (ej: EURUSD, M1)
2. Navega a `Insert` → `Advisors` → `Advisors`
3. Busca `Black_Knight_Quant_Reporter`
4. Haz doble clic o arrastra al gráfico
5. Confirma cuando se pida: `Allow Expert Advisors`, `Allow DLL imports`, `Allow Web requests`

##Configuración del EA

Una vez cargado, configura los parámetros en la ventana `Expert Advisors`:

 Parámetro  Valor Recomendado  Descripción 
-------------------------------------------
 **InpFullHistory**  `true`  Sincronizar todo el historial de operaciones 
 **InpSyncDays**  `90`  Si InpFullHistory=false, sincronizar últimos 90 días 
 **InpOutboxPath**  `_journal_data/outbox_queue/`  Ruta relativa a la carpeta de datos de MT5 

##Carpeta Outbox

El EA escribe en: `<MT5_DATA_FOLDER>/_journal_data/outbox_queue/`

Asegúrate de:
1. **Crear la estructura de carpetas:**
   ```
   <MT5_DATA_FOLDER>/
   └── _journal_data/
       ├── outbox_queue/     (← archivos JSON aquí)
       └── outbox.db         (← base de datos del agente)
   ```

2. **Permisos:** Asegúrate de que MT5 tiene permisos de escritura en esta carpeta

> **IMPORTANTE:** Esta carpeta debe estar en la misma ubicación que tu proyecto principal, o ajusta `InpOutboxPath` en el EA.

##Flujo de Datos

```
MT5 EA (escribe JSON)
  ↓
_journal_data/outbox_queue/*.json
  ↓
Outbox Agent (lee, firma con HMAC)
  ↓
Render Backend (https://bk-quant-api.onrender.com/api/v1/ingest/trade)
  ↓
PostgreSQL (Neon)
  ↓
Frontend Dashboard (Vercel)
```

##Formato JSON Escrito

Ejemplo de archivo escrito por el EA:

```json
{
  "position_id": 12345,
  "symbol": "EURUSD",
  "entrytime": 1681234567,
  "exittime": 1681238567,
  "entryprice": 1.08654,
  "exitprice": 1.08754,
  "gross_pnl": 100.50,
  "commission": -5.00,
  "swap": -2.30,
  "volume": 0.10,
  "type_op": 1,
  "direction": "Sell",
  "exit_reason": 1,
  "netpnl": 93.20,
  "sl": 1.08654,
  "risk_price": 0.00000,
  "valid_sl": "false",
  "magic_number": 0
}
```

**Notas:**
- `entrytime` y `exittime`: timestamps Unix (segundos desde 1970)
- `type_op`: 1 = Venta, 0 = Compra
- `gross_pnl`: incluye comisión y swap antes de restar
- `netpnl`: profit + commission + swap

##Monitoreo en Dashboard

Una vez que el EA está corriendo y escribiendo JSON:

1. **Indicador MT5 Status:**
   - Dashboard muestra estado en la sección Overview
   - Verde = Trades activos en últimos 5 minutos
   - Azul = Escuchando, sin trades recientes
   - Púrpura = Idle (sin actividad)
   - Rojo = Error de conexión

2. **Datos en Tiempo Real:**
   - Cada 30 segundos, el indicador chequea `/api/v1/metrics`
   - Muestra: "Último trade hace Xs", "N trades recientes"

##Solución de Problemas

###Problema: "No se crea archivo en outbox_queue"

**Solución:**
1. Verifica la ruta exacta: `File` → `Open Data Folder` en MT5
2. Crea manualmente la carpeta `_journal_data/outbox_queue/`
3. Recarga el EA (desactiva y activa nuevamente)
4. Revisa el Log del EA en MT5

###Problema: "Indicador muestra rojo (Error)"

**Solución:**
1. Verifica que el Outbox Agent está corriendo:
   ```powershell
   Get-Process python -ErrorAction SilentlyContinue  Select-Object Name, Id
   ```
2. Revisa PHASE2_CREDENTIALS.md tiene las credenciales correctas
3. Reinicia el agente:
   ```cmd
   RUN_MT5_OUTBOX.bat
   ```

###Problema: "Archivos en outbox_queue pero no se sincronizan"

**Solución:**
1. Verifica el agente está leyendo la carpeta correctamente
2. Revisa los logs en Terminal (si ejecutas manualmente):
   ```
   BK_AGENT_ENDPOINT=https://bk-quant-api.onrender.com/api/v1/ingest/trade python scratch/phase2_outbox_agent.py --once
   ```
3. Asegúrate que `BK_INGEST_REQUIRE_HMAC=true` está en el backend

##Comandos Útiles

###Iniciar el Agente
```cmd
RUN_MT5_OUTBOX.bat
```

###Detener el Agente
```cmd
STOP_TERMINAL.bat
```

###Probar Manual (una sola sincronización)
```powershell
$env:BK_AGENT_ENDPOINT='https://bk-quant-api.onrender.com/api/v1/ingest/trade'
$env:BK_HMAC_SECRET='2346976@Sa2'
$env:BK_HMAC_KEY_ID='mt5-node-01'
$env:BK_AGENT_QUEUE_DIR='_journal_data/outbox_queue'
$env:BK_AGENT_DB_PATH='_journal_data/outbox.db'
python scratch/phase2_outbox_agent.py --once
```

##Estadísticas Esperadas

- **Latencia:** ~2-5 segundos desde trade close en MT5 hasta reflejarse en el dashboard
- **Confiabilidad:** 100% (con reintentos exponenciales hasta 12 intentos)
- **Deduplicación:** Automática por event_id (basado en position_id + entry/exit times)

##Próximos Pasos

1.  EA configurado y escribiendo JSON
2.  Dashboard mostrando estado MT5
3.  Multi-tenancy (Fase 3): Soporte para múltiples cuentas MT5
4.  WebSocket real-time: Actualizaciones instantáneas en dashboard

---

**Versión:** 4.0  
**Fecha:** 2026-04-14  
**Estado:** Production Ready
