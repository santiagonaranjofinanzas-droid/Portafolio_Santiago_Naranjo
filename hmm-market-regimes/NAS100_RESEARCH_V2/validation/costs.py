from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CostScenario:
    name: str
    spread_price: float
    slippage_price: float
    commission_per_lot_per_side: float
    latency_ms: int


@dataclass(frozen=True)
class AxiCostModel:
    base_spread_price: float = 2.50
    p95_spread_price: float = 3.50
    max_observed_spread_price: float = 16.75
    slippage_price: float = 0.10
    commission_per_lot_per_side: float = 3.00
    latency_p95_ms: int = 250

    @classmethod
    def from_profile(cls, profile_path: str  Path) -> "AxiCostModel":
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        return cls(
            base_spread_price=float(profile["snapshot_spread_price"]),
            p95_spread_price=max(3.50, float(profile["snapshot_spread_price"])),
            slippage_price=float(profile["slippage_price_assumption"]),
            commission_per_lot_per_side=float(profile["commission_per_lot_per_side_assumption"]),
        )

    def scenarios(self) -> dict[str, CostScenario]:
        return {
            "base": CostScenario("base", self.base_spread_price, self.slippage_price, self.commission_per_lot_per_side, 0),
            "adverse": CostScenario("adverse", self.p95_spread_price, self.slippage_price * 1.5, self.commission_per_lot_per_side, self.latency_p95_ms),
            "crisis": CostScenario("crisis", self.p95_spread_price * 1.5, self.slippage_price * 2.0, self.commission_per_lot_per_side * 1.5, self.latency_p95_ms),
        }
