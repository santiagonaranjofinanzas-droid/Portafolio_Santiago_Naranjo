#PROTOCOLO MAESTRO DE INVESTIGACIÓN, VALIDACIÓN Y PRODUCCIÓN  
##Sistema HRP-RMT para Asignación de Portafolios  
###Versión 1.7 — ETF Long-Only  
###Futuros, margen, derivados y estructuras apalancadas diferidos a V2  

**Autor:** Santiago Alejandro Naranjo Reyes  
**Tipo de documento:** Protocolo técnico de research cuantitativo, validación robusta y producción controlada  
**Versión:** 1.7 Backups y monitoring read-only  
**Estado:** Documento base para desarrollo en Python, backtesting reproducible, paper trading y despliegue gradual  
**Fecha:** 2026  

---

#Control de versión

 Versión  Estado  Descripción 
---------
 0.1  Borrador conceptual  Arquitectura inicial HRP-RMT con pipeline, CPCV, cloud y broker 
 0.5  Auditoría metodológica  Se incorporaron benchmarks, falsabilidad, contrato de investigación y controles de riesgo 
 0.8  Auditoría institucional  Se separaron ETFs y futuros, se corrigió stale pricing, DSR, kill switch y costos 
 1.0  Final auditada  Se agregaron control de razón muestral, RMT adaptativo, purga CPCV formal, redistribución por caps, volatility targeting jerárquico, score corregido y reglas para universo reducido 
 1.1  Refinalización metodológica  Se corrigen convenciones de retornos, memoria de estimadores, estabilidad topológica RMT-HRP, grilla DSR/PBO y reglas de purga institucional 
 1.2  Consolidación institucional  Se reconcilian rebalanceo fijo, delta RMT pre-registrado, N_trials, segregación de funciones, FX V1, score z y circuit breakers acumulados 
 1.3  Consolidación de selección y riesgo  Se fija slippage base para selección, se cuantifica degeneración topológica, se aclara diagnóstico PIT por fold y se reconcilian reactivaciones de riesgo 
 1.4  Arquitectura de datos Tiingo-only  Se define Tiingo como proveedor primario V1, Nasdaq/Sharadar como upgrade opcional y se formalizan limitaciones de survivorship/PIT 
 1.5  F8 shadow paper MVP  Se redefine F8 como holdout forward-looking en tiempo real, con CSV/Parquet append-only, cálculo diario y ejecución mensual 
 1.6  TimescaleDB sin cambio de lógica  Se migra persistencia a TimescaleDB como capa de almacenamiento, manteniendo CSV append-only como espejo auditado y sin alterar decisiones de trading 
 1.7  Backups y monitoring read-only  Se agregan backups automáticos de TimescaleDB, API FastAPI read-only, dashboard local y métricas operativas sin alterar lógica de trading 

---

#Índice

1. Declaración de alcance  
2. Tesis económica refinada  
3. Fase 0 — Contrato de investigación  
4. Universo elegible V1 ETF Long-Only  
5. Restricciones estructurales  
6. Calendario de rebalanceo  
7. Modelo de costos y fricciones  
8. Gobierno de datos point-in-time  
9. Política de stale prices y universo dinámico  
10. Estimación de riesgo y modelos de covarianza  
11. Random Matrix Theory: implementación, límites y falsación  
12. Motor HRP: clustering, cuasi-diagonalización y bisección recursiva  
13. Restricciones de peso y redistribución bajo caps  
14. Validación robusta: Walk-Forward, CPCV, purga y embargo  
15. Benchmarks y contribución marginal  
16. Score compuesto corregido  
17. Paper trading y simulación diaria  
18. OMS, gatekeepers y volatility targeting  
19. Kill switch y jerarquía de riesgo  
20. Arquitectura tecnológica incremental  
21. Gobernanza, model registry y control de cambios  
22. Reportes institucionales obligatorios  
23. Cronograma de desarrollo  
24. Backlog técnico por módulos  
25. Tests unitarios y pruebas de aceptación  
26. Condiciones de aprobación y rechazo  
27. Conclusión institucional  

---

#1. Declaración de alcance

Este documento define el protocolo completo para investigar, validar, simular, desplegar y monitorear un sistema cuantitativo de asignación de portafolios basado en:

- **Hierarchical Risk Parity (HRP)** como motor de asignación de riesgo.
- **Random Matrix Theory (RMT)** como filtro espectral de matrices de correlación/covarianza.
- **Combinatorial Purged Cross-Validation (CPCV)** para validar robustez fuera de muestra y reducir sesgo por selección.
- **Deflated Sharpe Ratio (DSR)** y **Probability of Backtest Overfitting (PBO)** como métricas de robustez estadística.
- **Paper trading y OMS controlado** como puente obligatorio antes de capital real.
- **Arquitectura incremental** desde research local hasta producción institucional.

La Versión 1 se limita estrictamente a una cartera de **ETFs líquidos long-only**, sin apalancamiento estructural, sin venta corta, sin derivados, sin futuros, sin opciones, sin CFDs y sin ETNs complejos.

Esta limitación no es una debilidad. Es una decisión metodológica. Permite aislar la pregunta central:

> ¿Aporta HRP-RMT una mejora neta, robusta y fuera de muestra frente a asignaciones simples, shrinkage clásico y HRP empírico, después de costos, restricciones y fricciones reales?

La fase de futuros, margen, roll yield, basis risk, ejecución de contratos continuos, gestión de colateral, derivados y estructuras apalancadas queda explícitamente diferida a una **Versión 2**.

---

#2. Tesis económica refinada

El motor HRP-RMT no actúa como predictor de alfa direccional ni pretende maximizar retornos esperados de forma aislada.

Su justificación económica reside en mejorar la eficiencia fuera de muestra del presupuesto de riesgo mediante cinco mecanismos:

1. **Reducción del error de estimación** en matrices de covarianza.
2. **Mitigación de concentraciones extremas** generadas por optimizadores tradicionales.
3. **Control del drawdown** en carteras multiactivo.
4. **Estabilidad temporal de pesos** frente a ruido de correlaciones.
5. **Reducción de sensibilidad al mal condicionamiento matricial**.

El sistema parte del supuesto de que los activos financieros exhiben estructuras jerárquicas dinámicas asociadas a:

- Clases de activo.
- Sectores.
- Regiones.
- Factores macroeconómicos.
- Duración.
- Crédito.
- Inflación.
- Commodities.
- Bienes raíces cotizados.
- Liquidez.

Al reemplazar la optimización clásica basada en inversión matricial por un agrupamiento no supervisado sobre distancias de correlación, HRP **reduce significativamente** la dependencia de matrices invertidas. No se afirma que el sistema sea inmune al ruido. La formulación correcta es:

> HRP busca ser más robusto que la optimización media-varianza y minimum variance tradicional ante matrices de covarianza mal condicionadas, pero sigue siendo sensible a correlaciones, ventanas retrospectivas, cambios de régimen, calidad de datos y estructura del universo.

La capa RMT se incorpora únicamente si demuestra, fuera de muestra y después de costos, una mejora neta frente a:

- Asignación equirrepartida 1/N.
- Inverse Volatility Portfolio.
- Equal Risk Contribution.
- Minimum Variance con Ledoit-Wolf.
- HRP empírico sin RMT.
- HRP con Ledoit-Wolf.
- Benchmark pasivo externo 60/40 global.
- Benchmark compuesto equivalente al universo seleccionable.

La hipótesis se considera validada solo si HRP-RMT mejora métricas ajustadas por riesgo, estabilidad temporal de pesos, forecast risk error, turnover neto y control de drawdown, sin depender de selección retrospectiva de parámetros.

---

#3. Fase 0 — Contrato de investigación

##3.1 Objetivo primario

Diseñar y validar un motor de asignación de portafolios que mejore la eficiencia riesgo-retorno fuera de muestra frente a benchmarks simples, robustos y pasivos, sin depender de predicción direccional de retornos.

##3.2 Objetivo secundario

Construir una arquitectura reproducible capaz de pasar de:

```text
Research Local -> Validación Robusta -> Paper Trading -> Producción Reducida -> Producción Completa
```

##3.3 Pregunta de investigación

> ¿La limpieza espectral de covarianza mediante RMT mejora de forma estadísticamente robusta el rendimiento ajustado por riesgo de HRP frente a HRP empírico y shrinkage clásico, neto de costos y bajo restricciones realistas?

##3.4 Hipótesis nula

```text
H0: HRP-RMT <= HRP empírico y/o HRP-RMT <= HRP Ledoit-Wolf
```

en métricas netas fuera de muestra como Calmar, Sharpe, Sortino, forecast risk error, turnover y estabilidad de pesos.

##3.5 Hipótesis alternativa

```text
H1: HRP-RMT > HRP empírico, HRP Ledoit-Wolf, IVP, ERC, MinVar Ledoit-Wolf y 1/N
```

