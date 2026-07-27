"""Deployment remains fail-closed until parity and future evidence pass."""

from .parity import compare_python_mt5
from .h18_mt5_parity import compare_h18_decisions, compare_h18_risk_decisions, python_h18_decisions
from .release import evaluate_operational_release

__all__ = [
    "compare_h18_decisions",
    "compare_python_mt5",
    "evaluate_operational_release",
    "python_h18_decisions",
]
