#Plan de ejecucion Sovereign HMM

##Objetivo

Alcanzar paridad operacional 1 a 1 entre los modulos Python y los archivos MT5:

- `MT5/Sovereign_Core.mqh`
- `MT5/Sovereign_Signal.mq5`
- `MT5/Sovereign_Normal_Expert.mq5`

La paridad queda definida por tres niveles:

1. Paridad matematica: mismas formulas, clamps, ventanas, semillas y orden secuencial.
2. Paridad de buffers: mismos valores intermedios contra un export de MT5 con tolerancia `atol=1e-12`, `rtol=1e-12` cuando aplique.
3. Paridad operacional: mismas entradas, stops, lotaje, parciales y reglas de cierre bajo los mismos supuestos de mercado.

##Principios de complejidad por capas

Cada capa solo puede depender de capas anteriores y debe exportar artefactos auditables:

- Capa 0 produce datos OHLC limpios.
- Capa 1 produce primitivas matematicas puras.
- Capa 2 produce buffers de senal equivalentes al indicador MT5.
- Capa 3 produce parametros compatibles con el contrato CSV de MT5.
- Capa 4 produce ejecucion y backtest equivalentes al EA.
- Capa 5 produce validacion OOS con purga y embargo.
- Capa 6 produce optimizacion/reentrenamiento anti alpha decay sin contaminar el OOS.

No se debe introducir complejidad en una capa superior para compensar errores de una capa inferior. Si un buffer de Capa 2 esta mal, Capa 4 no debe corregirlo: debe fallar o reportarlo.

##Capa 0: datos

Archivo principal:

- `Analisis_Exploratorio_Datos.py`
- `Convertir_Datos_Crudos_Zip_A_Parquet.py`

Salida:

- `XAUUSD_M15_Training.parquet`
- `gold_data_parquet/year=YYYY/month=M/part_histdata_YYYYMM_0.parquet`
- `gold_data_parquet/Datos__Crudos 2024_2026/conversion_manifest.csv`

Reglas:

- Agregar ticks BID a velas M15.
- Ordenar por timestamp.
- Eliminar duplicados y NaNs.
- Mantener columnas `open`, `high`, `low`, `close`.
- Los ZIP HistData deben convertirse primero a Parquet tick-level con esquema `timestamp,bid,ask,last,volume,flags`.

##Capa 1: nucleo matematico

Archivos:

- `Capa_1/sovereign_core.py`
- `Capa_1/Validar_Capa1.py`

Paridad requerida:

- `CStatistics.LogisticClamped`
- `CStatistics.CalculateZScore`
- `CVolatilityEngine.StepGJRGARCH`
- `CStateSpace.StepKalman`
- `CStateSpace.EstimateOUDrift`

Validacion:

- Ejecutar `python Capa_1/Validar_Capa1.py`.
- Comparar contra export MT5 cuando exista.
- Tolerancia objetivo: `np.allclose(..., atol=1e-12, rtol=1e-12)`.

##Capa 2: senal e inferencia

Archivos:

- `Capa_2/sovereign_signal.py`
- `Capa_2/Validar_Capa2.py`

Contrato:

- `sovereign_signal.py` es la fuente canonica Python del nucleo de `OnCalculate`.
- `Validar_Capa2.py` solo ejecuta el motor y exporta buffers.

Buffers minimos exportados:

- `HMM_Prob_Bull` equivalente a buffer 15.
- `ML_Master_Strength` equivalente a buffer 17.
- `Regime_Buffer_18` equivalente a buffer 18.
- `Vol_Projected_Sigma` equivalente a buffer 32.
- `Kalman_Precio_Medio`, `Kalman_Covarianza_P`, `Kalman_Slope`, `Kalman_Regime`.
- `Entry_Bull_Buffer_6`, `Entry_Bear_Buffer_7`.

Validacion:

- Ejecutar `python Capa_2/Validar_Capa2.py`.
- Comparar columnas clave contra export de buffers MT5.

##Capa 3: calibracion

Archivos:

- `Capa_3/sovereign_calibration.py`
- `Capa_3/Calibrar_Sistema.py`

Contrato CSV estricto:

`HMM_Params_15M.csv` debe tener exactamente estas 18 columnas en este orden:

```text
InpPBull,InpPBear,InpSlopeT,InpLambdaJ,InpNu,WConf,WVol,WSlope,WAccel,WInter,MuConf,MuVol,MuSlope,MuAccel,StdConf,StdVol,StdSlope,StdAccel
```

Razon:

