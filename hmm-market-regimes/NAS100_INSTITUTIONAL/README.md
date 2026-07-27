#NAS100 Institutional Release Candidate

Este paquete audita los modelos Mean Reversion y Trend Following contra el contrato real `NAS100.fs` del terminal MT5 conectado.

##Estado

`LIVE_LOCKED`: ningún modelo está autorizado para cuenta real. El sistema solo puede usarse en investigación, Strategy Tester y forward demo hasta que `results/release_decision.json` indique aprobación y se hayan cerrado los controles de paridad y forward.

##Reproducir la auditoría

```powershell
$env:PYTHONPATH=(Resolve-Path '..').Path
python audit_nas100_release.py
```

El proceso retorna código `2` cuando el release gate rechaza la cartera; ese resultado es intencional y debe tratarse como bloqueo de despliegue.

##Refrescar el contrato del bróker

Compile y ejecute `MT5/Scripts/Export_NAS100_Symbol_Profile.mq5` sobre un gráfico `NAS100.fs`. El CSV se genera en `MQL5/Files`. Antes de una nueva auditoría, compare ese archivo con `config/broker_profile_nas100_fs.json`.

##Regla operativa

No copie EAs a una terminal real ni cambie `LIVE_LOCKED` manualmente. Primero deben pasar todos los controles definidos en `config/release_policy.json`, incluyendo paridad Python/MT5, backtest Every tick y forward demo independiente.