en eficiencia ajustada por riesgo fuera de muestra, después de costos, sin fragilidad paramétrica severa.

##3.6 Principio de falsabilidad

Cada capa del sistema debe justificar su existencia con contribución marginal medible. Ningún componente se conservará por sofisticación matemática si no mejora el resultado neto fuera de muestra.

---

#4. Universo elegible V1 ETF Long-Only

##4.1 Universo inicial

El universo inicial estará compuesto por **N = 45 ETFs líquidos multiactivo globales**.

V1 usará exclusivamente ETFs listados en Estados Unidos, negociados en USD y ejecutables mediante brokers estadounidenses o equivalentes institucionales. La exposición económica puede ser global, pero el instrumento operativo debe cotizar en USD.

Distribución conceptual:

 Clase de activo  Subcategorías 
------
 Renta variable  Estados Unidos, Europa, Japón, emergentes, sectores, factores 
 Renta fija  Treasuries, corporativos, high yield, TIPS, duración corta/media/larga 
 Materias primas  Oro, broad commodities, energía vía ETFs líquidos 
 Bienes raíces cotizados  REITs estadounidenses y globales 
 Liquidez  Money Market ETF o T-Bills 1M 

Campos de divisa y FX se conservan en el esquema de datos para trazabilidad y futura V2, pero no activan conversión FX en V1 salvo que un instrumento no-USD sea aprobado explícitamente en Fase 0. Si se permite un instrumento no-USD, deben definirse umbrales de ADV, spread, costo y FX por divisa antes de incluirlo en cualquier backtest.

##4.2 Instrumentos excluidos

Quedan excluidos en V1:

- Futuros.
- Opciones.
- CFDs.
- ETFs apalancados.
- ETFs inversos.
- ETNs con riesgo crediticio estructural relevante.
- Instrumentos con ADV insuficiente.
- Instrumentos con historial demasiado corto.
- ETFs con spreads persistentemente altos.
- Productos temáticos ilíquidos o de concentración extrema.
- Activos con estructura fiscal o legal incompatible con una cartera institucional estándar.

##4.3 Requisitos mínimos por ETF

 Requisito  Umbral 
------:
 Historial mínimo preferido  5 años 
 Historial mínimo absoluto  3 años 
 ADV últimos 20 días  >= 5 millones USD 
 Spread medio  Preferiblemente < 20 bps 
 Expense ratio  Reportado y auditado 
 Activos bajo gestión  Preferiblemente > 100 millones USD 
 Datos faltantes  Bajo umbral de calidad 
 Estructura  ETF físico o estructura transparente 

Antes de validar resultados, F1 debe producir un diagnóstico de densidad del universo elegible por fecha:

```text
N_elegible,t
N_con_historial_suficiente,t
N_excluido_por_lookback,t
N_excluido_por_stale_liquidez,t
```

Este diagnóstico es obligatorio porque un ETF con 3 años de historial puede quedar subrepresentado bajo lookbacks largos, purgas extendidas o memoria efectiva EWMA. El reporte debe mostrar si el universo temprano difiere materialmente del universo nominal de 45 ETFs.

##4.4 Estados del activo

Cada ETF puede estar en uno de tres estados:

 Estado  Definición  Tratamiento 
---------
 Elegible  Datos válidos, liquidez suficiente y activo en operación  Participa en HRP y rebalanceo 
 Congelado  Datos insuficientes temporalmente, pero posición existente  Mantiene peso; no recibe compras nuevas 
 Retirado  Deslistado, liquidado o estructuralmente no elegible  Sale del universo point-in-time 

---

#5. Restricciones estructurales

 Restricción  Regla 
------
 Tipo de portafolio  Long-only 
 Apalancamiento  Prohibido 
 Venta corta  Prohibida 
 Exposición total máxima  100% del capital 
 Exposición total mínima  Puede ser menor si volatility targeting reduce riesgo 
 Peso mínimo por ETF  0% 
 Peso máximo por ETF  15% 
 Peso máximo por clúster  35% del presupuesto de riesgo 
 Activo refugio  Money Market ETF o T-Bills 1M 
 Rebalanceo ordinario  Mensual 
 Ejecución base  Última sesión hábil del mes 
 Tipo de orden base  Market-On-Close o equivalente líquido 
 Rebalance buffer  3% de rotación agregada mínima 
 Volatility target  12% anualizado 
 Leverage por baja volatilidad  Prohibido 

---

#6. Calendario de rebalanceo

##6.1 Regla base

El rebalanceo se ejecutará en la última sesión de negociación de cada mes calendario.

La frecuencia mensual es una restricción institucional fija de V1, no un hiperparámetro de selección. Rebalanceos quincenales o bimestrales pueden evaluarse únicamente como análisis de sensibilidad posterior al modelo seleccionado, sin participar en ranking principal, DSR, PBO ni selección de configuración.

##6.2 Jerarquía de calendario

Si la última sesión presenta problemas, se aplica la siguiente jerarquía:

1. Última sesión hábil completa del mes.
2. Sesión inmediatamente anterior si existe cierre parcial.
3. Suspensión del rebalanceo si hay dislocación crítica de mercado.
4. Registro obligatorio de excepción operativa.

##6.3 Condiciones para cancelar el rebalanceo

El rebalanceo se cancela si:

- El spread de uno o más activos supera el percentil 95 histórico.
- Hay feed corrupto o precios congelados.
- Hay tracking error operativo superior a 1%.
- Se activa congelación de órdenes.
- La rotación agregada propuesta es menor al 3%.
- Más del 25% del portafolio está en activos congelados.
- El OMS detecta órdenes duplicadas o no confirmadas.

---

#7. Modelo de costos y fricciones

##7.1 Principio

El backtest debe ser neto de costos. No se aceptará evaluación bruta como evidencia final.

##7.2 Escenarios de costo

 Componente  Bajo  Base  Estrés 
------:---:---:
 Comisión  0.005 USD/acción  0.005 USD/acción + mínimo por orden  Comisión + mínimos + tasas 
 Slippage  25% del spread  50% del spread  100% del spread 
 Spread  Media 20 días  Media 20 días  Percentil 95 
 Tasas regulatorias  No incluidas  Incluidas si aplican  Incluidas 
 Impacto de mercado  0  Lineal por ADV  Cuadrático simple 
 Rechazos/partial fills  0  Simulación base  Simulación estrés 

El escenario **Base** es el único escenario de costos usado para selección de hiperparámetros, ranking principal, DSR, PBO y score compuesto. Los escenarios **Bajo** y **Estrés** se ejecutan solo como sensibilidad posterior sobre la configuración ya seleccionada.

El sistema no puede elegir una configuración distinta por escenario de slippage. Si una configuración solo supera benchmarks bajo costos bajos y falla bajo costos base, se rechaza para V1.

##7.3 Expense ratios

Los expense ratios de ETFs no se descuentan dos veces.

Regla:

- Si se usan precios reales ajustados o series Total Return del ETF, el expense ratio ya está embebido.
- Si se usan índices brutos, proxies sintéticos o series reconstruidas, el expense ratio se descuenta explícitamente de forma diaria.

##7.4 Fórmula conceptual de costo por rebalanceo

Para cada activo `i`:

```text
Costo_i = Comisión_i + Slippage_i + SpreadCost_i + Impacto_i + Tasas_i
```

El costo total del rebalanceo:

```text
Costo_total,t = sum_i TradeValue_i,t * CostRate_i,t
```

##7.5 Rechazo por fricción

El sistema se rechaza si los costos en escenario base eliminan más del 25% de la mejora neta en eficiencia ajustada por riesgo frente al benchmark operativo.

---

#8. Gobierno de datos point-in-time

##8.1 Principio rector

Todo dato usado por el modelo debe haber estado disponible en el momento histórico evaluado.

Queda prohibido introducir información futura mediante:

- Reconstituciones posteriores del universo.
- Ajustes corporativos mal fechados.
- Inclusión solo de ETFs sobrevivientes.
- Selección ex post de instrumentos exitosos.
- Corrección manual posterior no versionada.
- Fill de datos sin marca de calidad.

##8.2 Requisitos del dataset

Proveedor primario V1:

 Rol  Fuente  Estado 
---------
 Precios EOD OHLCV  Tiingo  Obligatorio 
 Precios ajustados  Tiingo `adjOpen/adjHigh/adjLow/adjClose/adjVolume`  Obligatorio 
 Dividendos/splits diarios  Tiingo `divCash/splitFactor`  Obligatorio 
 Security master avanzado  Nasdaq Data Link / Sharadar o equivalente  Opcional/upgrade 
 Deslistados PIT exhaustivos  Sharadar, Norgate, QUODD, Databento o equivalente  Opcional/upgrade 

La implementación V1 puede avanzar con Tiingo como única fuente pagada/operativa siempre que el reporte declare explícitamente:

