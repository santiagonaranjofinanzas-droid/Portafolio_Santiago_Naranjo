from datetime import datetime, timedelta

import pytest

from backend.app.engine import calculate_trade_physics


def _trade(**overrides):
    base = {
        "symbol": "TEST",
        "entrytime": datetime(2026, 1, 1, 10, 0),
        "exittime": datetime(2026, 1, 1, 10, 2),
        "entryprice": 100.0,
        "exitprice": 104.0,
        "type_op": 0,
        "sl": 95.0,
        "netpnl": 4.0,
    }
    base.update(overrides)
    return base


def _rates():
    start = datetime(2026, 1, 1, 10, 0)
    return [
        {"time": start, "high": 102.0, "low": 98.0},
        {"time": start + timedelta(minutes=1), "high": 106.0, "low": 99.0},
        {"time": start + timedelta(minutes=2), "high": 105.0, "low": 101.0},
    ]


def test_buy_excursions_use_intratrade_extremes_and_initial_stop():
    result = calculate_trade_physics(_trade(), _rates())
    assert result["mfe"] == pytest.approx(6.0)
    assert result["mae"] == pytest.approx(-2.0)
    assert result["mfe_r"] == pytest.approx(1.2)
    assert result["mae_r"] == pytest.approx(-0.4)
    assert result["efficiency"] == pytest.approx(4.0 / 6.0)
    assert result["excursion_source"] == "verified_m1"
    assert result["excursion_coverage"] == pytest.approx(1.0)


def test_sell_without_stop_has_price_excursions_but_no_r_metrics():
    trade = _trade(type_op=1, exitprice=96.0, sl=0.0)
    rates = [
        {"time": trade["entrytime"], "high": 103.0, "low": 99.0},
        {"time": trade["entrytime"] + timedelta(minutes=1), "high": 101.0, "low": 94.0},
        {"time": trade["exittime"], "high": 100.0, "low": 95.0},
    ]
    result = calculate_trade_physics(trade, rates)
    assert result["mfe"] == pytest.approx(6.0)
    assert result["mae"] == pytest.approx(-3.0)
    assert result["mfe_r"] != result["mfe_r"]
    assert result["mae_r"] != result["mae_r"]
    assert result["risk_basis"] == "price_only"


def test_missing_candles_never_fabricates_excursions_from_entry_exit():
    result = calculate_trade_physics(_trade(), [])
    assert result["mfe"] != result["mfe"]
    assert result["mae"] != result["mae"]
    assert result["efficiency"] != result["efficiency"]
    assert result["excursion_source"] == "unavailable"
    assert result["excursion_samples"] == 0


def test_subminute_trade_uses_the_overlapping_m1_candle():
    trade = _trade(
        entrytime=datetime(2026, 1, 1, 10, 0, 54),
        exittime=datetime(2026, 1, 1, 10, 0, 58),
        exitprice=101.0,
    )
    rates = [{"time": "2026-01-01T10:00:00Z", "high": 102.0, "low": 99.0}]
    result = calculate_trade_physics(trade, rates)
    assert result["excursion_source"] == "verified_m1"
    assert result["excursion_samples"] == 1
    assert result["excursion_coverage"] == pytest.approx(1.0)
