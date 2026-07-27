#Quant Release Workflow

A model cannot be released unless the following are present:

1. Reproducible environment.
2. Data version documented.
3. Config file frozen.
4. Random seeds fixed where applicable.
5. Backtest report generated.
6. Validation report generated.
7. Leakage audit passed.
8. Cost model included.
9. Benchmark comparison included.
10. Risk limits documented.
11. Failure cases documented.
12. No credentials committed.
13. Git diff reviewed.

Final output must include:

- release summary;
- model version;
- data version;
- config version;
- metrics table;
- known weaknesses;
- do-not-trade conditions.
