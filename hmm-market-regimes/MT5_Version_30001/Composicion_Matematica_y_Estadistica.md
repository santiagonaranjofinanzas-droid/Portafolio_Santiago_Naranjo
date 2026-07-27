#Composición Matemática y Estadística del Sistema de Trading Sovereign Quantum

Este documento detalla la formulación matemática y estadística del sistema de trading **Sovereign Quantum (Expert V30.0 / Signal V8.1)**, el cual opera bajo una política estricta de paridad $F(t-1)$ (Zero Lag, operando exclusivamente en el cierre de velas para evitar el repintado).

---

##1. Filtro de Hamilton con Difusión por Saltos de Merton (HMM)

El núcleo del sistema de clasificación de regímenes es un modelo de **Markov Oculto (HMM)** de dos estados ($S_t \in \{0, 1\}$, correspondientes a Bearish y Bullish) modificado para incorporar una densidad de probabilidad mixta que incluye una distribución $t$-Student (para capturar colas pesadas habituales en retornos financieros) y un proceso de **Difusión por Saltos de Merton**.

###1.1 Ecuación de Transición de Probabilidades
Dado el estado en el instante anterior $P(S_{t-1} = 1) = p_{t-1}$, la probabilidad predicha para el estado alcista (Bullish) antes de observar el retorno del período $t$ es:
$$p_{tt-1} = P(S_t = 1  \mathcal{F}_{t-1}) = P_{\text{Bull}} \cdot p_{t-1} + (1 - P_{\text{Bear}}) \cdot (1 - p_{t-1})$$
Donde:
*   $P_{\text{Bull}}$ (`ExtPBull`): Probabilidad de transición de continuar en régimen alcista.
*   $P_{\text{Bear}}$ (`ExtPBear`): Probabilidad de transición de continuar en régimen bajista.

###1.2 Densidades de Probabilidad Mixtas (Likelihoods)
El retorno logarítmico se define como $r_t = \ln(Close_{t-1} / Close_{t-2})$. La verosimilitud de cada estado se calcula mediante una combinación lineal ponderada por la tasa de saltos de Poisson ($\lambda$):

$$\mathcal{L}(r_t  S_t = s) = (1 - \lambda) \cdot f_{\text{Student}}(r_t; \mu_s, \sigma_t, \nu) + \lambda \cdot f_{\text{Jump}}(r_t; \sigma_{\text{jump}})$$

Donde:
1.  **Distribución $t$-Student** ($f_{\text{Student}}$):
    $$f_{\text{Student}}(r_t; \mu_s, \sigma_t, \nu) = \frac{\Gamma\left(\frac{\nu + 1}{2}\right)}{\Gamma\left(\frac{\nu}{2}\right) \sqrt{\pi \nu} \sigma_t} \left(1 + \frac{1}{\nu}\left(\frac{r_t - \mu_s}{\sigma_t}\right)^2\right)^{-\frac{\nu+1}{2}}$$
    *   $\mu_s$: Deriva estimada (donde $\mu_{\text{Bull}} = \mu_{\text{OU}}$ y $\mu_{\text{Bear}} = -\mu_{\text{OU}}$).
    *   $\sigma_t$ (`sig_t`): Desviación estándar de ventana corta.
    *   $\nu$ (`g_nu_dynamic`): Grados de libertad, calibrados dinámicamente mediante el exceso de curtosis de los retornos históricos ($\kappa_t$):
        $$\nu_t = \max\left(2.5, \min\left(30.0, \frac{6.0}{\kappa_t} + 4.0\right)\right)$$

2.  **Componente de Salto Lognormal** ($f_{\text{Jump}}$):
    Representa shocks extremos no persistentes del mercado. Se modela con una distribución normal de media cero y alta volatilidad $\sigma_{\text{jump}}$:
    $$f_{\text{Jump}}(r_t; \sigma_{\text{jump}}) = \frac{1}{\sigma_{\text{jump}} \sqrt{2\pi}} \exp\left(-\frac{r_t^2}{2\sigma_{\text{jump}}^2}\right)$$
    Donde la desviación del salto se amplifica usando la curtosis histórica para ensanchar la campana durante periodos de inestabilidad estructural:
    $$\sigma_{\text{jump}} = \sigma_{\text{long-run}} \cdot \max\left(2.0, \min\left(10.0, \sqrt{\kappa_t + 3.0}\right)\right)$$

