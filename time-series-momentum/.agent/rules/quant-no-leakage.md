#No-Leakage Rules for Quant Research

The agent must actively search for these leakage vectors:

1. Feature computed using future bars.
2. Rolling statistics not shifted before prediction.
3. Full-sample normalization.
4. PCA/SVD fitted on the entire dataset.
5. Feature selection using test data.
6. Hyperparameter optimization using final test results.
7. Labels overlapping train/test boundary without purging.
8. Embargo missing after test fold.
9. Target leakage through realized future volatility, future returns, future high/low, or future regime labels.
10. Using revised macroeconomic data as if it were available in real time.
11. Survivorship bias in asset universe.
12. Ignoring delisted or unavailable assets.
13. Evaluating strategy on mid prices while executing at bid/ask.
14. Ignoring swaps, financing, and overnight costs in CFD/FX.
15. Reusing the same test set after many model iterations without deflated statistics.

If any issue is found, produce a Leakage Report with:

- file;
- line/function;
- leakage type;
- why it matters;
- proposed correction;
- whether previous results are invalidated.
