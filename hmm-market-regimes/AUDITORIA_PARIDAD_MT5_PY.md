#Auditoria de paridad MT5 vs Python

Fecha de ejecucion: 2026-06-08

##Veredicto actualizado

La paridad estructural y operacional fue corregida en Python por capas. La paridad bitwise final contra MT5 queda pendiente de demostracion hasta contar con un export real de buffers MT5 para comparar con `np.allclose`.

##Hallazgos criticos

1. Capa 2 no esta implementada como modulo equivalente a `Sovereign_Signal.mq5`.
   - `Capa_2/sovereign_signal.py` solo contiene `LogGamma`, `LogTStudent` y `LogNormalJump`.
   - La mayor parte del indicador MT5 vive en `Capa_2/Validar_Capa2.py`, que es un arnes de simulacion, no un modulo reutilizable equivalente.
   - Faltan equivalentes modulares para buffers, `OnInit`, `OnCalculate`, `CalculateWMA`, `CalculateHMA`, `CalculateEMA`, `CalculateStdev`, `CalculateVariance`, `CalculateKurtosis`, regimen, flechas, velas y dashboard.

2. El CSV generado por Capa 3 no tiene paridad con el lector MT5.
   - MT5 lee exactamente 15 columnas: `string cols[15]` y `string vals[15]`.
   - Python genera 18 columnas: incluye `WAccel`, `WInter`, `MuAccel`, `StdAccel`.
   - MT5 espera `ExtWInter = vals[8]`, pero Python pone `WAccel` en la posicion 8 y `WInter` en la 9.
   - `has_stability = (cols[9] == "MuConf" && cols[14] == "StdSlope")` falla con el CSV actual, porque `cols[9]` es `WInter`, no `MuConf`.
   - Resultado: MT5 ignora `MuConf`, `MuVol`, `MuSlope`, `StdConf`, `StdVol`, `StdSlope` del CSV y usa fallbacks.

3. Capa 4 no replica la logica de entrada del EA.
   - El EA abre operaciones con `regime != 0 && strength >= InpMinStrength`, leyendo `regime` desde buffer 18.
   - El backtest Python ignora `regime` y decide con `hmm_prob > 0.65` o `< 0.35`.
   - Esto cambia las entradas porque el regimen MT5 incluye el gate de Kalman.

4. Capa 4 no replica el stop loss ni el sizing del EA.
   - MT5 calcula `vol_distance_price = price * sig_proj * InpVolMultiplier`.
   - Python calcula `price * sigma`, pero no aplica `InpVolMultiplier = 2.5`.
   - MT5 usa piso minimo de `3x spread`; Python usa un piso fijo `5.0`.
   - MT5 calcula lote con tick value, tick size y point; Python usa `point_value=1.0` por defecto.

5. Los validadores no comparan contra un export real de MT5.
   - Los scripts imprimen "alineado 1 a 1", pero no cargan buffers exportados desde MT5 ni ejecutan `np.allclose` contra columnas MQL5.
   - Actualmente son simuladores Python autocontenidos, no pruebas de paridad contra MT5.

##Hallazgos altos

1. `Validar_Capa1.py` falla si se ejecuta desde la raiz del proyecto.
   - Usa `ruta_lago = os.path.join("..", "XAUUSD_M15_Training.parquet")`.
   - Desde la raiz busca `C:/Users/YOUR_USERNAME/Desktop/Trading/XAUUSD_M15_Training.parquet`.
   - Desde `Capa_1` si encuentra el parquet correcto.

2. Los scripts fallan en consola Windows cp1252 antes de calcular.
   - Los `print` usan simbolos Unicode no representables en cp1252.
   - Con `PYTHONIOENCODING=utf-8` corren.

3. Capa 3 optimiza una verosimilitud distinta al indicador real.
   - El calibrador usa drift cero para ambos estados.
   - El indicador MT5 usa drift OU asimetrico por barra.
   - Por tanto la MLE offline no es 1 a 1 con el filtro live.

