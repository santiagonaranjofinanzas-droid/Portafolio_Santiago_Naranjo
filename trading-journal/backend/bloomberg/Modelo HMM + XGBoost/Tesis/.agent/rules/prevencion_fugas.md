#Prevención de Fugas de Información y Sesgos Analíticos

Todos los agentes que generen o auditen código de Machine Learning deben aplicar estrictamente validación cronológica (Walk-Forward) o validación cruzada depurada (Purged Cross-Validation) utilizando las técnicas de purging y embargoing. 

Está rotundamente prohibido introducir el sesgo de anticipación (look-ahead bias); procesos como la normalización Z-score o la reducción de dimensionalidad (PCA) deben aplicarse de manera recursiva o exclusivamente después de dividir los datos en conjuntos de entrenamiento y prueba para no contaminar la muestra.
