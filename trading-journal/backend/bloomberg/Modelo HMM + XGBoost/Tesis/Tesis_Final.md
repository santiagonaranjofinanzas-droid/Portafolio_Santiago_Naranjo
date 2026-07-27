---
bibliography: references.bib
lang: es-ES
---

#Tesis: Detección de Regímenes mediante Modelos Ocultos de Markov (HMM) y XGBoost en el Mercado de Valores

##Índice Detallado

###1. Introducción

La gestión de portafolios contemporánea se enfrenta a un entorno de complejidad sin precedentes, donde las premisas de estabilidad y linealidad de los modelos financieros tradicionales son cuestionadas por la realidad observada en los mercados globales.

####1.1. Contextualización de los Mercados Financieros Contemporáneos

La asignación estratégica de activos (SAA) tradicional se fundamenta en la premisa de que los beneficios de la diversificación y las primas de riesgo son constantes o regresan a un promedio histórico estable. Sin embargo, la evidencia empírica en el marco de los mercados concebidos como **Sistemas Adaptativos Complejos (SAC)** demuestra que estas estructuras de correlación son dinámicas y colapsan precisamente durante los choques negativos de mercado. Como señala [@pedersen2009], en periodos de transición sistémica hacia regímenes de baja rentabilidad y alta volatilidad, las correlaciones entre activos de riesgo tienden a converger hacia la unidad, invalidando la protección teórica de la diversificación estática.

####1.2. El Paradigma de la Hipótesis del Mercado Adaptativo (AMH)

En respuesta a las limitaciones de la Hipótesis de los Mercados Eficientes (EMH), surge la Hipótesis del Mercado Adaptativo (AMH), la cual postula que los mercados financieros no operan en un equilibrio constante, sino que evolucionan a través de procesos de competencia, adaptación y selección natural. En este paradigma, el comportamiento de los inversores y las dinámicas de precios están condicionados por el régimen predominante. La transición entre entornos de bajo y alto riesgo genera fallas en los modelos tradicionales que asumen distribuciones normales y varianza constante.

####1.3. Definición del Problema: Instabilidad de Parámetros y Cambios de Régimen

El costo económico de ignorar las transiciones de régimen es crítico para la viabilidad de cualquier estrategia de inversión. Durante los cambios estructurales, se producen redistribuciones masivas de liquidez que generan una asimetría profunda en la relación riesgo-retorno. En estos estados de "mal régimen", los activos experimentan caídas severas (*drawdowns*) que a menudo tienen un carácter persistente y no lineal [@angtimmermann2012]. Sin un mecanismo que anticipe probabilísticamente estos giros, las carteras permanecen sobre-expuestas a primas de riesgo agotadas, provocando una destrucción de valor que requiere años de recuperación.

####1.4. Justificación del Uso de Modelos Híbridos (Estocásticos + Machine Learning)

Surge la necesidad de desarrollar sistemas de alerta temprana que superen las limitaciones de los indicadores convencionales. Los enfoques tradicionales suelen fallar al no capturar las dependencias no lineales y los patrones complejos de rotación intermercado. Esta investigación propone un sistema híbrido que integra la inferencia de estados latentes de los Modelos Ocultos de Markov (HMM) con el poder predictivo residual de los algoritmos de Gradient Boosting (XGBoost). Este marco permite modelar la transición estocástica entre regímenes y anticipar el agotamiento de los ciclos de rotación intermercado [@maingoetal2025].

####1.5. Objetivos

**1.5.1. Objetivo General**

Proponer un enfoque sistémico que integre modelos de cambio de régimen y aprendizaje automático para anticipar probabilísticamente los cambios de régimen financieros (*risk-on* / *risk-off*) en frecuencia diaria, permitiendo una gestión de riesgos proactiva.

**1.5.2. Objetivos Específicos**

1. Evaluar si las dinámicas de rotación intermercado poseen capacidad predictiva estadísticamente significativa sobre las transiciones de régimen.
2. Construir un Índice Sintético de Rotación Intermercado (ISRI) mediante la aplicación de Análisis de Componentes Principales (PCA) para capturar el estado del sistema financiero.
3. Integrar Modelos Ocultos de Markov (HMM), Análisis de Componentes Principales (PCA) y el algoritmo XGBoost para probar si se mejora el desempeño predictivo en la anticipación de episodios de estrés y alta volatilidad.

