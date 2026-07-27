from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from NAS100_RESEARCH_V2.integration import TrendFoldEvaluator
from NAS100_RESEARCH_V2.validation import AxiCostModel, CandidateSpec
from NAS100_RESEARCH_V2.validation.splits import OuterFold


def _bars(n=1200):
    index = pd.date_range("2020-01-01", periods=n, freq="15min", tz="UTC")
    wave = np.sin(np.arange(n) / 40.0) * 10.0
    close = 10_000.0 + np.arange(n) * 0.05 + wave
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 2.0,
            "low": np.minimum(open_, close) - 2.0,
            "close": close,
            "tick_count": 100,
        },
        index=index,
    )


def test_momentum_adapter_enforces_utc_and_normalizes_trades():
    bars = _bars()
    train, test = bars.iloc[:800], bars.iloc[800:]
    fold = OuterFold(
        0,
        train.index[0],
        train.index[-1],
        test.index[0],
        test.index[-1],
        np.arange(len(train)),
        np.arange(len(test)),
        0,
    )
    candidate = CandidateSpec(
        "MOM_LONG",
        {
            "strategy": "momentum_long_only",
            "model": {"signals": {"momentum_threshold": 0.05}},
            "backtest": {"maximum_holding_bars": 64},
        },
        is_baseline=True,
    )
    result = TrendFoldEvaluator()(train, test, candidate, AxiCostModel().scenarios()["base"], fold)
    assert {"entry_time", "exit_time", "net_pnl", "return_pct", "pnl"}.issubset(result.trades.columns)
    if not result.trades.empty:
        assert (result.trades["entry_time"] >= test.index[0]).all()

    naive = bars.copy()
    naive.index = naive.index.tz_localize(None)
    with pytest.raises(ValueError, match="UTC"):
        TrendFoldEvaluator()(naive.iloc[:800], naive.iloc[800:], candidate, AxiCostModel().scenarios()["base"], fold)
