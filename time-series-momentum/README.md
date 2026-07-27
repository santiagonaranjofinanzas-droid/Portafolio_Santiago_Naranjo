# Time Series Momentum (TSMOM) & Volatility Targeting Engine

[ English ] | [ [Versión en Español](docs/README_ES.md) ]

---

## Executive Summary

> [!NOTE]
> **Core Objective:** Implement a systematic multi-asset trend-following engine featuring fixed-window fractional differentiation, volatility scaling, and risk parity capital allocation.

| Dimension               | Specification                                                 |
| :---------------------- | :------------------------------------------------------------ |
| **Strategy Class**      | Systematic Time Series Momentum (TSMOM) / Trend Following     |
| **Stationarity Method** | Fixed-Window Fractional Differentiation ($d \in [0.3, 0.7]$)  |
| **Risk Control**        | Dynamic Volatility Targeting (Constant Annualized Vol Target) |
| **Portfolio Sizing**    | Risk Parity Position Allocation                               |
| **Primary Stack**       | Python, Pandas, NumPy, Statsmodels, SciPy, Matplotlib         |

---

## Key Features

1. **Fractional Differentiation:** Induces time-series stationarity while preserving historical memory.
2. **Volatility Targeting:** Dynamically scales position sizing inversely to conditional volatility, smoothing returns across market regimes.
3. **Out-of-Sample Validation:** Tested across multi-asset futures and FX datasets under rigorous drawdown constraints.
