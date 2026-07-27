from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.trend_v2 import (
    BacktestConfig,
    SignalConfig,
    SlowTrendConfig,
    build_slow_trend_features,
    generate_momentum_benchmarks,
    generate_slow_trend_signals,
    generate_trend_signals,
    run_bar_backtest,
)


def _signal_frame() -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=14, freq="15min", tz="UTC")
    frame = pd.DataFrame(index=index)
    # range, a long trend episode, reset, then a short trend episode
    frame["p_trendable"] = [0.1, 0.7, 0.8, 0.8, 0.8, 0.8, 0.8, 0.1, 0.7, 0.8, 0.8, 0.8, 0.1, 0.1]
    frame["p_range"] = [0.8, 0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.8, 0.2, 0.1, 0.1, 0.1, 0.8, 0.8]
    frame["p_shock"] = 1.0 - frame["p_trendable"] - frame["p_range"]
    frame["momentum_score"] = [0.0, 0.4, 0.5, 0.6, -0.5, 0.6, 0.7, 0.0, -0.5, -0.6, -0.7, -0.7, 0.0, 0.0]
    return frame


def test_confirmed_transition_and_no_reentry():
    result = generate_trend_signals(_signal_frame(), SignalConfig(confirmation_bars=2))
    entry_rows = np.flatnonzero(result["entry_signal"].to_numpy())
    assert entry_rows.tolist() == [2, 9]
    assert result["entry_signal"].iloc[2] == 1
    assert result["entry_signal"].iloc[9] == -1
    assert result["exit_signal"].iloc[4]
    # Momentum returns positive in the same active episode but it cannot re-enter.
    assert not result["entry_signal"].iloc[5:8].any()


def test_long_and_short_modes_are_separable():
    frame = _signal_frame()
    long_only = generate_trend_signals(
        frame, replace(SignalConfig(), direction_mode="long")
    )
    short_only = generate_trend_signals(
        frame, replace(SignalConfig(), direction_mode="short")
    )
    assert (long_only["entry_signal"] >= 0).all()
    assert (short_only["entry_signal"] <= 0).all()


def _backtest_frame() -> pd.DataFrame:
    index = pd.date_range("2025-02-01", periods=8, freq="15min", tz="UTC")
    open_price = np.array([100.0, 101.0, 102.0, 103.0, 104.0, 106.0, 107.0, 108.0])
    frame = pd.DataFrame(
        {
            "open": open_price,
            "high": open_price + 0.4,
            "low": open_price - 0.4,
            "close": open_price + 0.2,
            "atr": 1.0,
            "entry_signal": [1, 0, 0, 0, 0, 0, 0, 0],
            "exit_signal": [False, False, False, False, True, False, False, False],
        },
        index=index,
    )
    return frame


def test_backtest_is_next_open_and_costs_are_adverse():
    frame = _backtest_frame()
    base = BacktestConfig(
        initial_cash=10_000.0,
        fixed_units=1.0,
        tick_size=1.0,
        tick_value=1.0,
        stop_atr_multiple=10.0,
        spread_price=0.0,
        slippage_price=0.0,
        commission_per_unit_per_side=0.0,
    )
    free = run_bar_backtest(frame, base)
    costly = run_bar_backtest(
        frame,
        replace(
            base,
            spread_price=2.0,
            slippage_price=0.5,
            commission_per_unit_per_side=1.0,
        ),
    )
    assert free.trades.iloc[0]["entry_i"] == 1
    assert free.trades.iloc[0]["entry_reference"] == 101.0
    assert free.trades.iloc[0]["exit_i"] == 5
    assert costly.metrics["net_profit"] < free.metrics["net_profit"]
    assert costly.trades.iloc[0]["commission_cost"] == 2.0
    assert costly.trades.iloc[0]["spread_slippage_cost"] == 3.0
    assert costly.trades.iloc[0]["costs"] == 5.0


