from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from backend.app import sentinel_service
from backend.app.models import AccountSnapshot, EconomicEvent, MacroNews, TradeArchive


def test_context_unifies_macro_and_selected_account(monkeypatch) -> None:
    test_engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(sentinel_service, "engine", test_engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(test_engine) as session:
        session.add(AccountSnapshot(
            organization_id=1,
            account_login="ACC-1",
            server_name="Broker-Real",
            captured_at=now,
            balance=100_000,
            equity=99_500,
            margin=2_000,
            margin_free=97_500,
            currency="USD",
        ))
        session.add(EconomicEvent(
            organization_id=0,
            event_key="cpi-context",
            title="Core CPI m/m",
            country="USD",
            currency="USD",
            scheduled_at=now + timedelta(minutes=30),
            impact="HIGH",
            impact_score=9,
            forecast="0.3%",
            previous="0.4%",
            updated_at=now,
        ))
        session.add(MacroNews(
            organization_id=0,
            title="Fed signals caution",
            content="Policy context",
            published_at=now,
            source="Test Wire",
            impact_score=8,
            ai_interpretation="Rates may remain restrictive.",
            ai_suggestion="Reduce duration risk.",
        ))
        session.add(TradeArchive(
            organization_id=1,
            position_id=101,
            symbol="XAUUSD",
            account_login="ACC-1",
            server_name="Broker-Real",
            entrytime=now - timedelta(hours=2),
            exittime=now - timedelta(hours=1),
            entryprice=2300,
            exitprice=2310,
            gross_pnl=100,
            commission=0,
            swap=0,
            volume=0.1,
            type_op=0,
            direction="Buy",
            exit_reason=0,
            netpnl=100,
            sl=2290,
            risk_price=10,
            valid_sl=True,
        ))
        session.commit()

    context = sentinel_service.build_sentinel_context(1, "ACC-1", "Broker-Real")

    assert context["context_id"]
    assert context["account"]["equity"] == 99_500
    assert context["events"][0]["title"] == "Core CPI m/m"
    assert context["news"][0]["title"] == "Fed signals caution"
    assert context["account_activity"]["symbols"][0]["symbol"] == "XAUUSD"
    assert context["source_health"]["account"]["status"] == "healthy"
