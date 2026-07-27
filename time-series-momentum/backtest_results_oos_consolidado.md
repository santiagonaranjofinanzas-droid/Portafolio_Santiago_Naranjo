#Reporte de Resultados del Backtest Out-of-Sample (OOS): Capas 0 a 8

Este reporte consolida el rendimiento de todos los modelos bajo la misma ventana de evaluacin Out-of-Sample.

##Tabla Comparativa OOS

 Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario %  Supera Capa Anterior? 
 :---  :---:  :---:  :---:  :---:  :---: 
 **Capa 0: Benchmark**  0.5883  6.85%  -24.80%  48.93%  - 
 **Capa 1: TSMOM Bruto**  0.1361  0.76%  -16.83%  28.88%  No 
 **Capa 2: Fricciones Netas**  -0.0340  -0.58%  -19.12%  21.95%  No 
 **Capa 3: Cartera Inv Vol (Neto)** 0.1708  0.36%  -5.96%  4.44%  S 
 **Capa 4: CATSMOM (Neto)**  -0.1188  -0.66%  -13.26%  11.62%  No 
 **Capa 5a: Filtro Vol (Neto)**  0.3446  1.38%  -6.42%  10.72%  S 
 **Capa 5b: Filtro HMM (Neto)**  -0.1328  -0.69%  -12.84%  12.34%  No 
 **Capa 5c: Filtro MSSSM (Neto)**  0.1539  0.32%  -4.82%  4.20%  No 
 **Capa 6: XGBoost (Neto)**  -0.0640  -0.17%  -6.86%  11.12%  No 
 **Capa 7: LSTM (Neto)**  0.5342  3.37%  -7.59%  14.62%  S 
 **Capa 8: Attention (Neto)**  0.0000  0.00%  0.00%  0.00%  No 

##Grid Search de Histresis: Capa 8 (Attention)

 Umbral  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario % 
 :---  :---:  :---:  :---:  :---: 
 0.0000  0.0000  0.00%  0.00%  0.00% 
 0.0001  0.0000  0.00%  0.00%  0.00% 
 0.0003  0.0000  0.00%  0.00%  0.00% 
 0.0005  0.0000  0.00%  0.00%  0.00% 
 0.0008  0.0000  0.00%  0.00%  0.00% 
 0.0010  0.0000  0.00%  0.00%  0.00% 
 0.0015  0.0000  0.00%  0.00%  0.00% 
 0.0020  0.0000  0.00%  0.00%  0.00% 

Mejor umbral de histresis encontrado: **0.0000** con Sharpe Neto = **0.0000**

##Auditora Final de Complejidad

1. **Rendimiento LSTM (Capa 7)**: Sharpe Neto OOS = **0.5342**.
2. **Rendimiento Attention (Capa 8)**: Sharpe Neto OOS = **0.0000**.

###Conclusin Operativa
El modelo con mejor rendimiento neto bajo condiciones reales de CFDs en el conjunto Out-of-Sample es **Capa 0** con un Sharpe de **0.5883**.