4. Capa 2 no exporta columnas necesarias para reproducir el EA.
   - Exporta `close`, `ATR_14`, `HMM_Prob_Bull`, `Vol_Projected_Sigma`, `ML_Master_Strength`, `Kalman_Precio_Medio`.
   - No exporta `b_regime`, `b_strength` con indice de buffer, `b_sig_proj` como buffer 32, ni diagnosticos de Kalman gate.

##Ejecuciones realizadas

- `python Capa_1/Validar_Capa1.py` desde raiz: falla por ruta de parquet.
- `python Validar_Capa1.py` desde `Capa_1` con `PYTHONIOENCODING=utf-8`: corre.
- `python Capa_2/Validar_Capa2.py` con `PYTHONIOENCODING=utf-8`: corre y regenera `Capa_2/auditoria_capa2_signals.csv`.
- `python Capa_3/Calibrar_Sistema.py` con `PYTHONIOENCODING=utf-8`: corre y regenera `HMM_Params_15M.csv`.
- `python Capa_4/Validar_Capa4.py` con `PYTHONIOENCODING=utf-8`: corre, pero el resultado no es paridad del EA por las diferencias arriba.

##Estado por capa

- Capa 1: paridad alta de primitivas; requiere corregir rutas, encoding y validar contra export MT5 real.
- Capa 2: paridad parcial; densidades correctas, pero falta convertir el indicador completo a modulo Python.
- Capa 3: paridad baja-media; genera parametros, pero CSV y objetivo MLE no calzan con MT5.
- Capa 4: paridad baja; el backtest no replica entradas, stops, lotaje ni uso de `regime` del EA.

##Prioridad de correccion

1. Reparar contrato CSV para que Python genere exactamente las columnas que MT5 lee, o actualizar MT5 para leer 18 columnas de forma explicita.
2. Exportar desde MT5 un CSV de buffers intermedios y convertir los validadores en comparadores `np.allclose`.
3. Migrar la logica completa de `Validar_Capa2.py` a `sovereign_signal.py` como motor determinista equivalente a `OnCalculate`.
4. Hacer que Capa 2 exporte `regime`, `strength`, `p1`, `sig_proj`, `kalman_slope`, `kalman_regime` y entradas exactas.
5. Reescribir Capa 4 para consumir `regime` y replicar `ExecuteOrder`, `ManagePosition` y `CalculateLot` con `point`, `spread`, `tick_value`, `tick_size`, `InpVolMultiplier` e `InpMaxLot`.
6. Normalizar ejecucion con rutas absolutas y `PYTHONIOENCODING=utf-8`.

##Correcciones aplicadas

- `Capa_3/Calibrar_Sistema.py` ahora genera `HMM_Params_15M.csv` con 15 columnas exactas y en el orden que lee `Sovereign_Signal.mq5`.
- `Capa_1/Validar_Capa1.py` usa rutas absolutas desde el archivo, por lo que puede ejecutarse desde la raiz del proyecto.
- `Capa_2/sovereign_signal.py` ahora contiene el motor secuencial canonico equivalente al nucleo de `OnCalculate`.
- `Capa_2/Validar_Capa2.py` dejo de duplicar logica y ahora exporta los buffers desde el motor canonico.
- `Capa_4/sovereign_execution.py` replica el calculo de stop y lote del EA.
- `Capa_4/Validar_Capa4.py` consume `Regime_Buffer_18`, aplica parciales y reporta flujos realizados.
- `Capa_5/validation_protocols.py` y `Capa_5/Validar_Capa5.py` agregan folds OOS con purga y embargo de 120 barras.
- `Plan de ejecucion.md` fue reemplazado por un plan actual con complejidad progresiva por capas.

##Verificacion posterior

- `python -m py_compile ...`: OK.
- `python Capa_1/Validar_Capa1.py`: OK.
- `python Capa_3/Calibrar_Sistema.py`: OK.
- `python Capa_2/Validar_Capa2.py`: OK.
- `python Capa_4/Validar_Capa4.py`: OK.
- `python Capa_5/Validar_Capa5.py`: OK.
- `HMM_Params_15M.csv`: 15 columnas.
