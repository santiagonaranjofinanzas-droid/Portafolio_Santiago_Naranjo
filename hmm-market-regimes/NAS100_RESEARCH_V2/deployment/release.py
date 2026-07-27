"""Operational release gate; absence of evidence is an explicit failure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read(path: str  Path  None) -> dict:
    if path is None or not Path(path).exists():
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def evaluate_operational_release(
    model_decision_path: str  Path  None,
    parity_path: str  Path  None,
    holdout_summary_path: str  Path  None,
    forward_summary_path: str  Path  None,
) -> dict[str, Any]:
    model, parity = _read(model_decision_path), _read(parity_path)
    holdout, forward = _read(holdout_summary_path), _read(forward_summary_path)
    checks = [
        {"name": "institutional_backtest", "passed": bool(model.get("institutional_gate", {}).get("approved", False))},
        {"name": "python_mt5_signal_parity", "passed": bool(parity.get("signal_approved", parity.get("approved", False)))},
        {"name": "python_mt5_risk_parity", "passed": bool(parity.get("risk_approved", False))},
        {"name": "server_stop_coverage", "value": forward.get("server_stop_coverage", 0.0), "required": 1.0, "passed": forward.get("server_stop_coverage", 0.0) == 1.0},
        {"name": "orphan_positions", "value": forward.get("orphan_positions", 1), "required": 0, "passed": forward.get("orphan_positions", 1) == 0},
        {"name": "holdout_months", "value": holdout.get("months", 0), "required": 4, "passed": holdout.get("months", 0) >= 4},
        {"name": "holdout_trades", "value": holdout.get("closed_trades", 0), "required": 40, "passed": holdout.get("closed_trades", 0) >= 40},
        {"name": "forward_months", "value": forward.get("months", 0), "required": 6, "passed": forward.get("months", 0) >= 6},
        {"name": "forward_trades", "value": forward.get("closed_trades", 0), "required": 60, "passed": forward.get("closed_trades", 0) >= 60},
        {"name": "future_total_trades", "value": holdout.get("closed_trades", 0) + forward.get("closed_trades", 0), "required": 100, "passed": holdout.get("closed_trades", 0) + forward.get("closed_trades", 0) >= 100},
        {"name": "forward_profit_factor", "value": forward.get("profit_factor", 0.0), "required": 1.10, "passed": forward.get("profit_factor", 0.0) >= 1.10},
        {"name": "forward_drawdown", "value": forward.get("max_drawdown_pct", 100.0), "required": 10.0, "passed": abs(forward.get("max_drawdown_pct", 100.0)) <= 10.0},
    ]
    approved = all(item["passed"] for item in checks)
    return {
        "status": "APPROVED_FOR_CONTROLLED_LIVE" if approved else "LIVE_LOCKED",
        "approved": approved,
        "checks": checks,
        "counter_reset_rule": "ANY_MODEL_OR_PARAMETER_CHANGE_RESTARTS_HOLDOUT_AND_FORWARD",
    }
