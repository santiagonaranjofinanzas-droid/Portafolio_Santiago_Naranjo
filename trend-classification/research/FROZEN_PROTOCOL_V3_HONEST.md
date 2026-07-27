#Frozen protocol v3 honest

Frozen before rerunning the corrected historical experiment on 2026-07-17.

- TP and SL are price levels frozen at signal time; ambiguous bars use stop-first.
- A fully observable event always ends in TP, SL, or executable close at its horizon.
- Model fitting, calibration and evaluation use deterministic non-overlapping events.
- Calibration is chronological: first third fits candidates, second selects the family,
  last third estimates economic payoffs and is never used to fit/select calibration.
- Daily equity includes unrealized bid/ask liquidation P&L until the realized exit.
- DSR uses all 420 registered historical trials. PBO uses the 15 current comparable candidates.
- The primary opportunity model is `all`, fixed before this rerun; no post-hoc regime gate.
- Historical folds are pseudo-OOS only. Shadow approval is impossible in this run.
- The sole valid new holdout begins strictly after 2026-05-29 and must not be used for redesign.