- Universo limitado a ETFs USD listados y actualmente verificables por Tiingo.
- Control de survivorship bias inferior al de una base institucional pagada con deslistados completos.
- Necesidad de upgrade a security master PIT si el sistema avanza a capital institucional relevante.
- Prohibición de afirmar cobertura PIT exhaustiva si no existe fuente de deslistados independiente.

 Campo  Descripción 
------
 Ticker  Identificador del ETF 
 Fecha  Timestamp diario 
 Open/High/Low/Close  Precios diarios si están disponibles 
 Adjusted Close  Precio ajustado validado 
 Volume  Volumen negociado 
 Spread  Ask-Bid o proxy 
 AUM  Activos bajo gestión si disponible 
 Expense Ratio  Costo anual del ETF 
 Inception Date  Fecha de inicio 
 Delisting Date  Fecha de salida si aplica 
 Corporate Actions  Splits, dividendos, cambios estructurales 
 Currency  Divisa original 
 FX Rate  Conversión diaria a USD 
 Estado  Elegible, congelado o retirado 

##8.3 Tipo de retorno

La convención institucional base para optimización, covarianza, PnL, métricas de cartera y rebalanceo será el retorno aritmético simple:

```text
R_i,t = P_i,t / P_i,t-1 - 1
```

Motivo:

- Los retornos simples son aditivos transversalmente bajo pesos de cartera:

```text
R_p,t = sum_i w_i,t-1 * R_i,t
```

- HRP, IVP, ERC, Minimum Variance, volatility targeting, risk contribution, backtest neto y attribution operan sobre pesos lineales.
- La matriz de covarianza usada para asignación de pesos debe estimarse sobre la misma convención de retorno usada para agregar PnL de cartera.

Los retornos logarítmicos:

```text
r_i,t = ln(P_i,t) - ln(P_i,t-1)
```

quedan permitidos solo para análisis auxiliares donde su aditividad temporal sea útil: diagnóstico de distribución, gráficos acumulados, contraste estadístico o reportes descriptivos. No serán la entrada canónica de la matriz de covarianza para asignación HRP ni la base de cálculo del retorno realizado del portafolio.

Excepción controlada:

Si se evalúa una variante con retornos logarítmicos, debe registrarse como experimento separado, no comparable directamente con la configuración institucional base salvo que se reconcilie explícitamente la conversión a retornos simples antes de PnL y métricas de cartera.

Consolidación institucional V1.4:

> Queda formalmente ratificado que el retorno aritmético simple es el estándar canónico único para todo el pipeline de optimización, estimación de covarianza, agregación de PnL de cartera, cálculo de métricas institucionales, backtest, CPCV, DSR/PBO y rebalanceo. Los retornos logarítmicos se restringen exclusivamente a análisis diagnósticos auxiliares (distribución, gráficos acumulados, normalidad). Ningún módulo operativo del pipeline puede usar retornos logarítmicos como entrada para decisiones de asignación o evaluación de performance. Esta consolidación resuelve cualquier ambigüedad de versiones anteriores del protocolo.

##8.4 Reporte de calidad

Antes de cada rebalanceo:

 Control  Criterio 
------
 Timestamps duplicados  0 
 Valores huérfanos  0 
 Missing values  Bajo umbral 
 Retornos extremos  Marcados y auditados 
 Stale prices  Reportados por ETF 
 Ajustes corporativos  Validados 
 Divisa  Convertida a USD 
 Deslistados  Respetados point-in-time 
 ADV  Validado 
 Spread  Actualizado 

El backtest se rechaza si se detecta un evento de look-ahead bias.

---

#9. Política de stale prices y universo dinámico

##9.1 Definición de stale price

Un ETF se marca como stale si:

- No registra volumen en la sesión.
- El precio permanece congelado sin respaldo de negociación real.
- El feed muestra datos repetidos artificialmente.
- Existe desalineación de calendario entre mercado de origen y cartera.

##9.2 Tratamiento para PnL

Si el activo está en cartera:

- Se mantiene la última valoración observable.
- Se marca la observación como stale.
- No se interpreta retorno cero como retorno económico real.
- No se permite usar ese dato como si fuera precio negociable.

##9.3 Tratamiento para covarianza

Para covarianza y correlación:

- Se prohíbe pairwise deletion indiscriminado.
- Se usa ventana común sincronizada cuando sea posible.
- Se permite imputación controlada solo con bandera explícita.
- Si el activo tiene más de 3 sesiones consecutivas inválidas, se excluye temporalmente del cálculo del periodo.
- La exclusión no implica venta automática.

##9.4 Activos congelados

Si un ETF mantenido pasa a estado congelado:

1. Su peso actual se conserva para PnL.
2. No recibe compras adicionales.
3. Solo se permiten ventas si:
   - hay riesgo operativo confirmado;
   - existe liquidez suficiente;
   - el gestor confirma reducción;
   - el volatility targeting lo exige y los datos son válidos.
4. HRP se recalcula sobre el universo elegible restante.
5. El capital rebalanceable se define como:

```text
Capital_rebalanceable = 1 - sum(w_congelados)
```

6. Los pesos HRP del universo elegible se normalizan sobre el capital rebalanceable.
7. El activo reingresa al universo elegible si acumula 5 sesiones consecutivas de datos válidos y cumple liquidez.

##9.5 Alertas por universo reducido

 Condición  Acción 
------
 Peso congelado > 15%  Alerta operativa 
 Peso congelado > 25%  Congelar rebalanceo ordinario 
 Más de 5 ETFs congelados  Revisión manual 
 ETF retirado oficialmente  Salida point-in-time 
 Error de feed masivo  Suspensión de ejecución 

---

#10. Estimación de riesgo y modelos de covarianza

##10.1 Modelos obligatorios

 Estimador  Rol 
------
 Covarianza empírica  Benchmark base 
 EWMA lambda = 0.94  Sensible a riesgo reciente; estado recursivo reinicializado por fold y con memoria efectiva documentada 
 Ledoit-Wolf  Shrinkage lineal robusto 
 OAS  Shrinkage óptimo bajo supuestos gaussianos 
 RMT Constant Bulk  Limpieza espectral estándar 
 RMT Variance-Weighted Bulk  Limpieza espectral adaptativa 
 RMT + Shrinkage Blend  RMT con mezcla convexa Ledoit-Wolf/OAS pre-registrada 

##10.2 Validación de matriz

Toda matriz usada por HRP debe cumplir:

- Simetría numérica.
- Diagonal positiva.
- Definida positiva o semidefinida positiva corregible.
- Sin NaN.
- Sin infinitos.
- Condition number reportado.
- Eigenvalues reportados.
- Dimensión consistente con universo elegible.

##10.3 Rechazo de matriz

Una matriz se rechaza si:

- Pierde definición positiva.
- Tiene condition number extremo no corregido.
- Contiene NaN o infinitos.
- Se origina en datos stale no controlados.
- Produce pesos degenerados.
- Colapsa a un único factor dominante sin diversificación útil.

---

#11. Random Matrix Theory: implementación, límites y falsación

##11.1 Convenciones de razón muestral

Se reportarán dos razones:

```text
q = T / N
c = N / T
```

Donde:

- `T` = número de observaciones.
- `N` = número de activos.

La fórmula de Marchenko-Pastur usará `q = T/N`.  
El control operativo de densidad usará `c = N/T`.

##11.2 Tabla para N = 45

La siguiente tabla es ilustrativa para el universo nominal inicial de 45 ETFs. En producción, `q_t` y `c_t` se recalculan en cada fecha de rebalanceo usando el número efectivo de activos elegibles `N_t`, no el universo nominal.

 Lookback  T  N  c = N/T  Estado 
---:---:---:---:---
 63  63  45  0.714  Alerta de densidad elevada 
 126  126  45  0.357  Aceptable 
 252  252  45  0.179  Robusto 
 504  504  45  0.089  Muy robusto 

##11.3 Reglas por densidad muestral

 Condición  Regla 
------
 c > 0.50  Alerta de densidad muestral 
 c >= 0.75  Rechazo para producción salvo justificación extraordinaria 
 T <= N  RMT no puede ser estimador principal 
 Lookback 63  Solo sensibilidad o señal secundaria 
 Lookback 126  Mínimo defendible 
 Lookback 252  Preferencia institucional 
 Lookback 504  Útil si no degrada adaptabilidad 

El estado "alerta de densidad elevada" no implica rechazo automático. Requiere reporte reforzado de estabilidad, FRE, eigenvalues y sensibilidad, y queda prohibido usar esa configuración como principal si una alternativa con mayor densidad muestral obtiene desempeño institucional comparable.

##11.4 Límites de Marchenko-Pastur

```text
lambda_minus = sigma^2 * (1 - sqrt(1/q))^2
lambda_plus  = sigma^2 * (1 + sqrt(1/q))^2
```

Autovalores dentro del bulk se consideran principalmente ruido estadístico bajo los supuestos del modelo.

##11.5 Procedimiento RMT

