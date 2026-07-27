import requests
import json

url = "https://black-knight-backend.onrender.com/api/v1/ingest/mql5"
headers = {
    "Content-Type": "application/json",
    "X-API-KEY": "MSrsOLPG5JYqaF6ORlbx3YsUnRDhMkoAV-s9_fGQxsI"
}
payload = {
    "position_id": 123456,
    "symbol": "XAUUSD.pro",
    "type": 0,
    "volume": 0.1,
    "price": 2000.0,
    "profit": 10.0,
    "commission": 0.0,
    "magic": 0,
    "reason": 0,
    "time": "2026.05.04 14:00:00",
    "organization_id": 1
}

print(f"Sending POST to {url}")
try:
    response = requests.post(url, headers=headers, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")
