"""MR V3 causal shock-rejection research package."""

from .backtest import MRV3BacktestResult, run_mr_v3_backtest, with_costs
from .config import CANDIDATE_ID, MAGIC, MRV3Config
from .features import build_mr_v3_features
from .signals import generate_mr_v3_signals

__all__ = [
    "CANDIDATE_ID",
    "MAGIC",
    "MRV3BacktestResult",
    "MRV3Config",
    "build_mr_v3_features",
    "generate_mr_v3_signals",
    "run_mr_v3_backtest",
    "with_costs",
]
