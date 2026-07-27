#MR V3 — Shock Rejection

##Decision

`REJECTED_RESEARCH_ONLY_NO_EA`

MR V3 was implemented as a one-shot causal hypothesis intended to coexist with
H18 Trend. Magic 6003 is reserved, but no executable EA is authorized or built.

##Frozen mechanism

- M15 return shock >= 3.0 past standard deviations.
- True range >= 1.5 times causal ATR(32).
- Rejection of the shock midpoint within four bars.
- Target at the pre-shock close.
- Stop one ATR outside the shock extreme.
- Maximum holding time of 16 M15 bars.
- Minimum reward/risk of 1.0 at confirmation and at next-open execution.
- Risk 0.10% of balance per trade.
- Entry blocked while either H18 6001/6002 logical position is active or either
  slow momentum score has absolute strength above 0.35.

All parameters were recorded in
`governance/config/mr_v3_preregistration_20260714.json` before PnL was computed.

##Outer OOS result

Seven six-month outer folds produced 196 qualifying shocks, but only six fully
confirmed, executable setups.

 Metric  Result  Gate 
------:---:
 Trades  6  >=200 
 PF  1.484  >=1.20 
 Net PnL  110.77  >0 
 Positive folds  2/7  >=5/7 
 Minimum fold trades  0  >=20 
 Daily Sharpe  0.178  — 
 DSR  0.013  >=0.95 
 Drawdown  0.205%  <=15% 
 Bootstrap PF p05  0.052  >1.00 
 Bootstrap P(benefit)  64.38%  >=95% 
 Adverse-cost PF  1.424  >=1.05 
 Crisis-cost PF  1.322  >=1.00 

The positive PF is not credible with six trades. Cost survival and low drawdown
do not compensate for the absence of sample size, fold stability, DSR or
bootstrap support.

##Coexistence result

An independent-ledger overlay added only 110.77 to either H18 candidate over the
complete historical interval and did not materially change PF, drawdown or DSR.
It therefore does not establish portfolio diversification.

##Bias controls

- Prefix-invariance passed for shock, ATR, H18 scores and veto state.
- Signal is observed at close and executed next-open.
- Pessimistic stop-before-target ordering is used when both touch one bar.
- Seven untouched outer OOS folds were used; no parameter was changed after the
  result.
- DSR includes 142 historical trials.
- PBO is not reported because exactly one MR V3 candidate was preregistered.

##Consequence

The Python implementation and tests remain as a reproducible falsification
artifact. Building or enabling an MQL trading EA would contradict the frozen
gate. Any looser shock threshold or weaker Trend veto is a new hypothesis that
requires new data or a separately budgeted research program.
