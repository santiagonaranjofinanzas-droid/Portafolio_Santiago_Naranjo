from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.risk import run_h18_portfolio_backtest


def _frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=12, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.full(12, 20_000.0),
            "high": np.full(12, 20_020.0),
            "low": np.full(12, 19_980.0),
            "close": np.full(12, 20_005.0),
            "entry_signal": np.zeros(12, dtype=int),
            "exit_signal": np.zeros(12, dtype=bool),
            "slow_decision": np.ones(12, dtype=bool),
            "slow_atr_h1": np.full(12, 50.0),
            "slow_vol_h1": np.full(12, 0.005),
            "spread_price": np.full(12, 2.5),
        },
        index=index,
    )
    frame.loc[index[1], "entry_signal"] = 1
    frame.loc[index[8], "exit_signal"] = True
    return frame


def test_portfolio_backtest_shares_equity_and_keeps_risk_audit():
    a = _frame()
    b = _frame()
    b["entry_signal"] = 0
    result = run_h18_portfolio_backtest({6001: a, 6002: b})
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["magic"] == 6001
    assert result.trades.iloc[0]["exit_reason"] == "signal_exit"
    assert len(result.risk_events) == 1
    assert result.risk_events.iloc[0]["approved"]
    assert result.metrics["closed_trades"] == 1


def test_disaster_stop_is_active_intrabar():
    a = _frame()
    b = _frame()
    b["entry_signal"] = 0
    # Entry happens on row 2.  With ATR 50 the server stop is about 400 points away.
    a.iloc[2, a.columns.get_loc("low")] = 19_000.0
    result = run_h18_portfolio_backtest({6001: a, 6002: b})
    assert result.trades.iloc[0]["exit_reason"] == "server_disaster_stop"
