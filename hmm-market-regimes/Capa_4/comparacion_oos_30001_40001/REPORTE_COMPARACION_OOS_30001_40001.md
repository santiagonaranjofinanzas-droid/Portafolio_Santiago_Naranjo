#Comparacion OOS 30001 vs 40001

Periodo: 2024-05-01 00:00:00 a 2026-05-29 16:45:00
Barras: 49137

Nota: 30001 venia de un CSV antiguo de 18 columnas. Para el motor actual se adapto a 15 columnas; WAccel, MuAccel y StdAccel quedan documentados pero no participan en esta simulacion.

##OHLC
 model_id  engine  total_return_pct  closed_trades  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_ratio  sortino_ratio  deflated_sharpe_probability  recovery_factor 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 30001  OHLC  112.4413  486.0000  48.3539  1.2939  -12.5938  7.0000  10.0000  2.2753  10.3924  0.9995  3.6886 
 40001  OHLC  136.1863  836.0000  46.2919  1.2080  -22.0473  7.0000  8.0000  2.0303  7.1818  0.6750  4.1310 

##TICK_BID_ASK
 model_id  engine  total_return_pct  closed_trades  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_ratio  sortino_ratio  deflated_sharpe_probability  recovery_factor 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 30001  TICK_BID_ASK  37.5584  479.0000  45.7203  1.1200  -12.9289  8.0000  10.0000  1.0473  4.2032  0.9148  1.8423 
 40001  TICK_BID_ASK  19.8340  828.0000  44.3237  1.0401  -23.6550  8.0000  8.0000  0.6375  2.3364  0.0403  0.6898 

##Delta 40001 - 30001
 engine  total_return_pct  closed_trades  win_rate_pct  profit_factor  max_drawdown_pct  sharpe_ratio  deflated_sharpe_probability 
 ---  ---  ---  ---  ---  ---  ---  --- 
 OHLC  23.7450  350.0000  -2.0620  -0.0859  -9.4535  -0.2450  -0.3245 
 TICK_BID_ASK  -17.7244  349.0000  -1.3966  -0.0799  -10.7261  -0.4098  -0.8744 

##Lectura rapida
- 30001 tick-level: retorno 37.56%, PF 1.120, DD -12.93%, Sharpe 1.047.
- 40001 tick-level: retorno 19.83%, PF 1.040, DD -23.65%, Sharpe 0.638.
- Delta 40001 vs 30001 tick-level: retorno -17.72 pp, PF -0.080, DD -10.73 pp.

Archivos generados: comparison_metrics_oos_30001_40001.csv, comparison_delta_40001_minus_30001.csv, trades/cashflows/equity por modelo.