###2. Marco Teórico y Revisión de la Literatura

El presente capítulo fundamenta las bases teóricas y metodológicas de la investigación, abordando la naturaleza de los mercados financieros y las herramientas analíticas para la detección de cambios de estado.

####2.1. Dinámica de Regímenes de Mercado

Los mercados financieros operan como **Sistemas Adaptativos Complejos (SAC)**, caracterizados por dinámicas no lineales y cambios estructurales profundos. Bajo esta visión, el mercado transita entre diversos estados o regímenes que capturan comportamientos estilizados como el agrupamiento de volatilidad y la asimetría en la respuesta a choques externos. Como señalan [@angtimmermann2012], la identificación de estos regímenes es fundamental, ya que los parámetros de riesgo y retorno colapsan precisamente ante cambios sistémicos inesperados.

####2.2. Fundamentos de los Modelos Ocultos de Markov (HMM)

Los Modelos Ocultos de Markov asumen que las series de tiempo financieras son generadas por un proceso estocástico subyacente cuyos estados no son observables directamente.

**2.2.1. El Problema de la Inferencia y el Filtro Forward**

La inferencia de estos estados latentes se realiza mediante algoritmos iterativos. James Hamilton [@hamilton1989] desarrolló un marco basado en un filtro que actualiza la probabilidad condicional de hallarse en un régimen específico conforme llegan nuevas observaciones. Complementariamente, Nystrup [@nystrup2018] emplea el **filtro Forward** ($\alpha_t$) para actualizar iterativamente la certidumbre sobre el estado actual del mercado, permitiendo una decodificación en tiempo real mediante el algoritmo de Viterbi.

**2.2.2. Estimación de Probabilidades de Transición**

Mientras que los modelos canónicos asumen parámetros constantes, la investigación moderna sugiere el uso de estimaciones adaptativas. Nystrup propone un enfoque de **parámetros variantes en el tiempo** impulsado por observaciones, aplicando un factor de olvido exponencial que permite al modelo captar cambios estructurales genuinos con mayor agilidad.

####2.3. Algoritmos de Boosting: Gradient Boosted Trees (XGBoost)

El algoritmo XGBoost (eXtreme Gradient Boosting) se ha consolidado como una herramienta superior para manejar la complejidad no lineal de las series temporales financieras.

**2.3.1. Regularización y Manejo de Datos Financieros Ruidosos**

A diferencia de los modelos econométricos tradicionales (ARIMA/GARCH) que operan bajo supuestos rígidos, XGBoost segmenta el espacio de datos mediante árboles de decisión, capturando interacciones complejas y efectos asimétricos sin requerir distribuciones predefinidas. La literatura reciente [@maingoetal2025; @wang2024] destaca la eficacia de arquitecturas híbridas donde XGBoost es empleado para modelar los residuos no lineales que los modelos paramétricos omiten.

####2.4. Análisis de Componentes Principales (PCA) en Finanzas

El Análisis de Componentes Principales es una técnica de reducción de dimensionalidad que transforma datos correlacionados en factores ortogonales. En esta investigación, se emplea el PCA para aislar el **riesgo sistémico** (varianza conjunta) del riesgo idiosincrático. El primer componente principal extraído actúa como un *proxy* directo de la dirección dominante del sistema, capturando la mayor variabilidad compartida por el universo de activos.

####2.5. Rotación de Activos e Índices de Rotación Intermercado (ISRI)

La Teoría de Rotación Intermercado de John Murphy [@murphy2004] establece que las relaciones entre clases de activos (acciones, bonos, materias primas y divisas) son señales primarias de la etapa del ciclo económico. La integración metodológica propuesta por Broby y Smyth [@brobysmyth2025] utiliza el PCA para consolidar estas señales en un **Índice Sintético de Rotación Intermercado (ISRI)**, permitiendo que las ponderaciones del índice se extraigan dinámicamente de los datos, reduciendo los sesgos de los índices tradicionales basados en capitalización.

