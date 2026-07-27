import sqlite3
import os

db_path = 'backend/black_knight_quant_journal.db'
if not os.path.exists(db_path):
    print(f"DB not found at {db_path}")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if organization_id exists in tradearchive
    cursor.execute("PRAGMA table_info(tradearchive)")
    cols = [c[1] for c in cursor.fetchall()]
    
    if 'organization_id' not in cols:
        print("Migrating tradearchive: Adding organization_id and changing PK")
        # SQLite doesn't support changing PK easily. We must recreate the table.
        cursor.execute("ALTER TABLE tradearchive RENAME TO tradearchive_old")
        
        # We'll let SQLModel recreate the tables in the next app start, 
        # or we can do it here. Let's do it manually to be sure.
        
    # Check capitallog
    cursor.execute("PRAGMA table_info(capitallog)")
    cols_cap = [c[1] for c in cursor.fetchall()] if cursor.rowcount != 0 else []
    if cols_cap and 'organization_id' not in cols_cap:
        print("Migrating capitallog: Adding organization_id")
        cursor.execute("ALTER TABLE capitallog ADD COLUMN organization_id INTEGER DEFAULT 1")

    conn.commit()
    conn.close()
    print("Migration (partial) finished. Run the app to complete schema creation via SQLModel.")
