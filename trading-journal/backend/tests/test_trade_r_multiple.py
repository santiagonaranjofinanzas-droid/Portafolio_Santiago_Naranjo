import pytest

from backend.app.main import _calculate_price_r_multiple, _normalize_trade_payload


def test_price_r_multiple_uses_trade_direction() -> None:
    assert _calculate_price_r_multiple(0, 100.0, 105.0, 10.0, True) == pytest.approx(0.5)
    assert _calculate_price_r_multiple(1, 100.0, 95.0, 10.0, True) == pytest.approx(0.5)
    assert _calculate_price_r_multiple(1, 100.0, 105.0, 10.0, True) == pytest.approx(-0.5)


def test_normalized_ea_payload_derives_r_multiple_when_missing() -> None:
    payload = {
        "position_id": 123,
        "symbol": "XAUUSD",
        "entrytime": 1_700_000_000,
        "exittime": 1_700_000_060,
        "entryprice": 100.0,
        "exitprice": 95.0,
        "gross_pnl": 50.0,
        "commission": 0.0,
        "swap": 0.0,
        "volume": 1.0,
        "type_op": 1,
        "exit_reason": 0,
        "netpnl": 50.0,
        "sl": 110.0,
        "valid_sl": True,
    }

    normalized = _normalize_trade_payload(payload)

    assert normalized["risk_price"] == pytest.approx(10.0)
    assert normalized["r_multiple"] == pytest.approx(0.5)


def test_normalized_payload_clears_r_multiple_without_valid_stop() -> None:
    payload = {
        "position_id": 123,
        "symbol": "XAUUSD",
        "entrytime": 1_700_000_000,
        "exittime": 1_700_000_060,
        "entryprice": 100.0,
        "exitprice": 105.0,
        "gross_pnl": 50.0,
        "volume": 1.0,
        "type_op": 0,
        "exit_reason": 0,
        "netpnl": 50.0,
        "sl": 0.0,
        "valid_sl": False,
        "r_multiple": 99.0,
    }

    normalized = _normalize_trade_payload(payload)

    assert normalized["valid_sl"] is False
    assert normalized["risk_price"] == 0.0
    assert normalized["r_multiple"] is None
