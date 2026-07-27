#!/usr/bin/env python3
"""Deep diagnostic of the BK database vs MT5 reality."""
import sqlite3, os, json, glob

conn = sqlite3.connect('black_knight_quant_journal.db')
c = conn.cursor()

#1. Check outbox queue
queue_dir = '_journal_data/outbox_queue'
files = glob.glob(os.path.join(queue_dir, '*.json'))
print(f"=== Pending outbox JSON files: {len(files)} ===")
for f in files[:5]:
    with open(f, 'r') as fh:
        data = json.load(fh)
    print(f"  File: {os.path.basename(f)}")
    keys = ['type_op','direction','position_id','symbol','gross_pnl','entryprice','exitprice','account_login']
    print(f"    {', '.join(f'{k}={data.get(k)}' for k in keys)}")

#2. Account trade stats
c.execute("""
SELECT COUNT(*) as total,
       SUM(CASE WHEN deal_ticket IS NOT NULL THEN 1 ELSE 0 END) as with_ticket,
       SUM(CASE WHEN deal_ticket IS NULL THEN 1 ELSE 0 END) as no_ticket,
       MIN(entrytime) as oldest,
       MAX(exittime) as newest
FROM tradearchive WHERE account_login = '10035063' AND type_op != 2
""")
row = c.fetchone()
print(f"\n=== Account 10035063 stats ===")
print(f"Total={row[0]} WithTicket={row[1]} NoTicket={row[2]} Oldest={row[3]} Newest={row[4]}")

#3. Sum of netpnl
c.execute("SELECT SUM(netpnl) FROM tradearchive WHERE account_login = '10035063' AND type_op != 2")
sum_net = c.fetchone()[0] or 0
print(f"Sum of netpnl in DB: {sum_net:.2f}")
print(f"Expected from balance (5182.44 - 5000): 182.44")
print(f"Delta: {sum_net - 182.44:.2f}")

#4. Check direction inversion
#In MT5: Position BUY -> closed by DEAL_TYPE_SELL (type=1)
#EA uses: int type_op = (type == DEAL_TYPE_SELL ? 1 : 0)
#So type_op=1 means the EXIT deal was a SELL, which means the POSITION was BUY!
#But the EA sets: string dir_str = (type_op == 1 ? "Sell" : "Buy")
#This means dir="Sell" when exit deal=SELL, i.e., position=BUY -> INVERTED!
print("\n=== Direction Inversion Analysis ===")
c.execute("""
SELECT position_id, symbol, direction, type_op, entryprice, exitprice, gross_pnl
FROM tradearchive
WHERE account_login = '10035063' AND type_op != 2
ORDER BY exittime DESC LIMIT 20
""")
rows = c.fetchall()
for r in rows:
    pid, sym, dir_, top, ep, xp, gross = r
    # Determine if direction is correct based on PnL
    if top == 0:  # EA says Buy
        if ep < xp and gross > 0: status = "OK(Buy-up-win)"
        elif ep > xp and gross < 0: status = "OK(Buy-down-loss)"
        elif ep < xp and gross < 0: status = "ANOMALY(Buy-up-loss)"  
        elif ep > xp and gross > 0: status = "INVERTED(Buy-down-win)"
        else: status = "FLAT"
    elif top == 1:  # EA says Sell
        if ep > xp and gross > 0: status = "OK(Sell-down-win)"
        elif ep < xp and gross < 0: status = "OK(Sell-up-loss)"
        elif ep > xp and gross < 0: status = "INVERTED(Sell-down-loss)"
        elif ep < xp and gross > 0: status = "INVERTED(Sell-up-win)"
        else: status = "FLAT"
    else:
        status = "BALANCE"
    print(f"  {pid} {sym} dir={dir_} top={top} entry={ep} exit={xp} gross={gross:.2f} => {status}")

#5. Check if there are duplicate position_ids (from different ingestion paths)
c.execute("""
SELECT position_id, COUNT(*) as cnt
FROM tradearchive 
WHERE account_login = '10035063'
GROUP BY position_id
HAVING cnt > 1
""")
dups = c.fetchall()
print(f"\n=== Duplicate position_ids: {len(dups)} ===")
for d in dups[:5]:
    print(f"  PID={d[0]} count={d[1]}")

conn.close()
