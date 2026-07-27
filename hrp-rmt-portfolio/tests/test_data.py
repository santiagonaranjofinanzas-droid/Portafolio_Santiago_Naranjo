"""Unit tests for the data ingestion, quality checks, stale prices, and returns."""

from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from data.stale_price_detector import detect_stale_prices
from data.point_in_time_universe import PITUniverseManager
from data.returns import calculate_returns, calculate_portfolio_return


def test_stale_price_detector():
    """Verify that stale prices are correctly detected under various rules."""
    # Create mock EOD data
    dates = pd.date_range("2026-01-01", periods=6)
    df = pd.DataFrame(
        {
            "adjClose": [10.0, 10.0, 10.1, 10.1, 10.2, 10.2],
            "adjVolume": [1000, 0, 500, 50, 1000, np.nan],
        },
        index=dates,
    )

    # volume threshold is 100
    is_stale = detect_stale_prices(df, min_volume_threshold=100)

    # Expected:
    # Row 0: Vol=1000, price=10.0 -> False
    # Row 1: Vol=0 -> True (volume is 0)
    # Row 2: Vol=500, price=10.1 (changed from 10.0) -> False
    # Row 3: Vol=50, price=10.1 (frozen and vol < 100) -> True
    # Row 4: Vol=1000, price=10.2 -> False
    # Row 5: Vol=NaN -> True (volume is NaN)
    
    expected = [False, True, False, True, False, True]
    assert is_stale.tolist() == expected


def test_calculate_returns_stale_propagation():
    """Verify that returns are set to 0.0 on stale dates and computed correctly otherwise."""
    dates = pd.date_range("2026-01-01", periods=5)
    df = pd.DataFrame(
        {
            "adjClose": [10.0, 11.0, 11.0, 12.0, 13.0],
            "is_stale": [False, False, True, False, False],
        },
        index=dates,
    )

    returns = calculate_returns(df)

    # Expected raw simple returns:
    # Row 0: NaN
    # Row 1: (11 - 10) / 10 = 0.1
    # Row 2: (11 - 11) / 11 = 0.0
    # Row 3: (12 - 11) / 11 = 0.090909
    # Row 4: (13 - 12) / 12 = 0.083333

    # Clean simple returns should have Row 2 as 0.0 (stale)
    assert pd.isna(returns["simple_return"].iloc[0])
    assert returns["simple_return"].iloc[1] == pytest.approx(0.1)
    assert returns["simple_return"].iloc[2] == 0.0  # marked as stale
    assert returns["simple_return"].iloc[3] == pytest.approx((12 - 11) / 11)
    assert returns["simple_return"].iloc[4] == pytest.approx((13 - 12) / 12)

    # Clean log returns should also have Row 2 as 0.0
    assert pd.isna(returns["log_return"].iloc[0])
    assert returns["log_return"].iloc[1] == pytest.approx(np.log(11 / 10))
    assert returns["log_return"].iloc[2] == 0.0
    assert returns["log_return"].iloc[3] == pytest.approx(np.log(12 / 11))


def test_calculate_portfolio_return_linear():
    """Verify that portfolio returns aggregate linearly with weights."""
    returns_df = pd.DataFrame(
        {
            "SPY": [0.01, -0.02, 0.005],
            "AGG": [-0.002, 0.001, 0.003],
        }
    )

    weights = {"SPY": 0.6, "AGG": 0.4}
    p_ret = calculate_portfolio_return(returns_df, weights)

    # Row 0: 0.6 * 0.01 + 0.4 * (-0.002) = 0.006 - 0.0008 = 0.0052
    # Row 1: 0.6 * (-0.02) + 0.4 * 0.001 = -0.012 + 0.0004 = -0.0116
    # Row 2: 0.6 * 0.005 + 0.4 * 0.003 = 0.003 + 0.0012 = 0.0042
    
    assert p_ret.iloc[0] == pytest.approx(0.0052)
    assert p_ret.iloc[1] == pytest.approx(-0.0116)
    assert p_ret.iloc[2] == pytest.approx(0.0042)