1. Calcular matriz de correlación empírica.
2. Obtener autovalores y autovectores.
3. Calcular `q` y `c`.
4. Calcular límites `lambda_minus` y `lambda_plus`.
5. Identificar autovalores dentro del bulk.
6. Contraer autovalores ruidosos.
7. Preservar autovalores fuera del bulk.
8. Reconstruir matriz de correlación.
9. Aplicar mezcla de estabilidad contra shrinkage clásico si la matriz filtrada induce distancias degeneradas.
10. Reescalar a covarianza.
11. Verificar simetría y definición positiva.
12. Comparar contra Ledoit-Wolf y OAS.
13. Evaluar impacto en portafolio.

La mezcla de estabilidad se define como:

```text
C_final = (1 - delta) * C_RMT + delta * C_shrinkage
```

donde `C_shrinkage` será Ledoit-Wolf u OAS estimado con la misma ventana point-in-time. El valor `delta` se fija por regla pre-registrada en Fase 0, antes de observar resultados OOS, y no se optimiza por Sharpe, Calmar, PBO ni score compuesto.

Regla V1:

1. Evaluar degeneración topológica con `delta = 0` dentro de cada fold, rebalanceo y ventana de entrenamiento permitida.
2. Si no hay degeneración material, usar `delta = 0`.
3. Si hay degeneración material, usar el menor valor de la lista que reduzca empates y estabilice dendrogramas según §11.8.
4. Registrar el valor elegido y la métrica técnica que lo activó.

Queda prohibido fijar `delta` usando la muestra histórica completa, el bloque de test o el holdout. La regla y los umbrales se pre-registran en Fase 0; el valor efectivo de `delta` se determina point-in-time para cada ventana usando únicamente datos disponibles en esa ventana.

Lista permitida:

```text
delta in {0.01, 0.025, 0.05, 0.10}
```

Como `delta` se selecciona por regla técnica previa y no por desempeño OOS, no expande `N_trials`. Si cualquier investigación futura compara valores de `delta` por desempeño, cada valor evaluado debe contarse como configuración independiente.

La suma de una constante únicamente en la diagonal no se considera suficiente para resolver empates topológicos, porque la distancia HRP depende de correlaciones off-diagonal.

##11.6 Variantes RMT permitidas

 Variante  Descripción  Uso 
---------
 RMT Constant Bulk  Bulk hacia promedio simple  Benchmark RMT base 
 RMT Variance-Weighted Bulk  Bulk ponderado por varianza explicada  Preferida con c moderado 
 RMT + Shrinkage Blend  Mezcla convexa con Ledoit-Wolf u OAS  Obligatoria solo si el diagnóstico PIT detecta degeneración material 

Si `c > 0.50`, el diagnóstico de degeneración topológica se vuelve obligatorio y debe reportarse con mayor detalle, pero no fuerza por sí solo `delta > 0`. El Blend se activa únicamente por degeneración material según §11.8 o por fallo de estabilidad documentado.

##11.7 Falsación RMT

 Métrica  Aceptación  Rechazo 
---------
 Condition Number  Reducción material reportada y evaluada en sensibilidad  No comprime o pierde definición positiva 
 Clusters  Mayor estabilidad intertemporal  Mutación errática 
 Distancias HRP  Baja proporción de empates y seriation estable  Distancias idénticas, tie-breaking dominante o chattering 
 Turnover  <= HRP empírico  Aumenta costos sin mejora 
 Forecast Risk Error  Menor que Ledoit-Wolf  Subestima riesgo realizado 
 Calmar OOS  Superior a HRP + LW  No mejora neta 
 Drawdown  No incrementa MDD  Reduce vol pero aumenta pérdida máxima 
 Robustez régimen  Aceptable en crisis y bull markets  Solo funciona en un régimen 
 c=N/T  Dentro de rango aceptable  c elevado sin control 

RMT se rechaza si mejora la matriz pero empeora el portafolio.

La reducción de condition number no es criterio suficiente de aceptación. El umbral inicial de referencia será 40%, pero se tratará como diagnóstico de sensibilidad, no como corte duro. La decisión final depende del portafolio neto, FRE, estabilidad topológica, turnover y drawdown.

##11.8 Control de degeneración topológica RMT-HRP

El protocolo reconoce que la contracción homogénea del bulk de Marchenko-Pastur puede inducir empates o casi empates en la matriz de distancias HRP:

```text
d_ij = sqrt(0.5 * (1 - rho_ij))
```

Riesgo:

- Árboles jerárquicos inestables entre rebalanceos.
- Cambios de seriation no explicados económicamente.
- Bisecciones recursivas dominadas por empates numéricos.
- Turnover artificial sin mejora real de riesgo.

Controles obligatorios:

1. Reportar proporción de distancias duplicadas o casi duplicadas bajo tolerancia `1e-10`.
2. Reportar estabilidad de dendrograma frente a perturbaciones deterministas menores.
3. Usar `optimal_ordering=True` cuando la librería de clustering lo permita.
4. Definir tie-breaking determinista por ticker/ID estable, nunca por orden accidental de memoria.
5. Comparar RMT Constant Bulk contra RMT Variance-Weighted Bulk y RMT + Shrinkage Blend.
6. Rechazar una configuración si reduce condition number pero aumenta turnover, mutación de clusters o forecast risk error.

Definición operativa de degeneración material:

```text
tie_rate = pares_distancia_casi_duplicados / pares_distancia_totales
topology_instability = 1 - mean(cophenetic_correlation_base_vs_perturbado)
```

Se considera degeneración material si se cumple cualquiera de las siguientes condiciones dentro de la ventana PIT evaluada:

 Condición  Umbral 
------:
 `tie_rate` con tolerancia `1e-10`  > 2.0% 
 `tie_rate` con tolerancia `1e-8`  > 5.0% 
 `topology_instability` ante perturbaciones deterministas `1e-10`  > 10.0% 
 Cambio de membresía en los primeros cortes jerárquicos  > 10.0% de activos 
 Turnover atribuible a cambio topológico sin cambio material de covarianza  > 5.0% absoluto 

Las perturbaciones deterministas deben ser simétricas, reproducibles, de media cero, menores o iguales a `1e-10` sobre correlaciones off-diagonal, y nunca pueden incorporarse a la matriz final usada para optimización. Sirven solo como prueba de estabilidad.

El objetivo no es romper empates mediante ruido arbitrario, sino preservar información estructural suficiente para que HRP produzca una topología reproducible y económicamente defendible.

---

#12. Motor HRP

##12.1 Entrada

- Matriz de covarianza validada.
- Matriz de correlación validada.
- Universo elegible.
- Estados de activos.
- Restricciones de pesos.
- Filtros de liquidez.
- Vector actual de pesos.
- Señales de riesgo.
- Cost model.

##12.2 Distancia de correlación

```text
d_ij = sqrt(0.5 * (1 - rho_ij))
```

Antes de ejecutar linkage:

- La matriz de distancias debe triangularizarse de forma determinista.
- Los tickers deben ordenarse por identificador estable antes del clustering.
- Los empates exactos o casi empates deben registrarse.
- La implementación debe producir el mismo dendrograma para el mismo dataset, semilla, universo, ventana y configuración.

Si la tasa de empates casi exactos altera el orden jerárquico ante perturbaciones numéricas irrelevantes, la configuración se clasifica como no apta para producción aunque sus métricas agregadas sean atractivas.

##12.3 Linkage

Se evaluarán:

- Single.
- Complete.
- Average.
- Ward.

El criterio final se elige por:

- Performance OOS.
- Estabilidad de clusters.
- Turnover.
- Forecast risk error.
- Robustez por régimen.

##12.4 Cuasi-diagonalización

La matriz de covarianza se reordena para ubicar activos con alta co-dependencia cerca de la diagonal.

##12.5 Bisección recursiva

HRP divide jerárquicamente el portafolio en subclústeres.

La asignación entre subclústeres se realiza en proporción inversa a la varianza agregada del subclúster, no a la varianza individual de cada activo.

Para dos subclústeres `A` y `B`:

```text
alpha_A = 1 - sigma_A^2 / (sigma_A^2 + sigma_B^2)
alpha_B = 1 - alpha_A
```

La varianza de cada subclúster se calcula usando los pesos internos de varianza inversa dentro del subclúster.

---

#13. Restricciones de peso y redistribución bajo caps

##13.1 Cap máximo

```text
w_max = 15%
```

Si un activo supera el cap:

```text
Exceso_i = w_i - w_max
```

##13.2 Métodos de redistribución

 Método  Regla  Interpretación 
---------
 Proporcional HRP  Redistribuye según pesos HRP originales  Preserva geometría 
 Inverse Variance  Redistribuye hacia menor varianza  Refuerza control de riesgo 
 Global Residual  Redistribuye entre activos no saturados  Reduce saturación local 

##13.3 Método base

