#End-to-end version 2 research report

##Scope completed

- Conservative intrabar triple barrier with executable bid/ask barrier prices.
- Entry/exit timestamps and one-position-at-a-time event selection.
- Student-t explicit-duration HSMM and Gaussian HMM benchmark.
- Hungarian state alignment against a frozen first-fold semantic anchor.
- Elastic Net opportunity model with calibration selected on calibration data only.
- `all`, `market_only`, and `regime_only` probability/economic ablations.
- Daily fixed-notional equity, daily Sharpe/Sortino, DSR, CSCV-PBO and cost stress.
- Shadow JSONL inference with probability-sum validation and active kill switch.

All versions use the same eight rolling 3y/3m/3m pseudo-OOS folds. These folds were
already observed in v1; neither v2 nor v2.1 can authorize deployment.

##Version comparison

 Version  Target  AUC  PF  Daily Sharpe  Total return  Positive folds  DSR  PBO 
---------:---:---:---:---:---:---:
 v1  bar-close reversal  0.505  1.196  n/a  n/a  62.5%  91.8%  31.4% 
 v2  intrabar TP before SL  0.815  0.737  -1.59  -12.4%  12.5%  0.003%  2.9% 
 v2.1  positive net PnL  0.558  1.724  2.31  +41.4%  75.0%  99.95%  0.0% 

Version 2 proved that TP/SL order is predictable but not sufficient for economic value.
Version 2.1 aligned the supervised target with the economic decision and recovered a
strong historical portfolio, including PF 1.545 and Sharpe 1.70 under cost ×1.5.

##Ablation result

 Opportunity inputs  AUC  PF  Daily Sharpe  Total return  Max DD 
------:---:---:---:---:
 Market + regime  0.558  1.724  2.31  +41.4%  -4.72% 
 Market only  0.556  1.738  2.46  +45.2%  -3.39% 
 Regime only  0.564  3.128  3.81  +55.9%  -3.55% 

The combined feature block is worse than either ablation. The regime-only variant is the
best candidate for a future holdout, but selecting it after viewing these results makes
it ineligible for a production claim.

##Remaining failed gates

- Net-profit AUC 0.558 is below 0.60.
- MCC 0.075 is below 0.15.
- Log-loss is worse than the constant predictor.
- Student-t HSMM likelihood beats the HMM in only 1/8 folds.
- Regime probabilities add only about 0.0016 AUC to the combined opportunity model.
- A second XAUUSD provider and 2012–2020 history remain absent.
- Exact tick ordering inside bars has not been reconstructed; same-bar ambiguity is
  resolved conservatively as stop-first.

##Decision

`review_or_reject`. The engineering and diagnostic research are complete, but shadow
authorization remains false. The only defensible next experiment is a pre-registered
regime-only candidate evaluated on genuinely new XAUUSD data after 2026-05-29.

