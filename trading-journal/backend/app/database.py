from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import inspect, text, event
from .settings import settings

database_url = settings.database_url
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

is_sqlite = database_url.startswith("sqlite") if database_url else True

connect_args = {"check_same_thread": False, "timeout": 30.0} if is_sqlite else {}
engine_kwargs = {"connect_args": connect_args}
if not is_sqlite:
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = 10
    engine_kwargs["max_overflow"] = 20

engine = create_engine(database_url, **engine_kwargs)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if is_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


def _ensure_runtime_columns() -> None:
    inspector = inspect(engine)

    table_columns = {
        "tradearchive": {
            "account_login": "TEXT",
            "server_name": "TEXT",
            "organization_id": "INTEGER DEFAULT 1",
            "partials": "TEXT",
            "user_notes": "TEXT",
            "setup_tags": "TEXT",
            "magic_number": "INTEGER",
            "entry_magic": "INTEGER",
            "exit_magic": "INTEGER",
            "deal_ticket": "INTEGER",
            "order_ticket": "INTEGER",
            "deal_comment": "TEXT",
            "order_comment": "TEXT",
            "external_id": "TEXT",
            "source_schema_version": "TEXT",
            "data_quality_score": "REAL",
            "data_quality_flags": "TEXT",
            "r_multiple": "REAL",
            "mae": "REAL",
            "mfe": "REAL",
            "mae_r": "REAL",
            "mfe_r": "REAL",
            "tw_mae_r": "REAL",
            "tw_mfe_r": "REAL",
            "efficiency": "REAL",
            "planned_tp": "REAL",
            "planned_max_r": "REAL",
            "what_if_result": "TEXT",
            "what_if_pnl": "REAL",
            "what_if_r": "REAL",
            "m1_candles_json": "TEXT",
        },
        "accountsnapshot": {
            "account_login": "TEXT",
            "server_name": "TEXT",
            "organization_id": "INTEGER DEFAULT 1",
        },
        "capitallog": {
            "organization_id": "INTEGER DEFAULT 1",
        },
        "ingestionevent": {
            "organization_id": "INTEGER DEFAULT 1",
        },
        "mt5node": {
            "organization_id": "INTEGER DEFAULT 1",
        },
        "apikey": {
            "key_secret": "VARCHAR(255)",
            "organization_id": "INTEGER DEFAULT 1",
        },
        "bloombergsnapshot": {
            "xi": "REAL DEFAULT 0.0",
            "lambda_dominant": "REAL DEFAULT 0.0",
            "entropy_spectral": "REAL DEFAULT 0.0",
            "mtl": "REAL DEFAULT 0.0",
            "kld": "REAL DEFAULT 0.0",
            "top_highest_corr": "TEXT DEFAULT '[]'",
            "top_lowest_corr": "TEXT DEFAULT '[]'",
            "context_id": "TEXT",
            "health_status": "TEXT DEFAULT 'degraded'",
            "source_health_json": "TEXT DEFAULT '{}'",
            "model_version": "TEXT",
            "feature_version": "TEXT",
            "account_login": "TEXT",
            "server_name": "TEXT",
            "fallback_active": "BOOLEAN DEFAULT 0",
            "alternative_scenario": "TEXT",
            "invalidation_conditions": "TEXT",
            "evidence": "TEXT",
            "account_implications": "TEXT",
            "llm_model": "TEXT",
            "prompt_version": "TEXT",
            "context_sent": "TEXT",
            "sources_used": "TEXT",
            "api_latency_ms": "INTEGER",
            "call_cost_usd": "REAL",
            "prompt_hash": "TEXT",
        },

        "aiauditevent": {
            "account_login": "TEXT",
            "server_name": "TEXT",
            "selected_bot": "INTEGER",
            "error_message": "TEXT",
        },
        "economicevent": {
            "actual": "TEXT",
            "released_to_feed": "BOOLEAN DEFAULT 0",
            "status": "TEXT DEFAULT 'scheduled'",
            "revision_count": "INTEGER DEFAULT 0",
            "surprise_value": "REAL",
        },
        "macronews": {
            "economic_event_key": "TEXT",
        },
    }

    with engine.begin() as conn:
        for table_name, columns in table_columns.items():
            if not inspector.has_table(table_name):
                continue

            existing = {col["name"] for col in inspector.get_columns(table_name)}
            for col_name, col_type in columns.items():
                if col_name in existing:
                    continue
                # For PostgreSQL, we need to handle types carefully. SQLite is more flexible.
                final_type = col_type.replace("TEXT", "VARCHAR(255)") if not is_sqlite else col_type
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {final_type}"))


def _ensure_runtime_indexes() -> None:
    index_statements = [
        "CREATE INDEX IF NOT EXISTS ix_tradearchive_metrics_scope ON tradearchive (organization_id, account_login, server_name, type_op, entrytime)",
        "CREATE INDEX IF NOT EXISTS ix_tradearchive_metrics_bot ON tradearchive (organization_id, account_login, server_name, magic_number, entrytime)",
        "CREATE INDEX IF NOT EXISTS ix_tradearchive_deal_ticket ON tradearchive (organization_id, deal_ticket)",
        "CREATE INDEX IF NOT EXISTS ix_tradearchive_exittime ON tradearchive (organization_id, exittime)",
        "CREATE INDEX IF NOT EXISTS ix_accountsnapshot_latest ON accountsnapshot (organization_id, captured_at)",
        "CREATE INDEX IF NOT EXISTS ix_ingestionevent_event ON ingestionevent (organization_id, event_id)",
        "CREATE INDEX IF NOT EXISTS ix_ingestionevent_status_received ON ingestionevent (organization_id, status, received_at)",
        "CREATE INDEX IF NOT EXISTS ix_ai_audit_org_created ON aiauditevent (organization_id, created_at)",
        "CREATE INDEX IF NOT EXISTS ix_economic_event_schedule ON economicevent (organization_id, scheduled_at, impact_score)",
        "CREATE INDEX IF NOT EXISTS ix_macro_news_event_key ON macronews (economic_event_key)",
        "CREATE INDEX IF NOT EXISTS ix_bloomberg_context ON bloombergsnapshot (organization_id, account_login, updated_at)",
        "CREATE INDEX IF NOT EXISTS ix_sentinel_context_scope ON sentinelcontextsnapshot (organization_id, account_login, generated_at)",
        "CREATE INDEX IF NOT EXISTS ix_sentinel_prediction_eval ON sentinelprediction (organization_id, evaluation_status, predicted_at)",
        "CREATE INDEX IF NOT EXISTS ix_portfolio_limits_scope ON portfoliolimits (organization_id, account_login)",
    ]


    with engine.begin() as conn:
        for statement in index_statements:
            table_name = statement.split(" ON ", 1)[1].split(" ", 1)[0]
            if inspect(engine).has_table(table_name):
                conn.execute(text(statement))


def create_db_and_tables():
    # Import model modules so every table is registered in SQLModel metadata.
    from . import models  # noqa: F401
    SQLModel.metadata.create_all(engine)
    _ensure_runtime_columns()
    _ensure_runtime_indexes()

def get_session():
    with Session(engine) as session:
        yield session