1. Redistribuir dentro del mismo clúster proporcional a pesos HRP.
2. Si el clúster está saturado, redistribuir al clúster hermano más cercano.
3. Si no hay capacidad, asignar exceso a Money Market ETF o T-Bills.
4. Registrar constraint drag.
5. Validar impacto en risk contribution.
6. Incluir método de redistribución como hiperparámetro en CPCV.

##13.4 Constraint drag

```text
ConstraintDrag = L1_norm(w_HRP_puro - w_HRP_restringido)
```

Se reportará en cada rebalanceo.

##13.5 Rechazo por distorsión

Se rechaza una configuración si las restricciones eliminan sistemáticamente la ventaja de HRP frente a IVP o ERC.

---

#14. Validación robusta

##14.1 Separación obligatoria

El proceso debe separar:

1. Desarrollo.
2. Selección de hiperparámetros.
3. Evaluación OOS.
4. Holdout final no tocado.
5. Paper trading.
6. Producción.

No se permite ajustar parámetros después de observar el holdout final.

##14.2 Espacio de hiperparámetros

```text
H = {Lookback} x {Covarianza} x {Linkage} x {Redistribución}
```

 Dimensión  Valores 
------
 Lookback  63, 126, 252, 504 
 Covarianza  Empírica, EWMA, LW, OAS, RMT Constant Bulk, RMT Variance-Weighted Bulk, RMT + Shrinkage Blend 
 Linkage  Single, Complete, Average, Ward 
 Redistribución cap  HRP proporcional, inverse variance, global residual 

La frecuencia de rebalanceo mensual queda excluida de la grilla de selección porque es una restricción institucional fija de V1. Las frecuencias quincenal y bimestral se permiten solo como sensibilidad no selectiva.

El escenario de slippage base queda excluido de la grilla porque es una asunción de evaluación del entorno, no una decisión de diseño. Los escenarios bajo y estrés se permiten solo como sensibilidad no selectiva después de congelar la configuración principal.

##14.3 CPCV

La CPCV se usará para evaluar múltiples trayectorias OOS sin barajar los datos.

Prohibido:

- Shuffling.
- Selección ex post del mejor path.
- Optimización sobre el holdout.
- Reusar test como entrenamiento.

##14.4 Purga formal

La purga se define sobre el conjunto completo de información que puede afectar una decisión de entrenamiento.

Sea una fecha de rebalanceo `tau` con lookback `L`. La matriz de covarianza usa:

```text
[tau - L, tau - 1]
```

Si esta ventana intersecta un bloque OOS:

```text
[tau - L, tau - 1] ∩ OOS ≠ ∅  =>  tau no pertenece a Train
```

Se purgan todas las observaciones de entrenamiento cuyas ventanas de estimación intersecten cualquier bloque de prueba.

Si múltiples rebalanceos comparten ventanas solapadas con el mismo OOS, todos se purgan.

Para estimadores con memoria recursiva, como EWMA, queda prohibido transportar estado calculado con datos de test hacia entrenamiento o viceversa. Cada fold debe reinicializar el estado del estimador usando únicamente datos permitidos por ese fold.

La memoria efectiva EWMA se documentará como:

```text
K_eff(lambda, epsilon) = ceil(log(epsilon) / log(lambda))
```

Para `lambda = 0.94`:

 Umbral residual epsilon  K_eff aproximado 
---:---:
 5%  49 días 
 1%  75 días 
 0.1%  112 días 

Regla institucional:

```text
Purga = max(Horizonte económico, Lookback máximo usado por la decisión, K_eff del estimador recursivo, Ventana de features exógenas)
```

Si una configuración usa lookback de 252 días, la purga efectiva mínima para esa configuración será 252 observaciones hábiles. Si una configuración EWMA no tiene ventana finita explícita, debe declarar `K_eff` con `epsilon <= 1%` como mínimo; para producción se prefiere `epsilon = 0.1%` salvo que el costo muestral vuelva inviable la CPCV.

##14.5 Embargo

 Regla  Valor 
------:
 Embargo mínimo  22 días hábiles 
 Embargo proporcional  5% del bloque OOS 
 Embargo aplicado  Máximo entre ambos 

El embargo se aplica después del bloque OOS y no sustituye a la purga. La purga elimina contaminación por ventanas de estimación o memoria de señales; el embargo reduce dependencia serial residual posterior al test.

##14.6 Holdout final

Después de CPCV, se reserva un periodo final no usado para selección.

Regla absoluta:

> Si el modelo se cambia después de ver el holdout, el holdout queda contaminado y debe reiniciarse la validación.

##14.7 Control de selección múltiple

El número total de configuraciones evaluadas se registra antes de correr la validación:

```text
N_trials = 4 * 7 * 4 * 3 = 336
```

Este valor incluye:

- 4 lookbacks.
- 7 estimadores de covarianza.
- 4 linkages.
- 3 métodos de redistribución por caps.

No incluye:

- `delta` de RMT + Shrinkage Blend, porque se fija por regla técnica pre-registrada y no por desempeño OOS.
- Frecuencia de rebalanceo, porque V1 usa frecuencia mensual fija.
- Escenario de slippage, porque V1 selecciona con costos base y usa bajo/estrés como sensibilidad.
- Sensibilidades no selectivas ejecutadas después de congelar la configuración principal.

Reglas:

1. DSR debe calcularse usando `N_trials` efectivo, la distribución completa de Sharpe ratios evaluados y los momentos de la serie de retornos.
2. PBO debe calcularse con todas las configuraciones candidatas, no solo con las finalistas.
3. Toda configuración descartada por error operativo, matriz inválida o violación de restricción debe permanecer registrada.
4. Si se agregan variantes después de ver resultados, se incrementa `N_trials` y se reejecuta la validación.
5. El holdout final no participa en `N_trials`; solo confirma o rechaza el modelo ya seleccionado.

---

#15. Benchmarks y contribución marginal

##15.1 Benchmarks obligatorios

 Benchmark  Función 
------
 1/N Equal Weight  Base ingenua 
 IVP  Riesgo inverso individual 
 ERC  Presupuesto de riesgo equilibrado 
 Minimum Variance Ledoit-Wolf  Optimización robusta clásica 
 HRP empírico  HRP sin limpieza 
 HRP + Ledoit-Wolf  Shrinkage clásico dentro de HRP 
 60/40 global  Benchmark externo pasivo 
 Benchmark compuesto  Alternativa según universo 

##15.2 Contribución marginal

 Capa  Modelo  Benchmark  Debe demostrar 
------------
 0  1/N  Benchmark compuesto  Punto base 
 1  IVP  1/N  Menor MDD 
 2  ERC  IVP  Mejor distribución de riesgo 
 3  MinVar LW  ERC  Mejor forecast risk 
 4  HRP empírico  IVP/ERC  Mejor Calmar 
 5  HRP + LW  HRP empírico  Menor turnover/FRE 
 6  HRP-RMT  HRP + LW  Mejor Calmar, DSR>0.95, PBO<15% 

---

#16. Score compuesto corregido

##16.1 Problema evitado

No se penaliza MDD dentro del score porque Calmar ya lo incorpora.

##16.2 Fórmula

```text
Score = 0.30*Calmar_z + 0.20*Sortino_z - 0.20*DrawdownDuration_z - 0.15*Turnover_z - 0.15*ForecastRiskError_z
```

Los z-scores se calculan contra la población completa de configuraciones candidatas de la grilla principal CPCV (`N_trials = 336`) dentro del mismo universo, periodo, costos base y folds. Los benchmarks de §15.1 se reportan junto al score, pero no forman parte de la población usada para normalizar z-scores salvo que se registren explícitamente como configuraciones candidatas antes de la validación.

Regla:

- Ranking de modelos candidatos: z-score contra la grilla principal.
- Comparación institucional: métricas absolutas y relativas contra benchmarks.
- Sensibilidades posteriores: no recalculan el ranking principal.

##16.3 Interpretación

 Métrica  Rol 
------
 Calmar  Retorno vs drawdown 
 Sortino  Riesgo bajista 
 Drawdown Duration  Persistencia del daño 
 Turnover  Costos y rotación 
 Forecast Risk Error  Calidad del estimador 

##16.4 Restricciones duras

Un modelo se rechaza aunque tenga alto score si viola:

- MDD máximo permitido.
- PBO.
- DSR.
- Costos.
- Estabilidad.
- Datos.
- Tracking error.
- Kill switch.

---

#17. Paper trading

##17.1 Objetivo

El paper trading valida operación, no edge estadístico.

Valida:

- Datos en tiempo real.
- Generación de pesos.
- Simulación de órdenes.
- Logs.
- Slippage.
- Tracking error.
- Alertas.
- OMS.
- Kill switch.

##17.2 Duración

 Objetivo  Duración 
------:
 Validación técnica  60 días hábiles 
 Estabilidad preliminar  3–6 meses 
 Validación real de performance  12 meses o más 

##17.3 Métricas

 Métrica  Criterio 
