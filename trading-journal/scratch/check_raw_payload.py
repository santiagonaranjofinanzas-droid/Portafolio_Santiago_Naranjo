import sqlite3

conn = sqlite3.connect("black_knight_quant_journal.db")
r = conn.execute("select payload_json from ingestionevent where payload_json like '%89651764%' order by id desc limit 1").fetchone()
if r:
    print(r[0])
else:
    print("No event found")
conn.close()
