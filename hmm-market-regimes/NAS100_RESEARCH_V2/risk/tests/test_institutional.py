from __future__ import annotations

from NAS100_RESEARCH_V2.risk import (
    InstitutionalRiskGovernor,
    InstrumentSpec,
    PortfolioPosition,
    RiskSnapshot,
)


SPEC = InstrumentSpec("NAS100.fs", 0.01, 0.20, 0.01, 10.0, 0.01, 1_000.0)


def snapshot(*, equity: float = 100_000.0, day: float = 100_000.0, high: float = 100_000.0):
    return RiskSnapshot(equity, equity, 80_000.0, 800.0, day, high)


def test_risk_is_bounded_and_two_sleeves_share_budget():
    governor = InstitutionalRiskGovernor()
    first = governor.authorize_long(
        magic=6001,
        entry_price=20_000.0,
        atr_h1=50.0,
        vol_h1=0.005,
        snapshot=snapshot(),
        spec=SPEC,
        maximum_volume=10.0,
    )
    assert first.approved
    assert first.authorized_risk_cash <= 250.0
    second = governor.authorize_long(
        magic=6002,
        entry_price=20_000.0,
        atr_h1=50.0,
        vol_h1=0.005,
        snapshot=snapshot(),
        spec=SPEC,
        positions=[PortfolioPosition(6001, "NAS100.fs", first.volume, 20_000.0, first.disaster_stop)],
        maximum_volume=10.0,
    )
    assert second.approved
    assert first.authorized_risk_cash + second.authorized_risk_cash <= 500.0


def test_minimum_lot_is_rejected_instead_of_rounded_up():
    tiny = InstrumentSpec("NAS100.fs", 0.01, 100.0, 1.0, 10.0, 1.0, 20_000.0)
    decision = InstitutionalRiskGovernor().authorize_long(
        magic=6001,
        entry_price=20_000.0,
        atr_h1=500.0,
        vol_h1=0.05,
        snapshot=snapshot(),
        spec=tiny,
    )
    assert not decision.approved
    assert decision.reason == "BELOW_MINIMUM_SAFE_VOLUME"


def test_unprotected_position_and_loss_limits_fail_closed():
    governor = InstitutionalRiskGovernor()
    unprotected = governor.authorize_long(
        magic=6002,
        entry_price=20_000.0,
        atr_h1=50.0,
        vol_h1=0.005,
        snapshot=snapshot(),
        spec=SPEC,
        positions=[PortfolioPosition(6001, "NAS100.fs", 0.1, 20_000.0, 0.0)],
    )
    assert unprotected.reason == "UNPROTECTED_PORTFOLIO_POSITION"
    daily = governor.authorize_long(
        magic=6001,
        entry_price=20_000.0,
        atr_h1=50.0,
        vol_h1=0.005,
        snapshot=snapshot(equity=98_900.0, day=100_000.0, high=100_000.0),
        spec=SPEC,
    )
    assert daily.reason == "DAILY_LOSS_LOCK"


def test_drawdown_throttles_then_locks_and_emergency_flattens():
    governor = InstitutionalRiskGovernor()
    base = governor.authorize_long(
        magic=6001, entry_price=20_000.0, atr_h1=50.0, vol_h1=0.005,
        snapshot=snapshot(), spec=SPEC,
    )
    throttled_snapshot = RiskSnapshot(94_000.0, 94_000.0, 80_000.0, 800.0, 94_000.0, 100_000.0)
    throttled = governor.authorize_long(
        magic=6001, entry_price=20_000.0, atr_h1=50.0, vol_h1=0.005,
        snapshot=throttled_snapshot, spec=SPEC,
    )
    assert throttled.approved and throttled.throttle == 0.5
    assert throttled.volume < base.volume
    locked_snapshot = RiskSnapshot(92_000.0, 92_000.0, 80_000.0, 800.0, 92_000.0, 100_000.0)
    assert governor.authorize_long(
        magic=6001, entry_price=20_000.0, atr_h1=50.0, vol_h1=0.005,
        snapshot=locked_snapshot, spec=SPEC,
    ).reason == "DRAWDOWN_ENTRY_LOCK"
    emergency = RiskSnapshot(89_000.0, 89_000.0, 80_000.0, 800.0, 89_000.0, 100_000.0)
    assert governor.emergency_flatten_required(emergency)
