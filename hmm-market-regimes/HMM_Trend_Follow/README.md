#HMM Trend Follow - Scripts Ordenados

Esta carpeta contiene las dependencias usadas por el sistema tendencial dentro del pipeline corregido.

##Orden de uso

1. `01_backtest_metrics.py`
   - Motor de backtest tendencial.
   - Calcula trades, cashflows, equity mark-to-market y metricas.

2. `02_sovereign_execution.py`
   - Motor financiero compartido.
   - Calcula stops por volatilidad y lotaje adaptativo.

El pipeline principal que llama estos scripts esta en `HMM_Mean_Reversion/HMM_GENERAL/04_run_reversion_pipeline.py`.
