#Frozen protocol amendment — version 2.0

Frozen before executing any v2 model result on 2026-07-17.

Version 2 preserves the v1 temporal splits and acceptance gates. It changes only the
following predeclared components:

1. Intrabar high/low Z barriers with conservative stop-first resolution when both
   barriers are touched in the same M15 bar.
2. One position at a time; overlapping candidate events are not double-counted.
3. Student-t emission likelihood with 5 degrees of freedom.
4. Hungarian state matching against the first-fold semantic anchor.
5. Train-only Elastic Net opportunity model using filtered regime probabilities as
   inputs; calibrator family is selected on the calibration block only.
6. Portfolio metrics and DSR use daily fixed-notional returns, not overlapping
   per-trade returns.

The v1 artifacts are frozen under `artifacts/v1_baseline`. The existing OOS periods
remain previously observed and therefore constitute comparative pseudo-OOS, not a new
virgin test. Shadow authorization remains disabled unless every frozen gate passes.
