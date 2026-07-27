import sqlite3
import os

db_paths = [
    'black_knight_quant_journal.db',
    'backend/black_knight_quant_journal.db'
]

for p in db_paths:
    if os.path.exists(p):
        print(f"Found DB at: {p}")
        conn = sqlite3.connect(p)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cur.fetchall()
        print("Tables:", tables)
        
        # Check tradearchive columns
        try:
            cur.execute("PRAGMA table_info(tradearchive)")
            columns = cur.fetchall()
            print("tradearchive columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
        except Exception as e:
            print("Error checking tradearchive:", e)
            
        try:
            cur.execute("SELECT entrytime, exittime FROM tradearchive LIMIT 5")
            rows = cur.fetchall()
            print("First 5 rows of entrytime/exittime:")
            for row in rows:
                print(f"  Entry: {row[0]}, Exit: {row[1]}")
        except Exception as e:
            print("Error reading rows:", e)
        conn.close()
