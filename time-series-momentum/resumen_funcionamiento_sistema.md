#Resumen Operativo y de Funcionamiento del Sistema: DMN-CFD

Este documento proporciona una guÃ­a conceptual de alto nivel sobre la arquitectura, la lÃ³gica financiera y el flujo operativo del **Sistema de Trading Cuantitativo Neuronal DMN-CFD**. Este sistema ha sido diseÃ±ado especÃ­ficamente para operar estrategias de **Time Series Momentum (TSMOM)** en mercados OTC de CFDs de alta liquidez.

---

##1. VisiÃ³n General del Concepto

Las estrategias tradicionales de momentum de series temporales (TSMOM) sufren de dos debilidades crÃ­ticas en mercados reales:
1.  **Desfase Temporal (Phase Lag):** Los filtros de tendencia deterministas (como medias mÃ³viles o MACD clÃ¡sicos) tardan demasiado en responder a los puntos de giro del mercado, destruyendo el capital al final de las tendencias o durante mercados laterales.
2.  **Fricciones Devastadoras (Transaction & Carry Costs):** En el mercado de CFDs, los spreads y, sobre todo, las tasas de financiamiento diario (*overnight swaps*) pueden erosionar por completo la rentabilidad de las posiciones largas o cortas de mediano plazo si no se integran de forma nativa en el proceso de toma de decisiones.

El sistema **DMN-CFD** resuelve estas limitaciones fusionando un **modelo estocÃ¡stico de espacio de estados con cambio de rÃ©gimen de Markov (M-SSSM)** y una **red neuronal de momentum profundo (DMN)** en un Ãºnico pipeline de datos a ejecuciÃ³n, optimizado bajo el criterio de crecimiento Ã³ptimo de **Kelly coordinado con volatilidad objetivo**.

---

##2. Los Tres Pilares de la Estrategia

La arquitectura del sistema descansa sobre tres pilares fundamentales que operan secuencialmente:

```
+------------------------------------+
  PILAR 1: DetecciÃ³n de RÃ©gimen       --> Filtro de Kim JerÃ¡rquico de 2 Niveles
  (Â¿CÃ³mo estÃ¡ el mercado global?)         3 Factores Sectoriales con Q diagonal.
+------------------------------------+
                    [Probabilidad de Crisis: Î¾_3,t]
                  v
+------------------------------------+
  PILAR 2: GeneraciÃ³n de SeÃ±ales      --> Deep Momentum Network (DMN)
  (Â¿QuÃ© activos tienen momentum?)        V-VSN silencia carry cost adverso.
+------------------------------------+
                    [DirecciÃ³n de Trading: X_i,t]
                  v
+------------------------------------+
  PILAR 3: Dimensionamiento y Riesgo  --> Multiplicador CATSMOM Regularizado + Target Scaler
  (Â¿CuÃ¡nto capital asignamos?)           Control de correlaciÃ³n y lÃ­mites de margen.
+------------------------------------+
```

###Pilar 1: DetecciÃ³n Adaptativa de RÃ©gimen (Filtro de Kim M-SSSM JerÃ¡rquico)
Para capturar las dinÃ¡micas independientes entre clases de activos y unificar la lectura macro del tensor (ERR-07), el sistema implementa un modelo jerÃ¡rquico de dos niveles estructurado en **3 Factores Latentes Sectoriales** gobernados por un Ãºnico proceso de Markov global de cambio de rÃ©gimen $S_t^{\text{global}} \in \{1, 2, 3\}$:
1.  **Factor de Riesgo SistÃ©mico (Equities + G10 FX):** Ãndices BursÃ¡tiles (SPX500, NAS100, DJI30, GER30, EU50, UK100, JPN225) y Divisas procÃ­clicas de G10 FX (EUR/USD, GBP/USD, AUD/USD).
2.  **Factor de EnergÃ­a y Materias Primas CÃ­clicas:** PetrÃ³leo Brent, PetrÃ³leo WTI, Gas Natural y Cobre. Las materias primas agrÃ­colas (MaÃ­z, Trigo, Soja) y de carry de nicho (CafÃ©, AzÃºcar) se asignan a este factor con cargas libres y alta varianza.
3.  **Factor de Refugio y DeflaciÃ³n:** Oro, Plata, Renta Fija (US10Y, BUND), USD/CHF y USD/JPY.

Dado que la matriz de proceso $Q^{(S_t^{\text{global}})}$ es diagonal y los factores sectoriales son condicionalmente independientes, el Filtro de Kim multivariado se estima de forma matemÃ¡ticamente exacta como **3 instancias paralelas del filtro de Kim univariado estÃ¡ndar** que comparten la misma cadena de Markov del estado global $S_t^{\text{global}}$, aplicando restricciones de escala ($Q_j^{(1)} = 1$ para cada factor $j$) y de signo ($\lambda_{\text{SPX500}} > 0$). La probabilidad filtrada global de crisis sistÃ©mica ($\xi_{3, t}$) se inyecta directamente en el tensor de entrada de la red neuronal.

