#Plan por capas para fortalecer el edge

Fecha: 2026-06-09

##Objetivo

Convertir la senal debil detectada por el HMM en una ventaja estadistica robusta, sobreviviendo a:

- backtest tick-level bid/ask;
- costes reales;
- nested walk-forward;
- data snooping;
- cambio de regimen;
- validacion forward/paper.

El objetivo no es optimizar mas la misma grilla. El objetivo es mejorar la calidad del edge antes de volver a seleccionar parametros.

##Estado actual

El sistema muestra una senal, pero no robusta:

- Tick-level OOS candidato previo: PF 1.053, DSR 0.047.
- Tick-level OOS candidato nested: PF 1.040, DSR 0.040.
- Nested walk-forward: mean PF 1.043, min PF 0.903.
- Bot 30001 con paridad 18 parametros: tick-level OOS 202405 PF 1.127, retorno 39.59%, DD -12.35%.
- Diagnostico 30001: sesion NY_13_20 negativa y regimen HIGH_STRENGTH dominante.
- Accion demo aplicada: guardia 30001 con `ML_Master_Strength >= 0.66` y bloqueo de nuevas entradas entre horas servidor 13:00-19:59.
- Accion demo 50001 aplicada: Layered V1 con sesiones London/Late, fuerza minima 0.50, sigma acotada, spread maximo, pausa por racha de perdidas, salida por flip de regimen y stop temporal.
- Walk-forward tick-level 50001 Layered V1:
  - PF mediano test: 1.017;
  - PF minimo test: 0.923;
  - trades test: 261;
  - decision: no aprueba robustez final, solo demo/live-shadow.
- Capa 7 aplicada: diagnostico por dia, direccion, volatilidad, fuerza, duracion, distancia a cambio de regimen y MAE/MFE.
- Capa 9 aplicada: busqueda de politicas de salida. Resultado usado como hipotesis, no como prueba final, porque MAE/MFE puede introducir sesgo si se interpreta como ejecucion causal.
- Salidas 50001 desplegadas:
  - cierre por flip de regimen;
  - cierre por fuerza deteriorada bajo 0.45 tras 12 barras;
  - parcial retrasado minimo 12 barras;
  - parcial mas temprano si fuerza cae bajo umbral de capa;
  - stop temporal 96 barras.

Conclusion: hay informacion util, pero el edge neto queda demasiado cerca de cero despues de bid/ask y validacion estricta.

##Principio rector

Cada nueva capa debe mejorar la robustez fuera de muestra. Si mejora solo el IS o solo una ventana OOS ya usada, no cuenta.

Regla:

```text
No se acepta ningun cambio que mejore OHLC pero no mejore tick-level.
```

##Capa A: Saneamiento de ejecucion realista

Objetivo:

Eliminar cualquier optimismo residual del simulador.

Implementaciones:

- Usar tick-level bid/ask como backtest primario.
- Modelar comision por lote.
- Modelar slippage:
  - base;
  - p75;
  - p95;
  - stress.
- Modelar spread dinamico desde ticks.
- Calcular DD mark-to-market, no solo balance cerrado.
- Registrar MAE/MFE por trade.

Artefactos:

- `Capa_4/tick_cost_model.py`
- `Capa_4/mark_to_market.py`
- `Capa_4/mae_mfe.py`
- `Capa_4/tick_audit_costed/`

Criterio de aceptacion:

- El PF tick-level con costes realistas debe seguir > 1.10.
- DD mark-to-market debe estar dentro del limite definido.
- La diferencia OHLC vs tick-level debe reportarse siempre.

##Capa B: Diagnostico del edge por segmentos

Objetivo:

Encontrar donde existe la ventaja y donde se destruye.

Segmentaciones:

- Hora del dia.
- Sesion:
  - Asia;
  - Londres;
  - New York;
  - overlap.
- Dia de semana.
- Mes/trimestre.
- Volatilidad:
  - baja;
  - media;
  - alta;
  - extrema.
- Spread:
  - normal;
  - alto;
  - anomalo.
- Direccion:
  - long;
  - short.
- Regimen HMM:
  - probabilidad alta;
  - probabilidad media;
  - transicion;
  - neutral.
- Rachas posteriores a cambio de regimen.

Artefactos:

- `Capa_7/edge_diagnostics.py`
- `Capa_7/segment_report.py`
- `Capa_7/reportes_segmentacion/`

Criterio de aceptacion:

- Identificar al menos 2 segmentos con PF tick-level > 1.20.
- Identificar segmentos destructivos con PF < 0.95 para excluirlos.
- La mejora debe observarse en nested walk-forward.

##Capa C: Filtros defensivos de mercado

Objetivo:

Reducir operaciones de baja calidad sin destruir la muestra.

Filtros candidatos:

1. Filtro de spread:
   - no operar si spread > percentil 75/90 historico por sesion.

2. Filtro de volatilidad extrema:
   - no operar cuando sigma proyectada o ATR relativo este en cola extrema.

3. Filtro de compresion:
   - evitar entradas cuando ATR/volumen sea demasiado bajo.

4. Filtro horario:
   - operar solo sesiones con edge positivo.

5. Filtro de direccion:
   - permitir long/short segun estabilidad por regimen.

