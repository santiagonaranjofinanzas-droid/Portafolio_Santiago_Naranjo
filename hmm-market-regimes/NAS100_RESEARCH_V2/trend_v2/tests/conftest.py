from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="session")
def synthetic_bars() -> pd.DataFrame:
    rng = np.random.default_rng(24051989)
    blocks = [
        (260, 0.00022, 0.00055, 115.0),
        (220, 0.00000, 0.00025, 70.0),
        (180, -0.00010, 0.00220, 320.0),
        (260, -0.00020, 0.00060, 125.0),
        (220, 0.00000, 0.00028, 75.0),
    ]
    returns: list[np.ndarray] = []
    activity: list[np.ndarray] = []
    for length, drift, volatility, ticks in blocks:
        innovations = rng.standard_t(df=7, size=length) / np.sqrt(7.0 / 5.0)
        returns.append(drift + volatility * innovations)
        activity.append(ticks + rng.normal(0.0, ticks * 0.10, size=length))
    log_returns = np.concatenate(returns)
    close = 17_000.0 * np.exp(np.cumsum(log_returns))
    open_price = np.r_[close[0], close[:-1]]
    intrabar = np.maximum(np.abs(log_returns), 0.00012) * close
    index = pd.date_range("2024-01-02", periods=len(close), freq="15min", tz="UTC")
    return pd.DataFrame(
        {
            "open": open_price,
            "high": np.maximum(open_price, close) + intrabar * 0.45,
            "low": np.minimum(open_price, close) - intrabar * 0.45,
            "close": close,
            "tick_volume": np.maximum(1.0, np.concatenate(activity)),
        },
        index=index,
    )
