from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v3 import (
    MRV3Config,
    build_mr_v3_features,
    generate_mr_v3_signals,
    run_mr_v3_backtest,
)


def _bars(n: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(73)
    index = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = 15_000.0 * np.exp(np.cumsum(rng.normal(0.0, 0.0008, n)))
    open_ = np.r_[close[0], close[:-1]]
    width = rng.uniform(1.0, 4.0, n)
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + width,
            "low": np.minimum(open_, close) - width,
            "close": close,
        },
        index=index,
    )


def test_features_are_prefix_invariant() -> None:
    bars = _bars()
    full = build_mr_v3_features(bars)
    prefix = build_mr_v3_features(bars.iloc[:900])
    columns = ["mr_shock_z", "mr_atr", "mr_h18_medium_score", "mr_trend_block"]
    pd.testing.assert_frame_equal(full.loc[prefix.index, columns], prefix[columns])


def test_rejection_requires_next_open_execution() -> None:
    index = pd.date_range("2025-01-01", periods=6, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [120, 120, 96, 98, 100, 100],
            "high": [121, 121, 101, 101, 101, 101],
            "low": [119, 119, 90, 96, 99, 99],
            "close": [120, 120, 92, 100, 100, 100],
            "mr_atr": [5.0] * 6,
            "mr_shock_z": [0.0, 0.0, -4.0, 0.0, 0.0, 0.0],
            "mr_shock": [False, False, True, False, False, False],
            "mr_trend_block": [False] * 6,
        },
        index=index,
    )
    signals = generate_mr_v3_signals(frame)
    assert signals.iloc[3]["entry_signal"] == 1
    result = run_mr_v3_backtest(signals)
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["entry_time"] == index[4]


def test_same_bar_stop_precedes_target() -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="15min", tz="UTC")
    signals = pd.DataFrame(
        {
            "open": [100.0, 100.0, 100.0],
            "high": [101.0, 106.0, 101.0],
            "low": [99.0, 94.0, 99.0],
            "close": [100.0, 100.0, 100.0],
            "entry_signal": [1, 0, 0],
            "mr_target_reference": [105.0, np.nan, np.nan],
            "mr_stop_reference": [95.0, np.nan, np.nan],
        },
        index=index,
    )
    result = run_mr_v3_backtest(signals)
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["exit_reason"] == "shock_stop"
    assert result.trades.iloc[0]["net_pnl"] < 0.0


def test_config_rejects_posthoc_risk_expansion() -> None:
    try:
        MRV3Config(risk_fraction=0.02)
    except ValueError:
        pass
    else:
        raise AssertionError("risk above 1% must fail")
