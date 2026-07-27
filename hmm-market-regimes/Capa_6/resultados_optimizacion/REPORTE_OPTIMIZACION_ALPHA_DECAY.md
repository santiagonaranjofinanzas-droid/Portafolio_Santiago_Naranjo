#Reporte Capa 6: Optimizacion anti alpha decay

##Mejor candidato

```json
{
  "threshold": 0.65,
  "min_strength": 0.35,
  "vol_multiplier": 2.5,
  "reward_risk": 2.5,
  "kalman_gate": true
}
```

##Holdout OOS

- Balance final: 21,745.69
- Retorno OOS: 117.46%
- Trades cerrados: 508
- Win rate: 42.32%
- Profit factor: 1.23
- Expectancy por trade: 23.12
- Payoff ratio: 1.68
- Max DD: -16.52%
- Max ganancias seguidas: 6
- Max perdidas seguidas: 10
- Sharpe: 2.09
- Sortino: 8.81
- DSR probability: 0.723 con `DSR_TRIALS=81`
- Recovery factor: 3.11

##Alpha decay

El holdout OOS completo es positivo, pero el reporte trimestral detecta deterioro reciente:

- 2025-Q2: PF 1.61, pnl 3,138.61
- 2025-Q3: PF 1.42, pnl 2,246.95
- 2025-Q4: PF 1.32, pnl 2,247.02
- 2026-Q1: PF 1.13, pnl 1,238.98
- 2026-Q2 parcial: PF 0.66, pnl -1,590.77

Lectura: el alpha no esta muerto en el agregado OOS, pero si hay una alerta de degradacion reciente. La siguiente iteracion debe probar reentrenamiento rolling con mas peso en 2025-2026 y filtros de proteccion cuando el PF trimestral rolling caiga por debajo de 1.0.

##Archivos generados

- `ranking_parametros.csv`
- `best_params.json`
- `best_oos_holdout_metrics.csv`
- `best_oos_trades.csv`
- `best_oos_cashflows.csv`
- `best_oos_equity.csv`
- `alpha_decay_oos_quarterly.csv`

##Nota sobre DSR

El reporte fue recalculado con `DSR_TRIALS=81`, equivalente al barrido completo de la grilla actual. Si se amplia la grilla, ese numero debe subir.
