#Reporte de robustez IS/OOS

##Configuracion

- Capital inicial: 10,000
- Datos IS: `Capa_5/XAUUSD_M15_IS_PURGED.parquet`
- Datos OOS: `Capa_5/XAUUSD_M15_OOS_202405.parquet`
- Parametros HMM: recalibrados usando solo IS purgado
- DSR trials: 1
- Supuestos de ejecucion: `point=0.01`, `tick_size=0.01`, `tick_value=1.0`, `spread_price=0.0`

##Resumen

 Dataset    Trades  Return  Win rate  Profit factor  Max DD  Max wins  Max losses  Sharpe  Sortino  DSR prob 
-------------------------------------------------------------------------------------------------------------
 IS_PURGED  715     79.24%  44.90%    1.13           -26.84% 6         10          1.17    11.00    0.981    
 OOS_202405 581     90.42%  46.13%    1.18           -15.58% 8         11          1.78    7.13     0.995    

##Lectura

La estrategia muestra continuidad OOS: mejora retorno, profit factor, drawdown y Sharpe frente al IS purgado. El win rate esta por debajo de 50%, pero el payoff ratio mayor a 1 compensa la frecuencia de perdida.

La robustez no debe declararse definitiva hasta repetir el DSR con el numero real de variantes/prototipos probados. Si se probaron muchas configuraciones, ejecutar:

```powershell
$env:DSR_TRIALS='50'; python Evaluar_Robustez_Backtest.py
```

##Archivos generados

- `resumen_metricas_is_oos.csv`
- `signals_IS_PURGED.parquet`
- `signals_OOS_202405.parquet`
- `trades_IS_PURGED.csv`
- `trades_OOS_202405.csv`
- `cashflows_IS_PURGED.csv`
- `cashflows_OOS_202405.csv`
- `equity_IS_PURGED.csv`
- `equity_OOS_202405.csv`