6. Filtro de regimen reciente:
   - si PF rolling de ultimos N trades < 1.0, reducir riesgo o pausar.

Artefactos:

- `Capa_7/filters.py`
- `Capa_7/filter_search.py`
- `Capa_7/filter_audit_tick.py`

Criterio de aceptacion:

- Reducir drawdown tick-level al menos 20%.
- Mantener al menos 200 trades OOS o justificar menor frecuencia.
- Mejorar DSR penalizado por variantes.

##Capa D: Mejoras del modelo HMM

Objetivo:

Que el HMM capture cambios de regimen de forma mas util para trading real.

Mejoras candidatas:

1. Estado neutral explicito:
   - pasar de 2 estados a 3 estados: bull, bear, neutral/chop.

2. Estado de volatilidad:
   - separar direccion y volatilidad:
     - direction HMM;
     - volatility regime.

3. Probabilidad de transicion adaptativa:
   - matriz HMM dependiente de volatilidad/spread/sesion.

4. Recalibracion rolling:
   - ventana reciente;
   - media vida;
   - shrinkage hacia parametros historicos.

5. Penalizacion por turnover:
   - evitar flip-flop de regimen.

Artefactos:

- `Capa_8/hmm_3state.py`
- `Capa_8/volatility_regime.py`
- `Capa_8/rolling_calibration.py`
- `Capa_8/hmm_model_selection.py`

Criterio de aceptacion:

- Nested walk-forward con HMM recalibrado por fold.
- PF tick-level > baseline.
- Menor frecuencia de trades falsos en regimen neutral.

##Capa E: Reglas de salida y gestion de trade

Objetivo:

El problema reciente sugiere que esperar recorridos largos destruye edge. Hay que redisenar salidas antes de tocar entradas.

Pruebas:

- TP parcial mas temprano.
- TP final menor en regimen rapido.
- Stop temporal:
  - cerrar si no avanza despues de N barras.
- Break-even condicional:
  - no mover BE demasiado temprano si aumenta stop-outs.
- Trailing volatility stop.
- Salida por degradacion de HMM:
  - cerrar si `Regime_Buffer_18` revierte.
- Salida por spike de spread.

Artefactos:

- `Capa_9/exits.py`
- `Capa_9/exit_policy_search.py`
- `Capa_9/exit_tick_audit.py`

Criterio de aceptacion:

- Mejorar expectancy tick-level.
- Reducir max consecutive losses.
- Reducir DD sin matar PF.

##Capa F: Robustez estadistica

Objetivo:

Validar que el edge no sea data snooping.

Implementaciones:

- Combinatorial Purged Cross-Validation.
- Nested walk-forward obligatorio.
- White Reality Check o SPA test.
- DSR con numero real de variantes.
- Bootstrap de trades por bloque temporal.
- Monte Carlo de orden de trades.
- Stress test de spread/slippage.

Artefactos:

- `Capa_10/cpcv.py`
- `Capa_10/reality_check.py`
- `Capa_10/bootstrap_blocks.py`
- `Capa_10/slippage_stress.py`

Criterio de aceptacion:

- DSR > 0.80 con trials reales.
- PF mediano por fold > 1.10.
- Peor fold no menor a 0.98, o regla defensiva que lo neutralice.
- Monte Carlo p5 no negativo o DD aceptable.

##Capa G: Forward/paper protocol

Objetivo:

Separar investigacion de decision real.

Reglas:

- Ningun parametro pasa directo a real.
- Todo candidato pasa por paper/forward.
- La ventana forward debe ser posterior al ultimo dato usado para decidir.
- Minimo:
  - 50 trades, o
  - 6 semanas de mercado, lo que ocurra despues.

Metricas de liberacion:

- PF forward > 1.10.
- DD forward dentro del presupuesto.
- Slippage real no destruye expectancy.
- Regime monitor fuera de `PAUSE_AND_RETRAIN`.

Artefactos:

- `Capa_11/live_shadow_ledger_50001.py`
- `Capa_11/forward_50001/live_shadow_ledger_50001.csv`
- `Capa_11/forward_50001/forward_status_50001.csv`
- `Capa_11/release_gate_50001.py`
- `Capa_11/forward_50001/release_gate_50001.csv`

##Orden de implementacion recomendado

1. Capa A: Costes, spread, slippage y DD mark-to-market.
2. Capa B: Segmentacion del edge.
3. Capa C: Filtros defensivos.
4. Capa E: Salidas y gestion de trade.
5. Capa F: Robustez estadistica.
6. Capa D: Mejoras HMM, si los filtros no son suficientes.
7. Capa G: Forward/paper antes de real.

##Criterio de "edge fortalecido"

Se declara edge fortalecido solo si:

- PF tick-level con costes > 1.15.
- Sharpe tick-level > 1.0.
- DSR penalizado > 0.80.
- Max DD tick-level < limite definido.
- Nested walk-forward estable.
- Forward/paper confirma el comportamiento.

##Decision actual

Estado actual:

```text
NO REAL
SOLO DEMO / PAPER
```

La ventaja estadistica existe como senal debil, pero requiere filtros y ejecucion realista para convertirse en edge operable.
