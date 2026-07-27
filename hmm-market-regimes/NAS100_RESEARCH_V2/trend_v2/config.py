"""Configuration objects for the NAS100 Trend V2 research model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DirectionMode = Literal["both", "long", "short"]
StopMode = Literal["intrabar", "decision_close_next_open"]


@dataclass(frozen=True)
class FeatureConfig:
    """Causal feature windows, expressed in bars."""

    trend_horizon: int = 16
    efficiency_window: int = 32
    fast_vol_window: int = 16
    slow_vol_window: int = 96
    range_baseline_observations: int = 20
    range_baseline_min_observations: int = 3
    activity_baseline_observations: int = 20
    activity_baseline_min_observations: int = 3
    atr_window: int = 32
    momentum_horizons: tuple[int, ...] = (16, 32, 64)
    volume_columns: tuple[str, ...] = (
        "tick_count",
        "tick_volume",
        "volume",
        "real_volume",
    )
    epsilon: float = 1e-12

    @property
    def context_bars(self) -> int:
        # Hour-conditioned seasonal baselines require observations from prior days.
        seasonal = 24 * max(
            self.range_baseline_observations,
            self.activity_baseline_observations,
        )
        return max(self.slow_vol_window + 2, max(self.momentum_horizons) + 2, seasonal + 2)


@dataclass(frozen=True)
class RegimeConfig:
    """Parameters of the robust sticky Student-t hidden Markov model."""

    degrees_of_freedom: float = 7.0
    max_iter: int = 100
    tolerance: float = 1e-5
    sticky_prior: float = 18.0
    transition_prior: float = 1.5
    transition_floor: float = 1e-5
    mean_shrinkage: float = 8.0
    variance_shrinkage: float = 12.0
    variance_floor: float = 0.04
    robust_scale_floor: float = 1e-6
    min_state_occupancy: float = 0.10
    min_state_separation: float = 0.20
    random_state: int = 1729


@dataclass(frozen=True)
class SignalConfig:
    """Rules applied after regime filtering."""

    trend_probability: float = 0.55
    maximum_shock_probability: float = 0.35
    confirmation_bars: int = 2
    momentum_threshold: float = 0.20
    direction_mode: DirectionMode = "both"
    exit_on_momentum_flip: bool = True


@dataclass(frozen=True)
class SlowTrendConfig:
    """Preregistered H18 slow, asymmetric time-series momentum rules."""

    momentum_horizons_h1: tuple[int, ...] = (16, 32, 64)
    volatility_window_h1: int = 96
    atr_window_h1: int = 32
    entry_threshold: float = 0.35
    exit_threshold: float = 0.0
    confirmation_closes: int = 2
    minimum_holding_h1: int = 8
    rearm_threshold: float = 0.0

    @property
    def context_bars(self) -> int:
        observations = max(
            max(self.momentum_horizons_h1),
            self.volatility_window_h1,
            self.atr_window_h1,
        )
        return 4 * (observations + 4)

    def __post_init__(self) -> None:
        if not self.momentum_horizons_h1 or min(self.momentum_horizons_h1) < 2:
            raise ValueError("momentum_horizons_h1 must contain values >= 2")
        if tuple(sorted(set(self.momentum_horizons_h1))) != self.momentum_horizons_h1:
            raise ValueError("momentum_horizons_h1 must be unique and increasing")
        if min(self.volatility_window_h1, self.atr_window_h1) < 2:
            raise ValueError("H1 volatility and ATR windows must be >= 2")
        if self.confirmation_closes < 1 or self.minimum_holding_h1 < 1:
            raise ValueError("confirmation and minimum holding must be positive")
        if self.exit_threshold > self.entry_threshold:
            raise ValueError("exit_threshold cannot exceed entry_threshold")


@dataclass(frozen=True)
class BacktestConfig:
    """Bar-level execution assumptions.

    ``spread_price`` is the complete bid/ask spread. ``slippage_price`` is
    applied independently to entry and exit. ``commission_per_unit_per_side``
    is charged on every fill.
    """

    initial_cash: float = 100_000.0
    fixed_units: float  None = 1.0
    target_annual_volatility: float  None = None
    volatility_column: str = "realized_vol_slow"
    risk_fraction: float = 0.005
    min_units: float = 0.01
    max_units: float = 100.0
    unit_step: float = 0.01
    tick_size: float = 0.01
    tick_value: float = 0.20
    spread_price: float = 0.0
    spread_column: str  None = "spread_price"
    slippage_price: float = 0.0
    commission_per_unit_per_side: float = 0.0
    stop_atr_multiple: float = 2.5
    maximum_holding_bars: int = 96
    periods_per_year: int = 252 * 26
    force_close: bool = True
    pessimistic_intrabar: bool = True
    stop_mode: StopMode = "intrabar"
    stop_check_column: str  None = None

    def __post_init__(self) -> None:
        if self.target_annual_volatility is not None and not 0 < self.target_annual_volatility <= 1.0:
            raise ValueError("target_annual_volatility must be in (0, 1]")
        if self.stop_mode == "decision_close_next_open" and not self.stop_check_column:
            raise ValueError("decision-close stop requires stop_check_column")


@dataclass(frozen=True)
class TrendV2Config:
    features: FeatureConfig = field(default_factory=FeatureConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    signals: SignalConfig = field(default_factory=SignalConfig)
    slow_trend: SlowTrendConfig = field(default_factory=SlowTrendConfig)
