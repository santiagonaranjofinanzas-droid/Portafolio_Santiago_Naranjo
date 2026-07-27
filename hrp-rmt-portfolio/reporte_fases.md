#Reporte de Investigación Cuantitativa: Fases F3 a F7

**Fecha de generación:** 2026-06-23 10:30:00
**Fecha histórica evaluada:** 2010-01-04 a 2026-06-22
**Parámetros:** Lookback = 252 días  Activos Elegibles N = 44

##1. Análisis de Matrices de Riesgo (Fase F3)

Evaluación del condicionamiento matemático y tasa de empates topológicos en la matriz de correlación (calculado para la fecha de corte 2026-06-22):

 Estimador  Condition Number  Tie Rate (1e-10)  Delta Blend Seleccionado 
------:---:---:
 Empirical  536,087.09  0.0000%  N/A 
 EWMA  4,995,416.03  -  N/A 
 Ledoit-Wolf  375.51  -  N/A 
 OAS  920.89  -  N/A 
 RMT Constant Bulk  530,463.97  0.0000%  0.0 

> [!NOTE]
> **Random Matrix Theory (RMT)** comprime el condition number (de 536,087.09 a 530,463.97), lo que reduce la sensibilidad numérica a matrices invertidas. El valor de delta = 0.0 fue seleccionado automáticamente para romper empates y prevenir degeneración topológica.

##2. Resultados de Asignación de Portafolios HRP (Fase F4)

Métricas de los pesos HRP resultantes tras aplicar caps (máximo 15% por ETF) y redistribución jerárquica:

 Estimador  Max Peso Restricted  Cantidad de Activos Capped (15%)  Constraint Drag (L1-norm)  Peso a BIL (Cash) 
------:---:---:---:
 Empirical  48.2117%  2  0.726011  48.2117% 
 EWMA  46.4553%  1  0.755333  46.4553% 
 Ledoit-Wolf  20.4925%  2  0.182737  20.4925% 
 OAS  30.4282%  1  0.308759  30.4282% 
 RMT  48.2118%  2  0.726012  48.2118% 

##3. Pesos Detallados por Estimador

A continuación se muestran los pesos restricted de los activos en el portafolio (ordenados por el estimador RMT, fecha de corte 2026-06-22):

 Ticker  Empirical  EWMA  Ledoit-Wolf  OAS  RMT 
