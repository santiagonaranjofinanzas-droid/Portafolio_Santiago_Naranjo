"""Institutional research implementation of the NAS100 Trend V2 candidate."""

from .backtest import BacktestResult, run_bar_backtest
from .config import (
    BacktestConfig,
    FeatureConfig,
    RegimeConfig,
    SignalConfig,
    SlowTrendConfig,
    TrendV2Config,
)
from .features import REGIME_FEATURES, build_causal_features, causal_prefix_invariant
from .model import TrendV2Model
from .regime import STATE_NAMES, StickyStudentTHMM
from .signals import (
    SignalState,
    generate_momentum_benchmark_signals,
    generate_momentum_benchmarks,
    build_slow_trend_features,
    generate_slow_trend_signals,
    generate_trend_signals,
)

__all__ = [
    "BacktestConfig",
    "BacktestResult",
    "FeatureConfig",
    "REGIME_FEATURES",
    "RegimeConfig",
    "STATE_NAMES",
    "SignalConfig",
    "SlowTrendConfig",
    "SignalState",
    "StickyStudentTHMM",
    "TrendV2Config",
    "TrendV2Model",
    "build_causal_features",
    "build_slow_trend_features",
    "causal_prefix_invariant",
    "generate_momentum_benchmark_signals",
    "generate_momentum_benchmarks",
    "generate_slow_trend_signals",
    "generate_trend_signals",
    "run_bar_backtest",
]
