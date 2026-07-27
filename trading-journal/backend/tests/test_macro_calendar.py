from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app import macro_service
from backend.app.models import EconomicEvent, MacroNews


def test_due_calendar_event_is_released_to_ai_feed(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(macro_service, "engine", engine)
    released_at = datetime.now(timezone.utc) - timedelta(seconds=20)
    monkeypatch.setattr(
        macro_service.MacroService,
        "fetch_economic_calendar",
        classmethod(
            lambda cls: [
                {
                    "event_key": "core-cpi-test",
                    "title": "Core CPI m/m",
                    "country": "USD",
                    "currency": "USD",
                    "scheduled_at": released_at.replace(tzinfo=None),
                    "impact": "HIGH",
                    "impact_score": 9,
                    "forecast": "0.3%",
                    "previous": "0.4%",
                    "actual": "0.2%",
                }
            ]
        ),
    )

    result = macro_service.MacroService.sync_economic_calendar()

    assert result["released"] == 1
    with Session(engine) as session:
        event = session.exec(select(EconomicEvent)).one()
        news = session.exec(select(MacroNews)).one()
    assert event.released_to_feed is True
    assert news.title == "Core CPI m/m"
    assert news.impact_score == 9
    assert "actual 0.2%" in news.ai_interpretation
