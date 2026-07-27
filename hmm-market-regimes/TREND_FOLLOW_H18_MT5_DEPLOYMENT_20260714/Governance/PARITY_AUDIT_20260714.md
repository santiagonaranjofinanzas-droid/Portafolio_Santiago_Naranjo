#Auditoría de paridad Python ↔ MQL (2026-07-14)

##Veredicto

La paridad 1:1 completa todavía **no está certificada**. La implementación MQL
queda alineada por inspección con el contrato matemático de señales H18 y compila
sin errores, pero falta una comparación observada sobre el mismo feed de barras.
El gate de producción continúa `LIVE_LOCKED`.

##Extensión de riesgo institucional V1

El motor MQL ahora incluye un gobernador compartido para 6001/6002, sizing por
equity y stop, límite agregado, controles diarios/drawdown/margen, stop ejecutivo
de 6 ATR y stop de desastre server-side de 8 ATR. Las órdenes requieren
`OrderCheck`, `TRADE_RETCODE_DONE` y confirmación de SL en la posición.

La referencia Python y el comparador de decisiones de riesgo están implementados,
pero todavía no existe un replay observado con los mismos snapshots de cuenta y
especificación de `NAS100.fs`. Por tanto, la paridad de riesgo también permanece
no aprobada. La paridad de señales por sí sola ya no puede desbloquear ejecución.

##Contrato alineado por inspección

- Magics inmutables: 6001 y 6002.
- Horizontes H1: 12/24/48 y 24/48/96.
- Sólo horas completas formadas por M15 `00/15/30/45`.
- Volatilidad de 96 retornos logarítmicos con desviación muestral (`n-1`).
- ATR H1 simple de 32 observaciones.
- Score: mediana de tres momentums normalizados.
- Entrada long: score >= 0.35 durante dos cierres H1.
- Salida de modelo: score <= 0 tras un mínimo de 8 decisiones H1.
- Rearme: score <= 0.
- Ejecución: señal al cierre `:45`, orden en el primer tick de la siguiente M15.
- Stop ejecutivo: 6 ATR, comprobado al cierre H1 y ejecutado después.
- Target de volatilidad: 10% anual; H1 se convierte a M15 dividiendo sigma por 2.

##Correcciones hechas durante la auditoría

1. El modo observador ahora mantiene una posición lógica independiente de la
   posición del broker. Antes, `InpTradingEnabled=false` divergía después de la
   primera entrada.
2. `exit_signal` representa únicamente la salida del modelo. El nuevo campo
   `execution_exit` registra por separado el stop de catástrofe.
3. El modo observador es el valor predeterminado.
4. Los CSV usan `FILE_COMMON`, también desde Strategy Tester.
5. Si la posición del broker y el estado persistido no coinciden, el motor falla
   cerrado.

##Por qué el BT nested no puede compararse directamente con una corrida continua

Cada outer fold del BT:

- termina el train 500 barras M15 antes del test;
- usa sólo la cola del train como contexto y omite las barras de purga;
- reinicia el estado de señales y el capital en 100,000;
- fuerza el cierre al final del fold;
- concatena posteriormente las operaciones de los folds.

MT5, en cambio, consume todas las barras anteriores, conserva estado/capital y no
fuerza cierres semestrales. Por tanto, el CSV nested congelado no es una secuencia
de operaciones que deba reproducir una corrida continua. Para paridad institucional
se requieren dos pruebas distintas:

1. **Replay por fold:** mismas barras, hueco de purga, estado/capital reiniciado y
   cierre forzado en cada límite.
2. **Referencia de despliegue continua:** Python y MT5 sobre el mismo export M15,
   mismo instante inicial y sin resets artificiales.

##Divergencias de ejecución que impiden igualdad de PnL sin calibración

- Python aplica spread, slippage y comisión modelados; MT5 usa ticks, spread,
  comisión y reglas del símbolo del tester/broker.
- Python llena exactamente al `open` de la barra con costes deterministas; MQL
  envía una orden de mercado al primer tick disponible.
- El dimensionamiento sólo coincide si tick size, tick value, lote mínimo, step,
  balance y costes son idénticos.
- La conversión de hora histórica del servidor durante cambios DST debe validarse
  contra el export de MT5. El agrupamiento por hora se mantiene si el offset del
  servidor es un número entero de horas, pero el texto UTC del log puede requerir
  normalización histórica.

##Evidencia ejecutada

- Ambos EAs: `0 errors, 0 warnings` con MetaEditor build 5833.
- Pruebas Python del módulo: 19 aprobadas.
- Artefactos `.ex5` reinstalados y verificados contra el repositorio.
- Intento de Strategy Tester aislado en `Axi-US50-Demo`: el agente cargó el EA y
  preparó `NAS100.fs,M15`, pero la credencial demo guardada estaba vencida
  (`Invalid account`) y el terminal no pudo sincronizar/obtener el histórico.
  No se obtuvo un CSV MQL observado; esto no cuenta como paridad aprobada.

##Gate de aprobación de paridad continua

- 100% de timestamps de decisión iguales.
- 100% de entradas y salidas de modelo iguales.
- `abs(score_py-score_mql) <= 1e-9`.
- `abs(ATR_py-ATR_mql) <= 0.01`.
- `abs(vol_py-vol_mql) <= 1e-10`.
- Cero barras duplicadas o faltantes en el intervalo auditado.
- PnL se evalúa aparte, después de fijar costes y especificación del símbolo.
