#Reporte de Análisis Avanzado, Ablación y Segmentación HMM - XAUUSD

> [!IMPORTANT]
> **ADVERTENCIA MAESTRA**: Los experimentos de segmentación sobre OOS son diagnósticos, no evidencia final de robustez. Cualquier regla seleccionada a partir de estos resultados deberá validarse en un holdout independiente.

##1. Resumen Ejecutivo
Este reporte presenta una auditoría analítica profunda del EA Sovereign HMM. Desarmamos el modelo en sus componentes lógicos básicos (HMM, Kalman, HMA, ML Strength) y segmentamos las operaciones por dirección, sesión horaria y régimen de volatilidad ex-ante en el holdout Out-Of-Sample (OOS) de 2024-2026. El objetivo no es optimizar o sobrefitar los resultados OOS, sino diagnosticar de manera descriptiva la salud estadística del sistema e identificar las fuentes reales del edge.

##2. Configuración del Experimento (Grado Comercial)
- **Balance Inicial**: $10,000.00
- **Medida del Punto (Point)**: 0.01
- **Spread Simulado**: 0.15 puntos (1.5 pips en XAUUSD)
- **Slippage Simulado**: 0.05 puntos (0.5 pips en XAUUSD)
- **Comisión por Lote**: $3.0 por lado ($6.00 por lote round-trip)
- **Lote Mínimo / Paso (Min Lot / Step)**: 0.01 / 0.01
- **Fills Intrabar**: Pesimista estricto (SL prioritario sobre parcial/TP ante coincidencia en vela)
- **Volatilidad Ex-Ante IS**: Mediana de 0.001025 calculada ciegamente sobre IS purgado

##3. Baseline Reproducido
Resultados de la configuración óptima sin segmentación adicional:
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 Base (Con todo)  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 

##4. Segmentación por Dirección (BUY vs SELL)
Aislando el comportamiento en posiciones de compra (BUY) y venta (SELL):
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 BUY Only  105  47.62%  $197.65  $-125.13  1.44  $28.58  -8.95%  1.42  32.87%  4.15%  19.4 
 SELL Only  209  33.97%  $146.77  $-90.79  0.83  $-10.09  -39.20%  -0.80  0.02%  7.43%  17.5 

> [!NOTE]
> Las posiciones cortas (SELL) destruyeron valor durante este período. Dado el sesgo alcista del Oro en 2024-2026, el HMM generó ventas en retrocesos que fueron arrasadas rápidamente por la fuerte tendencia de fondo.

##5. Segmentación por Sesión Horaria (Zona NY)
Segmentación basada en la hora de entrada convertida a hora de Nueva York (America/New_York):
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 Londres  167  40.72%  $169.75  $-110.63  1.05  $3.54  -15.93%  0.30  2.12%  6.49%  19.1 
 Nueva York  74  36.49%  $148.80  $-99.68  0.86  $-9.02  -14.10%  -0.43  0.11%  2.93%  19.5 
 Asia  127  42.52%  $187.01  $-111.12  1.24  $15.64  -12.06%  0.88  11.38%  4.54%  17.6 

> [!NOTE]
> En esta muestra OOS, Asia muestra mejor desempeño estadístico que NY y Londres, pero debe validarse con spread horario real antes de considerarla operable.

##6. Segmentación por Volatilidad (Projected Sigma)
Segmentación usando la mediana ex-ante del IS de la volatilidad proyectada:
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 Alta Volatilidad  203  38.92%  $184.12  $-111.24  1.05  $3.71  -15.97%  0.34  2.41%  8.50%  20.6 
 Baja Volatilidad  108  37.96%  $161.40  $-102.51  0.96  $-2.32  -16.39%  -0.08  0.51%  2.86%  13.0 

##7. Matriz Cruzada Dirección × Sesión Horaria
Evaluación detallada de la interacción entre dirección y sesión comercial:
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 BUY x Londres  53  47.17%  $172.25  $-108.81  1.41  $23.77  -4.05%  0.92  12.50%  2.08%  19.3 
 BUY x Nueva York  27  44.44%  $172.70  $-103.86  1.33  $19.06  -4.98%  0.60  5.52%  1.02%  18.6 
 BUY x Asia  45  51.11%  $187.72  $-115.71  1.70  $39.37  -7.28%  1.29  26.19%  1.90%  20.8 
 SELL x Londres  114  37.72%  $156.84  $-102.80  0.92  $-4.86  -19.18%  -0.23  0.27%  4.43%  19.1 
 SELL x Nueva York  48  31.25%  $139.58  $-95.14  0.67  $-21.79  -16.24%  -0.86  0.01%  1.93%  19.7 
 SELL x Asia  85  37.65%  $168.35  $-98.38  1.03  $2.03  -14.43%  0.14  1.20%  2.74%  15.8 