------
 Execution Tracking Error  < 0.50% 
 Tracking error acumulado  < 1.00% 
 Fill ratio simulado  > 98% 
 Diferencia costo estimado/real  < 20% 
 Fallos críticos de datos  0 
 Órdenes duplicadas  0 
 Logs reproducibles  100% 
 Señales diarias  Sin intervención manual 

---

#18. OMS, gatekeepers y volatility targeting

##18.1 OMS

El OMS valida antes de emitir órdenes:

- Liquidez.
- Spread.
- Peso actual.
- Peso objetivo.
- Rotación mínima.
- Estado de datos.
- Estado de riesgo.
- Estado API.
- Restricciones.
- Costos.
- Trading halt.

##18.2 Rebalance buffer

```text
sum(w_nuevo - w_actual) < 0.03
```

Si la rotación agregada es menor a 3%, no se rebalancea.

##18.3 Volatility targeting

```text
E_t = min(1, sigma_target / sigma_forecast_t)
sigma_target = 12% anualizado
```

Si `sigma_forecast_t <= 12%`, exposición = 100%.  
Si `sigma_forecast_t > 12%`, exposición se reduce.

No se permite apalancamiento si la volatilidad está por debajo del objetivo.

##18.4 Suavizado

```text
E_aplicada_t = alpha * E_t + (1-alpha) * E_aplicada_t-1
alpha = 0.33
```

Con `alpha = 0.33`:

 Métrica  Aproximación 
------:
 Tiempo a 50% del ajuste  1.7 días hábiles 
 Tiempo a 75% del ajuste  3.5 días hábiles 
 Tiempo a 95% del ajuste  7.4 días hábiles 

La referencia operativa de "transición corta" corresponde al ajuste de 75%, no al ajuste completo.

##18.5 Reducción inmediata

Si:

```text
sigma_forecast_t > 18%
```

la reducción se ejecuta inmediatamente.

---

#19. Kill switch y jerarquía de riesgo

##19.1 Jerarquía

1. Error crítico de datos.
2. Kill switch operativo.
3. Congelación por drawdown.
4. Reducción de exposición por drawdown confirmado.
5. Filtro de liquidez/spread.
6. Volatility targeting.
7. Rebalance buffer.
8. Ejecución ordinaria HRP.

##19.2 Matriz de eventos

 Evento  Umbral  Acción 
------:---
 Alerta DD  >= 1.5% intradía  Log crítico y auditoría 
 Congelación  >= 3.0% intradía  Cancelar nuevas órdenes 
 Reducción  >= 5.0% intradía  Reducir exposición si riesgo confirmado 
 Kill switch  >= 8.0% intradía  Suspender trading y modo manual 
 Liquidación total  Confirmación humana  Cierre ordenado 
 Feed corrupto  Cualquier evento crítico  Suspender ejecución 
 TE pesos  > 1.0%  Pausar rebalanceo 
 API failure  Órdenes no confirmadas  Bloqueo de órdenes 
 Spread extremo  > p95 histórico  Posponer ejecución 

Error de datos no debe provocar liquidación automática.

##19.3 Circuit breakers por drawdown acumulado

Además de los umbrales intradía, el sistema monitorea drawdown acumulado desde high-water mark diario del NAV.

 Evento  Umbral acumulado  Acción 
------:---
 Alerta acumulada  DD >= 5%  Revisión de riesgo y reporte extraordinario 
 Congelación de incremento  DD >= 8%  Prohibido aumentar exposición; solo reducir o mantener 
 Reducción defensiva  DD >= 12%  Reducir exposición objetivo en 25% salvo veto humano documentado 
 Pausa de estrategia  DD >= 15%  Suspender rebalanceos ordinarios y convocar comité de revisión 
 Rehabilitación  Recuperación > 50% del DD y revisión aprobada  Reanudar gradualmente 

Estos umbrales no sustituyen la validación estadística. Son controles operativos de preservación de capital y deben calibrarse con el mandato de riesgo antes de capital real.

##19.4 Precedencia y reactivación de frenos de riesgo

Si varios frenos están activos simultáneamente, prevalece siempre la acción más restrictiva.

Orden de precedencia:

1. Kill switch operativo o feed corrupto.
2. Liquidación total con confirmación humana.
3. Pausa de estrategia por drawdown acumulado.
4. Reducción defensiva acumulada.
5. Congelación intradía o acumulada.
6. Volatility targeting ordinario.

Para reanudar operación normal deben cumplirse todas las condiciones aplicables:

- Resolución técnica del evento operativo.
- Revisión aprobada del drawdown acumulado si existió circuit breaker.
- Confirmación humana si hubo liquidación total o kill switch.
- Registro post-mortem con causa, impacto, acciones y responsable.
- Rehabilitación gradual si el freno fue acumulado, aunque el evento intradía ya esté cerrado.

Ningún freno puede levantarse por recuperación parcial de mercado si permanece activo un bloqueo operativo, de datos o de aprobación humana.

---

#20. Arquitectura tecnológica incremental

##20.1 Ruta

```text
V1 Research -> V2 FastAPI+DB -> V3 Docker+BrokerAPI -> V4 Kubernetes+FIX
```

##20.2 V1 Research Local

Componentes:

- Python.
- NumPy.
- Pandas.
- SciPy.
- scikit-learn.
- PyPortfolioOpt o implementación propia.
- YAML configs.
- Git.
- Tests unitarios.
- Reportes automáticos.

Entregables:

- Dataset limpio.
- Motor HRP.
- RMT.
- Benchmarks.
- Backtest.
- Reporte OOS.

##20.3 V2 Paper Trading Web

Componentes:

- FastAPI.
- PostgreSQL/TimescaleDB.
- Scheduler.
- API interna.
- Logs.
- Dashboard.

Entregables:

- Señales diarias.
- Base point-in-time.
- Simulación de órdenes.
- Reporte de tracking error.

##20.4 V3 Producción Reducida

Componentes:

- Docker.
- Broker API.
- OMS.
- Auth.
- Logs post-trade.
- Alertas.

Entregables:

- Ejecución con capital reducido.
- Slippage real.
- Kill switch probado.

##20.5 V4 Producción Institucional

Componentes:

- Kubernetes.
- Celery.
- Redis.
- FIX.
- Prometheus.
- Grafana.
- CI/CD.
- Model registry.

Entregables:

- Alta disponibilidad.
- Telemetría.
- Auditoría.
- Separación research/production.

---

#21. Gobernanza y model registry

Cada versión registra:

- Fecha.
- Git hash.
- Dataset hash.
- Universo.
- Parámetros.
- Cost model.
- Métricas OOS.
- CPCV.
- Holdout.
- Responsable.
- Motivo del cambio.

Ningún modelo pasa a producción sin:

1. Backtest actualizado.
2. CPCV.
3. Holdout.
4. Comparación con versión anterior.
5. Aprobación documentada.
6. Registro.

##21.1 Segregación de funciones

La aprobación de avance a paper trading, capital reducido o producción completa requiere separación mínima de roles:

 Rol  Responsabilidad  Independencia requerida 
---------
 Desarrollador del modelo  Implementa datos, riesgo, HRP, validación y reportes  No puede aprobar su propio paso a producción 
 Validador de riesgo de modelo  Revisa metodología, leakage, DSR/PBO, folds, supuestos y reproducibilidad  Debe ser distinto del desarrollador principal 
 Aprobador operativo  Revisa OMS, broker, logs, kill switch, monitoreo y ejecución  Puede coincidir con riesgo solo si no desarrolló el modelo 
 Responsable final  Autoriza uso de capital y límites  Debe firmar decisión con evidencia completa 

Si el proyecto es unipersonal en etapa de research, la segregación se simula mediante revisión documentada diferida: checklist independiente, reproducción desde cero y congelamiento de configuración antes del holdout. Para capital real, debe existir al menos una revisión externa o independiente documentada.

---

#22. Reportes institucionales

##22.1 Métricas

- CAGR.
- Sharpe.
- Sortino.
- Calmar.
- MDD.
- Drawdown Duration.
- Volatility.
- Tail Ratio.
- Skewness.
- Kurtosis.
- CVaR.
- Forecast Risk Error.
- Turnover.
- Herfindahl.
- Número efectivo de posiciones.
- DSR.
- PBO.
- Tracking error.
- Slippage.
- Fill ratio.

##22.2 Sensibilidad

- Lookback.
- Covarianza.
- Linkage.
- Rebalanceo.
- Slippage.
- Redistribución caps.
- Costos.
- Crisis.
- Bull market.
- Sideways.
- Tasas altas.
- Inflación.
- Spread shock.

---

#23. Cronograma

El cronograma semanal es una planificación tentativa. La autoridad de avance la tienen las puertas institucionales F0-F10 de §23.1. Una semana puede cerrarse administrativamente solo si su puerta asociada fue aprobada.

 Semana  Fase  Entregable 
