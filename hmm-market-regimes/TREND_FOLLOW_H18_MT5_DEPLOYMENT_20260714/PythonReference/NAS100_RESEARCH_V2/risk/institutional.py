"""Deterministic portfolio risk governor for the NAS100 H18 sleeves.

The module does not generate signals and never uses future PnL.  It is the
Python reference contract for the independently implemented MQL governor.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite, sqrt
from typing import Iterable


@dataclass(frozen=True)
class InstitutionalRiskPolicy:
    policy_id: str = "H18_RISK_V1_20260714"
    allowed_magics: tuple[int, ...] = (6001, 6002)
    expected_symbol: str = "NAS100.fs"
    risk_fraction_per_sleeve: float = 0.0025
    aggregate_risk_fraction: float = 0.0050
    portfolio_target_annual_volatility: float = 0.10
    executive_stop_atr: float = 6.0
    disaster_stop_atr: float = 8.0
    daily_entry_lock_fraction: float = 0.010
    drawdown_throttle_fraction: float = 0.050
    drawdown_entry_lock_fraction: float = 0.075
    drawdown_emergency_fraction: float = 0.100
    throttle_multiplier: float = 0.50
    max_margin_fraction: float = 0.20
    minimum_margin_level_pct: float = 300.0
    periods_per_year: int = 252 * 26

    def __post_init__(self) -> None:
        fractions = (
            self.risk_fraction_per_sleeve,
            self.aggregate_risk_fraction,
            self.portfolio_target_annual_volatility,
            self.daily_entry_lock_fraction,
            self.drawdown_throttle_fraction,
            self.drawdown_entry_lock_fraction,
            self.drawdown_emergency_fraction,
            self.throttle_multiplier,
            self.max_margin_fraction,
        )
        if any(not isfinite(x) or x <= 0.0 for x in fractions):
            raise ValueError("risk policy fractions must be finite and positive")
        if self.aggregate_risk_fraction < self.risk_fraction_per_sleeve:
            raise ValueError("aggregate risk cannot be below per-sleeve risk")
        if not (
            self.drawdown_throttle_fraction
            < self.drawdown_entry_lock_fraction
            < self.drawdown_emergency_fraction
        ):
            raise ValueError("drawdown thresholds must be strictly increasing")
        if self.disaster_stop_atr <= self.executive_stop_atr:
            raise ValueError("disaster stop must be wider than executive stop")
        if len(set(self.allowed_magics)) != len(self.allowed_magics):
            raise ValueError("allowed magics must be unique")
        if self.periods_per_year < 1 or self.minimum_margin_level_pct <= 100.0:
            raise ValueError("invalid annualization or margin threshold")


@dataclass(frozen=True)
class InstrumentSpec:
    symbol: str
    tick_size: float
    tick_value: float
    volume_min: float
    volume_max: float
    volume_step: float
    margin_per_lot: float

    def __post_init__(self) -> None:
        numeric = (
            self.tick_size,
            self.tick_value,
            self.volume_min,
            self.volume_max,
            self.volume_step,
            self.margin_per_lot,
        )
        if any(not isfinite(x) or x <= 0.0 for x in numeric):
            raise ValueError("instrument specification must be finite and positive")
        if self.volume_max < self.volume_min:
            raise ValueError("volume_max cannot be below volume_min")


@dataclass(frozen=True)
class PortfolioPosition:
    magic: int
    symbol: str
    volume: float
    entry_price: float
    disaster_stop: float


@dataclass(frozen=True)
class RiskSnapshot:
    equity: float
    balance: float
    free_margin: float
    margin_level_pct: float
    day_start_equity: float
    high_water_equity: float

    @property
    def daily_loss_fraction(self) -> float:
        return max(0.0, 1.0 - self.equity / self.day_start_equity)

    @property
    def drawdown_fraction(self) -> float:
        return max(0.0, 1.0 - self.equity / self.high_water_equity)


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str
    volume: float = 0.0
    executive_stop: float = 0.0
    disaster_stop: float = 0.0
    requested_risk_cash: float = 0.0
    authorized_risk_cash: float = 0.0
    existing_portfolio_risk_cash: float = 0.0
    throttle: float = 1.0


class InstitutionalRiskGovernor:
    """Pure pre-trade policy evaluator; caller owns state persistence/locking."""

    def __init__(self, policy: InstitutionalRiskPolicy  None = None) -> None:
        self.policy = policy or InstitutionalRiskPolicy()

    @staticmethod
    def _risk_per_lot(entry: float, stop: float, spec: InstrumentSpec) -> float:
        return abs(entry - stop) * spec.tick_value / spec.tick_size

    @staticmethod
    def _floor_volume(raw: float, spec: InstrumentSpec, cap: float) -> float:
        upper = min(spec.volume_max, cap)
        if not isfinite(raw) or raw < spec.volume_min or upper < spec.volume_min:
            return 0.0
        steps = floor((min(raw, upper) + 1e-12) / spec.volume_step)
        value = steps * spec.volume_step
        return value if value + 1e-12 >= spec.volume_min else 0.0

    def portfolio_risk_cash(
        self, positions: Iterable[PortfolioPosition], spec: InstrumentSpec
    ) -> float:
        total = 0.0
        for position in positions:
            if position.symbol != self.policy.expected_symbol:
                continue
            if position.magic not in self.policy.allowed_magics:
                continue
            if position.volume <= 0.0 or position.disaster_stop <= 0.0:
                return float("inf")
            total += self._risk_per_lot(
                position.entry_price, position.disaster_stop, spec
            ) * position.volume
        return total

    def authorize_long(
        self,
        *,
        magic: int,
        entry_price: float,
        atr_h1: float,
        vol_h1: float,
        snapshot: RiskSnapshot,
        spec: InstrumentSpec,
        positions: Iterable[PortfolioPosition] = (),
        maximum_volume: float = float("inf"),
        existing_risk_cash_override: float  None = None,
    ) -> RiskDecision:
        p = self.policy
        if magic not in p.allowed_magics:
            return RiskDecision(False, "MAGIC_NOT_ALLOWED")
        if spec.symbol != p.expected_symbol:
            return RiskDecision(False, "SYMBOL_MISMATCH")
        scalars = (
            entry_price,
            atr_h1,
            vol_h1,
            snapshot.equity,
            snapshot.balance,
            snapshot.free_margin,
            snapshot.day_start_equity,
            snapshot.high_water_equity,
        )
        if any(not isfinite(x) or x <= 0.0 for x in scalars):
            return RiskDecision(False, "INVALID_MARKET_OR_ACCOUNT_INPUT")
        if snapshot.margin_level_pct > 0.0 and snapshot.margin_level_pct < p.minimum_margin_level_pct:
            return RiskDecision(False, "MARGIN_LEVEL_LOCK")
        if snapshot.daily_loss_fraction >= p.daily_entry_lock_fraction:
            return RiskDecision(False, "DAILY_LOSS_LOCK")
        if snapshot.drawdown_fraction >= p.drawdown_entry_lock_fraction:
            return RiskDecision(False, "DRAWDOWN_ENTRY_LOCK")

        executive_stop = entry_price - p.executive_stop_atr * atr_h1
        disaster_stop = entry_price - p.disaster_stop_atr * atr_h1
        if disaster_stop <= 0.0 or disaster_stop >= executive_stop:
            return RiskDecision(False, "INVALID_STOP_GEOMETRY")
        risk_per_lot = self._risk_per_lot(entry_price, disaster_stop, spec)
        if risk_per_lot <= 0.0 or not isfinite(risk_per_lot):
            return RiskDecision(False, "INVALID_STOP_RISK")

        existing = (
            self.portfolio_risk_cash(positions, spec)
            if existing_risk_cash_override is None
            else float(existing_risk_cash_override)
        )
        if not isfinite(existing):
            return RiskDecision(False, "UNPROTECTED_PORTFOLIO_POSITION")
        aggregate_budget = snapshot.equity * p.aggregate_risk_fraction
        remaining_aggregate = max(0.0, aggregate_budget - existing)
        sleeve_budget = snapshot.equity * p.risk_fraction_per_sleeve
        requested = min(sleeve_budget, remaining_aggregate)
        if requested <= 0.0:
            return RiskDecision(
                False,
                "AGGREGATE_RISK_LIMIT",
                existing_portfolio_risk_cash=existing,
            )

        throttle = (
            p.throttle_multiplier
            if snapshot.drawdown_fraction >= p.drawdown_throttle_fraction
            else 1.0
        )
        stop_lot = requested / risk_per_lot
        vol_m15 = vol_h1 / 2.0
        annual_cash_vol_per_lot = (
            entry_price
            * vol_m15
            * (spec.tick_value / spec.tick_size)
            * sqrt(p.periods_per_year)
        )
        # Two highly correlated sleeves share the portfolio volatility budget.
        sleeve_vol_target = p.portfolio_target_annual_volatility / len(p.allowed_magics)
        volatility_lot = (
            snapshot.equity * sleeve_vol_target / annual_cash_vol_per_lot
        )
        margin_lot = (
            snapshot.free_margin * p.max_margin_fraction / spec.margin_per_lot
        )
        raw = min(stop_lot, volatility_lot, margin_lot, maximum_volume) * throttle
        volume = self._floor_volume(raw, spec, maximum_volume)
        if volume <= 0.0:
            return RiskDecision(
                False,
                "BELOW_MINIMUM_SAFE_VOLUME",
                executive_stop=executive_stop,
                disaster_stop=disaster_stop,
                requested_risk_cash=requested,
                existing_portfolio_risk_cash=existing,
                throttle=throttle,
            )
        authorized = risk_per_lot * volume
        if authorized > requested + max(0.01, requested * 1e-9):
            return RiskDecision(False, "NORMALIZED_VOLUME_EXCEEDS_RISK")
        return RiskDecision(
            True,
            "APPROVED",
            volume=volume,
            executive_stop=executive_stop,
            disaster_stop=disaster_stop,
            requested_risk_cash=requested,
            authorized_risk_cash=authorized,
            existing_portfolio_risk_cash=existing,
            throttle=throttle,
        )

    def emergency_flatten_required(self, snapshot: RiskSnapshot) -> bool:
        return snapshot.drawdown_fraction >= self.policy.drawdown_emergency_fraction
