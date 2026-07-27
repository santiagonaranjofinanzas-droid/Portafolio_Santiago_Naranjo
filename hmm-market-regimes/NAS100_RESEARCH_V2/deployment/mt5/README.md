#H18 MT5 institutional-risk demo incubation

This package contains two independently calculated MQL5 implementations of the frozen H18 candidates:

 EA  Candidate  Magic  H1 horizons  Stop 
---------:------:
 `H18_TREND10_6001.mq5`  TREND_10_MEDIUM_LONG  6001  12/24/48  6 ATR ejecutivo / 8 ATR servidor 
 `H18_TREND11_6002.mq5`  TREND_11_ULTRASLOW_LONG  6002  24/48/96  6 ATR ejecutivo / 8 ATR servidor 

##Safety contract

- Demo account or Strategy Tester only. A live account causes `INIT_FAILED`.
- M15 chart and exact symbol `NAS100.fs` only.
- Hedging account required when both EAs share one account. A netting account cannot isolate positions by magic on one symbol.
- Long-only; no HMM and no Python runtime dependency.
- Only complete M15 quarters form an H1 decision.
- Decision at the `:45` close; market order at the first tick of the next M15 bar.
- The frozen 6 ATR executive stop remains checked at an H1 close and executed next-open.
- Every broker position also receives an 8 ATR disaster SL at entry. An entry without a confirmed server SL fails closed.
- A shared governor caps each sleeve at 0.25% equity risk and both sleeves at 0.50% aggregate risk.
- The 10% annual volatility target is a portfolio target; each highly correlated sleeve receives half.
- Sizing is the minimum of stop risk, volatility, aggregate exposure, margin and broker constraints.
- A below-minimum safe lot is rejected; it is never rounded upward.
- New entries lock after 1% UTC-day loss or 7.5% drawdown, size halves from 5%, and 10% drawdown triggers emergency flattening.
- Orders receive `OrderCheck`; success also requires `TRADE_RETCODE_DONE`.
- State survives restarts through terminal Global Variables namespaced by magic.
- Observer mode (`InpTradingEnabled=false`) is the safe default and still advances the complete logical model state for parity auditing.

##Installation

Copy `Include/H18_SlowTrend_Core.mqh` into an `MQL5/Include/H18/` folder and adjust the wrapper include, or preserve this package's relative `Experts/../Include` layout. Compile both wrappers with MetaEditor and attach each to a separate `NAS100.fs` M15 chart.

The repository already includes compiled `.ex5` artifacts. They can be installed into a terminal data directory with:

```powershell
.\Install-H18-Demo.ps1 -TerminalDataPath "C:\Users\<user>\AppData\Roaming\MetaQuotes\Terminal\<id>"
```

Output logs use `FILE_COMMON`, including in Strategy Tester, and are created under
`%APPDATA%/MetaQuotes/Terminal/Common/Files`:

- `H18_6001_signals.csv`, `H18_6001_deals.csv`
- `H18_6002_signals.csv`, `H18_6002_deals.csv`
- `H18_6001_risk.csv`, `H18_6002_risk.csv`

Do not delete terminal Global Variables while a position is open. The EA fails closed if an owned position exists without a persisted virtual stop.

##Safe deployment sequence

1. Use a fresh Axi **demo hedging** account. Never attach these EAs to the real
   portable terminal; live initialization is deliberately rejected.
2. Install/refresh both compiled EAs and open two `NAS100.fs` M15 charts.
3. Attach 6001 and 6002 with `InpTradingEnabled=false`. Record the UTC start and
   archive the exact MT5 M15 export used during the observation window.
4. After at least 20 completed H1 decisions, run the parity command below for
   each magic. Do not enable orders unless both reports return `approved: true`.
5. Delete/reset the H18 terminal Global Variables before changing from observer
   to execution mode; then attach with `InpTradingEnabled=true` on demo only.
6. Incubate under the frozen governance gate. Any parameter/model change resets
   holdout and forward counters.

The two magics remain research candidates, not an approved ensemble. They must
share the same hedging demo account when validating the portfolio governor;
separate accounts do not exercise the aggregate 0.50% exposure limit.

##Parity

Python remains the golden reference and must not provide live signals. Run the independent audit after exporting the exact M15 feed used by MT5:

```powershell
python -m NAS100_RESEARCH_V2.deployment.h18_mt5_parity `
  --bars path/to/mt5_m15_bars.csv `
  --mt5-signals path/to/H18_6001_signals.csv `
  --magic 6001 `
  --start-utc 2026-07-13T00:00:00Z `
  --output parity_6001.json
```

Approval requires identical decision timestamps and entry/exit signals, score difference <=1e-9, ATR difference <=0.01 and volatility difference <=1e-10. Risk parity additionally requires one-for-one authorization reason, lot, executive stop, disaster stop, cash risk, existing portfolio risk and throttle. Trade/PnL parity remains governed by `deployment/parity.py` after raw deals are aggregated with `aggregate_mt5_deals`.

`exit_signal` is the model's momentum exit and is directly comparable with Python.
`execution_exit` additionally records a broker-side catastrophe stop; it must be
audited as execution behavior, not confused with the model-state signal.