###1.3 Calibración Dinámica de la Tasa de Salto ($\lambda$)
La probabilidad de ocurrencia de un salto en cada barra ($\lambda$) se estima dinámicamente en una ventana rodante de tamaño $W$ (`InpRecalibWindow` = 500 barras):
$$\lambda_t = \max\left(0.01, \min\left(0.30, \frac{1}{W} \sum_{k=0}^{W-1} \mathbb{I}\left(r_{t-k} > k \cdot \sigma_{\text{long-run}}\right)\right)\right)$$
Donde $\mathbb{I}(\cdot)$ es la función indicadora y $k$ (`InpJumpSigmaK` = 3.0) es el umbral de sigma para clasificar un retorno como un "salto".

###1.4 Actualización Bayesiana (Probabilidad Posteriori)
La probabilidad final actualizada del estado alcista $p_t$ tras observar $r_t$ se obtiene mediante el teorema de Bayes:
$$p_t = \frac{p_{tt-1} \cdot \mathcal{L}(r_t  S_t = 1)}{p_{tt-1} \cdot \mathcal{L}(r_t  S_t = 1) + (1 - p_{tt-1}) \cdot \mathcal{L}(r_t  S_t = 0)}$$

---

##2. Proceso de Retorno a la Media de Ornstein-Uhlenbeck (Deriva)

En lugar de utilizar medias móviles simples que introducen retraso temporal, la deriva condicional de cada régimen ($\mu_s$) se extrae ajustando un proceso de difusión de tipo **Ornstein-Uhlenbeck (OU)** de tiempo continuo sobre la ventana de retornos:
$$dr_t = \theta (\mu - r_t)dt + \sigma dW_t$$

En su forma discreta AR(1), esto se traduce en la regresión lineal:
$$r_{t} = \phi r_{t-1} + c + \epsilon_t$$

###2.1 Estimación de Parámetros por Mínimos Cuadrados
A partir de una muestra rodante de tamaño $N$ (`InpOUWindow` = 60), se calculan los coeficientes mediante:
$$\phi = \frac{N \sum r_t r_{t-1} - \sum r_t \sum r_{t-1}}{N \sum r_{t-1}^2 - (\sum r_{t-1})^2}$$
$$c = \frac{\sum r_t - \phi \sum r_{t-1}}{N}$$

Para garantizar que el proceso sea estrictamente ergódico y de retorno a la media, el coeficiente autorregresivo se restringe a:
$$\phi_{\text{clamped}} = \max(-0.9999, \min(0.9999, \phi))$$

La deriva asintótica de equilibrio (media del proceso) se deriva como:
$$\mu_{\text{OU}} = \frac{c}{1 - \phi_{\text{clamped}}}$$

###2.2 Limitador Asintótico de Seguridad
Para evitar singularidades matemáticas o explosiones numéricas si $\phi_{\text{clamped}} \to 1$, se aplica un clipping dinámico basado en la volatilidad de largo plazo ($\sigma_{\text{long-run}}$):
$$\mu_{\text{OU, final}} = \max\left(-2\sigma_{\text{long-run}}, \min\left(2\sigma_{\text{long-run}}, \mu_{\text{OU}}\right)\right)$$

Los parámetros finales del HMM toman los valores:
$$\mu_{\text{Bull}} = \max(\mu_{\text{OU, final}}, \epsilon), \quad \mu_{\text{Bear}} = \max(-\mu_{\text{OU, final}}, \epsilon)$$

---

##3. Filtro de Kalman Secuencial (Filtro de Tendencia)

El filtro de Kalman actúa como un clasificador de tendencia de baja latencia sobre el precio de cierre desplazado ($Close_{t-1}$). Modela el estado verdadero del precio como un sistema dinámico lineal univariado.

###3.1 Ecuaciones de Predicción (Time Update)
Dado el estado estimado previo $\hat{x}_{t-1t-1}$ y su covarianza de error $P_{t-1t-1}$:
$$\hat{x}_{tt-1} = \hat{x}_{t-1t-1}$$
$$P_{tt-1} = P_{t-1t-1} + Q$$
Donde $Q$ (`InpKalmanQ` = 0.0001) representa la varianza del ruido del proceso (reactividad).

###3.2 Ecuaciones de Actualización (Measurement Update)
Al observar la nueva medición de precio $z_t = Close_{t-1}$:
$$\text{Ganancia de Kalman: } K_t = \frac{P_{tt-1}}{P_{tt-1} + R}$$
$$\text{Actualización de Estado: } \hat{x}_{tt} = \hat{x}_{tt-1} + K_t \cdot (z_t - \hat{x}_{tt-1})$$
$$\text{Actualización de Covarianza: } P_{tt} = (1 - K_t) \cdot P_{tt-1}$$
Donde $R$ (`InpKalmanR` = 0.01) es la varianza del ruido de medición (suavizado).