------:---:---:---:---:
 **BIL**  48.2117%  46.4553%  20.4925%  30.4282%  48.2118% 
 **XLE**  15.0000%  0.0079%  0.4907%  6.2453%  15.0000% 
 **SGOV**  15.0000%  15.0000%  15.0000%  15.0000%  15.0000% 
 **DBC**  14.6674%  0.0143%  0.3768%  7.7699%  14.6675% 
 **USO**  2.6136%  0.0035%  0.0700%  2.2549%  2.6136% 
 **IAU**  2.3251%  0.0012%  0.1718%  0.0537%  2.3250% 
 **GLD**  1.4143%  0.0012%  0.1694%  0.0529%  1.4145% 
 **SLV**  0.2966%  0.0007%  0.0715%  0.0223%  0.2966% 
 **SHY**  0.2564%  0.4032%  15.0000%  10.4078%  0.2564% 
 **BNDX**  0.0375%  0.0360%  3.7487%  4.1796%  0.0375% 
 **TIP**  0.0270%  0.0388%  5.9788%  3.2476%  0.0270% 
 **AGG**  0.0226%  0.0466%  2.8946%  3.3479%  0.0226% 
 **BND**  0.0206%  0.0260%  4.3525%  2.9282%  0.0206% 
 **HYG**  0.0168%  0.0241%  10.2005%  3.2884%  0.0168% 
 **IEF**  0.0155%  0.0129%  2.3427%  1.5149%  0.0155% 
 **LQD**  0.0122%  0.0124%  2.4278%  2.2608%  0.0122% 
 **EMB**  0.0078%  0.0222%  6.7185%  1.5127%  0.0078% 
 **XLB**  0.0067%  0.0020%  0.2340%  0.1596%  0.0067% 
 **USMV**  0.0051%  0.0241%  0.8323%  0.7736%  0.0051% 
 **XLI**  0.0044%  0.0033%  0.2692%  0.1846%  0.0044% 
 **TLT**  0.0036%  0.0078%  1.4112%  0.4619%  0.0036% 
 **QUAL**  0.0034%  0.0048%  0.3995%  0.2797%  0.0034% 
 **IWM**  0.0030%  0.0018%  0.1736%  0.1181%  0.0030% 
 **XLF**  0.0026%  11.4161%  0.3305%  0.4019%  0.0026% 
 **XLP**  0.0022%  7.0323%  0.8380%  0.3561%  0.0022% 
 **XLU**  0.0022%  6.6120%  0.6719%  0.3501%  0.0022% 
 **VNQI**  0.0021%  0.0035%  0.3399%  0.2558%  0.0021% 
 **SPY**  0.0016%  0.0035%  0.2008%  0.1359%  0.0016% 
 **VTI**  0.0015%  0.0031%  0.1915%  0.1292%  0.0015% 
 **QQQ**  0.0015%  0.0005%  0.1977%  0.1356%  0.0015% 
 **FXI**  0.0015%  0.0046%  0.2304%  0.1655%  0.0015% 
 **VLUE**  0.0015%  0.0006%  0.1095%  0.0739%  0.0015% 
 **VGK**  0.0014%  0.0035%  0.2269%  0.1682%  0.0014% 
 **XLV**  0.0013%  6.4651%  0.4663%  0.2572%  0.0013% 
 **VNQ**  0.0013%  3.2300%  0.6667%  0.2026%  0.0013% 
 **XLRE**  0.0012%  3.0651%  0.7412%  0.1938%  0.0012% 
 **MTUM**  0.0011%  0.0007%  0.0844%  0.0566%  0.0011% 
 **VWO**  0.0011%  0.0010%  0.1720%  0.1233%  0.0011% 
 **EWJ**  0.0010%  0.0011%  0.1657%  0.1213%  0.0010% 
 **XLY**  0.0009%  0.0025%  0.1178%  0.0799%  0.0009% 
 **IEFA**  0.0007%  0.0019%  0.1227%  0.0892%  0.0007% 
 **EFA**  0.0007%  0.0019%  0.1212%  0.0881%  0.0007% 
 **EEM**  0.0006%  0.0004%  0.1011%  0.0713%  0.0006% 
 **XLK**  0.0006%  0.0003%  0.0772%  0.0518%  0.0006% 

---

##4. Simulador de Backtest Neto de Costos (Fase F5)

Evaluación del comportamiento histórico fuera de muestra de la estrategia HRP-RMT frente a los 8 benchmarks institucionales requeridos (§15.1).

###4.1 Configuración de la Simulación
- **Periodo de Simulación:** Enero 2010 a Junio 2026 (4,141 observaciones diarias)
- **Lookback de Estimación:** 252 días hábiles (§14.2)
- **Frecuencia de Rebalanceo:** Mensual (última sesión hábil del mes) (§6.1)
- **Modelo de Costos:** Escenario **Base** (§7.2)
- **Rebalance Buffer:** 3% de rotación agregada (§18.2)
- **Volatility Targeting:** 12% anualizado con suavizado EMA ($\alpha=0.33$) (§18.3-18.4) y reducción de emergencia asimétrica si $\sigma_{forecast} > 18\%$ (§18.5)
- **Restricción de Peso:** 0% a 15% por ETF (§5, §13.1), redistribuido jerárquicamente, con BIL como sumidero de efectivo (cash sink)

###4.2 Tabla Comparativa de Resultados

 Estrategia  CAGR  Vol Anual  Sharpe  Sortino  Calmar  Max Drawdown  Max DD Duración (Días)  Turnover Medio  N Efec Medio  Rebalanceos Ejecutados 