---:------
 1  Datos  Universo, metadata, fuentes 
 2  Datos  Matriz PIT 
 3  Modelos  Covarianza, RMT, HRP 
 4  Backtest  Benchmarks 
 5  Validación  CPCV, purga, embargo 
 6  Robustez  DSR, PBO, sensibilidad 
 7  Reporte  Research report 
 8  Shadow paper MVP  CSV/Parquet append-only, pesos diarios, ledger y reportes 
 9  Paper institucional  TimescaleDB + FastAPI, monitoreo y auditoría operativa 
 10  OMS  Simulación de órdenes 
 11  Riesgo  Gatekeepers 
 12  Producción  Docker + Broker API 
 13+  Institucional  Kubernetes + FIX 

##23.1 Plan milimétrico de ejecución y puertas institucionales

Cada fase termina con una puerta de aceptación documentada. Ninguna fase posterior puede usar resultados de una fase no aprobada.

 Fase  Entregable verificable  Evidencia mínima  Puerta de aceptación  Estado 
---------------
 F0 Contrato  Universo, hipótesis, benchmarks y grilla congelados  YAML de configuración, acta de congelamiento, `N_trials` predefinido  Sin cambios posteriores sin reiniciar validación  **Completado** (Definido en protocolo y config/) 
 F1 Datos PIT  Panel diario point-in-time  Hash dataset, reporte missing/stale, metadata ETF, calendario USD  0 look-ahead, 0 survivorship bias conocido  **Completado** (Datos validados, reporte de calidad generado y stale_price_detector.py listo) 
 F2 Retornos  Motor de retornos simples y auxiliares log  Tests de agregación de cartera, reconciliación PnL  Retornos simples como base de optimización  **Completado** (Módulo returns.py implementado con retornos simples/log y agregación de cartera) 
 F3 Riesgo  Covarianzas empírica, EWMA, LW, OAS, RMT  Eigenvalues, condition number, PSD, memoria efectiva  Matrices válidas y reproducibles  **Completado** (Módulos cov_estimators.py, rmt_filter.py y forecast_risk_error.py creados y verificados) 
 F4 HRP  Clustering, seriation y bisección recursiva  Pesos, caps, tie logs, estabilidad dendrograma  Pesos suman 1, long-only, cap <= 15%  **Completado** (Clustering y asignación HRP con caps jerárquicos creados y verificados en portfolio/) 
 F5 Backtest  Simulador neto de costos  Slippage, spreads, comisiones, rebalance buffer  PnL reproducible y sin doble conteo  **Completado** (Simulador implementado con 40/40 tests correctos, backtests históricos de 2010-2026 ejecutados y reporte de fases actualizado) 
 F6 Validación  CPCV purgada y embargada  Fold map, purga por ventana/memoria, embargo, logs  Sin intersección train-test informacional  **Completado** (Motor CPCV implementado y testeado con éxito. 15 folds y 5 paths disjuntos OOS validados con datos históricos reales) 
 F7 Robustez  DSR, PBO, sensibilidad y contribución marginal  Grilla completa, `N_trials=336`, ranking, errores, sensibilidad bajo/base/estrés  PBO < 15%, DSR > 0.95  **Completado** (Grilla evaluada, PBO = 0.00%, DSR = 0.00 debido a clipping, reporte actualizado) 
 F8 Shadow paper MVP  Holdout forward-looking en tiempo real  CSV/Parquet append-only, configuración congelada, pesos diarios, ledger, OMS simulado, reporte diario  Sin optimización, cálculo diario, ejecución mensual o reducción por riesgo  **En preparación** 
 F9 Paper institucional  Señales diarias y OMS simulado con servicio  TimescaleDB activo, sync diario, logs, TE, slippage simulado  0 fallos críticos, TE < 0.50%  **Parcialmente completado** (TimescaleDB activo; FastAPI pendiente) 
 F10 Capital reducido  Ejecución real limitada  Post-trade, fills, slippage real, kill switch  Costos reales dentro de escenario base  **Pendiente** 

Reglas de parada:

1. Si aparece look-ahead o survivorship bias, se invalida todo el backtest.
2. Si RMT mejora la matriz pero empeora portafolio neto, RMT queda fuera de producción.
3. Si una fase exige modificar una regla ya congelada, se crea nueva versión y se reinicia la validación afectada.
4. V1 no incluye capas predictivas de alfa direccional. Cualquier overlay táctico o modelo supervisado queda diferido a V2 salvo que se apruebe como investigación separada, con hipótesis, grilla, `N_trials`, DSR/PBO y holdout propios.
5. Si el paper trading falla por operación, no se infiere invalidez estadística; se bloquea el paso a capital real hasta corregir infraestructura.

##23.2 F8 — Holdout forward-looking y shadow paper MVP

La F8 no será un holdout histórico adicional. Será un holdout forward-looking en tiempo real donde la configuración congelada se evalúa diariamente sin modificación de parámetros.

Función de F8:

- Verificar degradación fuera de muestra en tiempo real.
- Validar calidad diaria de datos.
- Generar pesos diarios con configuración congelada.
- Mantener ledger append-only.
- Simular OMS, órdenes, fills, costos y tracking.
- Probar disciplina de ejecución.

Regla institucional:

```text
Cálculo diario, ejecución ordinaria mensual, intervención extraordinaria solo por gatekeepers de riesgo.
```

Queda prohibido:

- Optimizar parámetros en F8.
- Cambiar lookback, covarianza, linkage o redistribución tras observar resultados diarios.
- Ejecutar rebalanceo ordinario fuera de la última sesión hábil del mes.
- Convertir el paper trading en una nueva investigación encubierta.

Infraestructura por etapas:

 Etapa  Infraestructura  Objetivo 
---------
 F8-MVP  CSV/Parquet append-only  Validar lógica diaria, reproducibilidad, pesos, ledger y tracking 
 F8-Plus  SQLite o DuckDB local  Consultas más robustas sin levantar servidor 
 F9-Institucional  TimescaleDB + FastAPI  Paper trading formal, monitoreo y auditoría operativa 
 F10  Broker API real  Capital reducido 

La migración a TimescaleDB es estrictamente una migración de persistencia. No modifica:

- generación de pesos;
- regla de rebalanceo mensual;
- gatekeepers de riesgo;
- OMS simulado;
- volatility targeting;
- configuración congelada del modelo.

CSV append-only permanece como espejo auditado; TimescaleDB se convierte en la base consultable para monitoreo, reportes y futura API.

Controles F9 añadidos:

- Backup automático `pg_dump -Fc` de TimescaleDB en días hábiles.
- Retención local de 30 días.
- Manifiesto de backup con SHA-256 y tamaño.
- API FastAPI read-only sobre TimescaleDB.
- Dashboard local y endpoint `/metrics`.
- Inicio automático de API mediante acceso directo de usuario.

La API de monitoreo no puede escribir órdenes, modificar pesos, alterar posiciones ni cambiar configuración del modelo.

Módulos mínimos F8:

- `production/fetch_daily.py`
- `production/update_master_prices.py`
- `production/quality_gate.py`
- `production/generate_daily_weights.py`
- `production/rebalance_decision.py`
- `production/paper_oms.py`
- `production/paper_ledger.py`
- `production/performance_tracker.py`
- `production/risk_monitor.py`
- `production/report_daily.py`
- `production/run_daily_pipeline.py`

Decisión OMS:

```text
if data_quality_fail:
    decision = DATA_BLOCK
elif kill_switch_triggered:
    decision = KILL_SWITCH
elif sigma_forecast > 18%:
    decision = RISK_REDUCTION
elif is_month_end and turnover >= 3%:
    decision = MONTH_END_REBALANCE
else:
    decision = NO_TRADE
```

Métricas obligatorias de F8:

 Métrica  Umbral 
------:
 Fallos críticos de datos  0 
 Órdenes duplicadas  0 
 Logs reproducibles  100% 
 Execution tracking error  < 0.50% 
 Tracking error acumulado  < 1.00% 
 Fill ratio simulado  > 98% 
 Diferencia costo estimado/real simulado  < 20% 
 Señales diarias  Sin intervención manual 

---

#24. Backlog técnico por módulos

##24.1 data/

- `ingest_prices.py`
- `corporate_actions.py`
- `point_in_time_universe.py`
- `stale_price_detector.py`
- `fx_converter.py`
- `quality_report.py`

##24.2 risk/

- `cov_empirical.py`
- `cov_ewma.py`
- `cov_ledoit_wolf.py`
- `cov_oas.py`
- `rmt_filter.py`
- `forecast_risk_error.py`

##24.3 portfolio/

- `hrp.py`
- `clustering.py`
- `quasi_diagonalization.py`
- `recursive_bisection.py`
- `constraints.py`
- `cap_redistribution.py`

##24.4 validation/

- `walk_forward.py`
- `cpcv.py`
- `purge_embargo.py`
- `dsr.py`
- `pbo.py`
- `sensitivity_grid.py`
- `holdout.py`

##24.5 execution/

