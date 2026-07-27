# Resumen del Portafolio Cuantitativo

**Autor:** Santiago Alejandro Naranjo Reyes  
**Perfil:** Analista Cuantitativo / Desarrollador de Sistemas de Trading & Riesgo  
**Contacto:** [santiagonaranjofinanzas-droid@gmail.com](mailto:santiagonaranjofinanzas-droid@gmail.com)

---

## Presentacion Ejecutiva

Estudiante de Economia en la Universidad de las Fuerzas Armadas ESPE especializado en **Finanzas Cuantitativas, Modelado Estocastico y Desarrollo de Sistemas de Trading Algoritmico**.

Este portafolio consolida 7 proyectos principales desarrollados en Python, C++, MQL5, R y TypeScript, cubriendo desde la investigacion matematica de alfa y estimacion de regímenes de mercado hasta motores de ejecucion sin latencia y plataformas full-stack de operaciones.

---

## Indice Jerarquico de Proyectos

| Prioridad | Proyecto / Repositorio                                 | Categoria Principal              | Tecnologias Clave                          | Estado        |
| :-------: | :----------------------------------------------------- | :------------------------------- | :----------------------------------------- | :-----------: |
| #1        | [trading-journal](trading-journal/README.md)           | Plataforma de Operaciones Quant  | FastAPI, Streamlit, SQLite, Supabase, MQL5 | Produccion    |
| #2        | [hmm-market-regimes](hmm-market-regimes/README.md)     | Modelado Estocastico & Regimenes | Python, Arch, C++, MQL5, MetaTrader 5      | Completado    |
| #3        | [time-series-momentum](time-series-momentum/README.md) | Momentum Sistematico             | Python, Pandas, Statsmodels, SciPy         | Completado    |
| #4        | [hrp-rmt-portfolio](hrp-rmt-portfolio/README.md)       | Optimizacion de Portafolios      | Python, SciPy, Scikit-Learn, Tiingo API    | Completado    |
| #5        | [trend-classification](trend-classification/README.md) | Machine Learning Financiero      | Python, XGBoost, LightGBM, Scikit-Learn    | Completado    |
| #6        | [thesis-project](thesis-project/README.md)             | Econometria & Investigacion      | R, Python, MathJax, Econometria PCA        | En Desarrollo |
| #7        | [academic-assistant](academic-assistant/README.md)     | Full-Stack & Automatizacion      | TypeScript, Next.js, Supabase, Telethon    | Desplegado    |

---

## Descripcion Sintetica por Proyecto

### 1. Trading Journal & Operations Platform (`trading-journal`)
- **Objetivo:** Centralizar el registro de ejecuciones, analitica de riesgo en tiempo real y sincronizacion automatizada con el broker.
- **Arquitectura:** Backend REST en FastAPI, interfaz analitica en Streamlit, persistencia en SQLite/Supabase y patron de cola outbox para MT5.
- **Métricas Clave:** Cero pérdida de datos, calculo automatico de Sharpe, Sortino, VaR y monitoreo de drawdown.

### 2. Deteccion de Regimenes de Mercado HMM (`hmm-market-regimes`)
- **Objetivo:** Mitigar drawdowns por cambios bruscos de regimen en estrategias sistematicas.
- **Arquitectura:** Filtro de Hamilton HMM + Salto-Difusion de Merton + GJR-GARCH(1,1) + motor C++/MQL5 sin latencia.
- **Metricas Clave:** Separacion estadistica significativa de estados de alta/baja volatilidad y paridad matematicas estricta.

### 3. Motor Time Series Momentum (`time-series-momentum`)
- **Objetivo:** Capturar momentum multiactivo controlando el drawdown mediante escalado de volatilidad.
- **Arquitectura:** Diferenciacion fraccional de ventana fija, volatility targeting y asignacion por paridad de riesgo.
- **Metricas Clave:** Curva de capital suavizada con drawdown maximo acotado en futuros y divisas.

### 4. Optimizacion de Portafolios HRP & RMT (`hrp-rmt-portfolio`)
- **Objetivo:** Eliminar el ruido de estimacion de la matriz de covarianza en la asignacion de activos.
- **Arquitectura:** Desparasitado mediante Teoría de Matrices Aleatorias (RMT) y clustering grafico con Hierarchical Risk Parity (HRP).
- **Metricas Clave:** Desempeño Out-of-Sample superior en Sharpe Ratio y menor drawdown que los benchmarks tradicionales.

### 5. Clasificacion Supervisada de Tendencia (`trend-classification`)
- **Objetivo:** Predecir tendencias direccionales mediante machine learning sin sesgo de sobreajuste.
- **Arquitectura:** Etiquetado por Método de Triple Barrera, caracteristicas fraccionales y ensambles XGBoost/LightGBM bajo CPCV.
- **Metricas Clave:** Scores ROC-AUC estadísticamente significativos fuera de muestra sin fuga de datos.

### 6. Tesis de Investigacion Macro-Financiera (`thesis-project`)
- **Objetivo:** Modelar la transmision no lineal de shocks macroeconomicos a la volatilidad financiera.
- **Arquitectura:** Analisis de Componentes Principales (PCA) para el Indice de Estres Financiero (ISRI) y regímenes HMM.
- **Metricas Clave:** Validacion empirica del derrame de volatilidad en mercados financieros latinoamericanos.

### 7. Asistente Academico & Automatizacion (`academic-assistant`)
- **Objetivo:** Automatizar el seguimiento de horarios universitarios, entregas de tareas y alertas de notificacion.
- **Arquitectura:** Plataforma web full-stack en Next.js respaldada por Supabase PostgreSQL y bots de Python.
- **Metricas Clave:** Notificaciones automatizadas en tiempo real via Telegram.