def test_momentum_benchmarks_include_required_comparators():
    frame = _backtest_frame()
    frame["momentum_score"] = [-0.5, -0.4, 0.0, 0.3, 0.5, 0.6, -0.4, -0.5]
    benchmarks = generate_momentum_benchmarks(frame)
    assert set(benchmarks) == {"momentum_long_only", "momentum_long_short"}
    assert (benchmarks["momentum_long_only"]["entry_signal"] >= 0).all()
    assert (benchmarks["momentum_long_short"]["entry_signal"] < 0).any()


def test_backtest_supports_explicit_volatility_target():
    frame = _backtest_frame()
    frame["realized_vol_slow"] = 0.01
    result = run_bar_backtest(
        frame,
        BacktestConfig(
            initial_cash=10_000.0,
            fixed_units=None,
            target_annual_volatility=0.10,
            tick_size=1.0,
            tick_value=1.0,
            stop_atr_multiple=10.0,
            spread_price=0.0,
        ),
    )
    assert not result.trades.empty
    assert result.trades.iloc[0]["units"] > 0.0
    assert result.trades.iloc[0]["units"] != 1.0


def _slow_bars(n: int = 620) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    x = np.arange(n, dtype=float)
    close = 10_000.0 * np.exp(0.00012 * x + 0.0008 * np.sin(x / 13.0))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 1.0,
            "low": np.minimum(open_, close) - 1.0,
            "close": close,
        },
        index=index,
    )


def test_slow_h1_features_are_prefix_invariant_and_require_complete_hours():
    bars = _slow_bars()
    prefix = bars.iloc[:500]
    full = build_slow_trend_features(bars)
    short = build_slow_trend_features(prefix)
    columns = ["slow_momentum_score", "slow_atr_h1", "slow_vol_h1", "slow_decision"]
    pd.testing.assert_frame_equal(full.loc[prefix.index, columns], short[columns])
    decision_times = full.index[full["slow_decision"]]
    assert len(decision_times) > 100
    assert set(decision_times.minute) == {45}

    missing = bars.drop(bars.index[10])
    incomplete = build_slow_trend_features(missing)
    affected_hour = bars.index[10].floor("h")
    affected_rows = incomplete.index[incomplete.index.floor("h") == affected_hour]
    assert not incomplete.loc[affected_rows, "slow_decision"].any()


def test_slow_trend_is_long_only_and_executes_at_next_m15_open():
    features = build_slow_trend_features(_slow_bars())
    signals = generate_slow_trend_signals(
        features,
        SlowTrendConfig(entry_threshold=0.05, confirmation_closes=2),
    )
    entry_rows = np.flatnonzero(signals["entry_signal"].to_numpy())
    assert len(entry_rows) >= 1
    assert (signals["entry_signal"] >= 0).all()
    assert all(signals.index[row].minute == 45 for row in entry_rows)
    result = run_bar_backtest(
        signals,
        BacktestConfig(
            initial_cash=100_000.0,
            fixed_units=1.0,
            tick_size=0.01,
            tick_value=0.20,
            stop_atr_multiple=6.0,
            maximum_holding_bars=100_000,
            stop_mode="decision_close_next_open",
            stop_check_column="slow_decision",
        ),
    )
    assert not result.trades.empty
    first = result.trades.iloc[0]
    source_i = int(first["entry_i"]) - 1
    assert signals.index[source_i].minute == 45
    assert first["entry_time"] == signals.index[int(first["entry_i"])]


def test_decision_close_stop_cannot_fill_on_the_signal_close():
    frame = _backtest_frame()
    frame["slow_decision"] = True
    frame.loc[frame.index[2], "close"] = 90.0
    result = run_bar_backtest(
        frame,
        BacktestConfig(
            initial_cash=10_000.0,
            fixed_units=1.0,
            tick_size=1.0,
            tick_value=1.0,
            stop_atr_multiple=5.0,
            maximum_holding_bars=100,
            stop_mode="decision_close_next_open",
            stop_check_column="slow_decision",
        ),
    )
    trade = result.trades.iloc[0]
    assert trade["exit_reason"] == "catastrophe_stop"
    assert trade["exit_i"] == 3
    assert trade["exit_reference"] == frame["open"].iloc[3]
