Nivel 1

Modelo base:

TSMOM+VolTarget

Nada más.

Nivel 2

Añadir:

costos reales
spreads
swaps

Verificar que sigue funcionando.

Nivel 3

Añadir:

ajuste de correlaciones CATSMOM

Verificar mejora.

Nivel 4

Añadir:

filtro de régimen

Comparar:

sin régimen
Markov
HMM
volatilidad realizada
Nivel 5

Solo si existe mejora estadísticamente significativa:

DMN
LSTM
Attention
Mi estimación

Si ejecutaras hoy:

Sistema A

TSMOM clásico:

retornos 1, 3, 6 y 12 meses
volatility targeting
costos reales
cartera diversificada

y

Sistema B

Todo tu blueprint DMN-CFD

no me sorprendería que el Sistema A capturara entre 70% y 90% del rendimiento final con apenas 10% de la complejidad operacional.

Ese resultado es bastante común en finanzas cuantitativas.


La regla es:

Ningún componente entra al sistema si no mejora significativamente los resultados fuera de muestra.

Capa 0: Benchmark Institucional

Antes de construir nada complejo necesitas un benchmark.

Estrategia

Para cada activo:

Signal
i
	​

=sign(R
252
	​

)

donde:

R
252
	​

=ln(
P
t−252
	​

P
t
	​

	​

)

Posiciones:

Long si retorno 12 meses > 0
Short si retorno 12 meses < 0

Volatility targeting al 15%.

Objetivo

Responder:

¿Cuál es el Sharpe mínimo que debo superar?

Muchos investigadores se saltan este paso.

Pero si tu sistema neuronal obtiene:

Sharpe = 1.2

y el benchmark obtiene:

Sharpe = 1.0

quizás no vale toda la complejidad.

Capa 1: TSMOM Profesional

Ahora pasas a un sistema que podría gestionar dinero real.

Señales

Momentum:

R
21
	​

R
63
	​

R
126
	​

R
252
	​


Normalizados por volatilidad.

Ensemble
S
i
	​

=0.1Z
21
	​

+0.2Z
63
	​

+0.3Z
126
	​

+0.4Z
252
	​

Posición
X
i
	​

=tanh(S
i
	​

)
Riesgo

Volatility Target:

15% anual.

Resultado esperado

Si esto no funciona:

olvida IA
olvida Markov
olvida Attention

Porque la base ya está rota.

Capa 2: Fricciones Reales CFD

Aquí comienza la parte donde la mayoría de backtests mueren.

Añadir:

Spread
TC
spread
	​

Comisión
TC
comm
	​

Swap
TC
swap
	​

Slippage
TC
slippage
	​

Objetivo

Medir:

Sharpe
bruto
	​


vs

Sharpe
neto
	​


Muchos sistemas pierden 30%-50% del rendimiento aquí.

Capa 3: Cartera Multiactivo

Ahora agregas diversificación.

No IA.

No redes.

Solo cartera.

Universo
Índices
FX
Metales
Energía
Bonos
Sizing

Volatility Scaling.

w
i
	​

=
∑
j
	​

1/σ
j
	​

1/σ
i
	​

	​

Objetivo

Determinar cuánto alpha viene de:

señal

y cuánto viene de:

diversificación.

Muchas veces la mitad del Sharpe proviene de la cartera, no de la señal.

Capa 4: Ajuste de Correlación

Aquí entra CATSMOM.

Tu idea es bastante buena.

Calcular:

ρ
ˉ
	​

t
	​


y

CF
t
	​

Prueba

Comparar:

Sin CATSMOM

vs

Con CATSMOM

Preguntas:

¿reduce drawdown?
¿reduce volatilidad?
¿aumenta CAGR?

Si no mejora claramente:

lo eliminas.

Capa 5: Régimen de Mercado

Aquí recién aparece Markov.

No antes.

Versión simple

Regímenes por volatilidad.

Por ejemplo:

σ
63
	​

Versión media

HMM de 2 estados.

Versión avanzada

Tu M-SSSM jerárquico.

Regla

Primero demostrar:

HMM>Volatilidad

Después demostrar:

MSSSM>HMM

Porque muchas veces un HMM sencillo captura casi todo.

Capa 6: Machine Learning Clásico

Antes del Deep Learning.

Entradas:

Momentum
Volatilidad
Carry
Correlación

Modelos:

Ridge
Lasso
Elastic Net
XGBoost
LightGBM
Pregunta

¿Existe información no lineal?

Si XGBoost no mejora nada:

probablemente la red tampoco.

Capa 7: Deep Momentum Network

Ahora sí.

Aquí tiene sentido.

Inputs:

u
i,t
	​


12 variables.

Arquitectura:

LSTM

o

Transformer temporal.

No necesariamente ambos.

Objetivo

Comparar:

XGBoost

vs

LSTM

Si la diferencia es mínima:

mantén XGBoost.

Será más estable.

Capa 8: Attention

Muchos investigadores la añaden demasiado pronto.

Pregunta:

¿LSTM ya captura suficiente contexto?

Si sí:

Attention sobra.

Solo entra si demuestra mejora estadística.

Capa 9: Optimización de Loss

Aquí entra:

Sharpe Loss
EVaR
Sortino
Utility

No al principio.

Porque si cambias:

arquitectura
datos
pérdidas

simultáneamente

no sabes qué produjo la mejora.

Capa 10: Producción

Recién aquí.

Sistema diario:

Descargar datos.
Actualizar volatilidades.
Actualizar señales.
Generar pesos.
Controlar margen.
Enviar órdenes.
Registrar operaciones.

Construir una tabla de contribución marginal.

Capa	Sharpe Neto OOS	Max DD	Turnover
Benchmark B	?	?	?
Capa 1	?	?	?
Capa 2	?	?	?
Capa 3	?	?	?
Capa 4	?	?	?
HMM	?	?	?
M-SSSM	?	?	?
XGBoost	?	?	?
LSTM	?	?	?
LSTM+Attention	?	?	? 