###3.3 Puerta de Regimen (Kalman Gate)
La pendiente instantánea del estado de Kalman se calcula como:
$$\Delta\hat{x}_t = \hat{x}_{tt} - \hat{x}_{t-1t-1}$$
Para filtrar fluctuaciones menores (ruido), se evalúa frente a un umbral adaptativo proporcional al ATR del activo:
$$\text{Régimen Kalman} = \begin{cases} 
1 & \text{si } \Delta\hat{x}_t > \text{ATR}_{t-1} \cdot \text{SlopeT} \\
-1 & \text{si } \Delta\hat{x}_t < -\text{ATR}_{t-1} \cdot \text{SlopeT} \\
0 & \text{en otro caso}
\end{cases}$$
Donde $\text{SlopeT}$ (`ExtSlopeT` = 0.0273) es el factor de umbralización.

---

##4. Modelo de Volatilidad Asimétrica GJR-GARCH(1,1)

Para capturar de forma precisa el agrupamiento de volatilidad (volatility clustering) y el efecto de apalancamiento financiero (leverage effect, donde los choques negativos generan mayor volatilidad que los positivos), el sistema implementa un modelo **GJR-GARCH(1,1)** estático puro:

$$\sigma_{gjr, t}^2 = \omega + \alpha \epsilon_{t-1}^2 + \gamma \cdot \mathbb{I}(\epsilon_{t-1} < 0) \cdot \epsilon_{t-1}^2 + \beta \sigma_{gjr, t-1}^2$$

Donde:
*   $\epsilon_{t-1} = r_{t-1} - \mu_{\text{ret}, t-1}$ son las innovaciones (retornos centrados).
*   $\mathbb{I}(\epsilon_{t-1} < 0)$ es la función indicadora que vale $1.0$ si el retorno previo fue negativo y $0.0$ si fue positivo.
*   $\omega$ (`InpGarchOmega`): Varianza de largo plazo de reserva.
*   $\alpha$ (`InpGarchAlpha`): Coeficiente del término ARCH.
*   $\gamma$ (`InpGarchGamma`): Parámetro de asimetría (leverage).
*   $\beta$ (`InpGarchBeta`): Coeficiente del término GARCH de persistencia.

###4.1 Restricción de Estacionariedad
Para evitar que el proceso de volatilidad diverja de forma infinita, la persistencia total debe ser estrictamente menor que la unidad:
$$\text{Persistencia} = \alpha + \beta + \frac{\gamma}{2.0} < 1.0$$
Si en algún cálculo la persistencia de los parámetros es $\ge 1.0$, el motor aplica un factor de escala dinámico para forzar la estacionariedad:
$$\text{Escala} = \frac{0.99}{\text{Persistencia}}, \quad \alpha \leftarrow \alpha \cdot \text{Escala}, \quad \beta \leftarrow \beta \cdot \text{Escala}, \quad \gamma \leftarrow \gamma \cdot \text{Escala}$$
A continuación, se define el intercepto como $\omega = \sigma^2_{\text{target}} \cdot (1.0 - 0.99)$, asegurando que la varianza tienda de vuelta a su objetivo incondicional.

---

##5. Machine Learning Online y Normalización Logística de Señales

Con el fin de evitar el efecto de **Concept Drift** (cambios en la distribución de las variables debido a cambios estructurales del mercado), las características de entrada del meta-clasificador no se evalúan de forma absoluta, sino que se normalizan en tiempo real a Z-Scores dinámicos.

###5.1 Normalización Z-Score Dinámica
Para cada característica $x_{i, t}$ en una ventana de tamaño $M$ (`InpDriftWindow` = 2000):
$$Z(x_{i, t}) = \frac{x_{i, t} - \mu_{x_i, M}}{\sigma_{x_i, M}}$$
Las 4 características procesadas son:
1.  **Confianza HMM**: $x_{1,t} = 2 \cdot p_t - 0.5$
2.  **Ratio de Volatilidad**: $x_{2,t} = \frac{\sigma_{gjr, t}}{\sigma_{\text{long-run}, t}}$
3.  **Magnitud de Pendiente HMA**: $x_{3,t} = \left\frac{dHMA_t}{dt}\right$
4.  **Aceleración HMA**: $x_{4,t} = x_{3,t} - x_{3,t-1}$

