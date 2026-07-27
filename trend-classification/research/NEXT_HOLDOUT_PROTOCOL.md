#Frozen next-holdout protocol

This protocol is intended for data not used in v1/v2/v2.1 and must not be evaluated by
relabeling or retuning the existing folds.

##Candidate

- Opportunity target: positive net PnL after bid/ask and frozen slippage.
- Opportunity inputs: `regime_only` (four filtered state probabilities, four expected
  state ages, absolute Z-score and signal direction).
- Model: Elastic Net logistic with `C=0.10`, `l1_ratio=0.25`.
- Calibration candidates: Platt, isotonic, identity; choose by calibration Brier then
  log-loss.
- Execution: next bar executable quote, intrabar stop-first, one position at a time.
- Costs: observed bid/ask + 10% spread slippage; stress ×1.5 remains mandatory.
- Sizing: fixed notional; no probability sizing.

##Required data

- Primary holdout begins strictly after the last XAUUSD timestamp currently available:
  `2026-05-29 17:00:00`.
- Preferred minimum: six months; shadow decision requires at least 8–12 weeks and enough
  conclusive events for calibration intervals.
- No parameter, state taxonomy, feature family or threshold changes during the holdout.

##Gates

- Brier and log-loss better than the frozen prevalence predictor.
- AUC ≥0.60 and MCC ≥0.15.
- PF ≥1.20 and daily Sharpe ≥1.0.
- Positive result in ≥70% monthly blocks.
- DSR ≥95%, PBO ≤20%, and positive expectancy at cost ×1.5.
- No single month contributes more than 50% of total profit.

Until these conditions are met on new data, `shadow.enabled=false` and
`kill_switch=true` remain mandatory.

