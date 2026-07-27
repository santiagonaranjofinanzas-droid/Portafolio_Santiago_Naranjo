#Entorno Aislado: Universo de Activos (Capa 0 a Capa 6)

Este directorio constituye un entorno de pruebas cuantitativo **completamente aislado** diseñado para replicar de extremo a extremo (Capas 0 a 6) el pipeline de análisis del sistema **Sovereign HMM (versión 30001)** para cualquier activo financiero. 

A diferencia del pipeline original que está ajustado únicamente para el Oro (XAUUSD), los scripts en esta carpeta se han generalizado para ser agnósticos de activos, aceptando especificaciones de point size, tick size, tick value y spread de forma dinámica.

---

## Estructura de Directorios del Entorno

*   [run_pipeline.py](file:///c:/Users/YOUR_USERNAME/Desktop/Trading/1_#####HMM#####/Universo%20de%20activos/run_pipeline.py): Orquestador CLI principal que coordina todas las fases de manera secuencial.
*   **`Capa_0_Datos/`**: Procesa y remuestrea datos a nivel de ticks o velas a formato M15 Parquet.
*   **`Capa_1_Core/`**: Expone las primitivas matemáticas (GJR-GARCH, Filtro de Kalman, etc.) importándolas del núcleo principal.
*   **`Capa_2_Signal/`**: Genera buffers secuenciales de señales usando parámetros HMM del activo.
*   **`Capa_3_Calibration/`**: Calibración estocástica (MLE + Momentos) de la matriz de transición HMM específica del activo.
*   **`Capa_4_Execution/`**: Simula el backtest y genera reportes financieros robustos de desempeño.
*   **`Capa_5_Validation/`**: Divide los datos aplicando purga (leakage) y embargo para validación cruzada.
*   **`Capa_6_WalkForward/`**: Analiza la estabilidad de los parámetros (Alpha Decay) mediante Walk-Forward nested.
*   **`datos/`**: Almacena los archivos consolidados `.parquet` de entrenamiento específicos por activo.
*   **`resultados/`**: Almacena reportes de backtest (.md), parámetros calibrados (.csv) y métricas de walk-forward.

---

## Guía de Ejecución Rápida

El orquestador maestro CLI [run_pipeline.py](file:///c:/Users/YOUR_USERNAME/Desktop/Trading/1_#####HMM#####/Universo%20de%20activos/run_pipeline.py) permite correr todo el ciclo de vida del activo con una sola línea de comandos.

###Ejemplo 1: Replicación de paridad (XAUUSD) como validación
Podemos correr XAUUSD para asegurar que el pipeline aislado genera los mismos resultados de paridad:
```bash
python "Universo de activos/run_pipeline.py" --asset XAUUSD --data XAUUSD_M15_Training.parquet --point 0.01 --tick-size 0.01 --tick-value 1.0 --run-all
```

###Ejemplo 2: Probar la Plata (XAGUSD)
Supongamos que tienes un archivo CSV exportado de MT5 con los datos de M15 de plata en la raíz del proyecto llamado `XAGUSD_M15.csv`:
```bash
python "Universo de activos/run_pipeline.py" --asset SILVER --data XAGUSD_M15.csv --point 0.01 --tick-size 0.01 --tick-value 1.0 --run-all
```

###Ejemplo 3: Probar el Nas100 (NAS100)
Para un índice tecnológico como el Nasdaq 100, asumiendo datos en `NAS100_M15.csv` con spread simulado de 1.0 puntos de índice:
```bash
python "Universo de activos/run_pipeline.py" --asset NAS100 --data NAS100_M15.csv --point 0.01 --tick-size 0.01 --tick-value 0.01 --spread 100 --run-all
```

---

## Ejecución por Capas Específicas

Si no deseas ejecutar el flujo completo, puedes especificar qué capas ejecutar mediante el argumento `--steps`:

*   **Paso 0**: Conversión y saneamiento de datos.
*   **Paso 3**: Calibración estocástica HMM (se corre antes de señales).
*   **Paso 2**: Inferencia secuencial de señales.
*   **Paso 4**: Simulación de backtest comercial.
*   **Paso 5**: Separación IS/OOS purgada y embargada.
*   **Paso 6**: Grid-Search Walk-Forward.

**Ejemplo de ejecución parcial (Solo Calibración y Backtest):**
```bash
python "Universo de activos/run_pipeline.py" --asset NAS100 --data datos/NAS100_M15_Training.parquet --steps 3,4
```

---

## Contratos de Salida en `resultados/`

Para cada activo procesado exitosamente se generarán los siguientes archivos:
1.  **`HMM_Params_15M_{ACTIVO}.csv`**: Parámetros de transición HMM y saltos listos para cargar en el Asesor Experto (EA) de MT5.
2.  **`{ACTIVO}_signals.csv`**: Historial completo de señales generadas por vela para auditoría.
3.  **`REPORTE_ROBUSTEZ_{ACTIVO}.md`**: Reporte en formato Markdown que detalla el desempeño comercial simulado (Sharpe, Profit Factor, Drawdown, etc.).
4.  **`{ACTIVO}_capa5_purged_embargo_folds.csv`**: Resultados de la validación cruzada.
5.  **`{ACTIVO}_nested_walk_forward/`**: Directorio con rankings de optimización y mapas de estabilidad para prevenir el sobreajuste.
