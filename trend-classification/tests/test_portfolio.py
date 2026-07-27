import numpy as np
import pandas as pd

from hsmm_xau.portfolio import (
    daily_returns_from_trades,
    mark_to_market_daily_returns,
    non_overlapping_mask,
    portfolio_metrics,
)


def test_non_overlapping_selector_and_daily_metrics():
    index = pd.date_range("2024-01-01", periods=4, freq="15min")
    exits = pd.to_datetime([index[2], index[2], index[3], index[3]])
    eligible = np.ones(4, dtype=bool)
    selected = non_overlapping_mask(index, exits, eligible)
    np.testing.assert_array_equal(selected, [True, False, False, True])
    daily = daily_returns_from_trades(exits, np.array([1, 1, 1, 1]), np.full(4, 100.0), selected)
    metrics = portfolio_metrics(daily)
    assert metrics["total_return"] > 0
    assert metrics["active_days"] == 1


def test_mark_to_market_distributes_open_position_path_by_day():
    index = pd.to_datetime(["2024-01-01 12:00", "2024-01-01 23:45", "2024-01-02 12:00"])
    bars = pd.DataFrame(
        {"bid_close": [100.0, 101.0, 102.0], "ask_close": [100.1, 101.1, 102.1]}, index=index
    )
    daily = mark_to_market_daily_returns(
        bars,
        pd.to_datetime([index[0]]),
        pd.to_datetime([index[-1]]),
        np.array([1.5]),
        np.array([100.0]),
        np.array([1]),
        np.array([True]),
    )
    np.testing.assert_allclose(daily.to_numpy(), [0.01, 0.005])
