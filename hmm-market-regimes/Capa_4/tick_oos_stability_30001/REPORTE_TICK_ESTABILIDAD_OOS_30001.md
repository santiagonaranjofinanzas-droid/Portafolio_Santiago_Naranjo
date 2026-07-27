#Auditoria tick-level OOS 30001

Periodo: 2024-05-06 04:00:00 a 2026-05-29 11:37:32.979000

Esta auditoria usa ejecucion con ticks bid/ask del bot 30001. El retorno segmentado es pnl del segmento sobre balance inicial 10,000.

##Conclusion ejecutiva

- Tick-level confirma que el OOS sigue positivo, pero mucho mas fragil que OHLC.
- Meses rentables: 60.00%.
- Trimestres rentables: 77.78%.
- Mejor mes: 2026-01 con 14.31%.
- Peor mes: 2026-04 con -8.74%.
- Sesion NY_13_20: -15.10%.
- Regimen HIGH_STRENGTH: 50.21%.
- Recomendacion aplicada: demo con guardia de regimen configurable; no promover a produccion real hasta cerrar walk-forward tick-level y monitor de deterioro.
- Escenario de guardia aplicado: strength >= 0.66 y bloqueo NY_13_20.

##Resultado global

 segment               trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 --------------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 TICK_OOS_202405_FULL  473     39.592                 46.300        1.127          -12.349           8                     9                       1.260        

##Escenarios de guardia

 segment                              trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -----------------------------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 BASE_TICK                            473     39.592                 46.300        1.127          -12.349           8                     9                       1.260        
 STRENGTH_GE_0_66                     159     51.298                 54.717        1.581          -6.895            9                     5                       2.797        
 BLOCK_NY_13_20                       401     54.694                 48.130        1.216          -8.756            7                     7                       1.899        
 STRENGTH_GE_0_66_AND_BLOCK_NY_13_20  138     52.075                 56.522        1.713          -5.115            9                     4                       3.068        

##Meses

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2024-05  17      3.306                  52.941        1.405          -1.975            3                     2                       0.668        
 2024-06  22      -1.190                 40.909        0.908          -5.470            6                     4                       -0.216       
 2024-07  24      1.169                  45.833        1.088          -3.087            3                     3                       0.197        
 2024-08  14      2.021                  50.000        1.268          -4.055            4                     4                       0.419        
 2024-09  17      5.294                  52.941        1.596          -2.621            3                     2                       0.924        
 2024-10  28      -4.347                 39.286        0.764          -6.882            2                     4                       -0.690       
 2024-11  23      6.049                  52.174        1.499          -3.179            3                     3                       0.932        
 2024-12  14      -4.905                 28.571        0.561          -8.284            1                     6                       -1.032       
 2025-01  30      8.272                  56.667        1.549          -5.302            8                     5                       1.160        
 2025-02  15      -0.010                 46.667        0.999          -2.431            2                     2                       -0.002       
 2025-03  23      -2.002                 39.130        0.875          -3.484            3                     4                       -0.306       
 2025-04  21      5.120                  52.381        1.426          -3.895            4                     3                       0.780        
 2025-05  14      5.813                  57.143        1.784          -3.426            3                     3                       1.025        
 2025-06  9       -0.208                 44.444        0.967          -3.790            2                     3                       -0.046       
 2025-07  22      -2.846                 36.364        0.838          -7.209            2                     4                       -0.396       
 2025-08  13      0.172                  46.154        1.020          -4.783            2                     4                       0.034        
 2025-09  25      8.804                  52.000        1.574          -4.678            7                     4                       1.096        
 2025-10  28      0.023                  42.857        1.001          -3.955            2                     3                       0.003        
 2025-11  17      -2.009                 41.176        0.850          -7.620            2                     6                       -0.319       
 2025-12  20      8.019                  55.000        1.664          -3.819            3                     3                       1.099        
 2026-01  24      14.310                 62.500        2.090          -4.087            4                     3                       1.758        
 2026-02  8       3.599                  50.000        1.590          -2.982            2                     2                       0.602        
 2026-03  22      1.887                  45.455        1.103          -6.151            2                     3                       0.219        
 2026-04  8       -8.743                 12.500        0.190          -10.579           1                     7                       -2.427       
 2026-05  15      -8.007                 26.667        0.503          -9.435            2                     6                       -1.288       

##Trimestres

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2024Q2   39      2.116                  46.154        1.100          -7.213            6                     4                       0.288        
 2024Q3   55      8.485                  49.091        1.285          -4.011            4                     4                       0.901        
 2024Q4   65      -3.202                 41.538        0.923          -8.148            3                     6                       -0.312       
 2025Q1   68      6.260                  48.529        1.154          -9.253            8                     6                       0.575        
 2025Q2   44      10.724                 52.273        1.415          -3.895            4                     3                       1.117        
 2025Q3   60      6.130                  45.000        1.148          -10.114           7                     4                       0.518        
 2025Q4   65      6.033                  46.154        1.129          -8.795            3                     7                       0.477        
 2026Q1   54      19.796                 53.704        1.527          -5.227            4                     3                       1.510        
 2026Q2   23      -16.749                21.739        0.378          -18.681           2                     9                       -2.339       

##Direccion

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 BUY      443     40.775                 46.727        1.141          -13.089           8                     9                       1.348        
 SELL     30      -1.183                 40.000        0.949          -7.263            2                     5                       -0.138       

##Sesion

 segment       trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 ------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 ASIA_00_07    116     17.097                 48.276        1.232          -7.456            4                     6                       1.084        
 LATE_20_24    71      19.173                 53.521        1.467          -6.930            5                     5                       1.561        
 LONDON_07_13  214     18.424                 46.262        1.133          -10.784           5                     9                       0.886        
 NY_13_20      72      -15.102                36.111        0.743          -22.045           6                     12                      -1.224       

##Regimen de fuerza

 segment        trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 HIGH_STRENGTH  158     50.209                 54.430        1.569          -7.196            9                     5                       2.740        
 LOW_STRENGTH   158     9.383                  44.937        1.088          -11.488           6                     9                       0.516        
 MID_STRENGTH   157     -19.999                39.490        0.829          -20.928           6                     6                       -1.137       

##Regimen de volatilidad

 segment   trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 --------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 HIGH_VOL  158     15.819                 46.203        1.138          -14.521           4                     9                       0.786        
 LOW_VOL   158     -3.809                 43.038        0.963          -16.630           7                     8                       -0.232       
 MID_VOL   157     27.582                 49.682        1.292          -11.287           5                     5                       1.556        