###5.2 Combinación Lineal y Función de Activación Logística Clamped
La fuerza de señal de salida (`Master Strength`) se obtiene proyectando estas puntuaciones normalizadas mediante un vector de pesos calibrado en la optimización y pasándolo por una función logística:

$$z_t = W_{\text{Conf}} \cdot Z(x_{1,t}) + W_{\text{Vol}} \cdot Z(x_{2,t}) + W_{\text{Slope}} \cdot Z(x_{3,t}) + W_{\text{Accel}} \cdot Z(x_{4,t}) + W_{\text{Inter}}$$

Para prevenir desbordamiento matemático (overflow) o valores NaN ante comportamientos extremos, la variable intermedia se restringe (clamping) a un rango estable antes de calcular la función logística:
$$z_{\text{clamped}, t} = \max\left(-20.0, \min\left(20.0, z_t\right)\right)$$
$$\text{Master Strength}_t = \frac{1.0}{1.0 + \exp(-z_{\text{clamped}, t})}$$

---

##6. Proyección de Volatilidad de Mezcla (Mixture Volatility)

Para calcular la colocación óptima de Stop Loss dinámicos de forma consistente con el modelo probabilístico del HMM, se realiza una proyección de volatilidad consolidada usando la **Ley de la Varianza Total**:

$$\sigma^2_{\text{proyectada}, t} = E[\text{Var}(r_t  S_t)] + \text{Var}(E[r_t  S_t])$$

Sustituyendo los componentes del modelo mixto con saltos de Merton:

1.  **Varianza Condicional Esperada** ($E[\text{Var}(r_t  S_t)]$):
    $$E[\text{Var}(r_t  S_t)] = (1 - \lambda) \cdot \left(\sigma_t^2 \cdot \frac{\nu}{\nu - 2}\right) + \lambda \cdot \sigma_{\text{jump}}^2 + \lambda(1 - \lambda)\mu_{S, t}^2$$
    Donde $\mu_{S, t} = \mu_{\text{Bull}}$ si $p_t > 0.5$, o $-\mu_{\text{Bear}}$ en caso contrario.

2.  **Varianza de las Medias Condicionales** ($\text{Var}(E[r_t  S_t])$):
    $$\text{Var}(E[r_t  S_t]) = p_t(1 - p_t) \cdot (1 - \lambda)^2 \cdot (\mu_{\text{Bull}} + \mu_{\text{Bear}})^2$$

El desvío estándar proyectado consolidado final $\sigma_{\text{proyectada}, t}$ (`sig_proj`) es la raíz cuadrada de la suma de estos dos términos:
$$\sigma_{\text{proyectada}, t} = \sqrt{\max\left(10^{-12}, E[\text{Var}(r_t  S_t)] + \text{Var}(E[r_t  S_t])\right)}$$

Esta métrica pondera dinámicamente tanto la incertidumbre de volatilidad interna de cada estado como la incertidumbre transicional (la probabilidad de que el mercado esté cambiando de régimen).

---

##7. Gestión de Riesgos y Dimensionamiento de Lotes

El sistema utiliza la volatilidad de mezcla calculada para definir los niveles de SL y TP:

###7.1 Distancia de Stop Loss Dinámica
La distancia del Stop Loss en términos de precio ($SL_{\text{dist}}$) se escala según la volatilidad de mezcla consolidada proyectada:
$$SL_{\text{dist}} = Price_t \cdot \sigma_{\text{proyectada}, t} \cdot \text{VolMultiplier}$$
Para evitar Stops anormalmente pequeños durante contracciones de liquidez extremas, se garantiza un límite mínimo estructural basado en el spread:
$$SL_{\text{dist, final}} = \max\left(SL_{\text{dist}}, 3.0 \cdot \text{Spread}_t\right)$$

###7.2 Cálculo del Lote Basado en Riesgo Fijo
El tamaño de la posición (lotes) se calcula de tal forma que la pérdida potencial máxima iguale exactamente el porcentaje de riesgo establecido sobre el balance de la cuenta ($Risk_{\%}$):
$$\text{Lote} = \frac{\text{Balance} \cdot \left(\frac{Risk_{\%}}{100}\right)}{SL_{\text{pts}} \cdot \left( \frac{\text{TickValue}}{\text{TickSize}} \cdot Point \right)}$$
Donde $SL_{\text{pts}} = \frac{SL_{\text{dist, final}}}{Point}$.
