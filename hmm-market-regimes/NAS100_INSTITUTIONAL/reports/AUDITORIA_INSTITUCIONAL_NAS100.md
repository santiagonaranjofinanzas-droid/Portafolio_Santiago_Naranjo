#Auditoría institucional NAS100 / NAS100.fs

**Decisión Mean Reversion:** REJECTED
**Decisión Trend Following:** REJECTED
**Decisión de cartera:** REJECTED

> La operación en cuenta real permanece bloqueada. Los artefactos son aptos únicamente para investigación, Strategy Tester y forward demo.

##Contrato real del bróker

Símbolo `NAS100.fs`; point `0.01`; tick size `0.01`; tick value `$0.2`; volumen `0.01`–`10.0`; spread flotante observado `2.5` puntos de precio.

Los resultados históricos anteriores usaban `point=1.0`, `tick_value=1.0` y spread fijo `1.0`; no son transferibles al contrato actual.

##Resultados recalculados

 Modelo  Motor  Trades  Retorno  PF  Sharpe diario  DSR  DD diario  Bootstrap PF p05  Peor PF trimestral 
 :---  :---  ---:  ---:  ---:  ---:  ---:  ---:  ---:  ---: 
 Mean Reversion  OHLC pesimista, contrato real  119  -1.52%  0.950  -0.115  0.007  -7.92%  0.654  0.362 
 Trend Following  Tick Bid/Ask  150  11.47%  1.155  0.521  0.063  -6.34%  0.876  0.528 

##Forward Axi posterior

El baseline Trend congelado produjo `2` operaciones, retorno `-1.72%` y PF `0.000` sobre ticks Axi entre `2026-06-22 01:00:00` y `2026-07-10 08:00:00`. La muestra queda marcada como consumida y no puede usarse para optimización.

##Nested walk-forward del Trend seleccionado

PF por fold con HMM recalibrado dentro de cada train: `0.999 / 0.925 / 0.983 / 1.005`. Mediana `0.991` y mínimo `0.925`.

##Fallos del release gate

 Modelo  Control  Valor  Requerido 
 :---  :---  ---:  ---: 
 MEAN_REVERSION  tick_bid_ask_backtest  False  True 
 MEAN_REVERSION  closed_trades  119  200 
 MEAN_REVERSION  profit_factor  0.9499774111761967  1.2 
 MEAN_REVERSION  daily_sharpe  -0.11492360454900996  1.0 
 MEAN_REVERSION  deflated_sharpe_probability  0.006879694767216273  0.8 
 MEAN_REVERSION  bootstrap_pf_p05  0.6542627997951023  1.0 
 MEAN_REVERSION  minimum_quarter_profit_factor  0.36211450730391875  0.9 
 MEAN_REVERSION  is_median_profit_factor  0.6772013118585392  1.05 
 MEAN_REVERSION  nested_min_fold_profit_factor  None  1.0 
 MEAN_REVERSION  nested_walk_forward_complete  False  True 
 MEAN_REVERSION  virgin_holdout  False  True 
 MEAN_REVERSION  python_mt5_signal_parity  False  True 
 MEAN_REVERSION  mt5_every_tick_parity  False  True 
 MEAN_REVERSION  paper_forward_closed_trades  0  60 
 MEAN_REVERSION  paper_forward_profit_factor  0.0  1.1 
 TREND_FOLLOW  closed_trades  150  200 
 TREND_FOLLOW  profit_factor  1.1545867021011722  1.2 
 TREND_FOLLOW  daily_sharpe  0.520976899017183  1.0 
 TREND_FOLLOW  deflated_sharpe_probability  0.06301541216035915  0.8 
 TREND_FOLLOW  bootstrap_pf_p05  0.8755058030305084  1.0 
 TREND_FOLLOW  minimum_quarter_profit_factor  0.5277335714416292  0.9 
 TREND_FOLLOW  is_median_profit_factor  0.990573450309147  1.05 
 TREND_FOLLOW  nested_min_fold_profit_factor  0.9249059864755732  1.0 
 TREND_FOLLOW  virgin_holdout  False  True 
 TREND_FOLLOW  python_mt5_signal_parity  False  True 
 TREND_FOLLOW  mt5_every_tick_parity  False  True 
 TREND_FOLLOW  paper_forward_closed_trades  2  60 
 TREND_FOLLOW  paper_forward_profit_factor  0.0  1.1 

##Conclusión

Mean Reversion pierde su edge al usar el contrato real del bróker y falla ya en los folds IS; debe retirarse del portafolio candidato. Trend Following conserva un edge histórico pequeño, pero falla el nested walk-forward y comenzó el forward Axi con dos pérdidas. Ningún modelo está aprobado para despliegue institucional.

Para desbloquear real se requieren: paridad Python/MT5, backtest MT5 Every tick sobre ticks del bróker, nested walk-forward completo bajo el contrato actual y al menos 60 operaciones de forward demo con PF >= 1.10.
