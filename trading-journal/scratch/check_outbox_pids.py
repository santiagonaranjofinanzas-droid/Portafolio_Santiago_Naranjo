#!/usr/bin/env python3
import sqlite3, json

conn = sqlite3.connect('_journal_data/outbox.db')
c = conn.cursor()

pids = [61884415, 61817100, 61486502]
for pid in pids:
    print(f"\n=== Searching for PID {pid} in outbox.db ===")
    c.execute("SELECT event_id, payload_json FROM outbox_events WHERE payload_json LIKE ?", (f'%"{pid}"%',))
    rows = c.fetchall()
    print(f"Found {len(rows)} events")
    for r in rows:
        print("  Event ID:", r[0])
        payload = json.loads(r[1])
        print("  Payload:", {k: payload.get(k) for k in ['position_id', 'symbol', 'direction', 'type_op', 'entryprice', 'exitprice', 'gross_pnl']})

conn.close()
