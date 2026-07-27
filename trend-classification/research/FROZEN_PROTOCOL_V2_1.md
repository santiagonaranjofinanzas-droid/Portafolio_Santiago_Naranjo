#Diagnostic amendment — version 2.1

Created after v2 showed high TP/SL discrimination but negative economics. Consequently,
v2.1 is **not** a virgin OOS experiment and cannot authorize shadow trading.

The single scientific correction is to align the opportunity target with the decision:

- Target: positive net PnL after observed bid/ask and frozen slippage.
- HSMM posterior and duration remain inputs, but no state is a hard entry gate.
- Entry requires positive expected value estimated only in the calibration block.
- All other data, model, split, execution and acceptance settings remain equal to v2.

The purpose is diagnosis: determine whether the market features can predict economic
profitability and whether regime probabilities add incremental information. A genuinely
new holdout or forward shadow period is still required for any production claim.
