#Auditoria metodologica: overfitting, look-ahead, data snooping y robustez

Fecha: 2026-06-09

##Veredicto ejecutivo

El sistema tiene una base cuantitativa razonable, pero aun no debe considerarse robusto a nivel institucional. Hay tres riesgos que pueden destruir el modelo si no se corrigen:

1. El OOS fijo ya fue usado para tomar decisiones de reentrenamiento reciente.
2. La optimizacion de parametros no es nested walk-forward completa.
3. El backtest OHLC contiene sesgos intrabar y no modela costes reales.

Conclusion: el modelo puede seguir investigandose, pero no debe pasar a real con size normal. El estado correcto es `PAUSE_AND_RETRAIN`, paper/forward y endurecimiento metodologico.

##Hallazgos criticos

###P0 - El OOS fue reutilizado para reentrenamiento reciente

Referencia:

- `Capa_6/Reentrenar_Reciente.py`, lineas 18, 28, 29, 33 y 52.
- El script toma `Capa_5/XAUUSD_M15_OOS_202405.parquet` como fuente, filtra desde `2025-01-01` y optimiza parametros sobre una validacion interna de esa misma ventana.

Riesgo:

- Esto convierte el OOS en set de desarrollo.
- El candidato `recent_best_params.json` no puede considerarse validado OOS.
- Si ese candidato se usa para real, hay data snooping.

Accion requerida:

- Tratar `recent_best_params.json` solo como candidato para paper/forward.
- No usarlo como prueba de robustez final.
- Crear un nuevo holdout intacto posterior al reentrenamiento, idealmente datos futuros no vistos.

###P0 - Validacion interna contaminada por parametros HMM entrenados con toda la IS

Referencia:

- `Capa_3/Calibrar_Sistema.py`, lineas 21-22.
- `Capa_6/optimizer.py`, lineas 30-33, 152 y 158.
- La optimizacion divide IS en train/validation, pero las senales de validacion usan `HMM_Params_15M.csv` ya calibrado sobre todo `IS_PURGED`, incluida la validacion interna.

Riesgo:

- La validacion interna no mide generalizacion limpia.
- El ranking de parametros operativos puede estar optimista.

Accion requerida:

- Implementar nested walk-forward:
  - para cada fold, calibrar HMM solo en el train del fold;
  - generar senales en validation;
  - optimizar parametros solo sobre validation;
  - reservar un holdout final que no participe en ninguna decision.

###P1 - Backtest OHLC con sesgo intrabar

Referencia:

- `Capa_4/backtest_metrics.py`, lineas 123-125, 160-180 y 189-210.
- El simulador usa `high_t` y `low_t` de la misma vela para decidir parciales, SL y TP.
- Para parciales BUY usa `fill = max(partial_target, close_t)`.
- Para parciales SELL usa `fill = min(partial_target, close_t)`.

Riesgo:

- Si una vela toca parcial y stop, el orden real es desconocido.
- El fill puede ser mejor que el nivel objetivo.
- Esto puede inflar retorno, profit factor y Sharpe.

Accion requerida:

- Rehacer backtest con ticks bid/ask ya disponibles.
- Si se usa OHLC, aplicar criterio conservador:
  - fill parcial siempre al target, no al close favorable;
  - si SL y TP/partial ocurren en la misma vela, asumir el peor orden.

###P1 - Costes de ejecucion incompletos

Referencia:

- `Capa_4/backtest_metrics.py`, `BacktestAssumptions`, lineas 9-23.
- `spread_price = 0.0`, sin slippage ni comision.
- Entradas usan `close_t` como precio ejecutable.

Riesgo:

- XAUUSD es sensible a spread, slippage y sesgo bid/ask.
- El PF cercano a 1.1-1.2 puede desaparecer con costes reales.

Accion requerida:

- Usar bid/ask tick-level.
- Modelar spread historico, comision y slippage.
- Reportar sensibilidad: spread 0, spread mediano, spread p95.

##Hallazgos altos

###P1 - El OOS fijo ya no es virgen

Referencia:

- `Capa_5/Validar_Capa5.py`, lineas 41-45.
- OOS: `2024-05-01` a `2026-05-29`.
- Posteriormente se uso ese OOS para reportar alpha decay, detectar regimen y reentrenar reciente.

Accion requerida:

- Congelar resultados OOS historicos como auditoria pasada.
- Crear `OOS2_FORWARD` con datos futuros nuevos.
- Ningun parametro debe elegirse usando `OOS2_FORWARD`.

###P1 - Data snooping por grilla y objetivo compuesto

Referencia:

- `Capa_6/parameter_space.json`.
- `Capa_6/optimizer.py`, lineas 37-59.

Riesgo:

- Se prueban 81 variantes.
- El DSR se penalizo con `DSR_TRIALS=81`, lo cual ayuda, pero no reemplaza White Reality Check, SPA test o Combinatorial Purged Cross-Validation.

Accion requerida:

- Mantener DSR con trials reales.
- Agregar CPCV/Deflated Sharpe por fold.
- Reportar estabilidad del ranking por fold, no solo el mejor global.

###P2 - Equity sin mark-to-market

Referencia:

- `Capa_4/backtest_metrics.py`, lineas 117, 151 y 244-246.

Riesgo:

- La equity curve solo registra balance realizado.
- Drawdown flotante de operaciones abiertas puede estar subestimado.

Accion requerida:

- Calcular equity mark-to-market por barra usando precio close/bid/ask.
- Reportar DD realizado y DD mark-to-market.

###P2 - Segmentos OOS arrancan con estado frio

Referencia:

- `Capa_2/sovereign_signal.py`, lineas 209-257.

Riesgo:

- Al correr OOS aislado, buffers HMM/GARCH/Kalman arrancan desde semillas.
- Esto no es look-ahead, pero puede crear discrepancia contra live continuo.

Accion requerida:

- Usar una ventana de burn-in previa al inicio OOS, sin contar sus trades.
- Para OOS desde `2024-05-01`, alimentar al motor con al menos 2000 barras previas y evaluar solo desde la fecha OOS.

##Hallazgos positivos

- Politica F(t-1) en retornos: `b_returns[i] = log(close[i-1] / close[i-2])`.
- Purga fija de 120 barras aplicada al split IS/OOS.
- DSR recalculado con 81 trials para el barrido completo.
- Detector de regimen evita seguir operando en tramo con PF reciente deteriorado.
- `recent_best_params.json` esta marcado como candidato de paper/forward, no como parametro final validado.

##Acciones inmediatas recomendadas

1. Mantener estado `PAUSE_AND_RETRAIN`.
2. No operar real con el candidato reciente.
3. Crear backtest tick-level bid/ask para Capa 4.
4. Implementar nested walk-forward real para Capa 6.
5. Crear un nuevo holdout forward con datos posteriores al reentrenamiento.
6. Solo liberar parametros a real si:
   - PF rolling forward > 1.0;
   - DD mark-to-market dentro de limite;
   - DSR penalizado por variantes > 0.80;
   - resultado estable en varios folds, no solo en un tramo.

##Estado final de robustez

Robustez actual: parcial.

El sistema esta protegido contra algunas fugas obvias, pero todavia no cumple un estandar suficientemente estricto para declarar edge robusto final. El siguiente gran salto de calidad es reemplazar el backtest OHLC por tick-level y convertir Capa 6 en nested walk-forward con holdout virgen.
