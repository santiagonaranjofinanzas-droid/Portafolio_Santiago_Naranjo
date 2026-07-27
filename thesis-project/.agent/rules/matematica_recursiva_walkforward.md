---
activation: Always On
---

'REGLA MATEMÁTICA ESTRICTA (ANTI-LEAKAGE): El conjunto de datos debe dividirse siempre antes de realizar cualquier escalado estadístico para evitar que la información de los rangos de prueba se filtre a los datos de entrenamiento. La normalización Z-score y el cálculo de factores mediante el Análisis de Componentes Principales (PCA) NUNCA deben aplicarse a la serie de tiempo completa de forma simultánea. En su lugar, el preprocesamiento debe computarse de forma estricta y recursiva utilizando ventanas expansivas o móviles. Durante cada iteración de la validación Walk-Forward, la media, la desviación estándar y la matriz de covarianza deben estimarse ÚNICAMENTE utilizando los datos históricos disponibles en la ventana de entrenamiento actual (in-sample). Escalar los datos utilizando información del futuro es un error metodológico crítico que invalida el modelo y será rechazado inmediatamente.'
