from backend.app.engine import sync_mt5_to_db
import MetaTrader5 as mt5

if mt5.initialize():
    print("MT5 Init Success")
    res = sync_mt5_to_db(days_back=180)
    print(f"Sync Result: {res}")
    mt5.shutdown()
else:
    print("MT5 Init Failed")
