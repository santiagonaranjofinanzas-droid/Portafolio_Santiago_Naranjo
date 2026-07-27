from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from backend.app import main
from backend.app.models import TradeArchive


def _trade(position_id: int, account_login: str, server_name: str) -> TradeArchive:
    now = datetime.now(timezone.utc)
    return TradeArchive(
        organization_id=1,
        position_id=position_id,
        symbol="XAUUSD",
        account_login=account_login,
        server_name=server_name,
        entrytime=now,
        exittime=now,
        entryprice=2300.0,
        exitprice=2301.0,
        gross_pnl=10.0,
        commission=0.0,
        swap=0.0,
        volume=0.1,
        type_op=0,
        direction="Buy",
        exit_reason=0,
        netpnl=10.0,
        sl=2299.0,
        risk_price=1.0,
        valid_sl=True,
        r_multiple=1.0,
    )


def test_journal_pending_is_scoped_to_selected_account(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(main, "db_engine", engine)

    with Session(engine) as session:
        session.add(_trade(101, "60300368", "Broker-Real"))
        session.add(_trade(202, "10044931", "Broker-Demo"))
        session.commit()

    pending = main.get_pending_journal(
        account_login="60300368",
        server_name="Broker-Real",
        org_id=1,
    )

    assert [trade.position_id for trade in pending] == [101]

    with pytest.raises(HTTPException) as error:
        main.get_trade_journal(
            position_id=202,
            account_login="60300368",
            server_name="Broker-Real",
            org_id=1,
        )

    assert error.value.status_code == 404
