#Capa 11 - Forward live-shadow

Objetivo: validar el 50001 Layered V1 en demo/paper sin contaminar investigacion ni promoverlo a real por backtest.

##Flujo operativo

1. Ejecutar el 50001 en demo con magic `50001`.
2. Exportar periodicamente el historial de operaciones MT5 a CSV.
3. Normalizar ese CSV con:

```powershell
python Capa_11\live_shadow_ledger_50001.py --source exports\mt5_history_50001.csv
```

4. Evaluar el gate:

```powershell
python Capa_11\release_gate_50001.py
```

##Criterios iniciales

- Minimo 50 trades cerrados o 6 semanas de forward.
- Profit factor forward mayor a 1.10.
- Max drawdown forward no peor que -12%.
- Slippage promedio menor o igual a 50 puntos.
- Sin racha de perdidas cerradas mayor a 6.
- Estado del monitor distinto de `PAUSE_AND_RETRAIN`.

Hasta cumplir esos puntos:

```text
50001 = DEMO / PAPER ONLY
```
