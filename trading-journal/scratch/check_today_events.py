import sqlite3
import os

db_path = 'black_knight_quant_journal.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT title, scheduled_at, actual, forecast, previous, status, surprise_value, released_to_feed FROM economicevent WHERE scheduled_at >= '2026-06-09' AND scheduled_at <= '2026-06-11' ORDER BY scheduled_at DESC")
        rows = cur.fetchall()
        print(f"Found {len(rows)} events between 2026-06-09 and 2026-06-11:")
        for r in rows:
            print(f"Title: {r[0]}  Time: {r[1]}  Actual: {r[2]}  Forecast: {r[3]}  Previous: {r[4]}  Status: {r[5]}  Surprise: {r[6]}  Released: {r[7]}")
    except Exception as e:
        print("Error querying economicevent:", e)
    conn.close()
else:
    print(f"DB not found at {db_path}!")
