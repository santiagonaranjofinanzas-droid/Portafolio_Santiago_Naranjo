#H18 institutional risk V1 — implementation and diagnostic

##Decision

- Implementation: complete in Python reference and MQL5 demo engine.
- Compilation: both EAs compile with 0 errors and 0 warnings.
- Historical diagnostic: improved tail control, but not all institutional gates pass.
- Operational status: `FUTURE_EVIDENCE_REQUIRED_LIVE_LOCKED`.

The TREND 10/11 signal contract was not changed. The risk overlay is a material
execution change and requires new Python/MQL risk parity and future evidence.

##Frozen policy

- `NAS100.fs`; magics 6001/6002; long-only.
- Per-sleeve risk 0.25% equity; aggregate risk 0.50% equity.
- Portfolio volatility target 10% annual, split equally between correlated sleeves.
- Executive stop 6 ATR H1; server disaster stop 8 ATR H1.
- Daily entry lock 1%; drawdown throttle 5%; entry lock 7.5%; emergency 10%.
- Margin allocation cap 20%; minimum margin level 300%.
- Volume always rounds down; an unsafe broker minimum is vetoed.

##Consumed-history diagnostic (2020-01-01 through 2026-07-10)

This run is diagnostic and cannot approve the model because the development
history was previously consumed.

 Metric  Result  Gate  Pass 
------:---::---:
 Closed trades, combined  906  —  — 
 PF  1.262  >=1.20  yes 
 Return on 100k  8.38%  >0  yes 
 Maximum drawdown  2.94%  <=15%  yes 
 Daily Sharpe  0.593  >=1.00  **no** 
 DSR, 142 trials  0.207  >=0.95  **no** 
 Bootstrap PF p05  1.010  >1.00  yes 
 Bootstrap expectancy p05  0.246  >0  yes 
 P(positive total)  96.19%  >=95%  yes 
 Risk vetoes  11  audited  yes 
 Disaster-stop exits  8  audited  yes 

Chronological trade-block PFs:
`1.603 / 1.148 / 1.051 / 1.504 / 1.474 / 1.066 / 1.035`.

The overlay preserved positive economic behavior and compressed drawdown in
this continuous shared-account diagnostic, but daily risk-adjusted performance
and DSR did not reach institutional thresholds. It is not directly comparable to the
prior nested result because this is a continuous two-sleeve portfolio.

##Outstanding release gates

1. 100% signal and risk-decision parity on the same MT5 feed/account snapshots.
2. 100% server-SL coverage and zero orphan positions in demo.
3. At least 4 holdout months / 40 trades.
4. At least 6 forward-demo months / 60 trades.
5. At least 100 future trades combined, PF >=1.10 and DD <=10%.
