import MetaTrader5 as mt5
from datetime import datetime, timedelta

if not mt5.initialize():
    raise SystemExit("MT5 init failed")

account = mt5.account_info()
print("MT5 Account Info:")
print(f"  Login: {account.login}")
print(f"  Server: {account.server}")
print(f"  Balance: {account.balance}")
print(f"  Equity: {account.equity}")

#Fetch all history from 2025 to now
from_date = datetime(2025, 1, 1)
to_date = datetime.now() + timedelta(days=1)
deals = mt5.history_deals_get(from_date, to_date)
if deals is None:
    print("No deals found")
    mt5.shutdown()
    exit()

print(f"\nTotal deals fetched: {len(deals)}")

deposits = []
trade_pnl = 0.0
trade_count = 0
other_deals = []

for deal in deals:
    d = deal._asdict()
    # deal types:
    # 0 = DEAL_TYPE_BUY
    # 1 = DEAL_TYPE_SELL
    # 2 = DEAL_TYPE_BALANCE (deposit/withdrawal)
    # 3 = DEAL_TYPE_CREDIT
    # etc.
    dtype = d.get('type')
    profit = d.get('profit', 0.0)
    comm = d.get('commission', 0.0)
    swap = d.get('swap', 0.0)
    net = profit + comm + swap
    
    if dtype in (0, 1):
        # We only count deals that are entries or exits of trades
        # Wait, to sum all profit from MT5, we can just sum the profit of all deals of type 0 and 1!
        # Because every trade has a deal. Entry deals have 0 profit, exit deals have the trade profit.
        trade_pnl += profit  # wait, profit field already includes swap/commission in some brokers, or does it not? Usually profit is gross.
        # Let's sum net = profit + commission + swap
        trade_count += 1
    elif dtype == 2:
        deposits.append(d)
    else:
        other_deals.append(d)

print(f"\nMT5 Deposits (type=2):")
for dep in deposits:
    print(f"  Ticket: {dep.get('ticket')}, Time: {datetime.fromtimestamp(dep.get('time'))}, Profit/Amount: {dep.get('profit')}, Comment: {dep.get('comment')}")

print(f"\nSum of all deal profits (type 0,1): {trade_pnl}")
print(f"Number of trade deals: {trade_count}")

#Let's group trade deals by position_id to see positions
from collections import defaultdict
pos_pnl = defaultdict(float)
for deal in deals:
    d = deal._asdict()
    if d.get('type') in (0, 1):
        pos_pnl[d.get('position_id')] += d.get('profit', 0.0) + d.get('commission', 0.0) + d.get('swap', 0.0)

print(f"\nTotal positions in MT5 history: {len(pos_pnl)}")
total_net_pos = sum(pos_pnl.values())
print(f"Sum of net PnL (profit + comm + swap) grouped by position: {total_net_pos}")

mt5.shutdown()