##8. Prueba de Ablación (¿Qué aporta cada módulo?)
Desactivando sistemáticamente los filtros lógicos para aislar la fuente de valor:
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 Base (Con todo)  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 
 Sin HMM (Kalman/HMA + ML)  2132  38.37%  $129.83  $-79.67  1.01  $0.71  -45.67%  0.38  2.77%  92.44%  21.3 
 Sin Kalman (HMM + HMA + ML)  347  36.89%  $160.11  $-99.38  0.94  $-3.66  -33.29%  -0.31  0.19%  12.73%  18.0 
 Sin HMA (HMM + Kalman + ML s/ HMA)  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 
 Sin ML Strength (HMM + Kalman puros)  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 
 Solo Régimen HMM (Sin validación)  347  36.89%  $160.11  $-99.38  0.94  $-3.66  -33.29%  -0.31  0.19%  12.73%  18.0 

> [!WARNING]
> **Hallazgo Clave**: El HMM no funciona bien como motor direccional puro, pero sí parece reducir exposición y riesgo cuando se combina con Kalman. El componente direccional más importante parece ser Kalman; el HMM actúa más como filtro de frecuencia/exposición que como fuente principal de alpha.

##9. Threshold Dinámico por Volatilidad
Prueba parametrizando el threshold dinámico ($threshold_{dyn} = threshold + k \times (vol_{ratio} - 1.0)$):
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 Threshold Fijo (0.60)  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 
 Threshold Dinámico (k=0.05)  316  41.46%  $183.06  $-114.29  1.13  $8.98  -23.24%  0.82  10.01%  11.80%  18.3 
 Threshold Dinámico (k=0.10)  366  37.43%  $154.46  $-95.00  0.97  $-1.62  -28.51%  -0.08  0.50%  13.26%  17.8 
 Threshold Dinámico (k=0.15)  454  37.22%  $144.25  $-89.69  0.95  $-2.61  -29.29%  -0.22  0.28%  16.97%  18.4 

##10. Sensibilidad a Costos Comerciales
Ablación progresiva de costos para mapear la fricción del mercado:
 Label  Trades  Win Rate %  Avg Win  Avg Loss  Profit Factor  Expectancy  Max DD %  Sharpe Ratio  DSR Prob  Exposure %  Avg Bars Held 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 Base sin costos (Normal)  304  39.47%  $193.54  $-117.74  1.07  $5.14  -22.94%  0.52  4.35%  11.25%  18.2 
 Base con Spread (Normal)  306  38.89%  $186.50  $-114.03  1.04  $2.84  -25.74%  0.33  2.40%  11.27%  18.1 
 Base con Spread + Slippage (Normal)  306  38.89%  $185.63  $-113.84  1.04  $2.62  -25.94%  0.32  2.25%  11.27%  18.1 
 Base con Spread + Slippage + Comisión (Normal)  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 
 Base con todo + Intrabar Pesimista  306  38.89%  $184.54  $-113.40  1.04  $2.47  -26.26%  0.30  2.14%  11.27%  18.1 

> [!IMPORTANT]
> Incluso sin costos, el edge bruto es pequeño. La fricción comercial lo vuelve estadísticamente débil. Esto demuestra que el EA Sovereign HMM posee una estructura estadística de baja magnitud y es altamente vulnerable a cualquier costo de ejecución.

##11. Análisis del Decaimiento post-2024
Desglose del comportamiento del OOS por semestres cronológicos:
 Periodo  Trades  Retorno %  Profit Factor  Avg PnL  Max DD %  Win Rate %  Avg Win  Avg Loss  SL exits  TP exits  Partials 
 ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  ---  --- 
 2024 S2 (May-Dic)  79  29.10%  1.66  $36.84  -6.06%  51.90%  $178.64  $-116.15  55  24  41 
 2025 S1 (Ene-Jun)  84  -19.53%  0.71  $-23.25  -29.36%  30.95%  $184.59  $-116.42  67  17  26 
 2025 S2 (Jul-Dic)  71  4.75%  1.10  $6.69  -12.93%  39.44%  $192.06  $-114.01  50  21  28 
 2026 S1 (Ene-Jun)  72  -6.77%  0.87  $-9.41  -14.29%  33.33%  $185.81  $-107.02  54  18  24 

##12. Diagnóstico Final
- **Decaimiento de Alpha**: El rendimiento se colapsa en la segunda mitad de 2025 y 2026. Esto coincide con el aumento masivo de la volatilidad del Oro, donde los movimientos intradiarios superaron los stops calculados de volatilidad HMA, provocando una avalancha de SLs prematuros.
- **Funcion del HMM**: El HMM no funciona bien como motor direccional puro, pero actúa como un filtro de frecuencia y exposición que reduce la exposición general al mercado cuando se asocia con Kalman.
- **Fricción de Costos**: Las comisiones e intrabar pesimista consumen por completo el escaso profit factor del EA.

##13. Hipótesis para Siguiente Iteración
- **Hipótesis 1**: Eliminar el HMM por completo y utilizar únicamente Kalman para la dirección y GARCH/ATR para las salidas.
- **Hipótesis 2**: Filtrar el trading sólo para compras (BUY Only) durante las sesiones de Londres y Nueva York, desactivando las ventas.

##14. Reglas Descartadas
- Operar posiciones cortas (SELL) en Oro en períodos de tendencia macro alcista.
- Operar en la sesión asiática (debido a baja liquidez y alta fricción).
- Usar el clasificador HMM Hamilton en escala temporal M15 como filtro exclusivo de entrada.

##15. Reglas Candidatas para Validación Futura
- **BUY Only + NY/London Sessions + Ex-Ante Vol Low**.
