"""Print TimescaleDB/PostgreSQL status and row counts."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.db import connect


TABLES = [
    "market_prices", "target_weights", "rebalance_decisions", "orders", "fills",
    "positions", "portfolio_nav", "tracking_error", "costs", "data_quality_log",
    "pipeline_status", "risk_log", "file_hashes",
]


def main() -> int:
    with connect() as conn:
        version = conn.execute("SELECT version()").fetchone()[0]
        ext = conn.execute("SELECT extversion FROM pg_extension WHERE extname='timescaledb'").fetchone()
        print(f"postgres={version}")
        print(f"timescaledb={'installed ' + ext[0] if ext else 'not_installed'}")
        for table in TABLES:
            count = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            print(f"{table}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
