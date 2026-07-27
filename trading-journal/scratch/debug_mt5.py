#!/usr/bin/env python3
import MetaTrader5 as mt5
from datetime import datetime, timedelta

if not mt5.initialize():
    print("Failed to initialize MT5")
    exit(1)

account = mt5.account_info()
if account is None:
    print("Failed to get account info")
    exit(1)

print("Account Login:", account.login)
print("Account Server:", account.server)
print("Balance:", account.balance)

to_date = datetime.now() + timedelta(days=1)
from_date = datetime.now() - timedelta(days=90)
deals = mt5.history_deals_get(from_date, to_date)
if deals is None:
    print("Failed to get deals:", mt5.last_error())
else:
    print("Fetched total deals:", len(deals))
    trading_deals = [d for d in deals if d.type in (0, 1)]
    print("Trading deals (Buy/Sell):", len(trading_deals))
    if trading_deals:
        print("Sample trading deal:", trading_deals[0]._asdict())

mt5.shutdown()
