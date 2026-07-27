import sqlite3
import os

db_path = "black_knight_quant_journal.db"
if not os.path.exists(db_path):
    print(f"File {db_path} not found")
    exit()

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print(f"Tables in {db_path}:")
for t in tables:
    cursor.execute(f"SELECT COUNT(*) FROM {t[0]}")
    count = cursor.fetchone()[0]
    print(f"  - {t[0]}: {count} rows")

conn.close()
