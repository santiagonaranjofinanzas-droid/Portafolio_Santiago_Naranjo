"""TimescaleDB/PostgreSQL utilities for F9 persistence.

This module is deliberately persistence-only. Trading logic remains in the
existing F8 pipeline modules.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import psycopg

from production.io_utils import PROJECT_ROOT, load_dotenv


DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5435/hrp_rmt"


def database_url() -> str:
    load_dotenv()
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


@contextmanager
def connect() -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url()) as conn:
        yield conn


def apply_schema(schema_path: Path  None = None) -> None:
    path = schema_path or PROJECT_ROOT / "sql" / "001_schema_timescaledb.sql"
    sql = path.read_text(encoding="utf-8")
    with connect() as conn:
        conn.execute(sql)
