#HMM Mean Reversion - Scripts Ordenados

Esta carpeta contiene las copias ordenadas de los scripts usados para regenerar los numeros reales de la subrama Mean Reversion.

##Orden de uso

1. `01_mean_reversion_signal.py`
   - Calcula `Z_dev`.
   - Genera senales descriptivas y senales ejecutables desplazadas para la siguiente apertura.

2. `02_backtest_mean_reversion.py`
   - Ejecuta el backtest MR.
   - Incluye costos, spread, slippage, comisiones, mark-to-market y cierre final si queda posicion abierta.

3. `03_analisis_coexistencia.py`
   - Construye coexistencia desde ledgers ya ejecutados.
   - Paralelo: sleeves 50/50.
   - Exclusivo: ledger sin solape con prioridad Trend.

4. `04_run_reversion_pipeline.py`
   - Punto de entrada principal.
   - Calibra MR en IS, ejecuta OOS, guarda ledgers y genera reporte.

##Outputs copiados

- `REAL_RESULTS_SUMMARY.csv`
- `REPORTE_SISTEMA_DUAL_CORREGIDO.md`

Los ledgers completos por activo estan en `SUB_RAMA_MEAN_REVERSION/resultados/<ACTIVO>/`.
