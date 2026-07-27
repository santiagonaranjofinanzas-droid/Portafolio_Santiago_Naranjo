from datetime import datetime, timedelta, timezone

from sqlmodel import Session, SQLModel, create_engine

from backend.app.main import _select_sentinel_snapshot, _sentinel_snapshot_payload
from backend.app.models import BloombergSnapshot


def _snapshot(*, account: str, server: str, modern: bool, updated_at: datetime) -> BloombergSnapshot:
    return BloombergSnapshot(
        organization_id=1,
        account_login=account,
        server_name=server,
        stress_prob=0.55,
        narrative="Institutional market baseline",
        weights_json='{"QQQ": 0.4, "CASH": 0.6}',
        model_version="v2" if modern else None,
        universe_version="systemic-v2" if modern else None,
        data_provider="Primary" if modern else None,
        data_status="fresh" if modern else "unavailable",
        observations=120 if modern else None,
        decision_json='{"weights": {"QQQ": 0.4, "CASH": 0.6}}' if modern else "{}",
        updated_at=updated_at,
    )


def test_legacy_demo_uses_modern_market_baseline_without_cross_account_weights() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(engine) as session:
        session.add(_snapshot(account="REAL-1", server="Broker-Live", modern=True, updated_at=now))
        session.add(_snapshot(account="DEMO-1", server="Broker-Demo", modern=False, updated_at=now + timedelta(minutes=1)))
        session.commit()

        snapshot, baseline_only = _select_sentinel_snapshot(session, 1, "DEMO-1", "Broker-Demo")
        payload = _sentinel_snapshot_payload(
            snapshot,
            requested_account_login="DEMO-1",
            requested_server_name="Broker-Demo",
            market_baseline_only=baseline_only,
        )

    assert snapshot is not None
    assert snapshot.account_login == "REAL-1"
    assert baseline_only is True
    assert payload["model_version"] == "v2"
    assert payload["account_login"] == "DEMO-1"
    assert payload["scope_status"] == "recalibrating"
    assert payload["weights"] == {}
    assert payload["decision"]["weights"] == {}


def test_exact_modern_demo_snapshot_wins_over_other_accounts() -> None:
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    with Session(engine) as session:
        session.add(_snapshot(account="REAL-1", server="Broker-Live", modern=True, updated_at=now))
        session.add(_snapshot(account="DEMO-1", server="Broker-Demo", modern=True, updated_at=now - timedelta(minutes=1)))
        session.commit()
        snapshot, baseline_only = _select_sentinel_snapshot(session, 1, "DEMO-1", "Broker-Demo")

    assert snapshot is not None
    assert snapshot.account_login == "DEMO-1"
    assert baseline_only is False

