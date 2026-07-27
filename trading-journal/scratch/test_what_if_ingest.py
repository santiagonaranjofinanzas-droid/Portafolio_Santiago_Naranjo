import requests
import sqlite3
import sys

base_url = "http://127.0.0.1:8080/api/v1"
api_key = "fpwulZF78N-U7quDuCvQ6Y4sMC_RDu_vgucbTYiIQic"

headers = {
    "X-API-KEY": api_key,
    "Content-Type": "application/json"
}

#1. Clear any existing test position in backend DB
db_path = "backend/black_knight_quant_journal.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("DELETE FROM tradearchive WHERE position_id = 888888")
cursor.execute("DELETE FROM ingestionevent WHERE event_id LIKE 'mql5:%'")
conn.commit()

#2. Ingest Entry Deal (IN)
print("--- Sending Entry Deal (IN) ---")
entry_payload = {
    "ticket": 999991,
    "position_id": 888888,
    "entry_type": 0, # IN
    "symbol": "XAUUSD.pro",
    "type": 0, # Buy
    "volume": 1.0,
    "price": 2000.0,
    "profit": 0.0,
    "commission": -2.0,
    "swap": 0.0,
    "magic": 10101,
    "reason": 0,
    "time": "2026-06-01 12:00:00",
    "organization_id": 1,
    "sl": 1990.0,
    "tp": 2030.0,
    "account_login": "123456",
    "server_name": "DemoServer"
}

r1 = requests.post(f"{base_url}/ingest/mql5", json=entry_payload, headers=headers)
print("Entry Status:", r1.status_code)
print("Entry Response:", r1.text)

if r1.status_code != 200:
    print("Ingestion failed. Exiting.")
    sys.exit(1)

#3. Ingest Exit Deal (OUT)
print("\n--- Sending Exit Deal (OUT) ---")
exit_payload = {
    "ticket": 999992,
    "position_id": 888888,
    "entry_type": 1, # OUT
    "symbol": "XAUUSD.pro",
    "type": 1, # Sell
    "volume": 1.0,
    "price": 2015.0,
    "profit": 1500.0,
    "commission": -2.0,
    "swap": 0.0,
    "magic": 10101,
    "reason": 3, # TP/Manual
    "time": "2026-06-01 12:15:00",
    "organization_id": 1,
    "sl": 1990.0,
    "tp": 2030.0,
    "account_login": "123456",
    "server_name": "DemoServer"
}

r2 = requests.post(f"{base_url}/ingest/mql5", json=exit_payload, headers=headers)
print("Exit Status:", r2.status_code)
print("Exit Response:", r2.text)

if r2.status_code != 200:
    print("Ingestion failed. Exiting.")
    sys.exit(1)

#4. Check DB results for position_id = 888888
print("\n--- Checking Database Results ---")
cursor.execute("""
    SELECT entryprice, exitprice, sl, planned_tp, r_multiple, planned_max_r, what_if_result, what_if_pnl, what_if_r
    FROM tradearchive
    WHERE position_id = 888888
""")
row = cursor.fetchone()
if row:
    keys = ["entryprice", "exitprice", "sl", "planned_tp", "r_multiple", "planned_max_r", "what_if_result", "what_if_pnl", "what_if_r"]
    for k, v in zip(keys, row):
        print(f"{k}: {v}")
else:
    print("Error: Trade not found in database!")

#Cleanup
cursor.execute("DELETE FROM tradearchive WHERE position_id = 888888")
conn.commit()
conn.close()
print("\nTest finished and database cleaned.")
