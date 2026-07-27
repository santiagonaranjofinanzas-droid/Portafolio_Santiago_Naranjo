#Auditoria de estabilidad OOS 30001

Periodo auditado: 2024-05-06 03:45:00 a 2026-05-29 11:30:00

Esta auditoria usa la corrida OHLC del bot 30001 que genero el OOS superior al IS. El retorno segmentado se expresa como pnl neto del segmento sobre balance inicial de 10,000, para detectar concentracion temporal.

##Conclusion ejecutiva

- El OOS superior al IS es posible, pero no debe leerse como robustez cerrada: el rendimiento es favorable en 17 de 25 meses y 8 de 9 trimestres, pero el tramo reciente 2026Q2 cae -23.64%.
- El mejor mes fue 2026-01 con 26.74% y el peor fue 2026-04 con -13.61%.
- Los 5 mejores trades explican 19.08% del pnl total; no parece una concentracion extrema de 5 trades, pero el top 10% explica 129.77%, lo que exige vigilancia de cola positiva.
- La sesion NY aporta -12.37% y es negativa; London, Asia y Late sostienen el edge.
- El tercil HIGH_STRENGTH aporta 83.11% del retorno sobre balance inicial. Esto sugiere que un filtro por fuerza alta podria mejorar robustez, pero debe probarse con walk-forward antes de tocar produccion.
- Lectura principal: no hay evidencia de que el OOS sea solo un golpe aislado, pero si hay evidencia de sensibilidad de regimen y deterioro reciente. El despliegue demo debe ir con monitoreo por trimestre, sesion y fuerza.

##Resultado global

 segment          trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 ---------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 OOS_202405_FULL  479     134.305                49.478        1.344          -11.138           7                     9                       2.982        

##Concentracion

 metric                               value     
 -----------------------------------  --------- 
 total_oos_pnl                        13430.500 
 top_5_trades_pnl                     2562.618  
 top_5_trades_share_of_total_pct      19.081    
 top_10pct_trades_count               48.000    
 top_10pct_trades_pnl                 17428.141 
 top_10pct_trades_share_of_total_pct  129.765   
 bottom_5_trades_pnl                  -1321.354 
 profitable_months                    17.000    
 total_months                         25.000    
 profitable_month_rate_pct            68.000    
 profitable_quarters                  8.000     
 total_quarters                       9.000     
 profitable_quarter_rate_pct          88.889    

##Mejores meses

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2026-01  24      26.744                 62.500        2.344          -6.229            4                     3                       1.989        
 2025-01  34      21.839                 64.706        2.430          -2.407            6                     2                       2.512        
 2025-04  21      18.098                 61.905        2.404          -4.836            7                     3                       1.949        
 2025-09  25      17.449                 56.000        1.835          -6.325            7                     4                       1.455        
 2025-12  20      16.017                 55.000        1.864          -5.709            5                     3                       1.347        

##Peores meses

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2026-04  8       -13.615                12.500        0.233          -17.042           1                     7                       -2.040       
 2026-05  15      -10.027                26.667        0.620          -14.937           2                     6                       -0.869       
 2024-10  28      -3.786                 39.286        0.798          -6.739            2                     4                       -0.572       
 2025-07  21      -3.480                 38.095        0.849          -8.570            2                     4                       -0.358       
 2025-11  17      -1.170                 41.176        0.942          -10.995           2                     6                       -0.116       

##Trimestres

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2024Q2   40      3.650                  47.500        1.169          -5.985            5                     4                       0.470        
 2024Q3   55      8.940                  49.091        1.301          -5.112            3                     4                       0.938        
 2024Q4   65      4.864                  46.154        1.124          -6.739            4                     4                       0.455        
 2025Q1   72      28.879                 55.556        1.666          -6.647            6                     6                       2.089        
 2025Q2   46      30.970                 58.696        1.953          -5.313            7                     3                       2.215        
 2025Q3   59      15.265                 47.458        1.273          -12.725           7                     4                       0.891        
 2025Q4   65      19.410                 46.154        1.278          -12.315           5                     7                       0.951        
 2026Q1   54      45.970                 57.407        1.849          -6.229            5                     3                       2.155        
 2026Q2   23      -23.642                21.739        0.464          -28.032           2                     9                       -1.780       

##Direccion

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 BUY      449     120.452                49.443        1.330          -12.227           7                     9                       2.786        
 SELL     30      13.853                 50.000        1.542          -8.705            4                     5                       1.080        

##Sesion

 segment       trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 ------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 ASIA_00_07    120     40.025                 50.000        1.425          -8.351            6                     5                       1.742        
 LATE_20_24    71      46.579                 56.338        1.900          -7.076            6                     5                       2.536        
 LONDON_07_13  215     60.067                 51.163        1.369          -12.139           6                     9                       2.149        
 NY_13_20      73      -12.366                36.986        0.849          -26.274           5                     12                      -0.643       

##Regimen de volatilidad

 segment   trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 --------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 HIGH_VOL  160     65.641                 50.000        1.418          -14.034           6                     8                       2.063        
 LOW_VOL   160     21.887                 47.500        1.198          -14.643           5                     8                       1.069        
 MID_VOL   159     46.777                 50.943        1.381          -12.803           6                     6                       1.909        

##Lectura tecnica

- El OOS no debe asumirse como prueba final de robustez solo porque supera al IS. Primero hay que verificar si el retorno viene distribuido entre meses/trimestres o si depende de pocos clusters.
- Si los peores meses tienen drawdown acotado y los mejores meses no explican casi todo el pnl, la hipotesis de cambio favorable de regimen gana peso.
- Si top 5 o top 10% de trades explican demasiado pnl, el resultado OOS puede estar inflado por convexidad puntual y necesita validacion tick-level por subventanas.
- Esta auditoria no reoptimiza parametros; solo diagnostica estabilidad del bot 30001 sobre la ventana OOS ya generada.
