"""Shared append-only IO utilities for the F8 shadow paper pipeline."""

from __future__ import annotations

import csv
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROD_DATA = PROJECT_ROOT / "data" / "production"
AUDIT_DIR = PROD_DATA / "audit"
LEDGER_DIR = PROD_DATA / "ledger"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dotenv(path: Path  None = None) -> None:
    env_path = path or PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def append_csv_row(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def log_file_hash(path: Path, source: str) -> None:
    if not path.exists():
        return
    append_csv_row(
        AUDIT_DIR / "file_hashes.csv",
        ["timestamp_utc", "source", "path", "sha256", "size_bytes"],
        {
            "timestamp_utc": utc_now(),
            "source": source,
            "path": str(path.relative_to(PROJECT_ROOT)),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        },
    )


def read_universe() -> list[str]:
    path = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
    rows = read_csv(path)
    return [row["ticker"].upper() for row in rows if row.get("ticker")]


def latest_rows(path: Path, date_field: str = "date") -> dict[str, dict[str, str]]:
    rows = read_csv(path)
    latest: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("ticker", "")
        if not key:
            continue
        previous = latest.get(key)
        if previous is None or row.get(date_field, "") >= previous.get(date_field, ""):
            latest[key] = row
    return latest
