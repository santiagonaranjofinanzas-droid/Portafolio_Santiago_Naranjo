#Reporte final: tick-level + nested walk-forward

Fecha: 2026-06-09

##Resumen ejecutivo

Se ejecuto el plan de robustez metodologica:

1. Backtest tick-level bid/ask conservador.
2. Nested walk-forward con recalibracion HMM por fold.
3. Auditoria tick-level del candidato previo y del candidato nested.

Resultado: el edge baja de forma drastica al quitar sesgos de OHLC. El sistema no debe considerarse listo para real con size normal.

##Backtest tick-level del candidato previo

Candidato:

```json
{
  "threshold": 0.65,
  "min_strength": 0.35,
  "vol_multiplier": 2.5,
  "reward_risk": 2.5,
  "kalman_gate": true
}
```

Resultados OOS tick-level:

- Trades: 495
- Return: 20.14%
- Win rate: 39.19%
- Profit factor: 1.053
- Max DD: -21.15%
- Sharpe: 0.605
- DSR con 81 trials: 0.047

Lectura: edge marginal. El DSR no respalda robustez.

##Nested walk-forward

Se ejecuto nested walk-forward sobre `IS_PURGED` con:

- 4 folds
- purga 120 barras
- recalibracion HMM por fold
- 81 candidatos
- DSR trials 81

Mejor candidato por estabilidad:

```json
{
  "threshold": 0.60,
  "min_strength": 0.35,
  "vol_multiplier": 3.0,
  "reward_risk": 2.0,
  "kalman_gate": true
}
```

Estabilidad nested:

- Mean PF: 1.043
- Min PF: 0.903
- Mean return: 6.28%
- Min return: -6.80%
- Worst DD: -16.82%
- Mean DSR: 0.033

Lectura: no hay estabilidad suficiente. Al menos un fold pierde edge.

##Tick-level del candidato nested

Resultados OOS tick-level:

- Trades: 828
- Return: 19.83%
- Win rate: 44.32%
- Profit factor: 1.040
- Max DD: -23.65%
- Sharpe: 0.638
- DSR con 81 trials: 0.040

Lectura: el candidato nested tampoco demuestra alpha robusto. Opera mucho mas, pero con PF apenas sobre 1 y DSR muy bajo.

##Decision

Estado: NO APROBADO PARA REAL.

Motivos:

- El PF tick-level queda cerca de 1.0.
- El DSR penalizado por data snooping queda muy bajo.
- Nested walk-forward muestra inestabilidad entre folds.
- El drawdown tick-level es material para un edge tan bajo.

##Accion recomendada

1. Mantener `PAUSE_AND_RETRAIN`.
2. No cargar parametros nuevos a real.
3. Usar solo paper/forward si se desea observar comportamiento.
4. Mejorar el modelo antes de optimizar mas:
   - incorporar costes reales por broker;
   - usar features/regime filters nuevos;
   - agregar filtro de volatilidad/evento para 2026;
   - evaluar time-of-day y news/session filters;
   - recalibrar con arquitectura que no dependa solo de threshold/RR.
5. Crear un nuevo forward holdout con datos posteriores a esta decision.

##Archivos generados

- `Capa_4/tick_audit/tick_metrics.csv`
- `Capa_4/tick_audit/tick_trades.csv`
- `Capa_4/tick_audit_nested/tick_metrics.csv`
- `Capa_4/tick_audit_nested/tick_trades.csv`
- `Capa_6/nested_walk_forward/nested_all_rankings.csv`
- `Capa_6/nested_walk_forward/nested_stability_ranking.csv`
- `Capa_6/nested_walk_forward/nested_best_params.json`

##Conclusiones

El HMM puede estar capturando algo, pero aun no lo suficiente para sobrevivir claramente a ejecucion realista y validacion estricta. La metodologia hizo su trabajo: evito que una curva OHLC optimista se convierta en una falsa seguridad.
