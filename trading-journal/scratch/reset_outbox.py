import sqlite3
import os

db_path = '_journal_data/outbox.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("UPDATE outbox_events SET status='pending', attempts=0, next_retry_at=0 WHERE status IN ('retry', 'dead')")
    conn.commit()
    print(f"Reset {cursor.rowcount} events to pending.")
    conn.close()
else:
    print("Database not found.")
