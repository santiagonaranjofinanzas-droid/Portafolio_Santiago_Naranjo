#Quant Validate Workflow

Run a full validation pass on the current strategy or model.

Required outputs:

1. Data Integrity Report.
2. Feature/Label Alignment Report.
3. Leakage Audit.
4. Cross-Validation Design Review.
5. Backtest Realism Review.
6. Statistical Significance Report.
7. Robustness Report.
8. Final Verdict.

Use this verdict format:

- PASS: acceptable for research continuation.
- CONDITIONAL PASS: usable only after listed fixes.
- FAIL: result is not reliable.

Never give PASS if:

- transaction costs are missing;
- train/test separation is unclear;
- purging is required but absent;
- scalers/models are fit on full data;
- the final test set was used for iterative tuning.
