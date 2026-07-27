#!/usr/bin/env python3
import json
import time
import hmac
import hashlib
import urllib.request
import urllib.error
import sqlite3

#Credentials matching local setup
HMAC_SECRET = "PRBmQn1tQ7ZcLoxgaf4DkqrjqefxfTZofjnSgrH5dz0"
KEY_ID = "bk_beef0d582708a053"
ENDPOINT = "http://127.0.0.1:8080/api/v1/ingest/trade"

#Sample trade payload with partials list
trade_payload = {
    "position_id": 999991,
    "deal_ticket": 888881,
    "account_login": 123456,
    "server_name": "DemoServer",
    "symbol": "EURUSD",
    "entrytime": int(time.time() - 3600),
    "exittime": int(time.time()),
    "entryprice": 1.08500,
    "exitprice": 1.09200,
    "gross_pnl": 150.00,
    "commission": -2.50,
    "swap": -0.50,
    "volume": 1.00,
    "type_op": 0, # Buy
    "direction": "Buy",
    "exit_reason": 4, # Target hit
    "netpnl": 147.00,
    "sl": 1.08000,
    "risk_price": 0.00500,
    "valid_sl": True,
    "magic_number": 9090,
    "entry_magic": 9090,
    "exit_magic": 9090,
    "partials": [
        {
            "ticket": 888882,
            "volume": 0.40,
            "price": 1.09000,
            "commission": -1.00,
            "profit": 50.00,
            "time": "2026-06-05T15:00:00Z"
        },
        {
            "ticket": 888881,
            "volume": 0.60,
            "price": 1.09333,
            "commission": -1.50,
            "profit": 100.00,
            "time": "2026-06-05T15:20:00Z"
        }
    ]
}

def main():
    payload_json = json.dumps(trade_payload, separators=(",", ":"), sort_keys=True)
    
    # Sign request using HMAC
    timestamp = str(int(time.time()))
    message = f"{timestamp}.{payload_json}".encode("utf-8")
    signature = hmac.new(HMAC_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()
    
    headers = {
        "Content-Type": "application/json",
        "X-BK-Timestamp": timestamp,
        "X-BK-Signature": signature,
        "X-BK-Key-Id": KEY_ID,
        "X-BK-Event-Id": f"test-trade-{trade_payload['position_id']}-{trade_payload['deal_ticket']}"
    }
    
    req = urllib.request.Request(
        ENDPOINT,
        data=payload_json.encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    print("Sending test trade payload with partials to backend...")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
            print(f"Ingestion Response: {body}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else str(exc)
        print(f"Error {exc.code}: {body}")
        return
    except Exception as exc:
        print(f"Connection error: {exc}")
        return

    # Check the DB using sqlite3 directly to verify serialization
    print("\nQuerying local database directly to verify partials storage...")
    db_path = "black_knight_quant_journal.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT position_id, symbol, volume, partials, netpnl FROM tradearchive WHERE position_id = ?", (trade_payload["position_id"],))
        row = cursor.fetchone()
        if row:
            pid, symbol, volume, partials_str, netpnl = row
            print(f"Found trade in DB: ID={pid}, Symbol={symbol}, Vol={volume}, NetPnL={netpnl}")
            print(f"Stored Partials field (Raw string in DB): {partials_str}")
            
            # Verify it parses back to a list of dicts
            parsed_partials = json.loads(partials_str)
            print(f"Parsed Partials Count: {len(parsed_partials)}")
            if len(parsed_partials) == 2:
                print("SUCCESS: Partials matched and parsed successfully from database!")
            else:
                print("FAILURE: Partials count mismatch in DB.")
        else:
            print("FAILURE: Trade not found in database.")
        conn.close()
    except Exception as exc:
        print(f"Database verification error: {exc}")

if __name__ == "__main__":
    main()
