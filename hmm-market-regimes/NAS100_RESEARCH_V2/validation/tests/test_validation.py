from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.validation import (
    PurgedCombinatorialCV,
    block_bootstrap,
    evaluate_gates,
    make_rolling_outer_folds,
    probability_backtest_overfitting,
    performance_summary,
)


def test_outer_folds_are_causal_and_six_or_more():
    index = pd.date_range("2020-01-01", "2026-06-30 23:45", freq="15min")
    folds = make_rolling_outer_folds(index, purge_bars=500, min_folds=6)
    assert len(folds) >= 6
    for fold in folds:
        assert fold.train_end < fold.test_start
        assert fold.test_indices[0] - fold.train_indices[-1] > 500


def test_cpcv_has_28_purged_splits():
    index = pd.date_range("2024-01-01", periods=800, freq="15min")
    event_end = index + pd.Timedelta(hours=2)
    cv = PurgedCombinatorialCV(8, 2, purge_bars=8, embargo_bars=8)
    splits = list(cv.split(index, event_end))
    assert len(splits) == 28
    assert all(np.intersect1d(train, test).size == 0 for train, test in splits)


def test_bootstrap_is_reproducible():
    values = np.tile(np.array([10.0, -5.0, 3.0, -2.0, 1.0]), 30)
    first = block_bootstrap(values, samples=200, block_size=5, seed=7)
    second = block_bootstrap(values, samples=200, block_size=5, seed=7)
    assert first == second
    assert first["probability_positive"] > 0.9


def test_pbo_and_gate_fail_closed():
    matrix = np.array([[1.0, -1.0, 1.0, -1.0], [-1.0, 1.0, -1.0, 1.0]])
    pbo = probability_backtest_overfitting(matrix)
    assert 0.0 <= pbo["pbo"] <= 1.0
    decision = evaluate_gates(
        {"closed_trades": 10, "profit_factor": 0.9, "daily_sharpe": 0.0, "dsr_probability": 0.0, "max_drawdown_pct": -20.0},
        {"pf_p05": 0.5, "expectancy_p05": -1.0, "pbo": 1.0},
        [{"profit_factor": 0.9}],
    )
    assert decision.approved is False


def test_performance_summary_aggregates_daily_pnl():
    trades = pd.DataFrame({
        "exit_time": ["2026-01-02 10:00", "2026-01-02 12:00", "2026-01-03 10:00"],
        "pnl": [100.0, -25.0, -10.0],
    })
    summary = performance_summary(trades, trials=3, start="2026-01-01", end="2026-01-04")
    assert summary["net_profit"] == 65.0
    assert summary["closed_trades"] == 3
    assert summary["profit_factor"] == 100.0 / 35.0
