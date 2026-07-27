from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v2 import (
    AR1Estimate,
    BacktestConfig,
    CostConfig,
    SignalConfig,
    generate_reentry_signals,
    run_mean_reversion_backtest,
)


def passing_ar1() -> AR1Estimate:
    return AR1Estimate(
        intercept=0.0,
        phi=0.85,
        standard_error=0.01,
        ci_low=0.83,
        ci_high=0.87,
        half_life=4.27,
        observations=500,
        hac_lags=5,
        converged=True,
        gate_passed=True,
        gate_reasons=(),
    )


def test_signal_requires_extreme_then_reentry_and_separates_sides() -> None:
    index = pd.date_range("2025-01-01", periods=9, freq="15min")
    close = np.array([100.0, 97.0, 96.0, 97.5, 100.0, 103.0, 104.0, 102.0, 100.0])
    z = np.array([0.0, -2.6, -3.0, -1.8, 0.0, 2.6, 3.0, 1.8, 0.0])
    frame = pd.DataFrame(
        {
            "close": close,
            "level_price": 100.0,
            "residual_scale": 0.01,
            "z_residual": z,
            "structural_break": False,
            "phi_gate_passed": True,
        },
        index=index,
    )
    result = generate_reentry_signals(
        frame,
        SignalConfig(extreme_z=2.5, reentry_z=2.0, min_expected_cost_multiple=0.0),
        CostConfig(spread_price=0.0, slippage_price_per_side=0.0, commission_per_lot_per_side=0.0),
        passing_ar1(),
    )

    assert result.frame.index[result.frame["mr_long_signal"]].tolist() == [index[3]]
    assert result.frame.index[result.frame["mr_short_signal"]].tolist() == [index[7]]
    triggers = result.events[result.events["event"] == "REENTRY_TRIGGER"]
    assert triggers["eligible"].all()
    assert set(triggers["side"]) == {"LONG", "SHORT"}


def test_failed_phi_gate_audits_but_blocks_trigger() -> None:
    index = pd.date_range("2025-01-01", periods=3, freq="15min")
    frame = pd.DataFrame(
        {
            "close": [100.0, 95.0, 98.0],
            "level_price": [100.0] * 3,
            "residual_scale": [0.01] * 3,
            "z_residual": [0.0, -3.0, -1.5],
            "structural_break": False,
            "phi_gate_passed": False,
        },
        index=index,
    )
    result = generate_reentry_signals(
        frame,
        SignalConfig(min_expected_cost_multiple=0.0),
        CostConfig(spread_price=0.0, slippage_price_per_side=0.0, commission_per_lot_per_side=0.0),
    )
    assert not result.frame["mr_long_signal"].any()
    trigger = result.events[result.events["event"] == "REENTRY_TRIGGER"].iloc[0]
    assert not bool(trigger["eligible"])
    assert "PHI_GATE_FAILED" in trigger["reason"]


def test_backtest_executes_next_open_frozen_mean_and_has_no_partial() -> None:
    index = pd.date_range("2025-01-01", periods=5, freq="15min")
    bars = pd.DataFrame(
        {
            "open": [95.0, 96.0, 97.0, 99.0, 100.0],
            "high": [96.0, 97.0, 99.0, 101.0, 101.0],
            "low": [94.0, 95.0, 96.0, 98.0, 99.0],
            "close": [95.0, 96.0, 98.0, 100.0, 100.0],
        },
        index=index,
    )
    signals = pd.DataFrame(
        {
            "mr_long_signal": [False, True, False, False, False],
            "mr_short_signal": False,
            "mr_signal_target_price": [np.nan, 100.0, np.nan, np.nan, np.nan],
            "mr_signal_residual_scale": [np.nan, 0.02, np.nan, np.nan, np.nan],
            "mr_signal_half_life": [np.nan, 3.0, np.nan, np.nan, np.nan],
            "mr_model_transform": "log",
            "structural_break": False,
        },
        index=index,
    )
    cfg = BacktestConfig(
        risk_fraction=0.001,
        costs=CostConfig(
            spread_price=0.0,
            slippage_price_per_side=0.0,
            commission_per_lot_per_side=0.0,
        ),
    )
    result = run_mean_reversion_backtest(bars, signals, cfg)
    trade = result.trades.iloc[0]

    assert trade["signal_time"] == index[1]
    assert trade["entry_time"] == index[2]
    assert trade["entry_price"] == 97.0
    assert trade["target_price"] == 100.0
    assert trade["exit_reason"] == "FROZEN_MEAN"
    assert not bool(trade["partial_exit"])
    assert result.metrics["partial_exits"] == 0


def test_same_bar_stop_and_target_resolves_to_stop() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="15min")
    bars = pd.DataFrame(
        {
            "open": [95.0, 96.0, 97.0, 97.0],
            "high": [96.0, 97.0, 105.0, 98.0],
            "low": [94.0, 95.0, 80.0, 96.0],
            "close": [95.0, 96.0, 97.0, 97.0],
        },
        index=index,
    )
    signals = pd.DataFrame(
        {
            "mr_long_signal": [False, True, False, False],
            "mr_short_signal": False,
            "mr_signal_target_price": [np.nan, 100.0, np.nan, np.nan],
            "mr_signal_residual_scale": [np.nan, 0.02, np.nan, np.nan],
            "mr_signal_half_life": [np.nan, 3.0, np.nan, np.nan],
            "mr_model_transform": "log",
            "structural_break": False,
        },
        index=index,
    )
    zero_cost = CostConfig(spread_price=0.0, slippage_price_per_side=0.0, commission_per_lot_per_side=0.0)
    result = run_mean_reversion_backtest(bars, signals, BacktestConfig(costs=zero_cost))
    assert result.trades.iloc[0]["exit_reason"] == "STOP"


def test_bid_bar_execution_crosses_full_spread_on_long_entry() -> None:
    index = pd.date_range("2025-01-01", periods=4, freq="15min")
    bars = pd.DataFrame(
        {
            "open": [95.0, 96.0, 97.0, 100.0],
            "high": [96.0, 97.0, 99.0, 104.0],
            "low": [94.0, 95.0, 96.0, 99.0],
            "close": [95.0, 96.0, 98.0, 103.0],
            "spread_median": 2.0,
        },
        index=index,
    )
    signals = pd.DataFrame(
        {
            "mr_long_signal": [False, True, False, False],
            "mr_short_signal": False,
            "mr_signal_target_price": [np.nan, 103.0, np.nan, np.nan],
            "mr_signal_residual_scale": [np.nan, 0.02, np.nan, np.nan],
            "mr_signal_half_life": [np.nan, 3.0, np.nan, np.nan],
            "mr_model_transform": "log",
            "structural_break": False,
        },
        index=index,
    )
    bid_cost = CostConfig(
        spread_price=9.0,  # row spread_median must override this value
        slippage_price_per_side=0.0,
        commission_per_lot_per_side=0.0,
        bar_price_basis="bid",
    )
    result = run_mean_reversion_backtest(bars, signals, BacktestConfig(costs=bid_cost))
    trade = result.trades.iloc[0]
    assert trade["entry_price"] == 99.0  # ask = bid open 97 + spread 2
    assert trade["exit_price"] == 103.0  # long liquidation occurs at bid
