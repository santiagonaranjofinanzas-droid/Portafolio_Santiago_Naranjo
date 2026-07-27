#!/usr/bin/env python3
from __future__ import annotations

import os
import sqlite3
import sys

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

con = sqlite3.connect(settings.queue_db_path)
row = con.execute(
    """
    select event_id, payload_json
    from outbox_events
    where status = 'pending' and event_id like 'trade-%'
    order by created_at desc
    limit 1
    """
).fetchone()

if row is None:
    print("No pending trade event found")
    sys.exit(0)

event_id, payload_json = row
ok, detail = agent.send_event(settings, event_id, payload_json)
print({"event_id": event_id, "ok": ok, "detail": detail[:500]})
