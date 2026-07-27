#Auditoria Tick-Level Mean Reversion OOS

Reejecucion de trades MR robustos usando ticks bid/ask reales. Las decisiones de regimen y objetivos Kalman permanecen en M15; el orden intrabar de SL/parcial/TP se resuelve con ticks.

 Activo  Estado  Trades Auditados  Total Disponible  Trades Tick  Fallidos  PnL OHLC  PnL Tick  Delta  Win OHLC  Win Tick 
 :---  :---  ---:  ---:  ---:  ---:  ---:  ---:  ---:  ---:  ---: 
 NSXUSD  OK  106  106  106  0  $1895.36  $1363.13  $-532.23  32.08%  29.25% 
 XAGUSD  OK  31  31  31  0  $41.71  $-582.35  $-624.06  64.52%  48.39% 
 XAUUSD  OK  48  48  48  0  $-262.98  $-334.91  $-71.93  66.67%  60.42% 

##Notas

- NSXUSD y XAGUSD usan ticks desde `Universo de activos/Datos_Crudos_Zip`.
- XAUUSD no esta en esa carpeta; se usa `gold_data_parquet/Datos__Crudos 2024_2026` si el archivo mensual existe.
- Esta auditoria valida microestructura de ejecucion; no reentrena HMM/Kalman sobre barras de rango o volumen.
