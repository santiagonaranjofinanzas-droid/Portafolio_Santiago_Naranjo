#!/usr/bin/env python3
"""
Black Knight DB Direction Fix - One-shot script.

Inverts the direction (type_op and direction) for ALL trades in the database
that were exported with the old buggy EA.

This script flips them:
  type_op 0 -> 1, direction "Buy" -> "Sell"
  type_op 1 -> 0, direction "Sell" -> "Buy"

Only affects type_op IN (0, 1). Balance events (type_op=2) are untouched.
"""
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = "black_knight_quant_journal.db"
BACKUP_SUFFIX = f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def main():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    # 1. Create backup
    backup_path = DB_PATH.replace(".db", f"{BACKUP_SUFFIX}.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"[OK] Backup created: {backup_path}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 2. Count affected trades
    c.execute("SELECT COUNT(*) FROM tradearchive WHERE type_op IN (0, 1)")
    total = c.fetchone()[0]
    print(f"  Total trading records to fix: {total}")

    # 3. Show pre-fix stats
    c.execute("""
        SELECT direction, COUNT(*), SUM(netpnl)
        FROM tradearchive WHERE type_op IN (0, 1)
        GROUP BY direction
    """)
    print("  Pre-fix direction distribution:")
    for row in c.fetchall():
        print(f"    {row[0]}: {row[1]} trades, net PnL = {row[2]:.2f}")

    # 4. Execute the fix - swap type_op and direction
    # Step A: Set all type_op=0 to a temp value 99
    c.execute("UPDATE tradearchive SET type_op = 99 WHERE type_op = 0")
    # Step B: Set all type_op=1 to 0, direction to "Buy"
    c.execute("UPDATE tradearchive SET type_op = 0, direction = 'Buy' WHERE type_op = 1")
    # Step C: Set all temp type_op=99 to 1, direction to "Sell"
    c.execute("UPDATE tradearchive SET type_op = 1, direction = 'Sell' WHERE type_op = 99")

    conn.commit()
    print(f"\n[OK] Direction fix applied to {total} trades")

    # 5. Show post-fix stats
    c.execute("""
        SELECT direction, COUNT(*), SUM(netpnl)
        FROM tradearchive WHERE type_op IN (0, 1)
        GROUP BY direction
    """)
    print("  Post-fix direction distribution:")
    for row in c.fetchall():
        print(f"    {row[0]}: {row[1]} trades, net PnL = {row[2]:.2f}")

    # 6. Verify anomalies are fixed
    c.execute("""
        SELECT COUNT(*) FROM tradearchive
        WHERE type_op IN (0, 1) AND (
            (type_op = 0 AND exitprice > entryprice AND gross_pnl < 0) OR
            (type_op = 0 AND exitprice < entryprice AND gross_pnl > 0) OR
            (type_op = 1 AND exitprice < entryprice AND gross_pnl < 0) OR
            (type_op = 1 AND exitprice > entryprice AND gross_pnl > 0)
        )
    """)
    anomalies = c.fetchone()[0]
    print(f"\n  Remaining price/PnL anomalies: {anomalies}")

    # 7. Verify total PnL unchanged
    c.execute("SELECT SUM(netpnl) FROM tradearchive WHERE type_op IN (0, 1)")
    total_pnl = c.fetchone()[0] or 0
    print(f"  Total net PnL (should be ~182.53): {total_pnl:.2f}")

    # 8. Also clean the test trade (position_id=999991) and the fake trade (888888)
    c.execute("DELETE FROM tradearchive WHERE position_id IN (999991, 888888, -900000001)")
    deleted = c.rowcount  
    if deleted > 0:
        conn.commit()
        print(f"\n[OK] Cleaned {deleted} test/fake records (PIDs: 999991, 888888, -900000001)")


    conn.close()
    print("\n[OK] Database fix complete. Restart the backend to see corrected metrics.")

if __name__ == "__main__":
    main()