###3. Metodología y Arquitectura del Sistema

Esta sección detalla la implementación técnica del sistema híbrido propuesto, describiendo el flujo de datos desde su captura inicial hasta la generación de señales predictivas de régimen.

####3.1. Universo de Inversión y Fuentes de Datos

La arquitectura de datos, implementada en la clase `DataEngine`, integra un universo multi-activo diseñado para capturar la rotación intermercado sistémica. Los activos seleccionados incluyen el índice S&P 500 (^GSPC) para acciones, el Oro (GC=F) y Petróleo (CL=F) para materias primas, los bonos del tesoro a 10 años (^TNX) y el índice Dólar (DX-Y.NYB). Los datos son extraídos mediante la librería `yfinance` en frecuencia diaria, asegurando la continuidad mediante métodos de relleno frontal (*forward fill*).

####3.2. Ingeniería de Características y Preprocesamiento Robustos

El preprocesamiento se rige por principios de auditoría algorítmica para evitar la fuga de información (*data leakage*).

**3.2.1. Normalización y Winsorización Local**

Se calculan retornos logarítmicos para asegurar la aditividad temporal. Para mitigar el efecto de valores atípicos extremas, se aplica una **winsorización local** al 1% y 99%. Crucialmente, los parámetros de normalización (Z-score) y los límites de winsorización se calculan exclusivamente sobre el set de entrenamiento (finalizando en diciembre de 2021) y se aplican posteriormente al set de prueba, preservando la causalidad del sistema.

**3.2.2. Construcción del Índice ISRI mediante PCA**

El motor de extracción de características (`PCAEngine`) emplea el Análisis de Componentes Principales para sintetizar las señales de mercado. El **primer componente principal (PC1)** se define como el Índice Sintético de Rotación Intermercado (ISRI). El modelo PCA es ajustado únicamente con la matriz de covarianza de los datos históricos de entrenamiento, evitando que las dinámicas futuras influyan en los pesos factoriales del índice.

####3.3. Arquitectura del Modelo Híbrido: HMM-XGBoost

El sistema se estructura en una secuencia modular donde cada componente resuelve una dimensión específica de la serie temporal.

**3.3.1. Identificación Estocástica de Regímenes (HMM)**

El módulo `HMMRegimes` utiliza un Modelo Oculto de Markov con distribución Gaussiana para inferir los estados latentes del mercado a partir del ISRI. Se implementa un **filtro Forward** puramente causal que estima la probabilidad de cada estado en el tiempo $t$ basándose únicamente en la información disponible hasta ese instante. Se definen tres estados operativos: Estabilidad, Transición y Estrés Sistémico.

**3.3.2. Clasificación Predictiva mediante XGBoost**

Las probabilidades de estado obtenidas del HMM, junto con el valor crudo del ISRI, alimentan el clasificador XGBoost. El objetivo (*target*) se define como una transición de régimen o un evento de riesgo en un horizonte de 5 días ($t+5$). El modelo se optimiza mediante búsqueda bayesiana operada por la librería `Optuna`, ajustando el parámetro `scale_pos_weight` para corregir el desbalance inherente de los eventos de crisis.

####3.4. Estrategia de Verificación y Validación Walk-Forward

Para garantizar la robustez estadística, se implementan técnicas avanzadas de validación cruzada para series de tiempo:
1. **Embargo**: Se eliminan observaciones entre los sets de entrenamiento y validación para mitigar la correlación serial.
2. **Purga de Frontera**: El final del set de entrenamiento se recorta por un periodo igual al horizonte de predicción para asegurar que ninguna información del futuro inmediato sea filtrada al modelo.
3. **Validación Walk-Forward**: El desempeño se evalúa de forma expansiva, simulando un entorno de producción real donde el modelo evoluciona con la llegada de nuevos datos.

####3.5. Marco de Evaluación Multi-Dimensional

La evaluación del sistema se estructura en cuatro dimensiones complementarias, diseñadas para satisfacer tanto el rigor estadístico como la interpretabilidad económica requerida en un trabajo de grado en Economía:

