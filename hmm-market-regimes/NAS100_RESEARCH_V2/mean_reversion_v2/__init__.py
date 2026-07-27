"""Mean Reversion V2: causal residual research stack for NAS100.fs."""

from .backtest import BacktestResult, run_mean_reversion_backtest
from .config import (
    BacktestConfig,
    CostConfig,
    FalsificationConfig,
    LocalTrendConfig,
    MeanReversionV2Config,
    SignalConfig,
)
from .falsification import (
    EdgeExistenceResult,
    FalsificationReport,
    build_falsification_report,
    evaluate_edge_existence,
    moving_block_bootstrap_mean,
)
from .model import AR1Estimate, ModelFitSummary, RobustLocalLinearTrend
from .pipeline import FoldEvaluation, MeanReversionV2
from .signals import SignalGenerationResult, generate_reentry_signals

__all__ = [
    "AR1Estimate",
    "BacktestConfig",
    "BacktestResult",
    "CostConfig",
    "EdgeExistenceResult",
    "FalsificationConfig",
    "FalsificationReport",
    "FoldEvaluation",
    "LocalTrendConfig",
    "MeanReversionV2",
    "MeanReversionV2Config",
    "ModelFitSummary",
    "RobustLocalLinearTrend",
    "SignalConfig",
    "SignalGenerationResult",
    "build_falsification_report",
    "evaluate_edge_existence",
    "generate_reentry_signals",
    "moving_block_bootstrap_mean",
    "run_mean_reversion_backtest",
]
