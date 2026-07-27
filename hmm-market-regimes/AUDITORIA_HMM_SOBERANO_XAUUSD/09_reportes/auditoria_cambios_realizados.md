#Auditoría de Cambios Institucionales - HMM Soberano (XAUUSD)

##1. Qué corregiste en el calibrador HMM
**Problema previo**: La optimización por Máxima Verosimilitud (MLE) usaba `drift = 0.0` para ambos estados (Bull y Bear), lo que volvía la matriz de transición completamente simétrica y delegaba el trabajo a los otros filtros.
**Solución**: Se inyectó `CStateSpace.estimate_ou_drift(returns...)` localmente en cada paso del iterador MLE. Ahora la función evalúa la densidad `log_t_student_density(ret, mu_bull_ou, sig_t, nu_d)` para el estado Bull y `log_t_student_density(ret, -mu_bear_ou, sig_t, nu_d)` para el estado Bear, dotando al HMM de verdadera capacidad direccional.

##2. Qué corregiste en el backtest
Se eliminaron todos los sesgos optimistas reportados:
- **Llenado de parciales exacto**: Se eliminó el sesgo favorable del `close_t`. Si el precio toca el `partial_target`, el PnL se calcula exactamente al `partial_target` (más el slippage negativo correspondiente).
- **Inclusión de Spread y Slippage asimétrico**.
- **DD Flotante estricto** en lugar de solo DD realizado.

##3. Cómo estás modelando spread
Se inyecta un parámetro de simulación (`spread_price = 0.15` por defecto para oro).
Para compras (BUY), el sistema entra al mercado pagando el ASK (`open + spread/2`) y toma stop o profit en el BID.
Para ventas (SELL), entra al BID (`open - spread/2`) y sale en el ASK.
Esto asume un spread promedio permanente que recorta el *edge* real.

##4. Cómo estás modelando slippage
Se inyecta un parámetro `slippage_price = 0.05` por defecto.
El slippage simula la latencia del broker o barridos de liquidez: siempre se resta del PNL.
Si un Take Profit o Stop Loss es tocado, el fill se calcula con el peor precio posible: `TP - slippage` o `SL - slippage` para BUY, y equivalente para SELL.

##5. Cómo calculas equity flotante
En lugar de agregar el `balance` a la curva de capital al cierre de la barra, ahora aplicamos Mark-to-Market.
Se calcula un `floating_pnl` midiendo la posición abierta contra el `close` de la barra actual (deduciendo también el spread). Luego, se registra `balance + floating_pnl` en `equity_values`. Esto visibiliza el verdadero Drawdown intra-trade que sufriría la cuenta.

##6. Cómo resuelves velas donde SL y TP ocurren en la misma barra
El motor de ejecución tiene un sesgo de "Path Intrabar Pesimista".
Por el orden estructural de evaluación en `backtest_metrics.py`, el código verifica **primero** si se tocó el Stop Loss (`if low_t <= stop_loss:` para BUY). Sólo si el SL no se tocó, evalúa el Take Profit. Por tanto, ante cualquier ambigüedad en velas de alto rango, el sistema asume que el trader fue sacado con pérdida.

##7. Fecha exacta de corte IS/OOS
La fecha de aislamiento OOS (Out-Of-Sample) es estricta: **`2024-05-01`**.
Además, se removió el *fallback* automático del 70%. Si la fecha está fuera de rango, el orquestador se quiebra devolviendo un `ValueError`. Se mantienen 120 barras de purga (embargo) entre el final del IS y el inicio del OOS.

##8. Número total de combinaciones probadas
La grilla de optimización Walk-Forward probó iterativamente configuraciones dictadas por `parameter_space.json`. Dependiendo del espacio activo, la grilla rápida computa 18 a 81 combinaciones. El parámetro `dsr_trials` (Deflated Sharpe Ratio) se actualizó para penalizar estadísticamente el Sharpe asumiendo exactamente el número dinámico de `len(candidates)`.

##9. Si el OOS fue mirado antes para ajustar parámetros
**Falso**. El orquestador divide el lago de datos en `IS_PURGED` y `OOS` en el Paso 5. Luego, el calibrador de la Capa 3 se ejecuta **exclusivamente** sobre `IS_PURGED` para extraer la matriz de transición, nu, lambda y pesos. El `OOS` (2024-2026) se reserva puramente para alimentar la inferencia en la Capa 2 y evaluar los resultados en el Paso 4. Además, el optimizador usa Walk-Forward anidado en el IS para seleccionar sus mejores parámetros antes de ver el OOS. No hay contaminación.

##10. Actualización: Intrabar Pesimista Estricto, Comisión y Holdout OOS
- **Intrabar Mode "pessimistic" (Conflicto SL vs Parcial)**: Si en la misma vela coinciden el SL original y el precio de Cierre Parcial, el SL se ejecuta de forma prioritaria sobre la totalidad de la posición original, cancelando el parcial. Lo mismo ocurre ante conflicto de SL y TP.
- **Comisión por Lote**: Se añade `commission_per_lot` en `BacktestAssumptions` y en el motor de backtest, aplicando una deducción monetaria de `lote_cerrado * 2.0 * commission_per_lot` en cada cierre parcial o total.
- **Archivos de Holdout OOS**: Se añaden y empaquetan en el ZIP de auditoría todos los resultados de la mejor configuración evaluada una única vez en el holdout OOS: `best_oos_holdout_metrics.csv`, `best_oos_trades.csv`, `best_oos_cashflows.csv`, `best_oos_equity.csv` y `alpha_decay_oos_quarterly.csv`.