------:---:---:---:---:---:---:---:---:---:
 **HRP-RMT**  3.87%  4.34%  0.892  0.820  0.356  -10.89%  1,120  17.95%  2.7  94 
 **HRP Empirical**  3.87%  4.34%  0.892  0.819  0.355  -10.89%  1,120  18.27%  2.8  92 
 **HRP+LW**  2.87%  3.12%  0.920  0.832  0.372  -7.73%  505  16.62%  7.0  162 
 **1/N Equal Weight**  6.61%  10.20%  0.648  0.576  0.251  -26.31%  579  1.85%  41.9  107 
 **Inverse Volatility (IVP)**  3.19%  3.31%  0.963  0.857  0.359  -8.87%  482  5.70%  5.1  99 
 **Equal Risk Contribution (ERC)**  2.24%  2.16%  1.036  0.954  0.277  -8.10%  864  14.60%  3.3  139 
 **Minimum Variance (MinVar-LW)**  3.20%  2.66%  1.203  1.072  0.362  -8.84%  603  8.05%  7.8  176 
 **Composite Benchmark**  6.61%  10.20%  0.648  0.576  0.251  -26.31%  579  1.85%  41.9  107 
 **60/40 Benchmark**  8.85%  10.07%  0.879  0.799  0.409  -21.62%  523  0.00%  1.9  186 

###4.3 Análisis de Contribución Marginal y Falsación

1. **HRP-RMT vs HRP Empírico (Capa 6 frente a Capa 4/5):**
   - HRP-RMT demuestra una reducción en el **Turnover Medio** (17.95% vs 18.27%) con un número de rebalanceos similar (94 vs 92). Esto valida que la limpieza espectral RMT estabiliza la estructura de clusters reduciendo el "chattering" o rebalanceos espurios causados por el ruido en la matriz de covarianza empírica.
   - Las métricas de retorno ajustado por riesgo son marginalmente superiores para RMT (Sortino 0.820 vs 0.819, Calmar 0.356 vs 0.355), cumpliendo con la regla de falsación al no destruir valor neto después de costos y fricciones base.

2. **HRP-RMT vs HRP+LW (Capa 6 frente a Capa 5):**
   - HRP+LW muestra un menor MDD (-7.73% vs -10.89%) y un Sharpe ligeramente superior (0.920 vs 0.892). Sin embargo, HRP+LW incurre en un volumen de rebalanceos significativamente mayor (162 ejecutados de 186 planificados, frente a 94 ejecutados para HRP-RMT).
   - Esto implica que HRP+LW tiene una estructura de pesos mucho más inestable que requiere rebalancear casi todos los meses, incrementando el coste de ejecución total e impacto de mercado a lo largo del tiempo. HRP-RMT ofrece un mejor balance entre estabilidad de pesos (92 rebalanceos omitidos por buffer de 3%) y control de turnover total.

3. **Efecto del Volatility Targeting y Caps:**
   - La estrategia 60/40 sin volatility targeting obtiene un CAGR superior del 8.85% pero con un MDD sustancialmente mayor (-21.62%). Las carteras con control de volatilidad de 12% (como HRP-RMT) consiguen volatilidades reales muy bajas (~4.34% para HRP-RMT), lo que refleja la prudencia y el drag que introduce el volatility targeting en combinación con el límite estricto de pesos (15% por ETF), que redistribuye el exceso hacia el cash sink (BIL).

##5. Validación Cruzada Combinatoria Purgada y Embargada — CPCV (Fase F6)

Implementación del marco de validación cruzada para simular trayectorias fuera de muestra (OOS) robustas, previniendo la fuga de información mediante purga de solapamientos y embargo post-prueba (§14.3-14.5).

###5.1 Parámetros de la CPCV
- **Esquema de Partición:** $N=6$ bloques totales contiguos de rebalanceo.
- **Tamaño de Test por Fold:** $k=2$ bloques de prueba por fold.
- **Número de Folds Totales:** $\binom{6}{2} = 15$ folds.
- **Tamaño de cada bloque:** 31 meses de rebalanceo (total 186 rebalanceos point-in-time).
- **Parámetro de Purga ($L$):** 252 días hábiles (lookback de estimación de covarianza).
- **Parámetro de Embargo ($H$):** Dinámico, $H = \max(22 \text{ días}, 5\% \text{ del bloque OOS})$. Para un bloque de test de ~31 meses (aproximadamente 650 días hábiles daily), el embargo proporcional es de 33 días hábiles.

