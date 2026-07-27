#Reporte Corregido: HMM Trend + Mean Reversion (OOS)

> Este reporte fue regenerado desde ledgers OOS. Correcciones aplicadas: filtros ex-ante de volatilidad/aceleracion/momentum, optimizacion robusta por folds con DSR, desempacado correcto del backtest tendencial, equity MR con mark-to-market, señales ejecutables desplazadas, TP parcial MR, coexistencia paralela 50/50 y coexistencia exclusiva por ledger con expectancy reciente.

##Parametros MR Calibrados IS

 Activo  OOS  Z Long  Z Short  SL ATR Mult  Score Robusto  DSR Mediano IS  Retorno Mediano IS  Peor DD IS 
 :---  :---  ---:  ---:  ---:  ---:  ---:  ---:  ---: 
 NSXUSD  2024-05-01 00:00:00 a 2026-06-19 12:45:00  3.0  3.25  3.5  0.2583  0.0462  6.01%  -14.86% 
 XAGUSD  2024-05-01 00:00:00 a 2026-06-19 12:45:00  3.0  3.25  3.0  -0.2037  0.0066  -0.81%  -4.37% 
 XAUUSD  2024-05-01 00:00:00 a 2026-05-29 16:45:00  3.0  3.0  3.5  0.5626  0.0802  0.78%  -5.08% 

##Resultados Reales OOS

###NSXUSD

Correlacion diaria de equity Trend/MR: `-0.0407`

 Sistema  Retorno  Profit  Sharpe  Max DD  Trades 
 :---  ---:  ---:  ---:  ---:  ---: 
 HMM Trend Only  9.46%  $945.80  0.51  -7.86%  157 
 Mean Reversion Only  18.95%  $1,895.36  0.69  -16.94%  106 
 Parallel 50/50 Sleeves  14.21%  $1,420.58  0.80  -11.26%  N/A 
 Exclusive Ledger Dynamic Expectancy  25.59%  $2,558.91  0.72  -14.96%  259 

###XAGUSD

Correlacion diaria de equity Trend/MR: `-0.0368`

 Sistema  Retorno  Profit  Sharpe  Max DD  Trades 
 :---  ---:  ---:  ---:  ---:  ---: 
 HMM Trend Only  5.23%  $523.02  0.31  -15.56%  128 
 Mean Reversion Only  0.42%  $41.71  0.09  -4.55%  31 
 Parallel 50/50 Sleeves  2.82%  $282.36  0.31  -7.39%  N/A 
 Exclusive Ledger Dynamic Expectancy  5.65%  $564.73  0.32  -13.56%  159 

###XAUUSD

Correlacion diaria de equity Trend/MR: `-0.0218`

 Sistema  Retorno  Profit  Sharpe  Max DD  Trades 
 :---  ---:  ---:  ---:  ---:  ---: 
 HMM Trend Only  -2.70%  $-270.11  -0.16  -13.03%  60 
 Mean Reversion Only  -2.63%  $-262.98  -0.44  -6.41%  48 
 Parallel 50/50 Sleeves  -2.67%  $-266.54  -0.35  -8.47%  N/A 
 Exclusive Ledger Dynamic Expectancy  -7.21%  $-721.03  -0.42  -17.10%  107 

##Veredicto

Estos numeros sustituyen al reporte anterior. La seleccion MR ya no optimiza por profit sino por robustez DSR en folds temporales. La coexistencia paralela no usa optimizacion L1 ni correlacion fija; es una suma auditada de sleeves 50/50. La coexistencia exclusiva filtra ledgers sin solape usando expectancy reciente. Para produccion real todavia conviene portar exactamente este ledger a MT5/tick-level antes de operar capital.
