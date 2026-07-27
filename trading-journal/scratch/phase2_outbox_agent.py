#!/usr/bin/env python3
"""
Phase 2 local outbox agent.

- Reads JSON trade events from a local folder.
- Persists events into a SQLite outbox queue.
- Sends events to BK ingest endpoint with retries.
- Adds optional HMAC headers for authenticated ingestion.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import hmac
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentSettings:
    endpoint: str
    queue_db_path: str
    queue_dir: str
    poll_seconds: float
    request_timeout_seconds: float
    max_attempts: int
    backoff_base_seconds: float
    hmac_secret: str
    hmac_key_id: str


def load_settings() -> AgentSettings:
    return AgentSettings(
        endpoint=os.getenv("BK_AGENT_ENDPOINT", "https://black-knight-backend.onrender.com/api/v1/ingest/trade"),
        queue_db_path=os.getenv("BK_AGENT_DB_PATH", "_journal_data/outbox.db"),
        queue_dir=os.getenv("BK_AGENT_QUEUE_DIR", "_journal_data/outbox_queue"),
        poll_seconds=float(os.getenv("BK_AGENT_POLL_SECONDS", "2")),
        request_timeout_seconds=float(os.getenv("BK_AGENT_TIMEOUT_SECONDS", "10")),
        max_attempts=int(os.getenv("BK_AGENT_MAX_ATTEMPTS", "12")),
        backoff_base_seconds=float(os.getenv("BK_AGENT_BACKOFF_BASE_SECONDS", "2")),
        hmac_secret=os.getenv("BK_HMAC_SECRET", ""),
        hmac_key_id=os.getenv("BK_HMAC_KEY_ID", ""),
    )


def ensure_db(conn: sqlite3.Connection) -> None:
    # Configure SQLite for concurrent non-blocking writes
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS outbox_events (
            event_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            next_retry_at REAL NOT NULL DEFAULT 0,
            last_error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
        """
    )
    conn.commit()


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def _normalize_payload_timestamps(payload: dict[str, Any]) -> None:
    # Backend expects datetime values; MT5 exporter may emit Unix epoch ints.
    for field in ("entrytime", "exittime", "captured_at"):
        value = payload.get(field)
        if isinstance(value, (int, float)):
            payload[field] = datetime.fromtimestamp(float(value), tz=timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


def _coerce_int(value: Any) -> int  None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:
            return None
        return int(value)

    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _normalize_trade_bot_id(payload: dict[str, Any]) -> None:
    is_snapshot = payload.get("event_type") == "account_snapshot" or (
        "balance" in payload and "equity" in payload and "position_id" not in payload
    )
    if is_snapshot:
        return

    for key in ("entry_magic", "open_magic", "entry_bot_id", "magic_number", "exit_magic", "magic", "magicNumber", "bot_id", "botId", "ea_id", "expert_id"):
        parsed = _coerce_int(payload.get(key))
        if parsed is not None:
            payload["magic_number"] = parsed
            return

    for key in ("comment", "deal_comment", "order_comment", "expert_comment", "user_notes"):
        raw = payload.get(key)
        if raw is None:
            continue
        match = re.search(r"(?:botnodemagic)[^0-9]{0,8}(\d{2,10})", str(raw), flags=re.IGNORECASE)
        if not match:
            continue
        parsed = _coerce_int(match.group(1))
        if parsed is not None:
            payload["magic_number"] = parsed
            return

    payload.setdefault("magic_number", None)


def _validate_payload(payload: dict[str, Any]) -> None:
    is_snapshot = payload.get("event_type") == "account_snapshot" or (
        "balance" in payload and "equity" in payload and "position_id" not in payload
    )

    if is_snapshot:
        if payload.get("balance") is None or payload.get("equity") is None:
            raise ValueError("Snapshot payload requires balance and equity")
        return

    pid = payload.get("position_id")
    if pid is None or str(pid).strip() == "":
        raise ValueError("Trade payload requires position_id")


def make_event_id(payload: dict[str, Any]) -> str:
    if payload.get("event_id"):
        return str(payload["event_id"]).strip()

    if payload.get("event_type") == "account_snapshot" or (
        "balance" in payload and "equity" in payload and "position_id" not in payload
    ):
        material = f"snapshot{payload.get('account_login','na')}{payload.get('captured_at','na')}"
        digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
        return f"snapshot-{digest}"

    material = (
        f"{payload.get('account_login','na')}"
        f"{payload.get('server_name','na')}"
        f"{payload.get('position_id','na')}"
        f"{payload.get('deal_ticket','na')}"
        f"{payload.get('entrytime','na')}"
        f"{payload.get('exittime','na')}"
        f"{payload.get('magic_number','na')}"
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"trade-{digest}"


def enqueue_payload(conn: sqlite3.Connection, payload: dict[str, Any]) -> str:
    now = time.time()
    _validate_payload(payload)
    _normalize_trade_bot_id(payload)
    _normalize_payload_timestamps(payload)
    event_id = make_event_id(payload)
    payload_json = canonical_json(payload)

    existing = conn.execute(
        "SELECT status FROM outbox_events WHERE event_id = ?",
        (event_id,),
    ).fetchone()

    if existing is None:
        conn.execute(
            """
            INSERT INTO outbox_events (event_id, payload_json, status, attempts, next_retry_at, created_at, updated_at)
            VALUES (?, ?, 'pending', 0, 0, ?, ?)
            """,
            (event_id, payload_json, now, now),
        )
    elif existing[0] != "sent":
        conn.execute(
            """
            UPDATE outbox_events
            SET payload_json = ?,
                status = 'pending',
                attempts = 0,
                next_retry_at = 0,
                last_error = NULL,
                updated_at = ?
            WHERE event_id = ?
            """,
            (payload_json, now, event_id),
        )
    conn.commit()
    return event_id


def ingest_drop_folder(conn: sqlite3.Connection, queue_dir: str) -> int:
    if "*" not in queue_dir:
        Path(queue_dir).mkdir(parents=True, exist_ok=True)
    imported = 0

    for json_path in glob.glob(os.path.join(queue_dir, "*.json")):
        try:
            # Accept both utf-8, utf-8 BOM, and utf-16 files written from PowerShell.
            try:
                with open(json_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
                payload = json.loads(content)
            except (UnicodeDecodeError, json.JSONDecodeError):
                with open(json_path, "r", encoding="utf-16") as f:
                    content = f.read()
                payload = json.loads(content)

            if not isinstance(payload, dict):
                raise ValueError("Payload must be a JSON object")
            enqueue_payload(conn, payload)
            os.remove(json_path)
            imported += 1
        except Exception as exc:
            err_path = f"{json_path}.err"
            try:
                os.rename(json_path, err_path)
            except OSError:
                pass
            print(f"[WARN] Could not import {json_path}: {exc}")

    return imported


def build_headers(settings: AgentSettings, payload_json: str) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }

    if settings.hmac_secret:
        timestamp = str(int(time.time()))
        message = f"{timestamp}.{payload_json}".encode("utf-8")
        signature = hmac.new(settings.hmac_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
        headers["X-BK-Timestamp"] = timestamp
        headers["X-BK-Signature"] = signature
        if settings.hmac_key_id:
            headers["X-BK-Key-Id"] = settings.hmac_key_id

    return headers


def send_event(settings: AgentSettings, event_id: str, payload_json: str) -> tuple[bool, str]:
    headers = build_headers(settings, payload_json)
    headers["X-BK-Event-Id"] = event_id

    request = urllib.request.Request(
        settings.endpoint,
        data=payload_json.encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        return False, f"HTTP {exc.code}: {body}"
    except Exception as exc:
        return False, str(exc)


def flush_outbox(conn: sqlite3.Connection, settings: AgentSettings) -> tuple[int, int]:
    now = time.time()
    rows = conn.execute(
        """
        SELECT event_id, payload_json, attempts
        FROM outbox_events
        WHERE (
            status IN ('pending','retry')
            OR (status = 'dead' AND last_error LIKE 'HTTP 401:%')
          )
          AND next_retry_at <= ?
        ORDER BY
          CASE
            WHEN event_id LIKE 'trade-%' THEN 0
            WHEN payload_json LIKE '%"position_id"%' THEN 0
            ELSE 1
          END ASC,
          created_at ASC
        LIMIT 100
        """,
        (now,),
    ).fetchall()

    sent = 0
    failed = 0

    for event_id, payload_json, attempts in rows:
        normalized_payload_json = payload_json
        try:
            payload_obj = json.loads(payload_json)
            if isinstance(payload_obj, dict):
                _normalize_payload_timestamps(payload_obj)
                normalized_payload_json = canonical_json(payload_obj)
                if normalized_payload_json != payload_json:
                    conn.execute(
                        """
                        UPDATE outbox_events
                        SET payload_json=?, updated_at=?
                        WHERE event_id=?
                        """,
                        (normalized_payload_json, time.time(), event_id),
                    )
        except Exception:
            normalized_payload_json = payload_json

        ok, detail = send_event(settings, event_id, normalized_payload_json)
        current_attempt = attempts + 1

        if ok:
            conn.execute(
                """
                UPDATE outbox_events
                SET status='sent', attempts=?, last_error=NULL, updated_at=?
                WHERE event_id=?
                """,
                (current_attempt, time.time(), event_id),
            )
            sent += 1
            print(f"[OK] Sent event {event_id} -> {detail}")
            continue

        # 4xx (except 429) is considered non-retryable payload/client error.
        if detail.startswith("HTTP 4") and not detail.startswith("HTTP 429"):
            conn.execute(
                """
                UPDATE outbox_events
                SET status='dead', attempts=?, last_error=?, updated_at=?
                WHERE event_id=?
                """,
                (current_attempt, detail[:500], time.time(), event_id),
            )
            failed += 1
            print(f"[DEAD] Event {event_id} non-retryable: {detail}")
            continue

        if current_attempt >= settings.max_attempts:
            conn.execute(
                """
                UPDATE outbox_events
                SET status='dead', attempts=?, last_error=?, updated_at=?
                WHERE event_id=?
                """,
                (current_attempt, detail[:500], time.time(), event_id),
            )
            failed += 1
            print(f"[DEAD] Event {event_id} after {current_attempt} attempts: {detail}")
            continue

        backoff = settings.backoff_base_seconds * (2 ** min(current_attempt, 6))
        next_retry_at = time.time() + backoff
        conn.execute(
            """
            UPDATE outbox_events
            SET status='retry', attempts=?, next_retry_at=?, last_error=?, updated_at=?
            WHERE event_id=?
            """,
            (current_attempt, next_retry_at, detail[:500], time.time(), event_id),
        )
        failed += 1
        print(f"[RETRY] Event {event_id} attempt {current_attempt}: {detail}")

    conn.commit()
    return sent, failed


def print_stats(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT status, COUNT(*)
        FROM outbox_events
        GROUP BY status
        ORDER BY status ASC
        """
    ).fetchall()
    if not rows:
        print("[STATS] outbox empty")
        return

    parts = [f"{status}={count}" for status, count in rows]
    print("[STATS] " + ", ".join(parts))


def ingest_multiple_folders(conn: sqlite3.Connection, queue_dir_str: str) -> int:
    total_imported = 0
    for path in queue_dir_str.split(";"):
        path = path.strip()
        if not path:
            continue
        total_imported += ingest_drop_folder(conn, path)
    return total_imported


def main() -> None:
    parser = argparse.ArgumentParser(description="Black Knight Phase 2 outbox agent")
    parser.add_argument("--once", action="store_true", help="Run one ingest + flush cycle and exit")
    args = parser.parse_args()

    settings = load_settings()
    Path(Path(settings.queue_db_path).parent).mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(settings.queue_db_path) as conn:
        ensure_db(conn)

        if args.once:
            imported = ingest_multiple_folders(conn, settings.queue_dir)
            sent, failed = flush_outbox(conn, settings)
            print(f"[ONCE] imported={imported} sent={sent} failed={failed}")
            print_stats(conn)
            return

        print("[START] Phase 2 outbox agent running")
        print(f"[CFG] endpoint={settings.endpoint}")
        print(f"[CFG] queue_dir={settings.queue_dir}")
        print(f"[CFG] queue_db_path={settings.queue_db_path}")

        while True:
            imported = ingest_multiple_folders(conn, settings.queue_dir)
            sent, failed = flush_outbox(conn, settings)
            if imported or sent or failed:
                print(f"[CYCLE] imported={imported} sent={sent} failed={failed}")
                print_stats(conn)
            time.sleep(settings.poll_seconds)


if __name__ == "__main__":
    main()
