#!/usr/bin/env python3
"""
Black Knight DB Selective Direction Fix.

Identifies ONLY the trades with inconsistent direction/PnL relationship
and flips their type_op and direction to correct them.
Leaves all other correct trades untouched.
"""
import sqlite3
import shutil
import os
from datetime import datetime

DB_PATH = "black_knight_quant_journal.db"
BACKUP_SUFFIX = f"_backup_selective_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

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

    # 2. Find anomalous position_ids
    anomaly_query = """
        SELECT position_id, symbol, direction, type_op, entryprice, exitprice, gross_pnl
        FROM tradearchive
        WHERE type_op IN (0, 1) AND (
            (type_op = 0 AND exitprice > entryprice AND gross_pnl < 0) OR
            (type_op = 0 AND exitprice < entryprice AND gross_pnl > 0) OR
            (type_op = 1 AND exitprice < entryprice AND gross_pnl < 0) OR
            (type_op = 1 AND exitprice > entryprice AND gross_pnl > 0)
        )
    """
    c.execute(anomaly_query)
    anomalous_trades = c.fetchall()
    
    print(f"Found {len(anomalous_trades)} anomalous trades to fix:")
    
    # 3. Flip only those trades
    fixed_count = 0
    for row in anomalous_trades:
        pid, sym, dir_, top, ep, xp, gross = row
        new_top = 1 if top == 0 else 0
        new_dir = "Sell" if new_top == 1 else "Buy"
        
        print(f"  Fixing PID {pid}: {sym} {dir_}({top}) -> {new_dir}({new_top})  entry={ep} exit={xp} gross={gross:.2f}")
        
        c.execute("""
            UPDATE tradearchive 
            SET type_op = ?, direction = ?
            WHERE position_id = ?
        """, (new_top, new_dir, pid))
        fixed_count += c.rowcount

    conn.commit()
    print(f"\n[OK] Selectively flipped {fixed_count} anomalous trades.")

    # 4. Verify remaining anomalies
    c.execute(anomaly_query)
    remaining = len(c.fetchall())
    print(f"Remaining anomalies: {remaining}")

    # 5. Clean test trades
    c.execute("DELETE FROM tradearchive WHERE position_id IN (999991, 888888, -900000001)")
    deleted = c.rowcount
    if deleted > 0:
        conn.commit()
        print(f"[OK] Cleaned {deleted} test/fake records (PIDs: 999991, 888888, -900000001)")

    conn.close()
    print("\n[OK] Database selective fix complete.")

if __name__ == "__main__":
    main()
