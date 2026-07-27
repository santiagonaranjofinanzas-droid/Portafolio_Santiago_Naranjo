#Quant Governance Rules

You are working on a quantitative finance research and trading-system codebase.

Your priority is not to maximize apparent backtest performance. Your priority is to produce statistically defensible, reproducible, leakage-free research.

##Non-negotiable rules

1. Never optimize directly on the final test period.
2. Never fit scalers, encoders, PCA, SVD, volatility estimators, feature selectors, or models using future data.
3. Never use shuffled K-Fold for financial time series unless explicitly justified for non-temporal cross-sectional data.
4. Any ML pipeline must separate:
   - raw data ingestion,
   - feature engineering,
   - label construction,
   - training,
   - validation,
   - backtest,
   - reporting.
5. Any backtest must include realistic transaction costs:
   - spread,
   - commissions,
   - slippage,
   - swaps/financing,
   - rollover effects when relevant.
6. Any strategy improvement must be compared against the previous layer and against a simple benchmark.
7. Any claim of alpha must include statistical evidence and robustness checks.
8. If leakage, look-ahead bias, target contamination, survivorship bias, or data snooping is detected, stop and report it before coding further.
9. Do not hide weak results. Report negative or inconclusive results explicitly.
10. Prefer simple models unless a complex layer has measurable marginal contribution.
