#Mean Reversion V3 — Shock Rejection

One-shot preregistered research hypothesis for `NAS100.fs M15`. It does not
resurrect the retired AR(1) residual model.

MR V3 observes an abnormal return/range shock, waits for a causal rejection of
the shock midpoint, then targets the pre-shock close. Entries are blocked while
either H18 Trend candidate is logically active or either slow score has absolute
strength above 0.35. This makes MR operationally compatible with magics 6001 and
6002 without opening an opposing trade during their active trend episodes.

Magic 6003 is reserved, but an MT5 EA is built only if the frozen statistical
gate passes. Until then this package is research-only.