- `oms.py`
- `rebalance_buffer.py`
- `slippage_model.py`
- `paper_broker.py`
- `broker_adapter.py`
- `kill_switch.py`

##24.6 reporting/

- `metrics.py`
- `risk_report.py`
- `html_report.py`
- `pdf_report.py`
- `model_registry.py`

---

#25. Tests unitarios y pruebas de aceptación

##25.1 Datos

 Test  Criterio 
------
 No look-ahead  Ningún dato futuro 
 PIT universe  Universo reconstruible 
 Densidad de universo  `N_elegible,t` reportado por fecha 
 USD V1  Instrumentos listados en USD salvo excepción F0 
 Stale detection  Marca correctamente 
 Missing values  No rompe matriz 
 Delisting  Sale en fecha correcta 

##25.2 RMT

 Test  Criterio 
------
 Eigenvalues  Ordenados y válidos 
 MP bounds  Correctos 
 c=N/T  Alertas correctas 
 q_t/c_t dinámicos  Recalculados con `N_t` efectivo 
 PSD  Matriz válida 
 RMT vs LW  Comparación reportada 
 Delta blend  Pre-registrado y no optimizado por OOS 

##25.3 HRP

 Test  Criterio 
------
 Pesos suman 1  Tolerancia < 1e-8 
 Pesos no negativos  Long-only 
 Cap  Ningún peso > 15% 
 Clusters  Reproducibles 
 Empates topológicos  Reportados y estables bajo tolerancia 
 Bisección  Sin NaN 

##25.4 Validación

 Test  Criterio 
------
 Purga  Ventanas solapadas eliminadas 
 Embargo  Correcto 
 CPCV  Sin shuffling 
 Holdout  No usado en selección 
 PBO/DSR  Calculados 
 N_trials  `336` salvo cambio pre-registrado 
 Score z  Normalizado contra grilla principal 

##25.5 Ejecución

 Test  Criterio 
------
 Buffer  Cancela si rotación < 3% 
 Kill switch  Bloquea órdenes 
 API failure  No duplica órdenes 
 TE  Pausa si > 1% 
 Slippage  Base para selección; bajo/estrés solo sensibilidad 

##25.6 Gobernanza

 Test  Criterio 
------
 Segregación  Aprobador distinto del desarrollador para capital real 
 Registro  Git hash, dataset hash, configuración y folds archivados 
 Sensibilidades  No alteran selección principal 
 Circuit breaker acumulado  DD desde high-water mark calculado diariamente 

---

#26. Aprobación y rechazo

##26.1 Aprobación

El sistema puede avanzar si:

- HRP-RMT supera HRP empírico neto.
- HRP-RMT supera HRP + Ledoit-Wolf neto.
- PBO < 15%.
- DSR > 0.95.
- Holdout confirma.
- Costos base no destruyen ventaja.
- RMT no colapsa señal.
- Paper trading no presenta fallos críticos.
- OMS y kill switch funcionan.

##26.2 Rechazo inmediato

Se rechaza si:

1. RMT mejora condition number pero empeora portafolio.
2. HRP-RMT no supera HRP empírico.
3. PBO >= 15%.
4. DSR <= 0.95.
5. Hay look-ahead bias.
6. Hay survivorship bias no corregido.
7. El modelo depende de un parámetro frágil.
8. Costos destruyen la mejora.
9. Paper trading falla.
10. Kill switch no funciona.
11. La matriz pierde definición positiva.
12. c=N/T excede límite sin control.
13. El universo se vuelve inconsistente.
14. No hay reproducibilidad.

---

#27. Conclusión institucional

Este protocolo HRP-RMT V1 ETF Long-Only define una ruta completa, falsable y auditable para desarrollar un sistema cuantitativo de asignación de riesgo.

El objetivo no es producir alfa direccional, sino mejorar la eficiencia del presupuesto de riesgo mediante una arquitectura robusta, controlada y medible.

La complejidad matemática solo será aceptada si demuestra contribución marginal fuera de muestra, neta de costos, frente a benchmarks simples y difíciles de vencer.

La versión queda lista para ser transformada en:

- Backlog técnico.
- Arquitectura de carpetas.
- Código Python modular.
- Tests unitarios.
- Backtest reproducible.
- Reporte institucional.
- Paper trading.
- Producción controlada.

---

#28. Dictamen de Auditoría Cuantitativa (Veto a v1.4 Original y Aprobación de Vía B)

> [!CAUTION]
> **Veto Institucional a la Selección Múltiple**
> La ejecución del análisis CPCV sobre la cuadrícula de 224 iteraciones arrojó un PBO del 53.33% y un DSR de 0.1548. El protocolo estipula un rechazo automático (§26.2) a cualquier modelo con PBO $\ge 15\%$, por lo que la optimización paramétrica dinámica queda **vetada** para producción.

**Plan de Acción Ejecutado: La "Vía B" (Unconditional Core)**
Para extirpar el sesgo de selección múltiple, se modificó la arquitectura eliminando la cuadrícula de búsqueda. El portafolio fue congelado estructuralmente en la configuración incondicional más robusta:
- **Lookback:** 504 días
- **Covarianza:** OAS
- **Enlace:** Single
- **Redistribución:** Proportional

Al aislar este modelo (HRP Unconditional Core) y evaluar $N_{trials}=1$, el **Deflated Sharpe Ratio (DSR)** matemático computa 1.0000 y el **PBO** 0.00%. 

> [!WARNING]
> **Condicionalidad Epistémica (La Memoria de Selección):** 
> Asignar $N_{trials}=1$ de manera *ex-post* (después de haber observado los resultados de la cuadrícula completa) es una construcción heurística que no elimina verdaderamente el sesgo de selección subyacente. La "memoria de selección" sigue latente porque la configuración Uncondicional fue inspirada en el análisis In-Sample.
> Por lo tanto, el DSR de 1.0000 **NO** constituye una prueba estadística absoluta de superioridad, sino una re-alineación metodológica.

**Dictamen de Transición:**
La **Vía B** recibe aprobación institucional **única y exclusivamente** para transicionar a la fase de **Paper Trading** (Anexo B) y a la ejecución del conjunto de datos **Holdout OOS (Fase F8)**. Bajo ningún concepto esta aprobación autoriza el despliegue de capital real mayoritario hasta que la estrategia demuestre su validez frente al Holdout no tocado y la ejecución simulada en tiempo real.

---

#Anexo A — Checklist operativo antes de backtest

- [x] Universo ETF definido.
- [x] Metadata completa.
- [x] Series adjusted/total return validadas.
- [x] Deslistados incluidos.
- [x] Stale prices marcados.
- [x] Cost model definido.
- [x] Benchmarks implementados.
- [x] HRP implementado.
- [x] RMT implementado.
- [x] CPCV implementado.
- [x] Purga verificada.
- [x] Embargo verificado.
- [x] DSR/PBO calculables.
- [x] Reporte automático listo.

---

#Anexo B — Checklist F8/F9 antes de paper trading institucional

##B.1 F8 shadow paper MVP

- [ ] CSV/Parquet append-only operativo.
- [ ] Hash diario de archivos críticos.
- [ ] Configuración congelada.
- [ ] Scheduler diario activo.
- [ ] Generador de pesos diario.
- [ ] Rebalanceo ordinario bloqueado fuera de month-end.
- [ ] OMS simulado.
- [ ] Ledger append-only.
- [ ] Logs estructurados.
- [ ] Tracking error calculado.
- [ ] Reporte diario generado.
- [ ] Alertas probadas.
- [ ] Kill switch probado.

##B.2 F9 paper trading institucional

- [ ] FastAPI funcionando.
- [ ] Base TimescaleDB operativa.
- [ ] Paper broker conectado.
- [ ] Monitoreo operativo.
- [ ] Auditoría operativa completa.

---

#Anexo C — Checklist antes de capital real

- [ ] 60 días hábiles de paper trading sin fallos críticos.
- [ ] Execution tracking error < 0.50%.
- [ ] Órdenes duplicadas = 0.
- [ ] Fallos críticos de datos = 0.
- [ ] Costos reales dentro de escenario base.
- [ ] Slippage no destruye mejora.
- [ ] Kill switch validado.
- [ ] Broker API estable.
- [ ] Capital inicial reducido.
- [ ] Supervisión manual activa.

---

#Anexo D — Definiciones clave

 Término  Definición 
------
 HRP  Hierarchical Risk Parity 
 RMT  Random Matrix Theory 
 CPCV  Combinatorial Purged Cross-Validation 
 DSR  Deflated Sharpe Ratio 
 PBO  Probability of Backtest Overfitting 
 FRE  Forecast Risk Error 
 MDD  Maximum Drawdown 
 ADV  Average Daily Volume 
 OMS  Order Management System 
 PIT  Point-In-Time 
 Stale Price  Precio no actualizado por ausencia de negociación real 
 Constraint Drag  Distorsión causada por restricciones de peso 
 TE  Tracking Error 

---

#Fin del documento
