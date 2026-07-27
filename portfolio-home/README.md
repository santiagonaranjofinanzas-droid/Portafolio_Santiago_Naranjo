# Quantitative Finance & Software Portfolio Hub

**Author:** Santiago Alejandro Naranjo Reyes  
**Positioning:** Quantitative Analyst / Systematic Trading Systems Developer / Econometrician  
**Contact:** [santiagonaranjofinanzas-droid@gmail.com](mailto:santiagonaranjofinanzas-droid@gmail.com) | [LinkedIn Profile]([LINKEDIN_URL])

---

## Portfolio Overview

This central repository indexes 7 production-grade projects spanning stochastic regime modeling, Machine Learning signal classification, portfolio optimization, full-stack trading platforms, and econometric research.

> [!IMPORTANT]
> **Methodological Rigor:** All quantitative models implement strict Out-of-Sample temporal validation, Combinatorial Purged Cross-Validation (CPCV) to eliminate look-ahead bias, and fractional differentiation to induce stationarity while preserving memory.

---

## Project Repository Index

| Priority | Repository Name                                             | Primary Category                 | Key Technologies                           | Status         |
| :------: | :---------------------------------------------------------- | :------------------------------- | :----------------------------------------- | :------------: |
| **#1**   | [`trading-journal`](../trading-journal/README.md)           | Quantitative Operations Platform | FastAPI, Streamlit, SQLite, Supabase, MQL5 | Production     |
| **#2**   | [`hmm-market-regimes`](../hmm-market-regimes/README.md)     | Stochastic Modeling & Regimes    | Python, Arch, C++, MQL5, MetaTrader 5      | Completed      |
| **#3**   | [`time-series-momentum`](../time-series-momentum/README.md) | Systematic Trend-Following       | Python, Pandas, Statsmodels, SciPy         | Completed      |
| **#4**   | [`hrp-rmt-portfolio`](../hrp-rmt-portfolio/README.md)       | Portfolio Construction & Risk    | Python, SciPy, Scikit-Learn, Tiingo API    | Completed      |
| **#5**   | [`trend-classification`](../trend-classification/README.md) | Machine Learning Signals         | Python, XGBoost, LightGBM, Scikit-Learn    | Completed      |
| **#6**   | [`thesis-project`](../thesis-project/README.md)             | Academic Econometrics            | R, Python, MathJax, Econometric PCA        | Research (WIP) |
| **#7**   | [`academic-assistant`](../academic-assistant/README.md)     | Full-Stack & Process Automation  | TypeScript, Next.js, Supabase, Telethon    | Deployed       |

---

## Detailed Project Descriptions

### 1. Trading Journal & Operations Platform (`trading-journal`)
- **Objective:** Centralize trade execution logging, real-time risk analytics, and secure automated broker synchronization.
- **Architecture:** FastAPI REST backend, Streamlit dashboard, SQLite/Supabase database, and HMAC outbox queue for MT5.
- **Key Metrics:** Zero data loss, automated Sharpe, Sortino, VaR, and AI-driven trade diagnostics.
- **Links:** [English Documentation](../trading-journal/README.md) | [Versión en Español](../trading-journal/docs/README_ES.md)

---

### 2. Stochastic HMM Market Regime Detection (`hmm-market-regimes`)
- **Objective:** Mitigate regime shift drawdowns in systematic strategies.
- **Architecture:** 3-layer architecture: Hamilton Filter HMM + Merton Jump Diffusion + GJR-GARCH(1,1) + zero-lag C++/MQL5 engine.
- **Key Metrics:** Statistically significant state separation and zero-lag parity between Python research and MQL5 production.
- **Links:** [English Documentation](../hmm-market-regimes/README.md) | [Versión en Español](../hmm-market-regimes/docs/README_ES.md)

---

### 3. Time Series Momentum Strategy Engine (`time-series-momentum`)
- **Objective:** Capture multi-asset trend momentum while controlling drawdown via volatility scaling.
- **Architecture:** Fixed-window fractional differentiation, volatility targeting, and risk parity capital allocation.
- **Key Metrics:** Smooth equity curve and controlled maximum drawdown across FX and commodity futures.
- **Links:** [English Documentation](../time-series-momentum/README.md) | [Versión en Español](../time-series-momentum/docs/README_ES.md)

---

### 4. HRP & RMT Portfolio Optimization (`hrp-rmt-portfolio`)
- **Objective:** Eliminate covariance matrix estimation noise in asset allocation.
- **Architecture:** Marchenko-Pastur Random Matrix Theory (RMT) denoising combined with Hierarchical Risk Parity (HRP) graph clustering.
- **Key Metrics:** Superior Out-of-Sample Sharpe ratio and lower Maximum Drawdown compared to 60/40 and Equal-Weight benchmarks.
- **Links:** [English Documentation](../hrp-rmt-portfolio/README.md) | [Versión en Español](../hrp-rmt-portfolio/docs/README_ES.md)

---

### 5. Supervised Trend Classification Engine (`trend-classification`)
- **Objective:** Predict market directional trends using machine learning without look-ahead bias.
- **Architecture:** Triple Barrier Method labeling, fractional diff features, and XGBoost/LightGBM ensembles under CPCV.
- **Key Metrics:** Statistically significant Out-of-Sample ROC-AUC scores with zero temporal data leakage.
- **Links:** [English Documentation](../trend-classification/README.md) | [Versión en Español](../trend-classification/docs/README_ES.md)

---

### 6. Macro-Finance Research Thesis (`thesis-project`)
- **Objective:** Model non-linear macroeconomic shock transmission to financial market volatility.
- **Architecture:** Principal Component Analysis (PCA) for economic stress indices (ISRI) combined with HMM regime classification.
- **Key Metrics:** Empirical validation of regime-dependent volatility spillover in Latin American financial markets.
- **Links:** [English Documentation](../thesis-project/README.md) | [Versión en Español](../thesis-project/docs/README_ES.md)

---

### 7. Academic Assistant Automation Platform (`academic-assistant`)
- **Objective:** Automate academic schedule tracking, assignment deadlines, and notification alerts.
- **Architecture:** Next.js full-stack platform backed by Supabase PostgreSQL and Python worker bots.
- **Key Metrics:** Automated real-time Telegram schedule alerts and task management.
- **Links:** [English Documentation](../academic-assistant/README.md) | [Versión en Español](../academic-assistant/docs/README_ES.md)

---

## Technical Competency Matrix Summary

| Competency Domain        | Primary Tools & Methods                              | Demonstrated Repositories                   |
| :----------------------- | :--------------------------------------------------- | :------------------------------------------ |
| **Stochastic Modeling**  | HMM, GJR-GARCH, Merton Jump Diffusion, Kalman Filter | `hmm-market-regimes`, `thesis-project`      |
| **Systematic Execution** | C++, MQL5, MetaTrader 5 API, Zero-Lag Execution      | `hmm-market-regimes`, `trading-journal`     |
| **Portfolio & Risk**     | HRP, RMT, Volatility Targeting, VaR, EVT             | `hrp-rmt-portfolio`, `time-series-momentum` |
| **Machine Learning**     | Triple Barrier, XGBoost, LightGBM, CPCV              | `trend-classification`                      |
| **Full-Stack Software**  | FastAPI, Streamlit, Next.js, React, Supabase, SQLite | `trading-journal`, `academic-assistant`     |
| **Econometrics**         | R, Time Series Analysis, PCA, Hypothesis Testing     | `thesis-project`, `time-series-momentum`    |
