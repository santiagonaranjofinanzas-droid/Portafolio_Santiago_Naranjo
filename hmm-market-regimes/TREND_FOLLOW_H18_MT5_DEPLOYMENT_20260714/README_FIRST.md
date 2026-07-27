#H18 Trend Follow — paquete único de despliegue MT5

Este paquete contiene exclusivamente el **Trend Follow H18**. No contiene ni
autoriza Mean Reversion.

 EA  Modelo  Magic  Horizontes H1 
---------:---
 `H18_TREND10_6001.ex5`  Medium Slow Trend  6001  12/24/48 
 `H18_TREND11_6002.ex5`  Ultra Slow Trend  6002  24/48/96 

##Estado de autorización

- Permitido: Strategy Tester y cuenta demo hedging.
- Prohibido: cuenta real. El código también falla cerrado en una cuenta live.
- El sistema es prometedor, pero no está aprobado institucionalmente.
- La paridad estática fue auditada; falta aprobar paridad runtime con el mismo
  feed MT5/Python.
- 6001 y 6002 son candidatos alternativos, no un ensemble aprobado. No se debe
  sumar su backtest ni presentar su exposición conjunta como el sistema validado.

##Motor institucional H18_RISK_V1_20260714

- Riesgo máximo por sleeve: 0.25% de equity.
- Riesgo agregado 6001 + 6002: 0.50% de equity.
- Target de volatilidad conjunto: 10% anual, dividido entre ambos sleeves.
- Stop ejecutivo congelado: 6 ATR H1.
- Stop de desastre colocado en el servidor: 8 ATR H1.
- Bloqueo diario de entradas: 1%; throttle desde 5% DD; bloqueo en 7.5%; emergencia en 10%.
- Volumen redondeado siempre hacia abajo; si el mínimo del broker excede el riesgo, la operación se rechaza.
- `OrderCheck`, retcode final y SL confirmado son obligatorios.

El diagnóstico consumido conservó PF 1.262 y DD 2.94%, pero falló Sharpe diario
(0.593 < 1.0) y DSR (0.207 < 0.95). El paquete continúa `LIVE_LOCKED`; falta paridad de riesgo y
evidencia futura independiente. Para probar el límite agregado, 6001 y 6002 deben
coexistir en una sola cuenta demo hedging sin otros sistemas.

##1. Verificar el paquete

```powershell
.\VERIFY_PACKAGE.ps1
```

##2. Instalar en el terminal demo

Obtén la carpeta de datos desde MT5 con `Archivo > Abrir carpeta de datos` y usa:

```powershell
.\INSTALL_DEMO.ps1 `
  -TerminalDataPath "C:\Users\<usuario>\AppData\Roaming\MetaQuotes\Terminal\<id>" `
  -ConfirmDemoAccount
```

##3. Iniciar observación sin órdenes

1. En una cuenta Axi demo **hedging**, abre dos gráficos `NAS100.fs M15`.
2. Adjunta 6001 al primer gráfico y 6002 al segundo.
3. Conserva `InpTradingEnabled=false`.
4. Si es un inicio completamente nuevo y no existen posiciones H18, pulsa `F3`
   y elimina variables globales cuyo nombre comience por `H18_`.
5. Registra la hora exacta de inicio en UTC.

Los logs se escriben en:

`%APPDATA%\MetaQuotes\Terminal\Common\Files`

##4. Auditar paridad

Instala una sola vez:

```powershell
python -m pip install -r .\requirements-parity.txt
```

Exporta las barras M15 exactas del mismo terminal y ejecuta para cada magic:

```powershell
.\RUN_PARITY.ps1 `
  -Bars "C:\ruta\NAS100_fs_M15.csv" `
  -Magic 6001 `
  -StartUtc "2026-07-15T00:00:00Z"
```

Repite con `-Magic 6002`. La aprobación completa también necesita `-RiskLog`;
Python reconstruye cada decisión desde sus inputs auditables. `-PythonRiskLog`
queda disponible como override. No habilites órdenes salvo que ambos informes contengan
`"signal_approved": true`, `"risk_approved": true` y `"approved": true`.

##5. Incubación con órdenes demo

Después de aprobar paridad:

1. Usa una sola cuenta demo hedging para 6001 y 6002, sin otros sistemas. El
   gobernador suma el riesgo correlacionado antes de autorizar cada entrada.
2. Detén los EAs y confirma que no haya posiciones H18.
3. Elimina las variables `H18_` para iniciar estado limpio.
4. Vuelve a adjuntar el EA correspondiente con `InpTradingEnabled=true`.
5. Mantén los parámetros congelados y evalúa cada magic por separado.
6. Exige como mínimo 4 meses/40 operaciones holdout, 6 meses/60 operaciones
   forward y 100 operaciones futuras combinadas antes de reconsiderar el gate.

Una modificación del modelo, parámetros o motor reinicia los contadores.

##Contenido

- `MT5/Experts`: binarios compilados y wrappers MQL auditables.
- `MT5/Include`: motor compartido.
- `PythonReference`: referencia causal mínima para comparar señales.
- `TesterTemplates`: configuraciones editables del Strategy Tester.
- `Governance`: gate y auditoría de paridad.
- `Research`: siguiente línea de investigación para Mean Reversion.
- `Reports`: destino de los reportes de paridad.

##Mean Reversion

MR V3 Shock Rejection fue implementado y evaluado para coexistencia, pero quedó
rechazado con sólo 6 operaciones OOS y DSR 0.013. Magic 6003 está reservado; este
paquete no contiene un EA Mean Reversion ejecutable. Los artefactos reproducibles
están bajo `Research/MeanReversionV3`.
