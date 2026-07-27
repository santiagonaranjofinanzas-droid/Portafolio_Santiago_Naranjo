from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v2 import (
    CostConfig,
    FalsificationConfig,
    SignalConfig,
    evaluate_edge_existence,
    moving_block_bootstrap_mean,
)


def deterministic_reversion_map(cycles: int = 40) -> tuple[pd.DataFrame, pd.DataFrame]:
    cycle_length = 24
    n = cycles * cycle_length
    price = np.full(n, 18_000.0)
    z = np.zeros(n)
    for cycle in range(cycles):
        start = cycle * cycle_length
        direction = -1.0 if cycle % 2 == 0 else 1.0
        shock = 120.0 * direction
        for offset in range(17):
            price[start + offset] = 18_000.0 + shock * np.exp(-offset / 5.0)
        z[start] = -3.0 if direction < 0 else 3.0
    index = pd.date_range("2020-01-01", periods=n, freq="15min")
    bars = pd.DataFrame({"close": price}, index=index)
    filtered = pd.DataFrame({"z_residual": z}, index=index)
    return bars, filtered


def test_edge_map_is_monotone_and_passes_both_sides() -> None:
    bars, filtered = deterministic_reversion_map()
    zero_cost = CostConfig(spread_price=0.0, slippage_price_per_side=0.0, commission_per_lot_per_side=0.0)
    cfg = FalsificationConfig(
        bootstrap_samples=200,
        min_events_per_side=10,
        min_events_per_time_block=2,
    )
    result = evaluate_edge_existence(
        bars,
        filtered,
        SignalConfig(extreme_z=2.5),
        zero_cost,
        cfg,
    )

    assert result.side_summary["LONG"]["existence_passed"]
    assert result.side_summary["SHORT"]["existence_passed"]
    assert result.side_summary["LONG"]["monotonic_positive_blocks"] >= 3
    assert result.side_summary["SHORT"]["monotonic_positive_blocks"] >= 3
    assert set(result.horizon_table["horizon"]) == {1, 2, 4, 8, 16}


def test_block_bootstrap_is_seed_reproducible() -> None:
    values = np.linspace(-0.01, 0.03, 100)
    a = moving_block_bootstrap_mean(values, 200, np.random.default_rng(7), block_length=5)
    b = moving_block_bootstrap_mean(values, 200, np.random.default_rng(7), block_length=5)
    assert a == b


def test_zero_response_is_falsified_after_costs() -> None:
    n = 500
    index = pd.date_range("2020-01-01", periods=n, freq="15min")
    bars = pd.DataFrame({"close": 18_000.0}, index=index)
    z = np.zeros(n)
    z[::20] = -3.0
    z[10::20] = 3.0
    filtered = pd.DataFrame({"z_residual": z}, index=index)
    result = evaluate_edge_existence(
        bars,
        filtered,
        config=FalsificationConfig(
            bootstrap_samples=100,
            min_events_per_side=5,
            min_events_per_time_block=1,
        ),
    )
    assert not result.side_summary["LONG"]["existence_passed"]
    assert not result.side_summary["SHORT"]["existence_passed"]
    assert "TERMINAL_BOOTSTRAP_CI_NOT_POSITIVE" in result.side_summary["LONG"]["failure_reasons"]

