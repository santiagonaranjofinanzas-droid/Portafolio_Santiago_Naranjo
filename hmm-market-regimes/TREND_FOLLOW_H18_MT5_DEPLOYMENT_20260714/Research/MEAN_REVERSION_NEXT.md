#Mean Reversion — siguiente hipótesis de investigación

> Update 2026-07-14: esta hipótesis fue implementada como MR V3 Shock Rejection
> y quedó falsada por insuficiencia muestral/estabilidad. Véase
> `MeanReversionV3/Governance/MR_V3_SHOCK_REJECTION_20260714.md`. No se autorizó
> un EA 6003.

##Diagnóstico de la versión retirada

Mean Reversion V2 no falló por un problema de portabilidad. Falló antes, en la
existencia del edge:

- `phi_gate_pass_folds = 0` frente a un mínimo requerido de 7.
- La half-life estimada estuvo aproximadamente entre 31 y 36 barras M15.
- El intervalo preregistrado exigía una half-life entre 2 y 16 barras.

Esto indica persistencia lenta, no una reversión rápida explotable con la lógica
anterior. Ampliar el máximo de 16 hasta acomodar el resultado sería ajuste
post-hoc y no recuperaría evidencia económica.

##Hipótesis nueva propuesta

**El NAS100 no revierte de forma incondicional después de una desviación. La
reversión puede aparecer sólo después de un shock de liquidez que fracasa en
continuar, y únicamente cuando no existe una tendencia lenta dominante.**

La entrada no debe ser “z-score extremo = fade”. Debe exigir una secuencia causal:

1. shock de retorno/rango anormal medido contra su distribución intradía pasada;
2. ausencia de continuidad en una ventana fija posterior al shock;
3. rechazo observable —cierre que vuelve dentro del rango previo—;
4. veto si el score Trend H18 indica tendencia lenta fuerte en la dirección del
   shock;
5. objetivo en equilibrio local calculado sólo con observaciones anteriores.

##Diseño para evitar sesgos

- Estacionalidad, escala, equilibrio y umbrales se estiman sólo dentro del train.
- El outer OOS nunca elige lado, sesión, horizonte ni threshold.
- Purga y embargo cubren el mayor horizonte de respuesta y la duración máxima de
  la operación.
- No se seleccionan retrospectivamente días, sesiones o signos rentables.
- La familia completa de hipótesis cuenta para DSR/PBO y corrección por múltiples
  pruebas.
- Feed y especificación son siempre `NAS100.fs`; no hay universo de acciones ni
  selección de supervivientes.
- Los resultados se publican incluyendo eventos sin operación y folds fallidos.

##Secuencia recomendada

1. Congelar y archivar MR V2 como hipótesis falsada.
2. Construir primero un event study causal de shock/rechazo, sin estrategia ni
   sizing.
3. Preregistrar una cuadrícula pequeña de horizontes y una sola definición de
   costes.
4. Exigir reversión condicional estable por fold y bajo costes adversos.
5. Sólo si existe respuesta económica, construir señales y backtest nested.
6. Someter el candidato a bootstrap por bloques, DSR, PBO, perturbación de
   parámetros y test por sesiones.
7. Portar a MQL únicamente después de superar el gate estadístico.

El primer entregable debe ser un **protocolo de falsificación**, no un nuevo EA.
