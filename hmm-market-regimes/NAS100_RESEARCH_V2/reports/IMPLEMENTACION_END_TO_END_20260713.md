#Implementación end-to-end NAS100 V2

##Decisión

- Mean Reversion V2: **RETIRADO**.
- Trend HMM V2: **RECHAZADO; el filtro HMM no se conserva**.
- Momentum long-only: **RECHAZADO**.
- Despliegue MT5: **NO AUTORIZADO**.
- Estado de cuenta real: **LIVE_LOCKED**.

##Gobierno y datos

El programa `NAS100_EDGE_RECOVERY_V2_20260710` mantiene un ledger append-only enlazado por SHA-256. Se registraron ocho candidatos Trend y nueve MR antes de observar sus resultados. Los 81 ensayos Trend y 48 MR anteriores se incluyen como 129 pruebas históricas en DSR/PBO.

El dataset combinado contiene 145,818 barras M15 UTC. Los 78 ZIP HistData están enlazados por SHA-256 y clasificados exclusivamente como `DEVELOPMENT_CONSUMED`. Se excluyeron 24 barras correspondientes a horas ambiguas de rollback. HistData no es evidencia elegible para release. La muestra Axi contiene 7,814,606 ticks, 1,300 barras completas, cobertura 100%, cero crossed/duplicados/out-of-order y spread mediano/p95 de 2.5/3.0.

##Mean Reversion V2

La falsificación se ejecutó antes del grid. En los siete folds completos ninguna estimación AR(1) cumplió la vida media preregistrada de 2–16 barras; las estimaciones quedaron entre 31.2 y 36.4 barras.

- Long: 5,259 extremos; respuesta monotónica positiva en 2/4 bloques; CI bootstrap terminal no positiva.
- Short: 5,349 extremos; respuesta monotónica positiva en 0/4 bloques; CI bootstrap terminal no positiva y edge bruto inferior a 2× costes.
- Folds con gate AR aprobado: 0/7.

Resultado: `RETIRE_MEAN_REVERSION`. Los otros ocho candidatos MR permanecen registrados pero nunca fueron iniciados ni inspeccionados contra resultados.

##Trend V2 y benchmarks

Se ejecutaron siete outer folds completos, train 36 meses/test 6 meses/paso 6 meses, purga 500 barras y 28 particiones inner CPCV por fold. El total de pruebas usado fue 137: 129 históricas más ocho nuevas.

Resultado nested corregido sobre el balance contractual de 100,000 USD:

 Métrica  Resultado  Gate investigación 
------:---:
 Trades  765  ≥200 
 PF agregado  0.831  ≥1.10 
 PF mediano por fold  0.799  ≥1.05 
 PF mínimo por fold  0.568  ≥1.00 
 Retorno  -14.92%  — 
 Sharpe diario  -0.773  ≥0.80 
 DSR  0.000009  ≥0.80 
 DD  -19.45%  ≤15% 
 Bootstrap PF p05  0.645  >1.00 
 Probabilidad de beneficio  3.76%  ≥95% 
 PBO  80.30%  ≤20% 
 PF costes 1.5×  0.781  ≥1.05 
 PF crisis  0.701  ≥1.00 

Ninguno de los ocho candidatos individuales alcanzó PF>1. El mejor fue momentum long-only: 3,421 trades, PF 0.915, retorno -29.27% y Sharpe -0.481. El mejor candidato HMM alcanzó PF 0.864.

Los estados tuvieron ocupaciones superiores al 10% y separación suficiente, pero una o más varianzas de emisión alcanzaron el floor en los siete folds. Esto viola el límite de parámetros en frontera. Además, la probabilidad bootstrap de mejora contra momentum fue 75.33%, inferior al 95% requerido, y el delta p05 fue negativo. Por ambas razones el HMM se elimina.

##Causalidad y ejecución

- Features y probabilidades OOS son prefix-invariant.
- Sólo se usan probabilidades filtradas; no smoothing OOS.
- Entradas en next-open y stop-first cuando la secuencia intrabar es ambigua.
- Trend usa volatilidad objetivo de 10% y contrato Axi real (`tick_size=0.01`, `tick_value=0.20`).
- MR usa target congelado en z=0, sin parciales y time-stop por vida media.
- Stress mantiene las señales congeladas y cambia únicamente los costes de ejecución.

##MT5 y futuro

No se generó EA ni se portaron parámetros porque ningún candidato aprobó el gate de investigación. El comparador de paridad Python/MT5 está implementado y exige señales/trades 100%, precios dentro de un tick y diferencia de PnL ≤0.5%.

El holdout iniciado el 11 de julio de 2026 permanece virgen. Para cualquier futura especificación aprobada serán obligatorios cuatro meses/40 trades de holdout, seis meses/60 trades de forward demo y al menos 100 trades futuros combinados. Cualquier cambio reinicia los contadores.