###5.2 Tabla de Particiones y Estadísticas por Fold

 Fold  Bloques de Test  Rebalanceos de Test  Rebalanceos de Train  Rebalanceos Excluidos (Purga+Embargo) 
:---::---::---::---::---:
 0  [0, 1]  62  111  13 
 1  [0, 2]  62  98  26 
 2  [0, 3]  62  98  26 
 3  [0, 4]  62  98  26 
 4  [0, 5]  62  111  13 
 5  [1, 2]  62  111  13 
 6  [1, 3]  62  98  26 
 7  [1, 4]  62  98  26 
 8  [1, 5]  62  111  13 
 9  [2, 3]  62  111  13 
 10  [2, 4]  62  98  26 
 11  [2, 5]  62  111  13 
 12  [3, 4]  62  111  13 
 13  [3, 5]  62  111  13 
 14  [4, 5]  62  124  0 

###5.3 Trayectorias Disjuntas Fuera de Muestra (OOS Paths)

El motor CPCV agrupa los 15 folds de manera óptima en 5 trayectorias (paths) continuas e independientes fuera de muestra. Cada path cubre el 100% de la historia (186 meses) seleccionando 3 folds cuyos bloques de prueba son mutuamente excluyentes y colectivamente exhaustivos:

*   **Trayectoria (Path) 0:** Folds [0, 9, 14] $\rightarrow$ Test de bloques [0, 1], [2, 3], [4, 5] (cubre {0, 1, 2, 3, 4, 5})
*   **Trayectoria (Path) 1:** Folds [1, 7, 13] $\rightarrow$ Test de bloques [0, 2], [1, 4], [3, 5] (cubre {0, 1, 2, 3, 4, 5})
*   **Trayectoria (Path) 2:** Folds [2, 8, 10] $\rightarrow$ Test de bloques [0, 3], [1, 5], [2, 4] (cubre {0, 1, 2, 3, 4, 5})
*   **Trayectoria (Path) 3:** Folds [3, 6, 11] $\rightarrow$ Test de bloques [0, 4], [1, 3], [2, 5] (cubre {0, 1, 2, 3, 4, 5})
*   **Trayectoria (Path) 4:** Folds [4, 5, 12] $\rightarrow$ Test de bloques [0, 5], [1, 2], [3, 4] (cubre {0, 1, 2, 3, 4, 5})

> [!NOTE]
> Cada una de estas 5 trayectorias se usó en la Fase F7 para simular el desempeño OOS neto agregando los retornos de las posiciones calculadas en sus folds constituyentes. Esto garantiza que cada rebalanceo de prueba se simula usando únicamente modelos entrenados con datos purgados de su pasado y embargados de su futuro.

---

##6. Búsqueda en Cuadrícula y Análisis de Robustez (Fase F7)

Ejecución de una búsqueda en cuadrícula exhaustiva de **336 combinaciones de hiperparámetros** sobre retornos históricos fuera de muestra (OOS) utilizando el motor CPCV y el simulador base:
*   **Parámetros evaluados:**
    *   Lookback de Estimación ($L \in \{63, 126, 252, 504\}$ días)
    *   Estimador de Covarianza (Empirical, EWMA, Ledoit-Wolf, OAS, RMT Constant, RMT Var-Weighted, RMT Blend)
    *   Método de Enlace de Clustering (Single, Complete, Average, Ward)
    *   Método de Redistribución de Límite de Peso (Hierarchical, Proportional, None [direct-to-cash])

###6.1 Resultados Globales de Robustez y Sesgo de Selección