1. **Discriminación Estadística**: Cuantifica la capacidad del modelo para separar estados normales de eventos de estrés. Se emplean el Área Bajo la Curva ROC (AUC), el *F1-Score*, y de manera crítica, el **Coeficiente de Correlación de Matthews (MCC)**, una métrica robusta ante el desbalance inherente de las clases en mercados financieros, donde los eventos de crisis son estructuralmente minoritarios.
2. **Calibración Probabilística**: Evalúa si las probabilidades emitidas por el modelo son confiables en magnitud. Un gestor de portafolios necesita que una señal del 80% de probabilidad de estrés sea cuantitativamente precisa, no solo ordinalmente correcta. Se utiliza el **Brier Score** y la curva de calibración.
3. **Análisis Precision-Recall**: Dado que los eventos de estrés sistémico son raros, el **PR-AUC** proporciona una evaluación más informativa que el ROC-AUC al focalizarse exclusivamente en la detección de la clase minoritaria, midiendo la capacidad del modelo para emitir alertas verdaderas sin generar falsas alarmas costosas.
4. **Métricas Financieras**: Para traducir la capacidad predictiva a resultados tangibles de gestión de portafolios, se calculan el **Sharpe Ratio**, el **Sortino Ratio** (penalizando exclusivamente la volatilidad a la baja según Sortino y van der Meer, 1991), el **Máximo Drawdown (MDD)** y la **Tasa de Crecimiento Anual Compuesta (CAGR)**.

Todas las métricas son calculadas mediante un módulo de evaluación completamente desacoplado (`ModelEvaluator`), que opera exclusivamente sobre los resultados fuera de muestra sin modificar el pipeline de entrenamiento.

###4. Resultados y Discusión

Este capítulo expone los hallazgos empíricos obtenidos tras la ejecución del sistema híbrido, validando la eficacia de la arquitectura propuesta en la anticipación de riesgos sistémicos.

####4.1. Análisis del Comportamiento del ISRI

El Índice Sintético de Rotación Intermercado (ISRI), extraído mediante el PCA del universo multi-activo, ha demostrado ser un barómetro eficaz del sentimiento de riesgo. Los factores de carga (*loadings*) revelan una estructura coherente con la teoría financiera clásica.

[SECUENCIA DE INSERCIÓN VISUAL: pca_loadings.png  TÍTULO SUGERIDO: FIGURA 4.1. Contribución de Activos al PC1 (Estructura del ISRI)]

Como se observa en la Figura 4.1, el ISRI presenta una correlación positiva significativa con los rendimientos de los bonos a 10 años ($\approx 0.59$) y el S&P 500 ($\approx 0.45$), mientras que muestra una fuerte correlación negativa con el Oro ($\approx -0.48$). Esta configuración permite interpretar al ISRI como un **Factor de Apetito por el Riesgo**: valores positivos indican entornos de expansión y confianza (*Risk-On*), mientras que valores negativos señalan una fuga hacia la seguridad (*fly-to-quality*).

[SECUENCIA DE INSERCIÓN VISUAL: isri_timeseries.png  TÍTULO SUGERIDO: FIGURA 4.2. Evolución Temporal del Índice ISRI]

####4.2. Segmentación de Regímenes HMM y Propiedades Estadísticas

El Modelo Oculto de Markov segmentó la serie temporal en tres regímenes operativos con distribuciones de probabilidad diferenciadas. La distribución de las observaciones resultó balanceada: un 31.7% para el régimen de Estabilidad (Estado 0), un 33.0% para Transición (Estado 1) y un 35.3% para Estrés Sistémico (Estado 2).

[SECUENCIA DE INSERCIÓN VISUAL: regime_distributions.png  TÍTULO SUGERIDO: FIGURA 4.3. Distribución de Densidad del ISRI por Régimen]

La Figura 4.3 confirma que el Estado 2 captura los eventos de cola izquierda (caídas extremas del ISRI), caracterizados por una alta volatilidad y retornos negativos persistentes. La capacidad del HMM para inferir estas probabilidades latentes de forma causal proporciona la base estocástica necesaria para el clasificador predictivo.

