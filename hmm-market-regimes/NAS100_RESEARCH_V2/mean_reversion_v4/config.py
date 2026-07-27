"""Frozen configuration for MR V4 trend-aligned pullback research."""

from __future__ import annotations

from dataclasses import dataclass, field

from NAS100_RESEARCH_V2.mean_reversion_v2.config import CostConfig


@dataclass(frozen=True)
class MRV4Config:
    return_scale_window: int = 96
    atr_window: int = 32
    session_lower_quantile: float = 0.02
    maximum_shock_z_threshold: float = -1.5
    minimum_range_atr: float = 1.25
    trend_score_floor: float = 0.35
    maximum_confirmation_bars: int = 4
    stop_atr: float = 0.75
    maximum_holding_bars: int = 16
    minimum_reward_risk: float = 0.75
    event_horizons_bars: tuple[int, ...] = (4, 8, 16, 32)
    event_cooldown_bars: int = 32
    risk_fraction: float = 0.001
    initial_balance: float = 100_000.0
    min_lot: float = 0.01
    max_lot: float = 10.0
    lot_step: float = 0.01
    costs: CostConfig = field(default_factory=CostConfig)

    def __post_init__(self) -> None:
        if min(self.return_scale_window, self.atr_window) < 2:
            raise ValueError("rolling windows must be >= 2")
        if not 0.0 < self.session_lower_quantile < 0.5:
            raise ValueError("session_lower_quantile must be in (0, 0.5)")
        if self.maximum_shock_z_threshold >= 0.0:
            raise ValueError("maximum shock threshold must be negative")
        if min(self.minimum_range_atr, self.trend_score_floor, self.stop_atr) <= 0.0:
            raise ValueError("range, trend and stop thresholds must be positive")
        if min(self.maximum_confirmation_bars, self.maximum_holding_bars) < 1:
            raise ValueError("confirmation and holding windows must be positive")
        if not self.event_horizons_bars or tuple(sorted(set(self.event_horizons_bars))) != self.event_horizons_bars:
            raise ValueError("event horizons must be unique and increasing")
        if self.event_cooldown_bars < max(self.event_horizons_bars):
            raise ValueError("event cooldown must cover the maximum horizon")
        if not 0.0 < self.risk_fraction <= 0.01:
            raise ValueError("risk_fraction must be in (0, 0.01]")


MAGIC = 6003
CANDIDATE_ID = "MR_V4_01_TREND_PULLBACK_LONG"
SESSIONS = ("ASIA", "EUROPE", "US", "ROLLOVER")
