#MR V4 — Trend Pullback Long (buy-the-dip)

##Decisión

`REJECTED_RESEARCH_ONLY_NO_EA`

La hipótesis fue implementada y falsificada end-to-end. No existe evidencia de
edge positivo en la formulación prerregistrada y no se autoriza portar un EA a
MT5. El Magic 6003 continúa reservado, no operativo.

##Hipótesis congelada

- NAS100.fs, M15, sólo LONG.
- Shock bajista: percentil inferior 2% del z-return causal, calibrado por sesión
  UTC exclusivamente en el train purgado de cada fold.
- Rango mínimo: 1.25 ATR(32), calculado sin la vela actual.
- Tendencia: ambos estados lógicos H18 long y ambos scores >= 0.35.
- Confirmación: primera vela alcista que cierre por encima del cierre del shock
  y del cierre anterior, dentro de cuatro velas.
- Entrada: apertura de la vela siguiente.
- Target: cierre previo al shock; stop: 0.75 ATR bajo el mínimo del shock.
- RR mínimo: 0.75; time stop: 16 velas; riesgo: 0.10%.
- Colisión intrabar: stop antes que target.

Los parámetros se fijaron en
`governance/config/mr_v4_preregistration_20260714.json` antes de calcular PnL.

##Capa 1 — existencia del efecto

Se estudiaron 209 eventos OOS no solapados, usando entrada en la apertura
siguiente y costes completos. El horizonte principal prerregistrado fue 16
velas (4 horas).

 Horizonte  Eventos  Media neta  Mediana  P(media > 0)  Folds positivos 
---:---:---:---:---:---:
 4 velas  209  -4.47 bps  -0.53 bps  2.97%  1/7 
 8 velas  209  -6.84 bps  -2.64 bps  1.06%  1/7 
 16 velas  209  -7.94 bps  -2.75 bps  2.58%  1/7 
 32 velas  209  -0.90 bps  0.52 bps  43.59%  3/7 

El efecto económico falla antes de introducir target o stop. Por tanto, ajustar
esas salidas sobre el mismo histórico sería optimización post hoc, no recuperación
demostrada del edge.

##Capa 2 — regla operable OOS

 Métrica  Resultado  Gate 
------:---:
 Trades  102  >=100 
 PF  0.914  >=1.20 
 PnL neto  -496.05  >0 
 Expectancy  -4.86/trade  >0 
 Win rate  44.12%  — 
 Folds positivos  2/7  >=5/7 
 Mínimo trades/fold  11  >=10 
 DSR (143 ensayos)  0.0011  >=0.95 
 Drawdown  0.94%  <=15% 
 Bootstrap PF p05  0.617  >1.00 
 Bootstrap P(PnL > 0)  32.80%  >=95% 

Las salidas fueron 52 stops, 37 recuperaciones al cierre pre-shock y 13 time
stops. Todos los 102 trades fueron long, como exige el contrato.

##Capa 3 — costes

 Escenario  PF  PnL neto 
------:---:
 Base  0.914  -496.05 
 Adverse  0.855  -866.09 
 Crisis  0.758  -1,542.76 

El spread adverse/crisis se aplica como piso sobre el spread observado o el
perfil horario, conservando siempre el mayor de ambos.

##Estabilidad temporal

Los trades se reparten entre 2023 y 2026 y los siete folds contienen al menos
11 operaciones. Sólo los folds 3 y 6 obtuvieron PF > 1; cinco folds fueron
negativos. La pérdida no se explica por una única crisis ni por falta de muestra
en un fold.

##Controles de sesgo

- Prefix invariance: aprobada para z-return, ATR, range/ATR, ambos scores H18 y
  alineación de tendencia.
- Look-ahead: threshold calibrado sólo en train; señal al cierre; fill next-open;
  sin backfill; stop-first cuando la secuencia intrabar es desconocida.
- Overfitting: una sola candidata prerregistrada; DSR penalizado por 143 ensayos
  históricos; no se reporta PBO porque no hubo selección entre candidatas V4.
- Supervivencia: no existe selección retrospectiva de constituyentes; se estudia
  un único instrumento continuo NAS100.fs. Esto no elimina riesgos de cambio de
  proveedor o contrato.
- Límite de evidencia: el dataset está clasificado `DEVELOPMENT_CONSUMED` y no
  puede autorizar live deployment aunque un gate histórico resultara positivo.

##Consecuencia

No debe incubarse ni desplegarse esta regla. Relajar thresholds, escoger sólo el
horizonte de 32 velas, cambiar sesiones o retocar stops sobre estos resultados
sería una hipótesis nueva y requeriría datos futuros realmente no vistos.