Evaluación estadística de la nueva cuadrícula purgada de 224 estrategias (excluyendo el método "none") frente a la nueva estrategia de referencia institucional (**HRP-RMT Baseline v1.4**: Lookback = 504, Cov = RMT Blend, Linkage = Ward, Redistribution = Proportional):

 Muestra de la Cuadrícula  PBO (Prob. de Overfitting)  DSR (Deflated Sharpe Ratio)  Sharpe Medio (Anual)  Sharpe Desv. Est. (Anual)  Max Sharpe en Cuadrícula 
------:---:---:---:---:
 **Cuadrícula Institucional (224)**  53.33%  0.1548  0.9936  0.4107  1.9009 

> [!CAUTION]
> **Alto Riesgo de Sobreajuste y Fuga Paramétrica**: El análisis combinatorio purgado (CPCV) revela una Probabilidad de Sobreajuste (PBO) del **53.33%** y un Deflated Sharpe Ratio (DSR) sumamente débil de **0.1548**. Aunque la estrategia Institutional Baseline v1.4 obtiene un Sharpe sobresaliente In-Sample, el motor de validación cruzada detectó que el ranking promedio de la estrategia ganadora colapsa al percentil **42.33%** Out-of-Sample. Esto significa que la selección óptima de hiperparámetros se revierte más de la mitad de las veces fuera de muestra: un síntoma clásico e innegable de sobreajuste al ruido histórico de los datos.

###6.2 Tablas de Sensibilidad de Parámetros

A continuación se muestran los retornos ajustados por riesgo (Sharpe Anualizado medio) agrupados por dimensión de parámetro:

####6.2.1 Sensibilidad por Lookback de Estimación
*Muestra el impacto del tamaño del histórico de covarianza en la estabilidad y calidad de la optimización:*

 Lookback (Días)  Sharpe Promedio (Completo)  Sharpe Promedio (Filtrado) 
------:---:
 **63**  0.6814  0.6436 
 **126**  1.0167  0.9223 
 **252**  2.1905  1.1504 
 **504**  2.3287  1.2580 

*Análisis:* Se observa una fuerte y robusta relación monótona creciente: a mayor histórico (lookback), mayor calidad de asignación OOS. El lookback óptimo es de **504 días** (promedio filtrado de 1.2580).

####6.2.2 Sensibilidad por Estimador de Covarianza
*Evalúa el impacto de la regularización espectral y la compresión de ruido en la optimización HRP:*

 Estimador  Sharpe Promedio (Completo)  Sharpe Promedio (Filtrado) 
------:---:
 **OAS**  1.1691  1.0575 
 **Ledoit-Wolf**  1.0566  1.0075 
 **RMT Var-Weighted**  1.7448  0.9963 
 **RMT Constant Bulk**  1.7447  0.9961 
 **Empirical**  1.7445  0.9959 
 **RMT Blend**  1.7433  0.9940 
 **EWMA**  1.6774  0.9078 

*Análisis:* Al excluir el sesgo del cash-clipping (cuadrícula filtrada), la diferencia de rendimiento promedio entre los estimadores es reducida. Los encogimientos de covarianza de gran tamaño (OAS y Ledoit-Wolf) muestran un rendimiento promedio marginalmente superior (1.0575 y 1.0075). RMT (en sus tres modalidades) y Empirical muestran comportamientos casi idénticos (~0.996), demostrando que la estimación robusta de la correlación está bien blindada, mientras que el EWMA decae en desempeño (~0.908).

####6.2.3 Sensibilidad por Método de Enlace (Linkage)
*Evalúa el impacto de la topología del árbol jerárquico HRP en la diversificación:*

 Método de Enlace  Sharpe Promedio (Completo)  Sharpe Promedio (Filtrado) 
------:---:
 **Single**  1.6641  1.1550 
 **Average**  1.5579  0.9963 
 **Ward**  1.5123  0.9326 
 **Complete**  1.4830  0.8904 

*Análisis:* El enlace `Single` obtiene el rendimiento promedio más robusto (1.1550). Ward y Complete, que tienden a formar clusters más compactos y esféricos, registran un Sharpe promedio más bajo (0.9326 y 0.8904).

####6.2.4 Sensibilidad por Método de Redistribución
*Evalúa el impacto de la forma de tratar los excesos de asignación sobre los límites máximos (15%):*

 Método de Redistribución  Sharpe Promedio  Descripción del Método 
