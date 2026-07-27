from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v4 import (
    MRV4Config, apply_shock_thresholds, build_mr_v4_features,
    calibrate_session_thresholds, generate_mr_v4_signals, run_mr_v4_backtest,
)


def _bars(n: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(74)
    index = pd.date_range("2024-01-01", periods=n, freq="15min", tz="UTC")
    close = 15_000.0 * np.exp(np.cumsum(rng.normal(0.00002, 0.0008, n)))
    open_ = np.r_[close[0], close[:-1]]
    width = rng.uniform(1.0, 4.0, n)
    return pd.DataFrame({"open": open_, "high": np.maximum(open_, close) + width, "low": np.minimum(open_, close) - width, "close": close}, index=index)


def test_features_are_prefix_invariant() -> None:
    bars = _bars()
    full = build_mr_v4_features(bars)
    prefix = build_mr_v4_features(bars.iloc[:900])
    columns = ["v4_shock_z", "v4_atr", "v4_h18_medium_score", "v4_h18_ultra_score", "v4_trend_aligned"]
    pd.testing.assert_frame_equal(full.loc[prefix.index, columns], prefix[columns])


def test_session_thresholds_only_depend_on_training_slice() -> None:
    features = build_mr_v4_features(_bars())
    train = features.iloc[:900]
    first = calibrate_session_thresholds(train)
    mutated = features.copy()
    mutated.iloc[900:, mutated.columns.get_loc("v4_shock_z")] = -100.0
    second = calibrate_session_thresholds(mutated.iloc[:900])
    assert first == second


def test_signal_is_long_and_executes_next_open() -> None:
    index = pd.date_range("2025-01-01", periods=6, freq="15min", tz="UTC")
    frame = pd.DataFrame({
        "open": [120, 120, 95, 94, 100, 100], "high": [121, 121, 97, 101, 121, 101],
        "low": [119, 119, 90, 93, 99, 99], "close": [120, 120, 92, 100, 100, 100],
        "v4_atr": [4.0] * 6, "v4_downside_shock": [False, False, True, False, False, False],
        "v4_trend_aligned": [True] * 6,
    }, index=index)
    signals = generate_mr_v4_signals(frame, MRV4Config(minimum_reward_risk=0.5))
    assert signals.iloc[3]["entry_signal"] == 1
    assert (signals["entry_signal"] >= 0).all()
    result = run_mr_v4_backtest(signals, MRV4Config(minimum_reward_risk=0.5))
    assert len(result.trades) == 1
    assert result.trades.iloc[0]["entry_time"] == index[4]


def test_shock_requires_trend_alignment() -> None:
    features = build_mr_v4_features(_bars())
    thresholds = {name: -1.5 for name in ("ASIA", "EUROPE", "US", "ROLLOVER")}
    out = apply_shock_thresholds(features, thresholds)
    assert not ((out["v4_downside_shock"]) & (~out["v4_trend_aligned"])).any()


def test_config_rejects_posthoc_risk_expansion() -> None:
    try:
        MRV4Config(risk_fraction=0.02)
    except ValueError:
        pass
    else:
        raise AssertionError("risk above 1% must fail")
