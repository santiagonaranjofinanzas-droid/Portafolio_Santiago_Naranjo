#H18 — Asymmetric Slow Trend

##Decisión

**H18 recupera una ventaja económica aparente, pero no recupera todavía un edge estadístico aprobable.**

- Estado: `REJECTED_LIVE_LOCKED`.
- Investigación: no aprobada.
- Institucional: no aprobada.
- Puerto MT5: no autorizado.
- Presupuesto Trend: 12/12 consumido; no se permite otro ajuste sobre estos datos.

##Especificación congelada

H18 es determinista, long-only y no utiliza HMM ni mean reversion. Parte de barras M15 UTC y sólo forma una observación H1 cuando existen exactamente los cierres `:00`, `:15`, `:30` y `:45`. Una hora incompleta se descarta.

- Variantes: 12/24/48, 16/32/64 y 24/48/96 observaciones H1.
- Entrada: score >= 0.35 durante dos cierres H1 completos.
- Salida: score <= 0 después de una permanencia mínima de ocho H1.
- Rearme obligatorio antes de una nueva entrada.
- Ejecución: apertura de la siguiente barra M15.
- Stop catastrófico: cruce confirmado al cierre H1 y ejecución en la siguiente apertura M15; controles de 3 y 6 ATR-H1.
- Riesgo: volatility target 10%, costes Axi y balance inicial contractual de 100,000 USD.

Los cuatro candidatos se registraron en el ledger append-only antes de observar PnL. La validación utilizó siete folds outer de seis meses, 36 meses de train, purga de 500 barras, 28 combinaciones inner por fold y 141 pruebas totales para DSR.

##Resultados individuales outer OOS

 Candidato  Trades  PF neto  PF bruto  PnL neto  DD  Sharpe  DSR  Bootstrap PF p05  P(beneficio) 
------:---:---:---:---:---:---:---:---:
 TREND_09 16/32/64, 6 ATR  254  1.229  1.274  24,801  10.71%  0.557  0.095  0.902  86.44% 
 TREND_10 12/24/48, 6 ATR  300  1.402  1.463  43,785  11.92%  0.956  0.415  1.056  97.52% 
 TREND_11 24/48/96, 6 ATR  180  1.532  1.582  43,624  8.36%  0.919  0.405  1.095  97.99% 
 TREND_12 16/32/64, 3 ATR  254  1.284  1.333  29,675  9.53%  0.667  0.157  0.941  91.27% 

Frente al momentum M15, TREND_10 redujo el número de trades 91.2% y los costes 92.0%. TREND_11 redujo trades 94.7% y costes 95.2%. Por tanto, el mecanismo de reducción de rotación sí quedó demostrado.

##Resultado nested

La selección inner eligió, por fold: `12, 11, 12, 10, 10, 10, 11`.

 Métrica  Resultado  Gate institucional 
------:---:
 Trades  258  >=250 
 PF  1.264  >=1.20 
 PnL  26,961  >0 
 Retorno  26.96%  — 
 DD  12.30%  <=15% 
 Sharpe diario  0.603  >=1.00 
 DSR  0.120  >=0.95 
 PF mínimo por fold  0.918  >=1.00 
 Trades mínimos por fold  22  >=30 
 Bootstrap PF p05  0.936  >1.00 
 Bootstrap expectancy p05  -5.63  >0 
 P(beneficio)  90.0%  >=95% 
 PBO global  32.68%  <=10% 
 PBO sólo H18  40.80%  <=10% 
 Peor trimestre PF  0.034  >=0.90 
 Vecinos positivos  66.67%  >=70% 
 PF costes adversos  1.248  >=1.05 
 PF costes crisis  1.213  >=1.00 

Aunque supera PF, drawdown y stresses de costes, falla diez controles de investigación/institucionales. La probabilidad pareada de mejora frente al momentum M15 fue 97.89%, pero mejorar un benchmark perdedor no equivale a demostrar edge desplegable.

##Fragilidad temporal

TREND_10 produjo PF por fold de `3.572 / 2.147 / 1.593 / 1.092 / 1.029 / 0.918 / 0.994`. Su ventaja se concentró en los primeros folds y desapareció en los dos últimos.

TREND_11 fue más estable (`2.635 / 2.498 / 1.155 / 1.737 / 0.988 / 1.279 / 1.377`), pero sólo generó 180 trades y entre 21 y 31 por fold. No cumple suficiencia muestral institucional.

Los stops catastróficos continuaron siendo la principal cola negativa. En TREND_10, ocho stops aportaron -15,961 mientras las salidas por señal aportaron +59,746. En TREND_11, ocho stops aportaron -16,343 y las salidas por señal +58,971. Esta descomposición no autoriza eliminar el stop: sigue siendo necesario un contrafactual futuro independiente.

##Controles de sesgo

###Look-ahead

- Features prefix-invariant: añadir o modificar datos futuros no altera el prefijo calculado.
- Sólo horas H1 completas; no hay `bfill`, interpolación ni smoothing futuro.
- Señal en cierre H1 y fill en la apertura M15 posterior.
- Stop por cierre también se ejecuta en next-open.
- Train termina estrictamente antes del test y existe purga de 500 barras.
- El holdout desde `2026-07-11T00:00:00Z` no fue leído.

###Supervivencia

El universo fue fijado ex ante a un único instrumento tradable, `NAS100.fs`. No se seleccionaron retrospectivamente acciones, símbolos supervivientes ni componentes del índice. El histórico del CFD/index level es apropiado para la unidad que se pretende operar, pero no permite atribuir el edge a componentes individuales.

###Overfitting y data snooping

- Sólo cuatro candidatos H18, todos preregistrados antes del backtest.
- Presupuesto Trend agotado en 12/12.
- 129 ensayos históricos incluidos en DSR; total 141.
- Vecinos de velocidad y stop evaluados explícitamente.
- PBO calculado globalmente y también sólo entre H18.
- Bootstrap block de 10,000 muestras.
- Ningún ajuste posterior está autorizado sobre el dataset consumido.

##Conclusión operativa

H18 constituye una **línea de investigación prometedora**: demuestra que ralentizar la señal y aplicar histéresis recupera PF bruto y reduce drásticamente el coste. Sin embargo, la evidencia no es suficientemente estable ni independiente para despliegue.

La única continuación válida es congelar TREND_10 y TREND_11 como observacionales y acumular datos Axi futuros. No debe elegirse uno de ellos usando nuevos resultados del mismo histórico. Cualquier nueva modificación exige un programa de investigación y un holdout nuevos.