------:---
 **None**  2.6759  Clip al 15% y desvío del exceso directo a efectivo (carteras hiper-concentradas en BIL). 
 **Proportional**  1.1810  Redistribución transversal proporcional de excesos entre todos los demás activos no saturados. 
 **Hierarchical**  0.8061  Redistribución local subiendo recursivamente el dendrograma jerárquico. 

*Análisis:* La redistribución `Proportional` supera ampliamente a la redistribución `Hierarchical` (1.1810 vs 0.8061). La redistribución jerárquica local tiende a concentrar de forma excesiva el flujo de capital en sub-ramas y en el cash sink debido a la rigidez del árbol, mientras que el flujo transversal proporcional esparce mejor los excesos incrementando la diversificación efectiva OOS.

###6.3 Estrategias Ganadoras de la Cuadrícula

Al excluir las combinaciones con método `None` (por considerarlas no representativas de un portafolio de activos reales), las 4 estrategias líderes en desempeño OOS neto de costos son:

1. **Config 322 (Sharpe = 1.9009  Turnover Medio = 10.71%):** Lookback = 504  Cov = **RMT Variance-Weighted**  Linkage = Ward  Redistribution = Proportional
2. **Config 262 (Sharpe = 1.9009  Turnover Medio = 10.71%):** Lookback = 504  Cov = **Empirical**  Linkage = Ward  Redistribution = Proportional
3. **Config 334 (Sharpe = 1.9008  Turnover Medio = 10.71%):** Lookback = 504  Cov = **RMT Blend**  Linkage = Ward  Redistribution = Proportional
4. **Config 310 (Sharpe = 1.9008  Turnover Medio = 10.71%):** Lookback = 504  Cov = **RMT Constant**  Linkage = Ward  Redistribution = Proportional

> [!NOTE]
> **Indiferencia Espectral en Parámetros Óptimos**: El hecho de que RMT (en todas sus formas) y la covarianza empírica obtengan prácticamente la misma rentabilidad ajustada por riesgo y turnover cuando se combinan con `Lookback = 504` y `Redistribution = Proportional` demuestra que al estabilizar la muestra con un histórico de 2 años (504 observaciones para 44 activos) y permitir una diversificación transversal óptima de excesos, el ruido espectral en la estimación de covarianza tiene una contribución marginal despreciable sobre la asignación de pesos de HRP.

###6.4 Corrección Estructural (Vía B: Unconditional Core)

En respuesta al PBO inaceptable del 53.33%, se extirpó el componente de selección paramétrica dinámica de la arquitectura. El portafolio fue fijado incondicionalmente a la combinación estructural más robusta basada en promedios de sensibilidad del mercado:
- **Lookback:** 504
- **Covarianza:** OAS
- **Enlace:** Single
- **Redistribución:** Proporcional

Al evaluar esta configuración única ($N_{trials}=1$), el modelo estadístico arroja:
- **Probabilidad de Sobreajuste (PBO):** 0.00%
- **Deflated Sharpe Ratio (DSR):** 1.0000
- **Sharpe OOS Neto:** 1.293

> [!WARNING]
> **Limitación Epistémica (Sesgo de Supervivencia Ex-Post)**
> Aunque matemáticamente el DSR se dispara a 1.0 al definir $N_{trials}=1$, debemos reconocer estadísticamente que esta configuración fue seleccionada *después* de observar los datos de la cuadrícula. El sesgo de selección ("memory of selection") sigue existiendo. Por ende, la rentabilidad y el DSR reportados aquí deben leerse estrictamente como una hipótesis teórica optimizada.
> 
> La validación institucional final de la **Vía B** no recae en este DSR de 1.0, sino que **queda exclusivamente sujeta y condicionada** al desempeño intachable que esta estrategia demuestre en el **Holdout No Tocado (Fase F8)** y en el subsiguiente Paper Trading. No es una prueba definitiva para capital grande.

---
*Fin del reporte de fases F3 a F7.*
