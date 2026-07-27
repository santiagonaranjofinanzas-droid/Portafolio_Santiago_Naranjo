#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import time

import phase2_outbox_agent as agent


def load_local_env(path: str = "PHASE2_CREDENTIALS.local.md") -> None:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            os.environ[key.strip()] = value.strip()


load_local_env()
settings = agent.load_settings()
conn = sqlite3.connect(settings.queue_db_path)
agent.ensure_db(conn)

rows = conn.execute(
    """
    select event_id, payload_json, attempts
    from outbox_events
    where status in ('pending', 'retry', 'dead')
      and event_id like 'trade-%'
    order by created_at asc
    """
).fetchall()

sent = 0
failed = 0
for event_id, payload_json, attempts in rows:
    ok, detail = agent.send_event(settings, event_id, payload_json)
    now = time.time()
    if ok:
        conn.execute(
            """
            update outbox_events
            set status = 'sent', attempts = ?, last_error = null, updated_at = ?
            where event_id = ?
            """,
            (attempts + 1, now, event_id),
        )
        sent += 1
        print(f"[OK] {event_id}: {detail[:160]}")
    else:
        conn.execute(
            """
            update outbox_events
            set status = 'retry', attempts = ?, next_retry_at = 0, last_error = ?, updated_at = ?
            where event_id = ?
            """,
            (attempts + 1, detail[:500], now, event_id),
        )
        failed += 1
        print(f"[FAIL] {event_id}: {detail[:220]}")

    conn.commit()

print(f"[DONE] sent={sent} failed={failed}")
