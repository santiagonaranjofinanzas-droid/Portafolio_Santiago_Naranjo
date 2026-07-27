"""MR V4 trend-aligned buy-the-dip research package."""

from .backtest import MRV4BacktestResult, run_mr_v4_backtest
from .config import CANDIDATE_ID, MAGIC, MRV4Config
from .event_study import build_event_study, summarize_event_study
from .features import apply_shock_thresholds, build_mr_v4_features, calibrate_session_thresholds
from .signals import generate_mr_v4_signals

__all__ = [
    "CANDIDATE_ID", "MAGIC", "MRV4BacktestResult", "MRV4Config",
    "apply_shock_thresholds", "build_event_study", "build_mr_v4_features",
    "calibrate_session_thresholds", "generate_mr_v4_signals",
    "run_mr_v4_backtest", "summarize_event_study",
]