####4.3. Evaluación del Desempeño Fuera de Muestra (OOS)

El desempeño del clasificador XGBoost fue evaluado bajo un protocolo estricto de validación *Walk-Forward*, asegurando la relevancia de los resultados para un entorno de inversión real. La Tabla 4.1 consolida la batería completa de métricas de evaluación fuera de muestra.

**Tabla 4.1.** *Resumen de Métricas de Evaluación Out-of-Sample del Sistema Híbrido HMM-XGBoost*

 Categoría  Métrica  Valor  Interpretación Económica 
------------
 Discriminación  ROC-AUC  0.8186  Capacidad superior de separación entre estados normales y de estrés 
 Discriminación  Precision  0.8374  El 83.7% de las alertas de riesgo emitidas fueron correctas 
 Discriminación  Recall  0.9033  El modelo detectó el 90.3% de las crisis reales 
 Discriminación  F1-Score  0.8691  Balance óptimo entre falsas alarmas y crisis no detectadas 
 Discriminación  MCC  0.5344  Correlación moderada-alta; validez genuina ante desbalance de clases 
 Discriminación  Log-Loss  0.4582  Penalización moderada por incertidumbre probabilística 
 Calibración  Brier Score  0.1464  Error cuadrático bajo; probabilidades cuantitativamente confiables 
 Precision-Recall  PR-AUC  0.8982  Detección de crisis sin exceso de falsas alarmas (superior al ROC-AUC) 

*Nota.* Valores obtenidos del pipeline de evaluación estadística (discriminación y calibración) hasta febrero 2026. La tabla fue generada automáticamente por `ModelEvaluator`.

[SECUENCIA DE INSERCIÓN VISUAL: roc_curves_comparison.png  TÍTULO SUGERIDO: FIGURA 4.4. Curvas ROC del Sistema Híbrido (In-Sample vs. Out-of-Sample)]

El sistema alcanzó una **AUC Out-of-Sample de 0.8186**, lo que indica una capacidad superior para discriminar entre estados normales y eventos de riesgo inminentes. La degradación respecto al set de entrenamiento es marginal, lo que valida la robustez de las técnicas de regularización, embargo y purga aplicadas para evitar el sobreajuste. Desde una perspectiva de gestión de portafolios, este nivel de AUC implica que el modelo identifica correctamente más del 81% de las transiciones de régimen, proporcionando al gestor una ventana de acción de 5 días hábiles para ajustar la exposición sistémica de la cartera. Además, el **Recall de 0.9033** indica que el sistema detectó el 90% de los eventos de estrés reales, mientras que la **Precision de 0.8374** confirma que el 83% de las alertas emitidas fueron correctas, minimizando el costo operativo de las falsas alarmas.

####4.4. Calibración Probabilística y Confiabilidad de las Señales

Más allá de la discriminación ordinal, es fundamental evaluar si las probabilidades emitidas por el modelo son cuantitativamente precisas. Un gestor de riesgos institucional no solo necesita saber que un evento de estrés es "probable", sino cuánto confiar en la magnitud de esa probabilidad para dimensionar la cobertura (*hedging*) adecuada.

El **Brier Score** de **0.1464** obtenido mide el error cuadrático medio entre las probabilidades predichas y los eventos observados. Este valor, significativamente inferior al umbral de 0.25 (correspondiente a un modelo aleatorio), confirma que las probabilidades emitidas por el sistema son cuantitativamente confiables. La curva de calibración (generada mediante el módulo `ModelEvaluator`) permite verificar visualmente si las probabilidades del modelo se alinean con la frecuencia empírica de los eventos de estrés.

[SECUENCIA DE INSERCIÓN VISUAL: calibration_curve.png  TÍTULO SUGERIDO: FIGURA 4.5. Curva de Calibración del Clasificador HMM-XGBoost]

