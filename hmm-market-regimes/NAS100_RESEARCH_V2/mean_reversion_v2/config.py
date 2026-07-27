"""Configuration objects for the causal NAS100 mean-reversion research model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal


Side = Literal["LONG", "SHORT"]


@dataclass(frozen=True)
class LocalTrendConfig:
    """Robust local-linear-trend and residual AR(1) settings.

    Prices are modelled in log space by default.  The process-variance ratios
    are selected on the training sample only, using a robust one-step forecast
    score.  No value is backfilled.
    """

    transform: Literal["log", "identity"] = "log"
    huber_c: float = 1.5
    level_q_ratios: tuple[float, ...] = (1e-4, 5e-4, 2e-3, 1e-2)
    slope_q_ratios: tuple[float, ...] = (1e-7, 1e-6, 1e-5, 1e-4)
    min_train_observations: int = 200
    score_burn_in: int = 50
    ar_burn_in: int = 50
    ar_confidence: float = 0.95
    ar_hac_lags: int  None = None
    min_phi: float = 0.0
    max_phi: float = 0.999
    min_half_life: float = 2.0
    max_half_life: float = 16.0
    structural_break_z: float = 6.0
    structural_scale_window: int = 64
    structural_scale_min_periods: int = 32
    structural_scale_multiplier: float = 2.5
    variance_floor: float = 1e-12

    def __post_init__(self) -> None:
        if self.huber_c <= 0:
            raise ValueError("huber_c must be positive")
        if self.min_train_observations < 30:
            raise ValueError("min_train_observations must be at least 30")
        if not 0 < self.ar_confidence < 1:
            raise ValueError("ar_confidence must be in (0, 1)")
        if self.min_half_life <= 0 or self.max_half_life <= self.min_half_life:
            raise ValueError("invalid half-life interval")
        if not self.level_q_ratios or not self.slope_q_ratios:
            raise ValueError("process variance grids cannot be empty")
        if min(self.level_q_ratios) <= 0 or min(self.slope_q_ratios) <= 0:
            raise ValueError("process variance ratios must be positive")
        if self.structural_scale_min_periods > self.structural_scale_window:
            raise ValueError("structural scale min_periods cannot exceed window")


@dataclass(frozen=True)
class SignalConfig:
    """Exhaustion/re-entry rules evaluated at the close of each bar."""

    extreme_z: float = 2.5
    reentry_z: float = 2.0
    max_setup_bars: int = 16
    min_expected_cost_multiple: float = 2.0
    require_phi_gate: bool = True
    block_on_structural_break: bool = True
    allowed_sides: tuple[Side, ...] = ("LONG", "SHORT")

    def __post_init__(self) -> None:
        if self.extreme_z <= 0:
            raise ValueError("extreme_z must be positive")
        if not 0 <= self.reentry_z < self.extreme_z:
            raise ValueError("reentry_z must be in [0, extreme_z)")
        if self.max_setup_bars < 1:
            raise ValueError("max_setup_bars must be positive")
        if self.min_expected_cost_multiple < 0:
            raise ValueError("min_expected_cost_multiple cannot be negative")
        invalid = set(self.allowed_sides).difference({"LONG", "SHORT"})
        if invalid:
            raise ValueError(f"invalid sides: {sorted(invalid)}")


@dataclass(frozen=True)
class CostConfig:
    """NAS100.fs execution assumptions, expressed in account-currency terms."""

    spread_price: float = 2.5
    slippage_price_per_side: float = 0.10
    commission_per_lot_per_side: float = 3.0
    bar_price_basis: Literal["bid", "mid"] = "bid"
    tick_size: float = 0.01
    tick_value: float = 0.20
    point: float = 0.01
    min_lot: float = 0.01
    max_lot: float = 10.0
    lot_step: float = 0.01

    def __post_init__(self) -> None:
        nonnegative = (
            self.spread_price,
            self.slippage_price_per_side,
            self.commission_per_lot_per_side,
        )
        if min(nonnegative) < 0:
            raise ValueError("cost assumptions cannot be negative")
        if min(self.tick_size, self.tick_value, self.point, self.min_lot, self.lot_step) <= 0:
            raise ValueError("contract and volume increments must be positive")
        if self.max_lot < self.min_lot:
            raise ValueError("max_lot must be at least min_lot")
        if self.bar_price_basis not in {"bid", "mid"}:
            raise ValueError("bar_price_basis must be 'bid' or 'mid'")

    @property
    def value_per_price_unit_per_lot(self) -> float:
        return self.tick_value / self.tick_size

    @property
    def commission_round_trip_price(self) -> float:
        cash = 2.0 * self.commission_per_lot_per_side
        return cash / self.value_per_price_unit_per_lot

    @property
    def round_trip_cost_price(self) -> float:
        return (
            self.spread_price
            + 2.0 * self.slippage_price_per_side
            + self.commission_round_trip_price
        )


@dataclass(frozen=True)
class BacktestConfig:
    """Single-position, next-open execution policy without partial exits."""

    initial_balance: float = 100_000.0
    risk_fraction: float = 0.0025
    stop_z: float = 4.0
    time_stop_half_lives: float = 2.0
    min_time_stop_bars: int = 2
    max_time_stop_bars: int = 64
    intrabar_policy: Literal["pessimistic"] = "pessimistic"
    force_close_end: bool = True
    costs: CostConfig = field(default_factory=CostConfig)

    def __post_init__(self) -> None:
        if self.initial_balance <= 0:
            raise ValueError("initial_balance must be positive")
        if not 0 < self.risk_fraction <= 0.05:
            raise ValueError("risk_fraction must be in (0, 0.05]")
        if self.stop_z <= 0 or self.time_stop_half_lives <= 0:
            raise ValueError("stop and time-stop multipliers must be positive")
        if self.min_time_stop_bars < 1 or self.max_time_stop_bars < self.min_time_stop_bars:
            raise ValueError("invalid time-stop bounds")


@dataclass(frozen=True)
class FalsificationConfig:
    """Pre-registered edge-existence and bootstrap criteria."""

    horizons: tuple[int, ...] = (1, 2, 4, 8, 16)
    chronological_blocks: int = 4
    minimum_monotonic_blocks: int = 3
    bootstrap_samples: int = 2_000
    bootstrap_block_length: int  None = None
    bootstrap_confidence: float = 0.95
    random_seed: int = 20260710
    min_events_per_side: int = 30
    min_events_per_time_block: int = 5
    gross_cost_multiple: float = 2.0
    monotonic_tolerance: float = 0.0

    def __post_init__(self) -> None:
        if not self.horizons or min(self.horizons) < 1:
            raise ValueError("horizons must contain positive integers")
        if tuple(sorted(set(self.horizons))) != self.horizons:
            raise ValueError("horizons must be strictly increasing")
        if self.chronological_blocks < 2:
            raise ValueError("at least two chronological blocks are required")
        if not 1 <= self.minimum_monotonic_blocks <= self.chronological_blocks:
            raise ValueError("invalid minimum_monotonic_blocks")
        if self.bootstrap_samples < 100:
            raise ValueError("bootstrap_samples must be at least 100")
        if not 0 < self.bootstrap_confidence < 1:
            raise ValueError("bootstrap_confidence must be in (0, 1)")
        if self.min_events_per_side < 1 or self.min_events_per_time_block < 1:
            raise ValueError("event minimums must be positive")


@dataclass(frozen=True)
class MeanReversionV2Config:
    model: LocalTrendConfig = field(default_factory=LocalTrendConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    falsification: FalsificationConfig = field(default_factory=FalsificationConfig)

    def to_dict(self) -> dict:
        return asdict(self)
