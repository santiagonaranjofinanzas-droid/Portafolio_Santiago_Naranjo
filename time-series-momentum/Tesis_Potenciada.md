#Tesis Potenciada: Detección de Recesiones y Regímenes de Crisis Mediante Ruptura de Correlaciones y Machine Learning Multivariado

Este documento presenta la formulación matemática, estadística y el diseño metodológico para un indicador avanzado de recesión y cambio de régimen de mercado. Este sistema está diseñado para integrarse de forma nativa en la **Capa 5 (Régimen de Mercado)** y la **Capa 6 (Machine Learning Clásico)** del sistema de trading neuronal **DMN-CFD**.

---

##1. Formulación de la Hipótesis

La hipótesis central postula que:
> *La transición de una economía desde una fase de expansión a una fase de recesión induce un cambio estructural no lineal en las interrelaciones (correlaciones) de los activos financieros globales. Este cambio no solo se manifiesta como un incremento en la volatilidad individual, sino como una **contracción del espacio de codependencia (ruptura de correlación y colapso dimensional)**. Un sistema de Machine Learning entrenado con características espectrales, de redes y de distancia probabilística extraídas de estas matrices de correlación puede detectar la inminencia y la presencia de recesiones macroeconómicas con mayor precisión y menor retardo que los indicadores económicos tradicionales rezagados.*

---

##2. Rigor Matemático y Feature Engineering

Definimos el vector de log-retornos diarios para los $N$ activos en el universo a un tiempo $t$ como:
$$\mathbf{r}_t = \begin{bmatrix} r_{1,t} \\ r_{2,t} \\ \vdots \\ r_{N,t} \end{bmatrix} \in \mathbb{R}^N, \quad \text{donde } r_{i,t} = \ln\left(\frac{P_{i,t}}{P_{i,t-1}}\right)$$

###2.1. Matriz de Correlación Dinámica Regularizada
Para estimar la covarianza móvil de forma robusta frente a ruidos de muestras cortas, definimos la matriz de covarianza muestral $\mathbf{\Sigma}_t$ sobre una ventana de lookback $w$:
$$\mathbf{\Sigma}_t = \frac{1}{w - 1} \sum_{\tau = t-w+1}^{t} (\mathbf{r}_\tau - \bar{\mathbf{r}}_t)(\mathbf{r}_\tau - \bar{\mathbf{r}}_t)^T$$

Donde $\bar{\mathbf{r}}_t$ es el retorno medio en dicha ventana. La matriz de correlación empírica correspondiente es:
$$\mathbf{C}_t = \mathbf{D}_t^{-1} \mathbf{\Sigma}_t \mathbf{D}_t^{-1}, \quad \mathbf{D}_t = \text{diag}(\sigma_{1,t}, \sigma_{2,t}, \dots, \sigma_{N,t})$$

Para evitar singularidades matemáticas y garantizar que la matriz sea estrictamente definida positiva ($\mathbf{C}_t \succ 0$), aplicamos regularización de tipo **Shrinkage de Ledoit-Wolf**:
$$\mathbf{C}_t^* = (1 - \alpha) \mathbf{C}_t + \alpha \mathbf{I}_N$$
Donde $\mathbf{I}_N$ es la matriz identidad de tamaño $N \times N$, y $\alpha \in (0, 1)$ se optimiza dinámicamente para minimizar el error cuadrático medio de la estimación.

---

###2.2. Características Espectrales (Teoría de Matrices Aleatorias - RMT)
De acuerdo con la Teoría de Matrices Aleatorias, si los retornos de los activos fuesen puramente ruido blanco mutuamente independientes, los autovalores de la matriz de correlación $\mathbf{C}_t^*$ seguirían la distribución de **Marchenko-Pastur**. Los límites teóricos de los autovalores para una matriz aleatoria pura son:
$$\lambda_{\pm} = \sigma^2 \left(1 \pm \sqrt{\frac{N}{w}}\right)^2$$

Donde $\sigma^2 = 1 - \frac{N}{w}$ es la varianza residual. Cualquier autovalor $\lambda_{i,t} > \lambda_+$ contiene información estructural verdadera (factores comunes no aleatorios). 

Extraemos tres características clave a partir de la descomposición en componentes principales (PCA) de $\mathbf{C}_t^*$:

1. **Autovalor Dominante ($\lambda_{1,t}$):**
   Mide la varianza explicada por el primer componente principal (el factor de mercado). Un incremento acelerado en $\lambda_{1,t}$ delata que el mercado se está moviendo de forma uniforme, síntoma de una contracción del espacio de codependencia durante un pánico:
   $$f_{1,t} = \lambda_{1,t}$$

2. **Ratio de Absorción Global (Global Absorption Ratio - GAR):**
   Mide la proporción de la varianza total explicada por los primeros $k$ componentes principales (donde típicamente $k \ll N$, por ejemplo, $k = 3$ sectores):
   $$\text{GAR}_t = \frac{\sum_{i=1}^k \lambda_{i,t}}{\sum_{j=1}^N \lambda_{j,t}}$$

