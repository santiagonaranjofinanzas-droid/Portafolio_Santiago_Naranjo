#Mean Reversion V2

This package is a fold-safe research implementation for `NAS100.fs`. It is not
a live release gate by itself.

The model decomposes log price into a robust causal local linear trend and a
transient residual. Process variances are selected only on `train`. A
Huber-IRLS AR(1), HAC confidence interval, and half-life gate determine whether
the residual is admissible. Test filtering freezes all learned parameters and
never backfills warm-up values.

```python
from NAS100_RESEARCH_V2.mean_reversion_v2 import MeanReversionV2

mr = MeanReversionV2().fit(train_bars)
filtered = mr.filter(test_bars)
generated = mr.generate(filtered)
bt = mr.backtest(test_bars, generated.frame)
report = mr.falsify(test_bars, filtered)
```

Signals are generated at bar close after an extreme has re-entered the
threshold. The backtest consumes them at the next open. It uses a frozen entry
mean as target, an adverse residual-z stop, a half-life time stop, a structural
break exit, pessimistic same-bar ordering, and no partial exit.

The default execution basis is MT5 bid OHLC: long entries and short exits cross
the full spread. Set `CostConfig(bar_price_basis="mid")` only for a verified
mid-price dataset. `spread_median`, `spread_price`, and `spread` columns override
the fixed spread row by row.

`evaluate_edge_existence` produces separate long/short conditional response
maps for horizons 1, 2, 4, 8, and 16. Moving-block bootstrap intervals preserve
overlap dependence. A side is admitted to nested validation only when at least
three of four chronological blocks show a monotone positive net response, the
terminal bootstrap lower bound is positive, and gross response covers the
pre-registered cost multiple.
