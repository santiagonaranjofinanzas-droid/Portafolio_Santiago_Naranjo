import sqlite3
import json

def check_db():
    # Let's check both database locations
    db_paths = ["black_knight_quant_journal.db", "backend/black_knight_quant_journal.db"]
    for path in db_paths:
        print(f"--- Checking database: {path} ---")
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            
            # check tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            print("Tables:", tables)
            
            if "bloombergsnapshot" in tables:
                # Get column names
                cursor.execute("PRAGMA table_info(bloombergsnapshot);")
                columns = [row[1] for row in cursor.fetchall()]
                print("Columns in bloombergsnapshot:", columns)
                
                # Get latest 5 rows
                cursor.execute("SELECT * FROM bloombergsnapshot ORDER BY updated_at DESC LIMIT 5;")
                rows = cursor.fetchall()
                print(f"Found {len(rows)} snapshots:")
                for r in rows:
                    row_dict = dict(zip(columns, r))
                    print({k: v for k, v in row_dict.items() if k not in ["narrative", "weights_json"]})
                    print("Narrative:", row_dict.get("narrative")[:100] if row_dict.get("narrative") else None)
            else:
                print("Table bloombergsnapshot NOT found.")
            conn.close()
        except Exception as e:
            print(f"Error checking {path}: {e}")

if __name__ == "__main__":
    check_db()
