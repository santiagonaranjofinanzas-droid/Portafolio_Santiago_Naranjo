#MR V4 — Trend Pullback Long

One-shot, long-only test of a buy-the-dip mechanism inside an active H18 trend.

The shock cutoff is the fixed two-percent lower quantile of causal standardized
M15 returns in each UTC session, estimated only on the purged training slice of
each outer fold. A setup requires both H18 6001/6002 logical states to be long
and both slow scores to be at least 0.35. Confirmation occurs at a close and
execution is delayed to the next open. Intrabar stop/target collisions are
resolved stop-first.

Run:

```powershell
python -m NAS100_RESEARCH_V2.experiments.mr_v4_program
python -m pytest NAS100_RESEARCH_V2/mean_reversion_v4/tests -q
```

The frozen decision is written to
`experiments/results/mean_reversion_v4/mr_v4_decision.json`. The current result
is rejected; Magic 6003 remains reserved and no MT5 EA is authorized.
