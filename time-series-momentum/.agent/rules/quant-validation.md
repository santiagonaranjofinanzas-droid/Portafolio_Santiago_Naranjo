#Quant Validation Protocol

All quantitative strategies must pass the following validation gates.

##Gate 1: Data Integrity

Check:

- timestamp alignment;
- timezone consistency;
- missing values;
- duplicated timestamps;
- corporate actions if equities are used;
- bid/ask availability if intraday;
- spread and swap availability if CFD/FX;
- contract roll treatment if futures;
- survivorship bias in asset universe.

Fail the validation if the data cannot support the claimed result.

##Gate 2: Feature/Label Alignment

For every feature, document:

- observation time;
- availability time;
- transformation window;
- whether the value would have been known at decision time.

For every label, document:

- prediction horizon;
- barrier logic if applicable;
- overlap structure;
- purging requirement.

##Gate 3: Cross-Validation

Use financial time-series validation:

- walk-forward validation;
- purged and embargoed cross-validation when labels overlap;
- combinatorial purged cross-validation when testing many model variants;
- nested validation when tuning hyperparameters.

The model must not tune hyperparameters using the final test period.

##Gate 4: Backtest Realism

Include:

- transaction costs;
- slippage model;
- spread model;
- borrow/financing/swap costs;
- latency assumption if intraday;
- execution rule;
- position sizing rule;
- risk limits;
- stop logic and take-profit logic if used.

##Gate 5: Statistical Evidence

Report:

- CAGR;
- volatility;
- Sharpe;
- Sortino;
- Calmar;
- max drawdown;
- hit rate;
- payoff ratio;
- turnover;
- exposure;
- skewness;
- kurtosis;
- VaR;
- CVaR or EVaR;
- Probabilistic Sharpe Ratio;
- Deflated Sharpe Ratio when multiple trials exist.

##Gate 6: Robustness

Run:

- parameter perturbation;
- cost inflation stress test;
- block bootstrap or stationary bootstrap;
- subperiod analysis;
- crisis-period analysis;
- ablation by model layer;
- benchmark comparison.

##Gate 7: Release Decision

A strategy can be marked as research-valid only if:

- it beats the previous layer after costs;
- it beats a simple benchmark after costs;
- the improvement survives robustness checks;
- the result is not concentrated in one tiny subperiod;
- implementation is reproducible from clean environment.