3. **Entropía de la Distribución de Autovalores (Von Neumann Entropy):**
   Mide el grado de dispersión del sistema. Una baja entropía denota que unos pocos factores dominan todo el sistema (alto riesgo sistémico):
   $$H_{\text{spect}, t} = -\sum_{i=1}^N \tilde{\lambda}_{i,t} \ln(\tilde{\lambda}_{i,t}), \quad \text{donde } \tilde{\lambda}_{i,t} = \frac{\lambda_{i,t}}{\sum_{j=1}^N \lambda_{j,t}}$$

---

###2.3. Métrica de Distancia de Correlación (Divergencia de Información)
Definimos un periodo histórico extendido de expansión y estabilidad macroeconómica estableciendo una matriz de correlación de referencia $\mathbf{C}_{\text{stable}}$. La desviación de la correlación actual respecto a este estado estable se modela formalmente mediante:

1. **Distancia de Frobenius (Norma de Matriz de Diferencia):**
   $$d_F(\mathbf{C}_t^*, \mathbf{C}_{\text{stable}}) = \\mathbf{C}_t^* - \mathbf{C}_{\text{stable}}\_F = \sqrt{\text{Tr}\left( (\mathbf{C}_t^* - \mathbf{C}_{\text{stable}})^2 \right)}$$

2. **Divergencia Kullback-Leibler Multivariada (KLD):**
   Asumiendo que los retornos locales en régimen estable e inestable siguen distribuciones Gaussianas multivariadas $\mathcal{N}(\mathbf{0}, \mathbf{\Sigma}_{\text{stable}})$ y $\mathcal{N}(\mathbf{0}, \mathbf{\Sigma}_t)$, la KLD acumulada mide la discrepancia informativa:
   $$\text{KLD}_t = \frac{1}{2} \left[ \text{Tr}(\mathbf{\Sigma}_{\text{stable}}^{-1} \mathbf{\Sigma}_t) - N + \ln\left(\frac{\det \mathbf{\Sigma}_{\text{stable}}}{\det \mathbf{\Sigma}_t}\right) \right]$$

---

###2.4. Características Basadas en Redes Complejas (Teoría de Grafos)
Definimos una distancia métrica no lineal entre los activos $i$ y $j$ basada en su correlación lineal $\rho_{ij,t}$:
$$d_{ij,t} = \sqrt{2(1 - \rho_{ij,t})}$$

Esta distancia satisface los tres axiomas métricos (no negatividad, simetría y desigualdad triangular). Construimos el **Árbol de Expansión Mínima (Minimum Spanning Tree - MST)** $T_t = (V, E_t)$ con el conjunto de vértices $V$ (activos) y el conjunto de aristas $E_t$ de menor distancia acumulada sin ciclos utilizando el algoritmo de Kruskal.

1. **Longitud Promedio del Árbol (Mean Tree Length - MTL):**
   Representa el grado de cercanía sistémica global. En periodos de recesión/pánico, los activos correlacionan fuertemente, por lo que $d_{ij} \to 0$ y la longitud total disminuye de manera drástica:
   $$\text{MTL}_t = \frac{1}{N - 1} \sum_{(i,j) \in E_t} d_{ij,t}$$

2. **Centralidad de Grado del Nodo Dominante (Max Degree Centrality):**
   Identifica si la red se está estructurando en forma de "estrella" (un solo activo absorbe la codependencia de todos los demás):
   $$\text{Cent}_t = \max_{i \in V} \text{Degree}(i, T_t)$$

---

##3. Formulación del Modelo de Machine Learning

El problema se formula como una clasificación supervisada binaria o estimación secuencial de régimen:

###3.1. Target del Modelo
Sea $y_t \in \{0, 1\}$ el indicador de recesión real a tiempo $t$. 
* Dado que las fechas oficiales de recesión de la NBER sufren de un severo retardo de publicación (look-ahead bias retrospectivo), definimos un **Target Causal Adelantado** para trading:
  $$y_t = \mathbb{I}\left( \max_{\tau \in [t+1, t+H]} \text{DD}_{\text{market}, \tau} > \theta_{\text{crisis}} \right)$$
  Donde $\text{DD}_{\text{market}, \tau}$ es el drawdown acumulado del índice global de renta variable (`SPX500`) en un horizonte futuro $H = 63$ días (un trimestre de trading) y $\theta_{\text{crisis}}$ es un umbral crítico (ej. $10\%$).

###3.2. Arquitectura del Clasificador
El clasificador mapea el vector de características $\mathbf{x}_t = [\lambda_{1,t}, \text{GAR}_t, H_{\text{spect}, t}, d_F, \text{KLD}_t, \text{MTL}_t, \text{Cent}_t]^T \in \mathbb{R}^7$ a la probabilidad de transición de régimen:
$$\hat{p}_{t+H} = P(y_t = 1 \mid \mathbf{x}_t) = g(\mathbf{w}^T \mathbf{x}_t + b)$$