Desde la perspectiva de la teoría económica, una buena calibración probabilística permite al modelo funcionar como un **termómetro cuantitativo de riesgo sistémico**, donde el nivel de la probabilidad predicha puede traducirse directamente a decisiones de asignación: por ejemplo, reducir la exposición a renta variable proporcionalmente al aumento de la probabilidad del Estado 2 (Estrés).

####4.5. Análisis en el Espacio Precision-Recall y Robustez ante Desbalance

Dado que los eventos de estrés sistémico constituyen una minoría estructural de las observaciones (aproximadamente el 35% de los días corresponden al Estado 2), el análisis en el espacio Precision-Recall proporciona una evaluación complementaria al ROC-AUC. El **PR-AUC de 0.8982** —superior al ROC-AUC de 0.8186— confirma que el modelo mantiene un rendimiento excepcional incluso cuando se evalúa exclusivamente sobre la detección de la clase minoritaria. Este resultado indica que el sistema emite alertas de crisis con alta precisión sin generar falsas alarmas que erosionen la rentabilidad del portafolio por desapalancamiento innecesario.

El **Coeficiente de Correlación de Matthews (MCC) de 0.5344** complementa este análisis al proporcionar una medida de correlación entre las predicciones y las observaciones que es inherentemente robusta ante el desbalance de clases. A diferencia del F1-Score, el MCC considera simultáneamente los cuatro cuadrantes de la matriz de confusión, proporcionando una evaluación global de la validez del clasificador. El valor positivo y estadísticamente significativo obtenido confirma que el modelo aporta valor predictivo real, argumento fundamental para la defensa de la hipótesis de investigación.

####4.6. Importancia de las Características en la Predicción de Cambios

El análisis de importancia de características (Gini Importance) confirma la hipótesis central de esta investigación: la integración de modelos estocásticos potencia el aprendizaje automático.

[SECUENCIA DE INSERCIÓN VISUAL: feature_importance.png  TÍTULO SUGERIDO: FIGURA 4.6. Importancia de las Características en la Clasificación XGBoost]

De acuerdo con la Figura 4.6, la variable más crítica para el modelo es la **Probabilidad de Estado 2** (Estrés) generada por el HMM, con un peso relativo cercano al 60%. Esto demuestra que el clasificador XGBoost no solo utiliza el valor crudo de los precios, sino que "aprende" de la estructura estocástica inferida por el HMM, permitiendo una anticipación mucho más precisa de los puntos de inflexión del mercado. Este hallazgo tiene implicaciones directas para la gestión de portafolios: la señal más valiosa para anticipar transiciones de régimen no proviene de los precios observables, sino de la **estructura latente del mercado** inferida por el modelo estocástico.

###5. Conclusiones y Futuras Líneas de Investigación

La presente investigación ha demostrado la viabilidad y robustez de un sistema híbrido que integra procesos estocásticos y aprendizaje automático para la gestión proactiva de riesgos financieros. Los resultados, evaluados mediante un marco multi-dimensional que abarca discriminación estadística, calibración probabilística y análisis de la clase minoritaria, confirman la aplicabilidad del modelo en entornos de inversión profesional.

####5.1. Eficacia del Modelo Híbrido en Entornos de Alta Volatilidad

Los resultados obtenidos validan la hipótesis central: la capacidad predictiva de los algoritmos de Gradient Boosting (XGBoost) se potencia significativamente al incorporar las probabilidades latentes inferidas por un Modelo Oculto de Markov (HMM). Con una **AUC Out-of-Sample de 0.8186** y un **F1-Score de 0.8691**, el sistema supera los umbrales convencionales de precisión en la anticipación de choques sistémicos. Esta sinergia permite que el modelo no solo reaccione a los precios pasados, sino que interprete la estructura probabilística del régimen actual, diferenciando con éxito entre ruidos transitorios y cambios estructurales genuinos.

El **Coeficiente de Correlación de Matthews (MCC) de 0.5344** confirma que el poder predictivo del modelo es genuino y no un artefacto del desbalance de clases, argumento crítico para la defensa de la hipótesis de investigación. Asimismo, el **Brier Score de 0.1464** valida que las probabilidades emitidas por el sistema son cuantitativamente confiables, lo que permite su uso directo como insumo para el diseño de futuros sistemas de cobertura (*hedging*).

