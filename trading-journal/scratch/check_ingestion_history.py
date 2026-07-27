#!/usr/bin/env python3
import sqlite3, json

conn = sqlite3.connect('black_knight_quant_journal.db')
c = conn.cursor()

c.execute("SELECT event_id, event_type, payload_json, status, processed_at FROM ingestionevent WHERE payload_json LIKE ?", ('%61486502%',))
rows = c.fetchall()
print(f"Found {len(rows)} ingestion events for PID 61486502:")
for r in rows:
    print(f"\nEvent ID: {r[0]}  Type: {r[1]}  Status: {r[3]}  Processed At: {r[4]}")
    payload = json.loads(r[2])
    print("Payload fields:")
    print(f"  direction: {payload.get('direction')}")
    print(f"  type_op: {payload.get('type_op')}")
    print(f"  entryprice: {payload.get('entryprice')}")
    print(f"  exitprice: {payload.get('exitprice')}")
    print(f"  gross_pnl: {payload.get('gross_pnl')}")
    print(f"  netpnl: {payload.get('netpnl')}")

conn.close()
