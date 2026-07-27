# SANTIAGO ALEJANDRO NARANJO REYES
**Analista Cuantitativo | Desarrollador de Sistemas de Trading Algoritmitco & Riesgo**  
Quito, Ecuador | santiagonaranjofinanzas-droid@gmail.com | +593 958788322  
**Portafolio GitHub:** [github.com/santiagonaranjofinanzas-droid/Portafolio_Santiago_Naranjo](https://github.com/santiagonaranjofinanzas-droid/Portafolio_Santiago_Naranjo)  
**Perfil GitHub:** [github.com/santiagonaranjofinanzas-droid](https://github.com/santiagonaranjofinanzas-droid) | **LinkedIn:** [LINKEDIN_URL]

---

## PERFIL PROFESIONAL

Estudiante de Economia en la Universidad de las Fuerzas Armadas ESPE especializado en **Finanzas Cuantitativas, Modelado Estocastico de Mercado e Ingenieria de Software de Produccion**. Capacidad demostrada para diseñar el ciclo de vida completo de sistemas cuantitativos: desde la formulacion matematica de alfa (Hidden Markov Models, GJR-GARCH, Diferenciacion Fraccional, HRP/RMT) y la validación fuera de muestra anti-sobreajuste (CPCV), hasta motores de ejecucion sin latencia en C++/MQL5 y plataformas full-stack de operaciones en FastAPI y Streamlit. Busco posicionarme en roles de Junior Quant Analyst, Quant Researcher, Quantitative Developer o Risk Analyst en firmas de trading sistematico, hedge funds, asset management o fintechs.

---

## COMPETENCIAS TECNICAS Y MODELADO

| Dominio | Herramientas y Metodologias |
| :--- | :--- |
| **Finanzas Cuantitativas & Riesgo** | Modelos Ocultos de Markov (HMM), Merton Jump Diffusion, GJR-GARCH(1,1), Value at Risk (VaR), Extreme Value Theory (EVT), Criterio de Kelly Fraccional, Volatility Targeting. |
| **Optimizacion & Machine Learning** | Hierarchical Risk Parity (HRP), Random Matrix Theory (RMT - Marchenko-Pastur), Triple Barrera, Combinatorial Purged Cross-Validation (CPCV), XGBoost, LightGBM, Scikit-Learn. |
| **Lenguajes de Programacion** | Python (Pandas, NumPy, Arch, Scikit-Learn, SciPy, Statsmodels), C++, MQL5, R (Econometria), TypeScript, SQL. |
| **Desarrollo de Software & Arquitectura** | FastAPI, Streamlit, Peewee ORM, SQLite, Supabase PostgreSQL, REST APIs, Outbox Event Queue, Docker, Git. |

---

## PROYECTOS CUANTITATIVOS DESTACADOS

### 1. Plataforma de Journal de Trading Cuantitativo y Operaciones (`trading-journal`)
* **Arquitectura:** Desarrolle una plataforma de operaciones cuantitativas full-stack integrada por un backend REST en FastAPI, panel analitico interactivo en Streamlit, persistencia en SQLite/Supabase y patron Outbox Queue para MetaTrader 5.
* **Impacto y Metricas:** Registro automatizado de ejecuciones con cero pérdida de datos, integracion de agentes de diagnostico con IA (Ollama/Nvidia API) y calculo automatizado de Sharpe, Sortino, VaR y monitoreo de drawdown.

### 2. Motor Estocastico de Regimenes HMM y Ejecucion Zero-Lag (`hmm-market-regimes`)
* **Modelado:** Diseñe un marco estocastico de 3 capas con filtro de Hamilton sobre HMM para clasificar regímenes latentes de alta/baja volatilidad, varianza condicional GJR-GARCH(1,1), estimador Corwin-Schultz y Stop Loss por EVT.
* **Producción:** Portabilidad matematica estricta entre la investigacion en Python y un motor de ejecucion en C++/MQL5 en MetaTrader 5 bajo politica Zero-Lag, validado mediante CPCV con purging y embargo.

### 3. Motor Time Series Momentum & Volatility Targeting (`time-series-momentum`)
* **Metodologia:** Implemente una estrategia sistematica de seguimiento de tendencia multiactivo aplicando diferenciacion fraccional de ventana fija ($d \in [0.3, 0.7]$) para inducir estacionariedad preservando memoria de la serie.
* **Control de Riesgo:** Escalado dinámico de volatilidad (Volatility Targeting) y asignacion por Paridad de Riesgo, logrando curvas de capital suavizadas en futuros y divisas.

### 4. Optimizacion de Portafolios HRP & RMT (`hrp-rmt-portfolio`)
* **Filtrado de Covarianza:** Combine la Teoría de Matrices Aleatorias (RMT) con la distribucion Marchenko-Pastur para desparasitar eigenvalores de ruido en la matriz de covarianza antes del clustering grafico con Hierarchical Risk Parity (HRP).
* **Desempeño:** Supero estadísticamente a los benchmarks 60/40 y Equal-Weight en Sharpe Ratio fuera de muestra y menor drawdown maximo.

---

## EXPERIENCIA PROFESIONAL

### Profesor de Econometria y Trading | Independiente
*Quito, Ecuador | 2023 - Presente*
* Imparticion de capacitaciones intensivas en econometria aplicada de series temporales y modelizacion estadistica avanzada en R y Python.
* Diseño de simulaciones cuantitativas practicas con datasets financieros reales enfocado en la gestion de riesgo y control de drawdown.

### Inversor y Planificador de Portafolios | Gestion Patrimonial Personal
*Quito, Ecuador | 2022 - Presente*
* Estructuracion y rebalanceo de portafolios diversificados (ETFs, Criptoactivos, Commodities) bajo parametros de Value at Risk (VaR) y ratio beneficio/riesgo.
* Ejecucion de trading intradia bajo estricto control estadistico de expectativas matematicas.

### Analista Bursatil y Trader | GenfinSchool
*Quito, Ecuador | 2024*
* Desarrollo de reportes diarios de mercado orientados a activos de alta volatilidad y backtesting de estrategias cuantitativas.

---

## EDUCACION Y CERTIFICACIONES

* **Licenciatura en Economia (8vo Semestre)** — Universidad de las Fuerzas Armadas ESPE | *2023 - Presente*
* **Alta Especializacion en Finanzas Cuantitativas** — CIIP LATAM | *2025*
* **Especializacion en Excel Avanzado y Analisis de Datos** — Camara de Comercio Exterior | *2024 - 2025*
