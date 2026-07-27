import pytest
import fakeredis
import pandas as pd
from app.engine import run_decision_engine

@pytest.fixture
def redis_mock():
    return fakeredis.FakeRedis(decode_responses=True)

def test_1_fallback_quant_collapse(redis_mock):
    res = run_decision_engine(100000, {"status": "fallback"}, None, market_state="stress", redis_client=redis_mock)
    assert res["fallback_active"] is True
    assert res["decision_inputs"]["fallback_action"] == "MOVE_TO_SAFE_BASE"
    assert res["exposure_total"] > 0

def test_2_normal_fusion(redis_mock):
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    miro_out = {"R_narr": 0.5, "omega_narr": 0.2}
    
    res = run_decision_engine(100000, quant_out, miro_out, redis_client=redis_mock)
    assert res["rebalance_required"] is True
    assert res["fallback_active"] is False
    assert res["decision_inputs"]["w_narr_final"] > 0.0

def test_3_drawdown_critical_halt(redis_mock):
    redis_mock.set("portfolio:hwm", 100000)
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    
    # 85k es -15% (Critical)
    res = run_decision_engine(85000, quant_out, None, redis_client=redis_mock)
    assert res["fail_safe_active"] is True
    assert res["fail_safe_level"] == "critical"
    assert res["exposure_total"] == 0.0
    assert redis_mock.exists("portfolio:cooldown_until")

def test_4_narrative_unavailable(redis_mock):
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    
    # MiroFish is None
    res = run_decision_engine(100000, quant_out, mirofish_output=None, redis_client=redis_mock)
    assert res["decision_inputs"]["w_narr_final"] == 0.0
    assert res["decision_inputs"]["omega_narr"] == float('inf')

def test_5_hwm_update(redis_mock):
    redis_mock.set("portfolio:hwm", 100000)
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    
    # NAV increases to 110k
    res = run_decision_engine(110000, quant_out, None, redis_client=redis_mock)
    
    # HWM should be updated to 110k
    assert float(redis_mock.get("portfolio:hwm")) == 110000.0
    assert res["decision_inputs"]["drawdown_current"] == 0.0

def test_6_mt5_stale_blocking(redis_mock):
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    old_w = {"QQQ": 0.3, "GLD": 0.2, "CASH": 0.5}
    res = run_decision_engine(100000, quant_out, None, old_weights=old_w, redis_client=redis_mock, is_mt5_stale=True)
    assert res["recommendations_blocked"] is True
    assert res["status"] == "stale"
    assert res["weights"] == old_w

def test_7_no_open_positions_100_percent_cash(redis_mock):
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    res = run_decision_engine(100000, quant_out, None, redis_client=redis_mock, positions=[])
    assert res["current_exposures"]["weights_by_proxy"] == {}
    assert res["weights"] == {"CASH": 1.0}
    assert res["status"] == "no_open_positions"
    assert res["shadow_mode"] is True
    assert res["execution_allowed"] is False

def test_8_derivative_exposure_calculation(redis_mock):
    from app.engine import calculate_exposure_metrics
    # 0.1 lots of XAUUSD (contract size 100) at price 2300, profit currency USD (conversion rate 1.0)
    positions = [
        {"symbol": "XAUUSD.pro", "volume": 0.1, "price_current": 2300.0, "type": 0}, # Buy
        {"symbol": "US100", "volume": 0.2, "price_current": 18000.0, "type": 1} # Sell
    ]
    stats = calculate_exposure_metrics(positions, 100000)
    assert stats["gross_exposure"] > 0
    assert "GLD" in stats["exposures_by_proxy"]
    assert "QQQ" in stats["exposures_by_proxy"]
    assert stats["exposures_by_proxy"]["GLD"] == 23000.0 # 0.1 * 100 * 2300 * 1.0
    assert stats["exposures_by_proxy"]["QQQ"] == -36000.0 # 0.2 * 10 * 18000 * 1.0 (US100 contract size = 10)

def test_9_dynamic_limits_inheritance(redis_mock):
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    # Try custom limits restricting QQQ to max 10%
    custom_limits = {"max_allocation_qqq": 0.10, "max_allocation_gld": 0.20, "min_cash": 0.70}
    positions = [{"symbol": "XAUUSD", "volume": 0.1, "price_current": 2300.0, "type": 0, "contract_size": 100}]
    res = run_decision_engine(100000, quant_out, None, redis_client=redis_mock, portfolio_limits=custom_limits, positions=positions)
    assert res["weights"]["QQQ"] <= 0.11
    assert res["weights"]["CASH"] >= 0.70


def test_10_stress_tests_and_approval_gate(redis_mock):
    quant_out = {"stress_probability_t5": 0.2, "omega_quant": 0.3, "regime_probabilities": {"low": 0.8}}
    positions = [{"symbol": "XAUUSD", "volume": 0.1, "price_current": 2300.0, "type": 0, "contract_size": 100}]
    res = run_decision_engine(100000, quant_out, None, redis_client=redis_mock, positions=positions)
    assert res["stress_tests"]["methodology_version"] == "sentinel-stress-v1"
    assert "liquidity_crisis" in res["stress_tests"]["scenarios"]
    assert res["approval_status"] in {"pending", "blocked"}
