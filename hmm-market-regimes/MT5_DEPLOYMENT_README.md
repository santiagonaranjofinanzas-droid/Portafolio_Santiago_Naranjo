#Sovereign MT5 Demo Deployment

30001: sistema antiguo / optimizacion previa. Magic 30001. Demo protegido con guardia de regimen.
40001: modelo optimizado actual sin capas de mejora. Magic 40001.
50001: modelo con capas de mejora Layered V1. Magic 50001.

Cada bot usa archivos propios: HMM_Params_15M_30001.csv, HMM_Params_15M_40001.csv, HMM_Params_15M_50001.csv.

Los HMM params usan contrato de 18 columnas:
InpPBull, InpPBear, InpSlopeT, InpLambdaJ, InpNu, WConf, WVol, WSlope, WAccel, WInter, MuConf, MuVol, MuSlope, MuAccel, StdConf, StdVol, StdSlope, StdAccel.

Indicadores: Sovereign\\Sovereign_30001_Signal, Sovereign\\Sovereign_40001_Signal, Sovereign\\Sovereign_50001_Signal.

30001, 40001 y 50001 son demo/paper. 50001 es el candidato con capas defensivas, no apto para real hasta forward.

Guardia 30001:

- Archivo: Sovereign_Regime_Guard_30001.csv.
- Activada por defecto en Sovereign_30001_Expert.mq5.
- No abre nuevas operaciones si `ML_Master_Strength < 0.66`.
- No abre nuevas operaciones entre horas servidor 13:00 y 19:59.
- Base: auditoria tick-level OOS en Capa_4/tick_oos_stability_30001.

Capas 50001:

- Archivo principal: Sovereign_Config_50001.csv.
- Archivo resumen: Sovereign_Layer_Config_50001.csv.
- Sesiones permitidas: 07:00-12:59 y 20:00-23:59 hora servidor.
- Fuerza minima efectiva: 0.50.
- Sigma proyectada permitida: 0.0008412616967549172 a 0.0032338662645819277.
- Filtro de spread: max 80 puntos.
- Monitor de deterioro: pausa si hay 4 perdidas consecutivas en 30 dias.
- Salidas defensivas: cierre por flip de regimen y stop temporal de 96 barras.
- Salidas Capa 9: cierre por fuerza debil bajo 0.45 tras 12 barras, parcial no antes de 12 barras, parcial adaptativo con factor 0.70 si fuerza debil.
- Base: auditoria tick-level en Capa_4/tick_oos_layers_50001.
- Walk-forward tick-level: Capa_10/walk_forward_tick_layers_50001.
- Estado walk-forward: bloqueado para real; PF minimo test 0.923.
- Forward/live-shadow: Capa_11/forward_50001.
