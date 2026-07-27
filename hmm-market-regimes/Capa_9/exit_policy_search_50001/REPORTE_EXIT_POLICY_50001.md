#Capa 9 - Optimizacion de salidas 50001

Este buscador usa trades tick enriquecidos con MAE/MFE. Es una simulacion de politica de salida sobre trades ya abiertos, por lo que no reemplaza el backtest intratrade completo; sirve para seleccionar candidatos antes de codificarlos en MQL/tick-engine.

##Resumen walk-forward

- PF mediano test: 7.340
- PF minimo test: 6.424
- Retorno medio test: 56.91%
- Peor DD test: -1.48%
- Trades test totales: 654
- Gate PF>=1.10 todos los folds: True

##Folds test

 fold  phase  policy      trades  return_pct_on_initial  win_rate_pct  profit_factor  max_drawdown_pct  max_consecutive_losses  sharpe_trade 
 ----  -----  ----------  ------  ---------------------  ------------  -------------  ----------------  ----------------------  ------------ 
 1     test   time_24_96  139     53.108                 47.482        8.113          -1.057            2                       7.057        
 2     test   time_12_96  142     52.634                 40.141        6.424          -1.162            2                       6.456        
 3     test   time_12_96  127     53.646                 42.520        7.340          -1.006            2                       6.747        
 4     test   time_12_96  130     70.945                 50.000        12.432         -1.287            2                       8.362        
 5     test   time_12_96  116     54.208                 41.379        6.510          -1.479            2                       5.853        

##Politicas seleccionadas

 fold  policy      min_hold_bars  max_hold_bars  weak_strength_cutoff  weak_tp_capture  be_mae_ratio 
 ----  ----------  -------------  -------------  --------------------  ---------------  ------------ 
 1     time_24_96  24             96             0.000                 1.000            10.000       
 2     time_12_96  12             96             0.000                 1.000            10.000       
 3     time_12_96  12             96             0.000                 1.000            10.000       
 4     time_12_96  12             96             0.000                 1.000            10.000       
 5     time_12_96  12             96             0.000                 1.000            10.000       

##Decision

La politica solo puede pasar a MQL si mejora PF minimo y DD sin reducir muestra de forma artificial. Si el gate falla, se mantiene como investigacion y se prioriza forward demo.