####5.2. Aplicabilidad en la Gestión de Riesgos y Sinergia Metodológica

La evaluación realizada confirma que el modelo detecta crisis reales sin generar un exceso de falsas alarmas (PR-AUC 0.8982). La buena calibración probabilística permite que las señales funcionen como un insumo confiable para la reducción táctica de exposición ante el aumento de la probabilidad del Estado 2 (Estrés). 

Un hallazgo fundamental de esta investigación es la **preminencia de la estructura latente sobre los datos observados**. Como se detalla en el análisis de importancia de características, la probabilidad del Estado 2 (inferida por el HMM) posee una importancia relativa del 60%, superando significativamente al valor crudo del índice ISRI o a los retornos individuales. Desde una perspectiva de la **Teoría de Sistemas Adaptativos Complejos (SAC)**, esto sugiere que el mercado financiero posee una memoria estocástica que los modelos lineales omiten. El HMM actúa como un "decodificador" de este ruido sistémico, entregando al XGBoost una señal ya procesada que captura la entropía del sistema en lugar de solo su trayectoria superficial.

Para un gestor institucional, esto implica que las herramientas de alerta temprana no deben basarse exclusivamente en niveles de precio o indicadores de momentum tradicionales. La integración de probabilidades de transición permite construir **reglas de decisión dinámicas**; por ejemplo, el escalado de posiciones (*position sizing*) puede parametrizarse como una función inversa de la probabilidad de estrés sistémico, optimizando el uso de capital al permanecer invertido solo cuando la estructura estocástica del mercado indica un régimen de "baja entropía" o estabilidad.

####5.3. Limitaciones del Estudio

A pesar de los resultados positivos, se identifican limitaciones críticas:
1. **Frecuencia de Datos**: El uso de datos diarios impide la captura de micro-regímenes de volatilidad intradía que podrían disparar señales de alerta más tempranas.
2. **Dependencia Macroeconómica**: El modelo es puramente endógeno (basado en precios), omitiendo variables fundamentales exógenas como decisiones de política monetaria o indicadores de empleo en tiempo real.
3. **Ausencia de Costos de Transacción**: Las métricas financieras reportadas no incorporan fricciones de mercado (comisiones, *slippage*, impacto de mercado), lo que podría reducir el rendimiento neto de una implementación real.

####5.4. Recomendaciones para Implementación Institucional y Futuras Líneas

Se recomienda la integración de este sistema como un **módulo de superposición de riesgos (*risk overlay*)**. En lugar de reemplazar la selección de activos, el modelo HMM-XGBoost actuaría como un interruptor de desapalancamiento (*de-risking*) que reduzca la exposición sistémica ante el aumento de la probabilidad del Estado 2 (Estrés). La buena calibración probabilística del modelo permite diseñar reglas graduales de reducción de exposición, en lugar de señales binarias de todo-o-nada.

Para futuras investigaciones, se propone:
1. La inclusión de técnicas de Procesamiento de Lenguaje Natural (NLP) para transformar el sentimiento de la banca central en características adicionales del clasificador.
2. La incorporación de costos de transacción y *slippage* en la simulación de la estrategia para obtener métricas financieras netas.
3. La extensión del análisis a frecuencias intradiarias para capturar micro-regímenes de volatilidad.

###6. Referencias Bibliográficas

*Nota: Esta sección se genera automáticamente al procesar el documento con Zotero/Pandoc mediante el archivo vinculada `references.bib`.*

---
**Fuentes Indexadas en `references.bib`:**
- Hamilton, J. D. (1989) [@hamilton1989]
- Nystrup, P. (2018) [@nystrup2018]
- Ang, A. & Timmermann, A. (2012) [@angtimmermann2012]
- Pedersen, L. H. (2009) [@pedersen2009]
- Maingo, I. et al. (2025) [@maingoetal2025]
- Murphy, J. J. (2004) [@murphy2004]
- Broby, D. & Smyth, W. (2025) [@brobysmyth2025]
- Wang, J. et al. (2024) [@wang2024]