- `Sovereign_Signal.mq5` y `sovereign_signal.py` leen el contrato completo de 18 parametros.
- `WAccel`, `MuAccel` y `StdAccel` son parte de la paridad 1 a 1 con el sistema 30001 original.
- Cualquier columna faltante o desplazada rompe paridad.

Validacion:

- Ejecutar `python Capa_3/Calibrar_Sistema.py`.
- Verificar que el CSV mantiene 18 columnas.

##Capa 4: ejecucion

Archivos:

- `Capa_4/sovereign_execution.py`
- `Capa_4/Validar_Capa4.py`
- `Capa_4/backtest_metrics.py`
- `Evaluar_Robustez_Backtest.py`

Contrato con EA:

- Entrada solo si `Regime_Buffer_18 != 0` y `ML_Master_Strength >= InpMinStrength`.
- Para 30001 demo protegido, aplicar guardia adicional de regimen:
  - `ML_Master_Strength >= 0.66`;
  - bloquear nuevas entradas entre horas servidor 13:00 y 19:59;
  - configuracion documentada en `Sovereign_Regime_Guard_30001.csv`.
- Stop dinamico: `price * sig_proj * InpVolMultiplier`.
- Piso minimo: `3x spread`.
- Lotaje: `risk_money / (sl_pts * (tick_value / tick_size * point))`.
- Clamp de lote: `[0.01, InpMaxLot]`.
- Parcial: cerrar 70% y mover SL a breakeven.

Validacion:

- Ejecutar `python Capa_4/Validar_Capa4.py`.
- Registrar los supuestos de mercado cuando no existan Ask/Bid reales.
- Ejecutar `python Evaluar_Robustez_Backtest.py` para metricas IS/OOS.
- Revisar `Capa_4/metricas_backtest/resumen_metricas_is_oos.csv`.
- Revisar `Capa_4/metricas_backtest/REPORTE_ROBUSTEZ_IS_OOS.md`.

Metricas minimas:

- Retorno neto y balance final.
- Win rate y loss rate.
- Profit factor, expectancy, payoff ratio.
- Ganancia maxima y perdida maxima.
- Maximo numero de ganancias seguidas.
- Maximo numero de perdidas seguidas.
- Drawdown maximo en dinero, porcentaje y barras.
- Sharpe anualizado, Sortino y Sharpe deflactado.
- Recovery factor.
- Estabilidad tick-level por subventanas:
  - `python Capa_4/audit_tick_oos_stability_30001.py`;
  - revisar `Capa_4/tick_oos_stability_30001/REPORTE_TICK_ESTABILIDAD_OOS_30001.md`.

##Capa 5: validacion OOS con purga y embargo

Archivos:

- `Capa_5/validation_protocols.py`
- `Capa_5/Validar_Capa5.py`

Purga:

Una muestra de entrenamiento se elimina si su intervalo de etiqueta se solapa con el bloque test:

```text
t_start_train <= t_end_test AND t_end_train >= t_start_test
```

Embargo:

Se elimina toda muestra de entrenamiento cuyo inicio caiga dentro de:

```text
[t_end_test, t_end_test + 120 barras]
```

Configuracion inicial:

- `label_horizon = 120`
- `embargo = 120`
- `n_splits = 5`

Validacion:

- Ejecutar `python Capa_5/Validar_Capa5.py`.
- Revisar `Capa_5/auditoria_capa5_purged_embargo.csv`.
- Revisar `Capa_5/auditoria_capa5_fixed_oos_202405.csv`.
- Usar `Capa_5/XAUUSD_M15_IS_PURGED.parquet` para calibracion sin fuga.
- Usar `Capa_5/XAUUSD_M15_OOS_202405.parquet` para evaluacion OOS fija.

##Capa 6: optimizacion y reentrenamiento anti alpha decay

Archivos:

- `Capa_6/parameter_space.json`
- `Capa_6/optimizer.py`
- `Capa_6/Reentrenar_Modelo.py`
- `Capa_6/Detectar_Cambio_Regimen.py`
- `Capa_6/Reentrenar_Reciente.py`
- `Capa_6/README.md`

Objetivo:

- Reducir la probabilidad de alpha decay mediante busqueda controlada de parametros.
- Separar optimizacion interna de validacion OOS final.
- Monitorear degradacion por periodos con reporte trimestral.

Parametros optimizados:

- `threshold`
- `min_strength`
- `vol_multiplier`
- `reward_risk`
- `kalman_gate`

Artefactos:

