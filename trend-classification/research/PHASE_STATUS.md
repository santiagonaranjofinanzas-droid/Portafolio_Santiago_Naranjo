#Phase execution status

Executed on 2026-07-16/17 using `configs/research_v1.yaml`.

 Phase  Status  Evidence / gate 
---------
 0. Protocol and ledger  Complete  Frozen config, ledger, data dictionary, pre-fit gap amendment 
 1. Data audit  Complete with scope limitation  524,766,414 ticks audited; XAUUSD only covers 2021-01 to 2026-05 
 2. Equilibrium and labels  Complete  One-sided local-level Kalman; 8/16/32-bar executable bid/ask triple barrier 
 3. Causal features  Complete  10 frozen emissions; prefix-invariance tests pass 
 4. HMM/HSMM  Complete  Four-state diagonal Gaussian HMM and explicit Poisson-duration HSMM; filtered posteriors 
 5. State semantics  Complete  Frozen taxonomy, train-only state mapping, separate calibrated success probability 
 6. Walk-forward  Complete  Eight rolling 3y/3m/3m purged folds; three HSMM seeds per fold 
 7. Economic decision  Complete  Next executable bid/ask, observed spread, 10% adverse slippage, EV gate 
 8. Robustness/overfit  Gate failed / partial  Cost ×1–2, HMM ablation, fixed-rule benchmarks, DSR and CSCV-PBO complete; full family ablation and second provider not justified/available after core rejection 
 9. Shadow/MT5  Interface ready, authorization blocked  JSONL inference contract and kill switch work; historical approval is false 

##Historical decision

`review_or_reject`. The calibrated success probability does not beat a constant predictor
on Brier or log-loss, discrimination is near random, explicit duration does not beat the
HMM likelihood in a majority of folds, and the frozen PF/DSR/PBO/fold-stability gates fail.
No shadow or capital deployment is authorized.

##Re-entry requirements

1. Add the missing 2012–2020 XAUUSD history and a second independent provider.
2. Diagnose state semantics and calibrate regime membership separately from trade success.
3. Improve discrimination on calibration only; do not tune against the existing OOS blocks.
4. Re-run full feature-family ablation only after the core model beats constant and HMM benchmarks.
5. Start a genuinely new 8–12 week shadow window only after all frozen historical gates pass.

##Version 2 end-to-end extension

Version 2 completed intrabar labels, Student-t emissions, Hungarian state matching,
supervised opportunity models, non-overlapping portfolio simulation, daily metrics and
economic ablations. Version 2.1 corrected the diagnostic target to net profitability and
produced strong comparative economics, but remains non-authorizable because the same OOS
folds were already observed and several predictive/duration gates still fail. See
`research/V2_END_TO_END_REPORT.md` and `research/NEXT_HOLDOUT_PROTOCOL.md`.