Proponemos dos aproximaciones competitivas:
1. **Modelo Paramétrico de Transición de Régimen (Markov-Switching HMM):**
   Donde la matriz de transición de estados ocultos $S_t \in \{1, 2, 3\}$ es gobernada por la probabilidad condicionada por las variables de correlación.
2. **Clasificador No Lineal Regularizado (XGBoost con monotonicidad y penalización L2):**
   Excelente para capturar no linealidades sin perder interpretabilidad matemática (aplicando restricciones de monotonicidad para que un aumento de la distancia o reducción del MST siempre incremente de forma no lineal la probabilidad de crisis).

---

##4. Buenas Prácticas de Machine Learning en Finanzas (Protocolo de Validación)

Para evitar los errores comunes que invalidan la mayoría de sistemas de ML en finanzas (como el sobreajuste y el sesgo de supervivencia), implementamos un protocolo estricto:

```
                  Segmentación de Datos en CPCV (Ejemplo)
[   Bloque 1   ] [   Bloque 2   ] [   Bloque 3   ] [   Bloque 4   ] ... [   Bloque K   ]
     Train           Purge           Test           Embargo            Train
```

###4.1. Combinatorial Purged & Embargoed Cross-Validation (CPCV)
Dado que las variables se calculan en una ventana móvil de $w = 63$ días y el target tiene un horizonte predictivo de $H = 63$ días, existe una fuerte dependencia temporal que invalida la validación cruzada aleatoria tradicional (K-Fold).

1. **Purging (Purga):** Eliminamos del conjunto de entrenamiento cualquier punto de datos cuyo vector de características contenga información que se solape con el periodo de evaluación (Test). La zona de purga antes y después de cada bloque de test debe ser de al menos $w + H$ días.
2. **Embargo (Embargo):** Dado que los retornos tienen efectos de memoria de largo plazo, aplicamos un embargo adicional de $E = 21$ días a los datos inmediatamente posteriores al conjunto de test antes de volver a utilizarlos en el entrenamiento.

###4.2. Corrección por Sesgo de Selección de Backtest (Bailey-Prado Theorem)
Cuando probamos múltiples combinaciones de hiperparámetros (ej. ventanas $w \in [21, 42, 63, 126]$), la probabilidad de encontrar un backtest exitoso por pura suerte aumenta exponencialmente. Evaluamos el rendimiento mediante el **Sharpe Ratio Deflactado (PSR)** y el **Sharpe Ratio Multitest (DSR)**, los cuales castigan el Sharpe del modelo en función del número de pruebas ejecutadas y la correlación entre ellas.

---

##5. Plan de Integración en el Pipeline de DMN-CFD

El sistema se integraría de forma secuencial y modular sin alterar el funcionamiento actual hasta su validación:

```
  [ Datos Crudos MT5 ]
           │
           ▼
[ Feature Engineering ] ──► Computar: Matriz de Correlación Ledoit-Wolf C_t*,
           │                        Autovalores, MTL de MST y Distancia Frobenius.
           ▼
 [ Inferencia Capa 5 ] ──► Estimar probabilidad de recesión/crisis sistémica (ξ_t)
           │               usando el clasificador entrenado sobre variables espectrales.
           ▼
 [ Inferencia Capa 6 ] ──► XGBoost decide pesos intermedios X_i,t incorporando ξ_t
           │               como feature de atenuación de riesgo.
           ▼
  [ Control de Kelly ] ──► Sizing final de portafolio y ejecución de órdenes.
```

---

###Mapeo de Activos Propuesto ($N=26$)
El modelo de correlación se entrenará de forma nativa utilizando los datos históricos de los 26 activos disponibles en tu Expert Advisor ([TSMOM_EA.mq5](file:///c:/Users/YOUR_USERNAME/Desktop/Trading/TSMOM/TSMOM_Bot_Demo/TSMOM_EA.mq5)):
* **Acciones / Índices:** `SPX500`, `NAS100`, `DJI30`, `GER30`, `EU50`, `UK100`, `JPN225`
* **Divisas G10:** `EURUSD`, `USDJPY`, `GBPUSD`, `AUDUSD`, `USDCHF`, `USDCAD`
* **Metales / Materias Primas Cíclicas:** `XAUUSD`, `XAGUSD`, `Cobre`, `Brent`, `WTI`, `GasNatural`
* **Soft Commodities:** `Cafe`, `Azucar`, `Trigo`, `Maiz`, `Soja`
* **Renta Fija / Tasas:** `US10Y`, `BUND`

Este universo balanceado provee las tres clases de activos óptimas para que el algoritmo espectral detecte la rotación de capital antes de una recesión.
