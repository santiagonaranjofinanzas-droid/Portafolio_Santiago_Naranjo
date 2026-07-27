#Comparacion OOS 30001 vs 40001 - Accel 18 parametros

Dataset: C:\Users\YOUR_USERNAME\Desktop\Trading\1_#####HMM#####\Capa_5\XAUUSD_M15_OOS_202405.parquet
Periodo: 2024-05-01 00:00:00 a 2026-05-29 16:45:00
Barras: 49137

30001 usa el contrato legacy de 18 columnas con WAccel/MuAccel/StdAccel activos.
40001 usa el contrato de 18 columnas con WAccel=0.0, MuAccel=0.0, StdAccel=1.0 para conservar el comportamiento actual hasta optimizar aceleracion.

##OHLC
 model_id  engine  total_return_pct  closed_trades  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_ratio  sortino_ratio  deflated_sharpe_probability  recovery_factor 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 30001  OHLC  134.3050  479.0000  49.4781  1.3438  -11.1378  7.0000  9.0000  2.5953  12.6642  0.9999  4.6011 
 40001  OHLC  136.1863  836.0000  46.2919  1.2080  -22.0473  7.0000  8.0000  2.0303  7.1818  0.6750  4.1310 

##TICK_BID_ASK
 model_id  engine  total_return_pct  closed_trades  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_ratio  sortino_ratio  deflated_sharpe_probability  recovery_factor 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 30001  TICK_BID_ASK  39.5923  473.0000  46.3002  1.1271  -12.3489  8.0000  9.0000  1.1003  4.5556  0.9256  2.0169 
 40001  TICK_BID_ASK  19.8340  828.0000  44.3237  1.0401  -23.6550  8.0000  8.0000  0.6375  2.3364  0.0403  0.6898 

##Delta 40001 - 30001
 engine  total_return_pct  closed_trades  win_rate_pct  profit_factor  max_drawdown_pct  sharpe_ratio  deflated_sharpe_probability 
 ---  ---  ---  ---  ---  ---  ---  --- 
 OHLC  1.8813  357.0000  -3.1862  -0.1358  -10.9095  -0.5650  -0.3249 
 TICK_BID_ASK  -19.7583  355.0000  -1.9765  -0.0870  -11.3060  -0.4628  -0.8853 

##Lectura rapida
- 30001 tick-level accel18: retorno 39.59%, PF 1.127, DD -12.35%, Sharpe 1.100.
- 40001 tick-level accel18: retorno 19.83%, PF 1.040, DD -23.65%, Sharpe 0.638.
- Delta tick-level 40001 vs 30001: retorno -19.76 pp, PF -0.087, DD -11.31 pp.