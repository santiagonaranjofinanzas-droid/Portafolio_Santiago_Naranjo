#Capa 6: Optimizacion y reentrenamiento anti alpha decay

##Objetivo

Optimizar parametros operativos y de filtro sin contaminar el OOS final, detectar decadencia del alpha y producir una configuracion candidata para nuevas condiciones de mercado.

##Flujo

1. Usar `Capa_5/XAUUSD_M15_IS_PURGED.parquet` como universo de optimizacion.
2. Separar internamente validacion temporal con purga de 120 barras.
3. Evaluar candidatos sobre validacion IS.
4. Seleccionar el mejor por score robusto.
5. Auditar el mejor contra `Capa_5/XAUUSD_M15_OOS_202405.parquet`.
6. Generar reporte trimestral de alpha decay en OOS.

##Ejecucion rapida

```powershell
python Capa_6\Reentrenar_Modelo.py
```

Por defecto evalua solo 8 candidatos para smoke test.

##Barrido completo

```powershell
$env:MAX_CANDIDATES='FULL'
python Capa_6\Reentrenar_Modelo.py
```

##Sharpe deflactado con penalizacion por multiples pruebas

Si probaste 50 variantes, usa:

```powershell
$env:DSR_TRIALS='50'
$env:MAX_CANDIDATES='FULL'
python Capa_6\Reentrenar_Modelo.py
```

##Artefactos

- `resultados_optimizacion/ranking_parametros.csv`
- `resultados_optimizacion/best_params.json`
- `resultados_optimizacion/best_oos_holdout_metrics.csv`
- `resultados_optimizacion/best_oos_trades.csv`
- `resultados_optimizacion/best_oos_equity.csv`
- `resultados_optimizacion/alpha_decay_oos_quarterly.csv`
- `resultados_optimizacion/regime_status.json`
- `resultados_optimizacion/regime_quarterly_diagnostics.csv`
- `resultados_reentrenamiento_reciente/ranking_reciente.csv`
- `resultados_reentrenamiento_reciente/recent_best_params.json`

##Parametros optimizados

- `threshold`
- `min_strength`
- `vol_multiplier`
- `reward_risk`
- `kalman_gate`

El archivo `parameter_space.json` controla la grilla, restricciones y pesos del objetivo.

##Detector de cambio de regimen

```powershell
python Capa_6\Detectar_Cambio_Regimen.py
```

Estados posibles:

- `NORMAL`: operar parametros vigentes.
- `WATCH`: mantener operacion, pero vigilar y endurecer fuerza minima.
- `DEFENSIVE`: reducir riesgo y disparar reentrenamiento.
- `PAUSE_AND_RETRAIN`: pausar nuevas entradas, reentrenar y validar en forward.

##Reentrenamiento rolling reciente

```powershell
$env:MAX_CANDIDATES='FULL'
$env:DSR_TRIALS='81'
python Capa_6\Reentrenar_Reciente.py
```

Este proceso genera un candidato adaptativo para el regimen reciente. No debe ir directo a real sin paper/forward test.
