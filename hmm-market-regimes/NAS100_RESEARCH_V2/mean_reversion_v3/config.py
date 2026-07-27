"""Frozen configuration for the preregistered MR V3 shock-rejection test."""

from __future__ import annotations

from dataclasses import dataclass, field

from NAS100_RESEARCH_V2.mean_reversion_v2.config import CostConfig


@dataclass(frozen=True)
class MRV3Config:
    return_scale_window: int = 96
    atr_window: int = 32
    shock_z: float = 3.0
    minimum_range_atr: float = 1.5
    maximum_rejection_bars: int = 4
    trend_score_veto: float = 0.35
    stop_atr: float = 1.0
    maximum_holding_bars: int = 16
    minimum_reward_risk: float = 1.0
    risk_fraction: float = 0.001
    initial_balance: float = 100_000.0
    min_lot: float = 0.01
    max_lot: float = 10.0
    lot_step: float = 0.01
    costs: CostConfig = field(default_factory=CostConfig)

    def __post_init__(self) -> None:
        if min(self.return_scale_window, self.atr_window) < 2:
            raise ValueError("rolling windows must be >= 2")
        if self.shock_z <= 0 or self.minimum_range_atr <= 0 or self.stop_atr <= 0:
            raise ValueError("shock, range and stop thresholds must be positive")
        if self.maximum_rejection_bars < 1 or self.maximum_holding_bars < 1:
            raise ValueError("rejection and holding windows must be positive")
        if not 0 < self.risk_fraction <= 0.01:
            raise ValueError("risk_fraction must be in (0, 0.01]")
        if self.minimum_reward_risk <= 0:
            raise ValueError("minimum_reward_risk must be positive")


MAGIC = 6003
CANDIDATE_ID = "MR_V3_01_SHOCK_REJECTION"
