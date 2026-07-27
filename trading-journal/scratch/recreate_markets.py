import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sqlite3
import hmac
import hashlib
import json

#Try to import MT5, otherwise handle error
try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 package not installed. Run 'pip install MetaTrader5'")
    exit(1)

def calculate_trade_physics(row):
    """Calcula MAE/MFE M1 via MT5"""
    if pd.isna(row['entrytime']) or pd.isna(row['exittime']):
        return None
    
    # Pad times slightly
    start = row['entrytime']
    end = row['exittime']
    
    rates = mt5.copy_rates_range(row['symbol'], mt5.TIMEFRAME_M1, start, end)
    if rates is None or len(rates) == 0:
        return None
    
    df_m1 = pd.DataFrame(rates)
    
    # Price physics
    if row['type_op'] == 0: # Buy
        mfe = df_m1['high'].max() - row['entryprice']
        mae = df_m1['low'].min() - row['entryprice']
    else: # Sell
        mfe = row['entryprice'] - df_m1['low'].min()
        mae = row['entryprice'] - df_m1['high'].max()
    
    risk_price = abs(row['entryprice'] - row['sl']) if row['sl'] > 0 else (abs(row['netpnl']) if row['netpnl'] < 0 else (row['entryprice'] * 0.01))
    
    return {
        'mae': float(mae),
        'mfe': float(mfe),
        'mae_r': float(mae / risk_price),
        'mfe_r': float(mfe / risk_price),
        'efficiency': float(row['netpnl'] / (mfe * row['volume'] * 100)) if mfe > 0 else 0.0
    }

def main():
    if not mt5.initialize():
        print(f"MT5 Initialize failed: {mt5.last_error()}")
        return

    print("Connected to MT5. Starting recovery...")
    
    # 1. Sync History to Local Outbox (Catch missing trades)
    to_date = datetime.now() + timedelta(days=1)
    from_date = datetime.now() - timedelta(days=90)
    
    deals = mt5.history_deals_get(from_date, to_date)
    if not deals:
        print("No deals found.")
    else:
        df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
        # Filter trade deals
        df_trades = df_deals[(df_deals['entry'].isin([0, 1])) & (df_deals['type'].isin([0, 1])) & (df_deals['symbol'].notna())].copy()
        
        # Group into positions
        positions = df_trades.groupby('position_id').agg({
            'symbol': 'first', 'time': ['first', 'last'], 'price': ['first', 'last'],
            'profit': 'sum', 'commission': 'sum', 'swap': 'sum', 'volume': 'first', 'type': 'first',
            'magic': 'first'
        })
        positions.columns = ['symbol', 'entrytime', 'exittime', 'entryprice', 'exitprice', 'gross_pnl', 'commission', 'swap', 'volume', 'type_op', 'magic_number']
        positions = positions.reset_index()
        
        print(f"Found {len(positions)} positions in MT5 history.")
        
        # Connect to local outbox
        db_path = '_journal_data/outbox.db'
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        acc = mt5.account_info()
        login = acc.login if acc else 0
        server = acc.server if acc else "Unknown"

        for _, row in positions.iterrows():
            pid = int(row['position_id'])
            # Check if exists in outbox or if we should just re-send
            # To be safe, we generate the payload and the outbox logic handles duplicates at the backend
            
            # Enrich with physics
            physics = calculate_trade_physics({
                'symbol': row['symbol'],
                'entrytime': datetime.fromtimestamp(row['entrytime']),
                'exittime': datetime.fromtimestamp(row['exittime']),
                'entryprice': row['entryprice'],
                'exitprice': row['exitprice'],
                'type_op': row['type_op'],
                'sl': 0.0, # Need order history for SL but let's skip for now
                'netpnl': row['gross_pnl'] + row['commission'] + row['swap'],
                'volume': row['volume']
            })
            
            payload = {
                "event_type": "trade",
                "position_id": pid,
                "symbol": row['symbol'],
                "entrytime": int(row['entrytime']),
                "exittime": int(row['exittime']),
                "entryprice": float(row['entryprice']),
                "exitprice": float(row['exitprice']),
                "gross_pnl": float(row['gross_pnl']),
                "netpnl": float(row['gross_pnl'] + row['commission'] + row['swap']),
                "volume": float(row['volume']),
                "type_op": int(row['type_op']),
                "exit_reason": 0,
                "magic_number": int(row['magic_number']),
                "account_login": str(login),
                "server_name": server,
                "organization_id": 1
            }
            if physics:
                payload.update(physics)
            
            event_id = f"manual-sync-{pid}"
            payload_json = json.dumps(payload)
            
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO outbox_events (event_id, payload_json, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (event_id, payload_json, 'pending', datetime.now().timestamp(), datetime.now().timestamp())
                )
            except Exception as e:
                print(f"Error inserting {pid}: {e}")
        
        conn.commit()
        print("Manual sync payloads added to outbox.")
        
    mt5.shutdown()

if __name__ == "__main__":
    main()
