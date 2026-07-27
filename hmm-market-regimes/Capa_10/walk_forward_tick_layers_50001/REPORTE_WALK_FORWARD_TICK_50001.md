#Walk-forward tick-level capas 50001

Este protocolo selecciona la mejor capa en una ventana previa y evalua solo en la ventana siguiente. Usa ticks bid/ask, parametros HMM 50001 y no reentrena el HMM.

##Resumen

- Folds test: 5
- PF mediano test: 0.986
- PF minimo test: 0.978
- Retorno medio test: 8.74%
- Peor DD test: -12.15%
- Trades test totales: 416
- Gate PF>=1.10 en todos los folds: False
- Gate minimo 20 trades por fold: True

##Decision

Si algun fold test queda por debajo de PF 1.10 o con muestra demasiado baja, el 50001 sigue en demo/paper. La salida por flip de regimen, filtro de spread real y pausa por racha de perdidas se validan en forward live-shadow porque dependen del flujo intratrade/live.
