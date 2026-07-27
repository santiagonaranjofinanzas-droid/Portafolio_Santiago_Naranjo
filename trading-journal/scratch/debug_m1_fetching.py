#!/usr/bin/env python3
import MetaTrader5 as mt5
from datetime import datetime, timedelta
import pandas as pd

if not mt5.initialize():
    print("MT5 initialization failed:", mt5.last_error())
    exit(1)

#Get current account details
account = mt5.account_info()
if account:
    print(f"Connected to: Account={account.login}, Server={account.server}")
else:
    print("Failed to get account info")

symbol = "XAUUSD.pro"
#Let's check if the symbol exists and is selected
symbol_info = mt5.symbol_info(symbol)
if symbol_info is None:
    print(f"Symbol {symbol} not found on this server.")
    # Print first 10 symbols available
    symbols = mt5.symbols_get()
    if symbols:
        print("First 10 available symbols:", [s.name for s in symbols[:10]])
else:
    print(f"Symbol {symbol} exists. Visible in Market Watch:", symbol_info.visible)
    if not symbol_info.visible:
        # Try to select it
        selected = mt5.symbol_select(symbol, True)
        print(f"Attempted to select {symbol}. Success:", selected)

#Try fetching M1 rates for a recent time window
end = datetime.now()
start = end - timedelta(hours=2)
print(f"Fetching M1 rates for {symbol} from {start} to {end}...")
rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M1, start, end)
if rates is None:
    print("Failed to fetch rates. MT5 Error:", mt5.last_error())
else:
    print("Successfully fetched rates count:", len(rates))

mt5.shutdown()
