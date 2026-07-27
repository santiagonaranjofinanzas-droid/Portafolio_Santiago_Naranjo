import sqlite3
import requests
import sys

#1. DB Setup: Check for an existing trade in tradearchive
db_path = "backend/black_knight_quant_journal.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT position_id, symbol, netpnl, r_multiple FROM tradearchive LIMIT 1")
trade = cursor.fetchone()
if not trade:
    print("Error: No trades found in tradearchive to run AI review test.")
    sys.exit(1)

position_id, symbol, netpnl, r_multiple = trade
print(f"Found trade to test: Position ID {position_id}, Symbol {symbol}, PnL {netpnl}, R {r_multiple}")

#2. Insert temporary tradejournal record
cursor.execute("SELECT COUNT(*) FROM tradejournal WHERE position_id = ?", (position_id,))
exists = cursor.fetchone()[0]

if not exists:
    print(f"Inserting temporary journal record for position_id {position_id}...")
    cursor.execute("""
        INSERT INTO tradejournal (
            organization_id, position_id, emotional_state, emotional_tags, 
            notes_general, notes_pre, notes_during, notes_post, timeframe_data, is_completed, created_at, updated_at
        ) VALUES (
            1, ?, 7, 'FOMO, Greed', 'Entrada rápida buscando continuación de tendencia en el oro.', '', '', '', 'M1', 1, '2026-06-01 12:00:00', '2026-06-01 12:00:00'
        )
    """, (position_id,))
    conn.commit()
    inserted_temp = True
else:
    print(f"Journal record for position_id {position_id} already exists.")
    inserted_temp = False

try:
    # 3. Call AI endpoints
    base_url = "http://127.0.0.1:8080/api/v1"

    # Test /api/v1/ai/chat
    print("\n--- Testing POST /api/v1/ai/chat ---")
    chat_payload = {
        "prompt": "Hola, ¿puedes sugerir un plan para mitigar el FOMO en el trading?",
        "focus": "Analista IA",
        "context": {
            "summary": {"net_profit": netpnl, "expectancy": r_multiple},
            "recent_trades": [{"symbol": symbol, "netpnl": netpnl, "r_multiple": r_multiple}]
        },
        "messages": []
    }
    r_chat = requests.post(f"{base_url}/ai/chat", json=chat_payload, timeout=30)
    print("Status:", r_chat.status_code)
    if r_chat.status_code == 200:
        res = r_chat.json()
        print("Provider:", res.get("provider"))
        print("Model:", res.get("model"))
        print("Answer preview:", res.get("answer")[:250], "...")
    else:
        print("Error response:", r_chat.text)

    # Test /api/v1/ai/insight
    print("\n--- Testing POST /api/v1/ai/insight ---")
    insight_payload = {
        "prompt": "Genera insights rápidos del rendimiento actual.",
        "focus": "Rendimiento",
        "context": {
            "summary": {"net_profit": netpnl, "expectancy": r_multiple},
            "recent_trades": [{"symbol": symbol, "netpnl": netpnl, "r_multiple": r_multiple}]
        },
        "messages": []
    }
    r_insight = requests.post(f"{base_url}/ai/insight", json=insight_payload, timeout=30)
    print("Status:", r_insight.status_code)
    if r_insight.status_code == 200:
        res = r_insight.json()
        print("Provider:", res.get("provider"))
        print("Model:", res.get("model"))
        print("Answer preview:", res.get("answer")[:250], "...")
    else:
        print("Error response:", r_insight.text)

    # Test /api/v1/journal/{position_id}/ai_review
    print(f"\n--- Testing GET /api/v1/journal/{position_id}/ai_review ---")
    r_review = requests.get(f"{base_url}/journal/{position_id}/ai_review", timeout=30)
    print("Status:", r_review.status_code)
    if r_review.status_code == 200:
        res = r_review.json()
        print("Provider:", res.get("provider"))
        print("Model:", res.get("model"))
        print("Answer preview:")
        print(res.get("answer"))
    else:
        print("Error response:", r_review.text)

finally:
    # 4. Clean up temporary tradejournal record
    if inserted_temp:
        print(f"\nCleaning up temporary journal record for position_id {position_id}...")
        cursor.execute("DELETE FROM tradejournal WHERE position_id = ?", (position_id,))
        conn.commit()
    conn.close()
    print("Test finished and database cleaned.")
