import sqlite3
import os
import requests
import json
from datetime import datetime

db_path = 'black_knight_quant_journal.db'

print("--- CHECKING ECONOMIC EVENTS IN DB ---")
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("SELECT event_key, title, country, scheduled_at, actual, forecast, previous, status, released_to_feed FROM economicevent ORDER BY scheduled_at DESC LIMIT 10")
        rows = cur.fetchall()
        print("Last 10 economic events in DB:")
        for r in rows:
            print(f"Key: {r[0][:8]}...  Title: {r[1]}  Country: {r[2]}  Time: {r[3]}  Actual: {r[4]}  Forecast: {r[5]}  Previous: {r[6]}  Status: {r[7]}  Released: {r[8]}")
    except Exception as e:
        print("Error querying economicevent:", e)
    conn.close()
else:
    print(f"DB not found at {db_path}!")

print("\n--- FETCHING FOREX FACTORY CALENDAR DIRECTLY ---")
url = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
try:
    r = requests.get(url, headers={"User-Agent": "Black-Knight-Terminal/1.0"}, timeout=10)
    print("Status code:", r.status_code)
    data = r.json()
    print(f"Total events in calendar: {len(data)}")
    
    # Print a few CPI or key events
    cpi_events = [e for e in data if "CPI" in str(e.get("title")) or "Refinancing Rate" in str(e.get("title"))]
    print(f"\nFound {len(cpi_events)} CPI or rate events:")
    for e in cpi_events[:10]:
        print(f"Date: {e.get('date')}  Title: {e.get('title')}  Country: {e.get('country')}  Actual: {e.get('actual')}  Forecast: {e.get('forecast')}  Previous: {e.get('previous')}")
        
    print("\nFirst 3 events in raw calendar:")
    for e in data[:3]:
        print(e)
except Exception as e:
    print("Error fetching calendar:", e)
