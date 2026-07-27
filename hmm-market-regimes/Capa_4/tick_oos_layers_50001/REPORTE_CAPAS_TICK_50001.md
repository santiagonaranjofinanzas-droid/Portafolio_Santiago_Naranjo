#Auditoria capas tick-level 50001

Base usada: 50001 hereda parametros del 40001 actual, por eso la auditoria parte de `tick_trades_oos_40001.csv`.

##Capas activadas

- Sesion: solo London 07:00-12:59 y Late 20:00-23:59 hora servidor.
- Fuerza minima: 0.50.
- Sigma proyectada: [0.000841261697, 0.003233866265].
- En MQL se agregan ademas filtro de spread, pausa por racha de perdidas, salida por flip de regimen y stop temporal.

##Escenarios

 segment                         trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 ------------------------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 BASE_50001_EQ_40001_TICK        828     19.834                 44.324        1.040          -23.655           8                     8                       0.549        
 SESSION_LONDON_LATE             485     56.853                 48.247        1.209          -8.290            7                     7                       2.036        
 SESSION_PLUS_STRENGTH_GE_0_50   446     62.280                 49.327        1.254          -8.739            7                     7                       2.327        
 LAYERED_SESSION_STRENGTH_SIGMA  360     62.207                 50.556        1.324          -6.334            6                     6                       2.595        

##Trimestres layered

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2024Q2   31      7.126                  51.613        1.479          -4.934            4                     3                       1.051        
 2024Q3   50      10.752                 52.000        1.415          -4.936            5                     4                       1.188        
 2024Q4   44      16.955                 59.091        1.863          -3.108            6                     3                       2.018        
 2025Q1   43      2.010                  46.512        1.078          -8.398            3                     4                       0.238        
 2025Q2   47      13.639                 57.447        1.676          -3.877            5                     4                       1.728        
 2025Q3   39      9.612                  53.846        1.537          -3.820            5                     4                       1.303        
 2025Q4   42      4.448                  47.619        1.200          -3.125            4                     3                       0.570        
 2026Q1   29      5.719                  48.276        1.333          -5.026            4                     5                       0.742        
 2026Q2   35      -8.053                 34.286        0.717          -10.144           3                     5                       -0.954       

##Meses layered

 segment  trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 -------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 2024-05  14      5.725                  57.143        1.934          -2.889            4                     3                       1.180        
 2024-06  17      1.401                  47.059        1.160          -3.385            3                     3                       0.291        
 2024-07  17      5.780                  58.824        1.837          -2.956            5                     4                       1.198        
 2024-08  14      4.103                  57.143        1.614          -4.119            5                     4                       0.850        
 2024-09  19      0.869                  42.105        1.071          -4.129            3                     4                       0.141        
 2024-10  16      1.829                  50.000        1.217          -3.051            3                     3                       0.373        
 2024-11  16      14.303                 75.000        4.231          -1.077            6                     1                       2.946        
 2024-12  12      0.823                  50.000        1.121          -3.438            3                     3                       0.186        
 2025-01  11      4.611                  63.636        2.036          -1.079            3                     1                       1.112        
 2025-02  21      -6.152                 33.333        0.619          -8.275            2                     4                       -1.063       
 2025-03  11      3.551                  54.545        1.689          -2.087            3                     2                       0.817        
 2025-04  18      8.281                  66.667        2.398          -1.021            5                     2                       1.813        
 2025-05  13      5.598                  61.538        2.110          -1.804            3                     2                       1.282        
 2025-06  16      -0.240                 43.750        0.974          -4.401            3                     4                       -0.050       
 2025-07  14      2.388                  50.000        1.341          -3.820            3                     4                       0.518        
 2025-08  8       0.462                  50.000        1.116          -2.090            2                     2                       0.144        
 2025-09  17      6.762                  58.824        1.976          -2.927            5                     3                       1.352        
 2025-10  14      6.137                  64.286        2.225          -1.159            4                     1                       1.439        
 2025-11  12      -0.314                 41.667        0.955          -2.727            1                     2                       -0.075       
 2025-12  16      -1.375                 37.500        0.867          -3.137            2                     3                       -0.271       
 2026-01  11      1.105                  45.455        1.178          -5.026            3                     5                       0.253        
 2026-02  6       4.457                  66.667        2.729          -1.330            2                     1                       1.155        
 2026-03  12      0.157                  41.667        1.019          -3.561            2                     3                       0.030        
 2026-04  13      0.953                  46.154        1.112          -3.558            3                     3                       0.181        
 2026-05  22      -9.007                 27.273        0.548          -9.191            2                     5                       -1.363       

##Sesion layered

 segment       trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_wins  max_consecutive_losses  sharpe_trade 
 ------------  ------  ---------------------  ------------  -------------  ----------------  --------------------  ----------------------  ------------ 
 LATE_20_24    93      42.595                 63.441        2.155          -4.767            11                    5                       3.657        
 LONDON_07_13  267     19.612                 46.067        1.126          -11.824           5                     7                       0.946        

##Decision

El escenario layered mejora PF y DD frente al 50001 base, pero sigue siendo demo/paper. La capa no se considera robusta final hasta validarse con walk-forward tick-level y forward posterior al periodo usado para decidir estas reglas.
