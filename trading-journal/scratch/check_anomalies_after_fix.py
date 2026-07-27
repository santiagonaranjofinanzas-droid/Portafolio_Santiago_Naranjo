#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('black_knight_quant_journal.db')
c = conn.cursor()

c.execute("""
SELECT position_id, symbol, direction, type_op, entryprice, exitprice, gross_pnl, netpnl
FROM tradearchive
WHERE type_op IN (0, 1) AND (
    (type_op = 0 AND exitprice > entryprice AND gross_pnl < 0) OR
    (type_op = 0 AND exitprice < entryprice AND gross_pnl > 0) OR
    (type_op = 1 AND exitprice < entryprice AND gross_pnl < 0) OR
    (type_op = 1 AND exitprice > entryprice AND gross_pnl > 0)
)
ORDER BY exittime DESC LIMIT 20
""")

print("=== Anomalous trades after fix ===")
for r in c.fetchall():
    pid, sym, dir_, top, ep, xp, gross, net = r
    print(f"PID={pid} {sym} {dir_} top={top} entry={ep} exit={xp} gross={gross:.2f} net={net:.2f}")

conn.close()