def test_point_in_time_universe_filters(tmp_path):
    """Test PITUniverseManager filters based on history and ADV."""
    # Create a temporary universe CSV
    universe_file = tmp_path / "universe.csv"
    with open(universe_file, "w", encoding="utf-8") as f:
        f.write("ticker,name,asset_class,sub_class,region,currency,role\n")
        f.write("AAA,Asset A,Equity,US,US,USD,core\n")
        f.write("BBB,Asset B,Equity,US,US,USD,core\n")

    # Create temporary price files
    price_dir = tmp_path / "prices"
    price_dir.mkdir()

    # Asset A: 100 days of history, ADV = 10 million USD
    dates_a = pd.date_range("2026-01-01", periods=100)
    df_a = pd.DataFrame(
        {
            "date": dates_a.strftime("%Y-%m-%dT00:00:00.000Z"),
            "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0,
            "volume": 1_000_000,
            "adjOpen": 10.0, "adjHigh": 10.0, "adjLow": 10.0, "adjClose": 10.0,
            "adjVolume": 1_000_000,  # ADV = 10,000,000 USD
            "divCash": 0.0, "splitFactor": 1.0,
        }
    )
    df_a.to_csv(price_dir / "AAA.csv", index=False)

    # Asset B: 20 days of history, ADV = 2 million USD
    dates_b = pd.date_range("2026-03-20", periods=20)
    df_b = pd.DataFrame(
        {
            "date": dates_b.strftime("%Y-%m-%dT00:00:00.000Z"),
            "open": 10.0, "high": 10.0, "low": 10.0, "close": 10.0,
            "volume": 200_000,
            "adjOpen": 10.0, "adjHigh": 10.0, "adjLow": 10.0, "adjClose": 10.0,
            "adjVolume": 200_000,  # ADV = 2,000,000 USD
            "divCash": 0.0, "splitFactor": 1.0,
        }
    )
    df_b.to_csv(price_dir / "BBB.csv", index=False)

    # Create manager with:
    # min_history_days = 50
    # min_adv_usd = 5,000,000
    manager = PITUniverseManager(
        universe_csv=universe_file,
        price_dir=price_dir,
        min_history_days=50,
        min_adv_usd=5_000_000.0,
    )

    # Check state on 2026-02-15 (day 45 for AAA, BBB not started)
    state1 = manager.get_universe_state("2026-02-15")
    # AAA has only 45 days of history (< 50) -> excluded_lookback
    assert state1["metrics"]["N_active"] == 1
    assert state1["metrics"]["N_con_historial_suficiente"] == 0
    assert state1["metrics"]["N_excluido_por_lookback"] == 1
    assert state1["metrics"]["N_elegible"] == 0

    # Check state on 2026-03-10 (day 68 for AAA, BBB not started)
    state2 = manager.get_universe_state("2026-03-10")
    # AAA has 68 days of history (>= 50), ADV = 10M (>= 5M) -> eligible
    assert state2["metrics"]["N_active"] == 1
    assert state2["metrics"]["N_con_historial_suficiente"] == 1
    assert state2["metrics"]["N_elegible"] == 1
    assert "AAA" in state2["eligible_tickers"]

    # Check state on 2026-04-05 (day 95 for AAA, day 17 for BBB)
    state3 = manager.get_universe_state("2026-04-05")
    # AAA: active, history=95 >= 50, ADV=10M >= 5M -> eligible
    # BBB: active (started 2026-03-20), history=17 < 50 -> excluded_lookback
    assert state3["metrics"]["N_active"] == 2
    assert state3["metrics"]["N_con_historial_suficiente"] == 1
    assert state3["metrics"]["N_excluido_por_lookback"] == 1
    assert state3["metrics"]["N_elegible"] == 1
    assert "AAA" in state3["eligible_tickers"]
    assert "BBB" not in state3["eligible_tickers"]
