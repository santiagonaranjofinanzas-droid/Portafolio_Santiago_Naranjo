#NAS100 Trend V2

Trend V2 is a fold-safe research candidate, not a live trading release. It
separates market-condition classification from trade direction:

- a sticky, diagonal multivariate Student-t HMM filters `TRENDABLE`, `RANGE`
  and `SHOCK` conditions;
- signed direction comes only from the median of volatility-normalized
  momentum over 16, 32 and 64 bars;
- entries require a newly observed TRENDABLE transition, two-bar confirmation
  by default, and one entry maximum per regime episode;
- all signals are evaluated at the close and filled by the backtester at the
  next bar open with bid/ask spread, slippage and commissions;
- simple long-only and long/short momentum strategies are first-class
  benchmarks. The HMM candidate should be kept only if it adds robust OOS value.

##Fold API

```python
from NAS100_RESEARCH_V2.trend_v2 import (
    BacktestConfig,
    TrendV2Model,
    run_bar_backtest,
)

model = TrendV2Model().fit(train_m15)
oos = model.transform(test_m15)       # filtered probabilities, never smoothed
signals = model.generate_signals(oos)
result = run_bar_backtest(
    signals,
    BacktestConfig(
        tick_size=0.01,
        tick_value=0.20,
        spread_price=2.50,
        slippage_price=0.25,
        commission_per_unit_per_side=0.0,
    ),
)
diagnostics = model.diagnostics()
benchmarks = model.generate_benchmarks(oos)
```

`transform(test, context=...)` accepts an explicit causal prefix for rolling
feature warm-up. If omitted, the model uses the saved tail of the training fold.
The prefix is neither fitted nor returned. The OOS filter starts from the final
filtered train probability.

##Required bar schema

`open`, `high`, `low`, `close`; `tick_volume` is recommended. A timezone-aware
`DatetimeIndex` should already be normalized to the desired research timezone.
If available, a `spread_price` column overrides the fixed spread bar by bar.

##Identification diagnostics

`model.diagnostics()["regime"]` reports convergence, state occupancy, pairwise
separation, semantic feature means, transition probabilities, implied duration,
boundary warnings and an `identified` gate. An un-identified fit must be rejected
for that validation fold; relabeling is deterministic but is not evidence of a
stable economic state.