- `Capa_6/resultados_optimizacion/ranking_parametros.csv`
- `Capa_6/resultados_optimizacion/best_params.json`
- `Capa_6/resultados_optimizacion/best_oos_holdout_metrics.csv`
- `Capa_6/resultados_optimizacion/alpha_decay_oos_quarterly.csv`
- `Capa_6/resultados_optimizacion/REPORTE_OPTIMIZACION_ALPHA_DECAY.md`
- `Capa_6/resultados_optimizacion/regime_status.json`
- `Capa_6/resultados_reentrenamiento_reciente/recent_best_params.json`

Ejecucion smoke:

```powershell
python Capa_6\Reentrenar_Modelo.py
```

Ejecucion completa:

```powershell
$env:MAX_CANDIDATES='FULL'
python Capa_6\Reentrenar_Modelo.py
```

Ejecucion con DSR penalizado por variantes:

```powershell
$env:DSR_TRIALS='81'
$env:MAX_CANDIDATES='FULL'
python Capa_6\Reentrenar_Modelo.py
```

Regla anti-overfit:

- Optimizar solo en validacion interna de IS purgado.
- Usar OOS fijo como holdout de auditoria, no como espacio de busqueda.
- Si `alpha_decay_oos_quarterly.csv` muestra PF rolling bajo 1.0, activar reentrenamiento rolling y reducir riesgo operativo.

Detector de regimen:

```powershell
python Capa_6\Detectar_Cambio_Regimen.py
```

Reentrenamiento rolling reciente:

```powershell
$env:MAX_CANDIDATES='FULL'
$env:DSR_TRIALS='81'
python Capa_6\Reentrenar_Reciente.py
```

Regla operativa de emergencia:

- Si el detector devuelve `PAUSE_AND_RETRAIN`, pausar nuevas entradas.
- Reentrenar rolling reciente.
- Activar solo paper/forward con riesgo reducido hasta que el PF rolling vuelva a superar 1.0.

##Orden operativo recomendado

1. Regenerar datos si cambia la fuente: `python Analisis_Exploratorio_Datos.py`.
2. Validar Capa 1: `python Capa_1/Validar_Capa1.py`.
3. Calibrar parametros: `python Capa_3/Calibrar_Sistema.py`.
4. Generar buffers de senal: `python Capa_2/Validar_Capa2.py`.
5. Validar ejecucion: `python Capa_4/Validar_Capa4.py`.
6. Construir folds OOS: `python Capa_5/Validar_Capa5.py`.
7. Comparar contra export MT5 cuando este disponible.

##Pendiente indispensable para paridad bitwise final

Exportar desde MT5 un CSV de al menos 1,000 barras con:

- `b_p1`
- `b_strength`
- `b_regime`
- `b_sigma2_gjr`
- `b_sig_proj`
- `b_kalman_x`
- `b_kalman_p`
- `b_hma_val`
- `b_hma_raw_slope`
- `g_nu_dynamic`
- `g_lambda_dynamic`

Sin ese export, Python puede lograr paridad estructural y operacional, pero la paridad bitwise final no queda demostrada.

##Bloqueo de robustez institucional

Antes de declarar el sistema robusto o pasarlo a real con size normal, debe cerrarse la auditoria metodologica:

- Revisar `AUDITORIA_ROBUSTEZ_METODOLOGICA.md`.
- Reemplazar backtest OHLC por backtest tick-level bid/ask.
- Modelar spread, comision y slippage.
- Implementar nested walk-forward en Capa 6:
  - recalibrar HMM solo con train de cada fold;
  - optimizar parametros en validation;
  - reservar holdout virgen.
- No usar OOS historico para seleccionar parametros finales.
- Crear un nuevo forward holdout posterior al reentrenamiento reciente.
- Reportar DD realizado y DD mark-to-market.

Regla de liberacion:

- `regime_status != PAUSE_AND_RETRAIN`
- PF rolling forward > 1.0
- DSR penalizado por variantes > 0.80
- Max DD mark-to-market dentro del limite de riesgo
- Ranking estable en varios folds

##Resultado de auditoria robusta ejecutada

Ver reporte:

- `REPORTE_EJECUCION_ROBUSTEZ_FINAL.md`

Estado actual:

- NO APROBADO PARA REAL.
- Tick-level OOS del candidato previo: PF 1.053, Sharpe 0.605, DSR 0.047.
- Nested walk-forward top stability: mean PF 1.043, min PF 0.903, mean DSR 0.033.
- Tick-level OOS del candidato nested: PF 1.040, Sharpe 0.638, DSR 0.040.

Bloqueo:

- No cargar parametros nuevos en real hasta rediseñar o ampliar el edge.
- Solo paper/forward para observacion.
- Proxima fase: mejorar modelo/filtros, no optimizar mas la misma grilla.