###Pilar 2: GeneraciÃ³n de SeÃ±ales Inteligente (Deep Momentum Network)
El motor de predicciÃ³n es una red neuronal recursiva y de atenciÃ³n causal (DMN) que procesa una ventana de lookback LSTM de **$L = 63$ dÃ­as** para preservar una muestra de entrenamiento neta viable y evitar la subdeterminaciÃ³n (ERR-11). Su diseÃ±o incorpora:
*   **Overnight Gap Normalizado Rezagado ($Z_{i, t-1}^{(\text{gap})}$):** Reemplaza la seÃ±al clÃ¡sica de 1 dÃ­a para capturar con precisiÃ³n la reacciÃ³n de apertura del mercado sin sufrir look-ahead bias ni la inestabilidad matemÃ¡tica de estimar Yang-Zhang en ventanas de 5 dÃ­as.
*   **Vectorized Variable Selection Network (V-VSN):** Capa de compuertas lÃ³gicas (GLU) que silencia inputs individuales si el costo de carry estimado (swap) supera el alpha esperado del CFD.
*   **MACD Normalizado sobre Log-Precios:** Calcula diferencias de EMAs sobre logaritmos de precios divididos por la volatilidad de log-retornos, adaptando la ventana de normalizaciÃ³n de forma proporcional al tamaÃ±o de la EMA lenta para garantizar estabilidad de escala.
*   **Positional Encoding Sinusoidal:** Agregado antes de la autoatenciÃ³n causal para permitir que la red reconozca la procedencia temporal de las secuencias del LSTM.
*   **Causal Masked Self-Attention:** Evita el sesgo de futuro (*look-ahead bias*) mediante una mÃ¡scara aditiva causal con elementos $A_{t, \tau} = -\infty$ si $\tau > t$.
*   **Loss de Sharpe Bailey-Prado Corregido y EVaR con Annealing CÃ­clico:** Para unificar los objetivos y evitar gradientes ruidosos, se optimiza el dual de EVaR sobre el **Ratio de Sharpe Diferenciable Corregido de Bailey-LÃ³pez de Prado (2012)** exacto (con el denominador ajustado teÃ³ricamente para asimetrÃ­a y exceso de curtosis cuadrÃ¡tico), neto de costos de rotaciÃ³n. El factor de aversiÃ³n al riesgo $\alpha_{\text{epoch}}$ se regula mediante un **Cyclic Cosine Annealing** con reinicios y warmup de learning rate para evitar el colapso de gradientes y la caÃ­da en mÃ­nimos locales.

###Pilar 3: Control de Fricciones y GestiÃ³n de Riesgos
Una vez que la DMN calcula la direcciÃ³n ideal de cada activo ($X_{i, t} \in [-1, 1]$), el sistema calcula el tamaÃ±o final de la posiciÃ³n aplicando dos filtros matemÃ¡ticos:
1.  **Multiplicador de CorrelaciÃ³n CATSMOM Regularizado:** El multiplicador incorpora un regularizador numÃ©rico $\epsilon = 0.1$ para evitar singularidades matemÃ¡ticas, y se trunca dinÃ¡micamente en el rango $[0.5, \, 2.0]$ para evitar el sobreapalancamiento en entornos de seÃ±ales mixtas.
2.  **Sizing por Volatilidad Objetivo Coordinada:** Las posiciones se dimensionan de forma inversamente proporcional a su volatilidad diaria ex-ante (Yang-Zhang adaptativa) y se escalan de forma agregada para cumplir estrictamente con un objetivo de volatilidad de cartera $\tau_{\text{efectivo}} = \phi \cdot \tau$ (e.g., 3.75% de target operativo para un target macro $\tau = 15\%$ y $\phi = 0.25$). Se aplica ademÃ¡s un floor empÃ­rico $\delta_{\min, t}$ estimado causalmente con una ventana rodante de 252 dÃ­as para evitar divisiones por cero en periodos de transiciÃ³n de rÃ©gimen.

---

##3. Flujo Diario de EjecuciÃ³n (Pipeline Temporal)

El sistema opera con una sola ejecuciÃ³n diaria en el cierre de la sesiÃ³n de Nueva York:

```
[4:55 PM EST] Ingesta de Datos (OHLC, Swaps actuales y Spreads del broker)
      
      v
[4:56 PM EST] Feature Engineering:
              - CÃ¡lculo de volatilidad adaptativa Yang-Zhang (N_s para cada s)
              - MACD logarÃ­tmico normalizado cross-asset y Overnight Gap Rezagado (t-1)
              - NormalizaciÃ³n de Swaps diarios usando volatilidad diaria
      
      v
[4:57 PM EST] Inferencia M-SSSM (Filtro de Kim Sectorial JerÃ¡rquico) --> Probabilidad sistÃ©mica de crisis (Î¾_3,t)
      
      v
[4:58 PM EST] Inferencia DMN --> Genera direcciÃ³n cruda de portafolio X_i,t
      
      v
[4:59 PM EST] Control de Riesgos & Kelly:
              - Multiplicador de correlaciÃ³n CATSMOM regularizado y truncado (CF_t)
              - Sizing por Vol Target coordinado con floor causal (f_final)
              - VerificaciÃ³n de la Barrera de Margen Requerido (Margin < 35%)
      
      v
[4:59:30 PM EST] Ruteo de Ã³rdenes lÃ­mite directamente al broker vÃ­a Socket API (MT5 / FIX)
```

---

##4. PrÃ¡cticas de ValidaciÃ³n de Modelos (CPCV)

Para asegurar la validez del sistema fuera de muestra y evitar la fuga de informaciÃ³n temporal (data leakage) causada por la autocorrelaciÃ³n de variables de momentum de largo plazo, el entrenamiento utiliza **Combinatorial Purged Cross-Validation (CPCV)** con un periodo de purga temporal de **147 dÃ­as** y **10 bloques de validaciÃ³n**, limitando el horizonte mÃ¡ximo de retornos a 126 dÃ­as.
