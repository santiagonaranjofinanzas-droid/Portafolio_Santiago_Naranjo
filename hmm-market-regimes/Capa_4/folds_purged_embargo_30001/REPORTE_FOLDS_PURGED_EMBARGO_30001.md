#Bot 30001 - Folds con Purga y Embargo

Parametros: C:\Users\YOUR_USERNAME\Desktop\Trading\1_#####HMM#####\MT5_Version_30001\Files\HMM_Params_15M_30001.csv
Threshold=0.65, MinStrength=0.35, VolMultiplier=2.5, RewardRisk=2.0, KalmanGate=True
Purga=120 barras, Embargo=120 barras, Horizonte etiqueta=120 barras.

##Metricas principales IS/OOS
 dataset  Trades  Return  Win rate  PF  Max DD  Max wins  Max losses  Sharpe  DSR 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 IS_PURGED  551  42.34%  44.28%  1.10  -28.42%  7  11  0.85  0.931 
 OOS_202405  479  134.31%  49.48%  1.34  -11.14%  7  9  2.60  1.000 

##Ventanas por fold
 fold_id  test_start_time  test_end_time  train_count  test_count  purged_count  embargoed_count  Trades  Return  Win rate  PF  Max DD  Max wins  Max losses  Sharpe  DSR 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 0  2021-01-03 18:15:00  2022-01-23 19:15:00  97798  24479  0  120  168  52.43%  51.79%  1.53  -6.38%  7  6  2.80  0.999 
 1  2022-01-23 19:30:00  2023-02-06 07:15:00  97678  24479  120  120  188  -2.29%  41.49%  0.98  -18.30%  5  11  -0.08  0.467 
 2  2023-02-06 07:30:00  2024-05-02 22:15:00  97677  24480  120  120  200  -6.35%  40.00%  0.94  -19.33%  5  7  -0.34  0.367 
 3  2024-05-02 22:30:00  2025-05-16 01:45:00  97678  24479  120  120  239  71.16%  51.46%  1.47  -6.86%  8  5  3.29  1.000 
 4  2025-05-16 02:00:00  2026-05-29 16:45:00  97797  24480  120  0  226  16.80%  44.25%  1.12  -11.35%  5  6  1.03  0.851 

Archivos CSV: main_metrics_is_oos_30001.csv, fold_windows_purged_embargo_30001.csv, fold_metrics_purged_embargo_30001.csv.