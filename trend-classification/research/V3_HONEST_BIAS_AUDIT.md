#V3 honest bias audit and corrected backtest

Run date: 2026-07-17. Decision: **REJECT / NO SHADOW**.

##Bias corrections implemented

- Barriers and equilibrium are frozen using signal-time information. Intrabar touches use
  future OHLC only to resolve the already-fixed price levels; ambiguous bars are stop-first.
- Gaps through a barrier fill at the next available opening bid/ask, not the theoretical level.
- Every fully observable event terminates in TP, SL, or executable horizon close. Censored tail
  rows are not events and are never passed to fitting or evaluation.
- Fitting, calibration and testing use a deterministic chronological non-overlapping sample.
- Calibration uses temporal thirds: fit, family selection, and untouched economic estimation.
- Daily equity is marked to bid/ask liquidation value throughout each open position.
- DSR includes all 420 ledger trials. PBO covers 15 current mode/threshold candidates; a
  no-trade candidate/block receives return zero.
- The `all` opportunity model and no regime hard gate were frozen before this rerun.

##Mechanical audit

 Horizon  Observable  Missing label/exit/P&L  Non-overlap sample  Overlaps 
---:---:---:---:---:
 8  18,947  0 / 0 / 0  9,477  0 
 16  18,941  0 / 0 / 0  9,411  0 
 32  18,933  0 / 0 / 0  9,386  0 

Selected OOS trade overlaps: 0. Tests: 15 passed. Ruff: passed.

##Corrected historical pseudo-OOS result

- Probability events: 3,539; ROC AUC 0.7559; MCC 0.0877; ECE 0.0244.
- Trades: 1,318; TP 443, SL 798, horizon exits 77.
- Total P&L: -1,085.31 price points; expectancy -0.8234; PF 0.8023.
- Mark-to-market total return: -28.65%; daily Sharpe -1.8755; max drawdown -31.41%.
- Positive folds: 0/8. DSR probability with 420 trials: 1.62e-9. PBO: 32.86%.
- Cost x1.5: PF 0.7421 and total return -36.77%.
- HSMM beat HMM likelihood in only 1/8 folds; regime inputs did not add AUC.

All eight fold returns were negative: -1.74%, -0.97%, -3.22%, -6.58%, -13.20%,
-0.93%, -1.20%, and -4.54%.

The previously positive v2.1 result does not survive causal execution and complete-event
accounting. It must not be used as evidence of deployable edge.

##Required true holdout

The local XAUUSD series ends at `2026-05-29 17:00:00 UTC`. It contains **zero** rows after
2026-05-29, so evaluation solely on later data cannot yet be performed. The v3 protocol,
configuration and trial count are frozen. New XAUUSD ticks after that cutoff may be appended
and evaluated once, without changing the model or decision rules. Until then the kill switch
remains active.
