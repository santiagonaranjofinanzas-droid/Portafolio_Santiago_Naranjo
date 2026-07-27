#Diagnostico profundo de edge 50001

Base: trades tick bid/ask del 50001 equivalente al 40001 actual.

##Dia de semana

 segment    trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 ---------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 Friday     131     1.213                  43.511        1.015          -13.481           11                      0.084        
 Monday     155     -1.626                 43.226        0.983          -20.871           12                      -0.106       
 Sunday     44      9.115                  50.000        1.389          -7.515            8                       1.051        
 Thursday   173     18.155                 47.399        1.183          -10.512           6                       1.074        
 Tuesday    150     12.797                 46.667        1.149          -8.209            6                       0.824        
 Wednesday  175     -19.820                39.429        0.826          -23.590           11                      -1.234       

##Direccion

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 BUY      487     47.985                 47.433        1.176          -9.923            8                       1.740        
 SELL     341     -28.151                39.883        0.873          -43.026           12                      -1.213       

##Sesion

 segment       trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 ------------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 ASIA_00_07    224     -27.463                37.946        0.813          -35.221           7                       -1.507       
 LATE_20_24    123     31.495                 54.472        1.525          -7.601            5                       2.277        
 LONDON_07_13  362     25.358                 46.133        1.120          -11.120           8                       1.047        
 NY_13_20      119     -9.556                 40.336        0.876          -31.332           12                      -0.702       

##Volatilidad

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 Q1_vol   207     -5.311                 42.995        0.957          -15.235           7                       -0.308       
 Q2_vol   207     17.869                 46.377        1.154          -7.167            6                       1.001        
 Q3_vol   207     3.822                  43.961        1.031          -17.850           8                       0.212        
 Q4_vol   207     3.454                  43.961        1.026          -13.225           8                       0.180        

##Fuerza HMM/ML

 segment      trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 -----------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 Q1_strength  207     0.374                  42.512        1.003          -23.656           12                      0.021        
 Q2_strength  207     31.362                 49.758        1.280          -9.749            10                      1.726        
 Q3_strength  207     11.155                 45.894        1.093          -12.499           6                       0.619        
 Q4_strength  207     -23.057                39.130        0.831          -28.059           8                       -1.293       

##Duracion

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 0_8      281     -123.681               24.911        0.454          -123.709          20                      -6.599       
 25_48    169     77.403                 62.130        2.135          -4.152            4                       4.872        
 49_96    100     69.655                 71.000        3.260          -1.893            2                       5.956        
 97_plus  14      7.108                  71.429        2.582          -2.233            2                       1.706        
 9_24     264     -10.650                42.045        0.935          -26.192           6                       -0.526       

##Distancia al cambio de regimen

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 0_4      693     24.204                 44.589        1.059          -24.321           8                       0.733        
 13_48    43      -1.588                 41.860        0.943          -7.657            6                       -0.187       
 5_12     92      -2.782                 43.478        0.951          -9.159            4                       -0.233       

##MAE/MFE por salida

 exit_reason  trades  avg_pnl  avg_mae_money  avg_mfe_money  median_mfe_to_mae 
 -----------  ------  -------  -------------  -------------  ----------------- 
 SL           588     -62.628  97.092         73.130         0.506             
 TP           240     161.703  48.338         217.424        5.018             

##Uso

Este reporte define los candidatos para Capa 9: salidas por deterioro, reversa de regimen, TP adaptativo, trailing volatilidad, stop temporal y politica de break-even.
