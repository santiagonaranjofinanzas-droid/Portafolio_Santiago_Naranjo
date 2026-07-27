import pandas as pd

from NAS100_RESEARCH_V2.deployment import compare_python_mt5, evaluate_operational_release


def test_parity_requires_exact_signals_and_one_tick_prices():
    signals = pd.DataFrame({"time": ["2026-01-01T00:00:00Z"], "signal": [1]})
    python = pd.DataFrame({"entry_time": ["2026-01-01T00:15:00Z"], "exit_time": ["2026-01-01T01:00:00Z"], "side": [1], "entry_price": [100.0], "exit_price": [101.0], "pnl": [20.0]})
    mt5 = python.copy()
    mt5["entry_price"] += 0.01
    assert compare_python_mt5(signals, signals.copy(), python, mt5)["approved"]
    mt5["entry_price"] += 0.01
    assert not compare_python_mt5(signals, signals.copy(), python, mt5)["approved"]


def test_operational_gate_is_locked_without_future_evidence():
    result = evaluate_operational_release(None, None, None, None)
    assert result["status"] == "LIVE_LOCKED"
    assert not result["approved"]
