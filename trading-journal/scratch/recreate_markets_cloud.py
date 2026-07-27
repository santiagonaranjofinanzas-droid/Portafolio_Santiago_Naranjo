import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import psycopg
import json

#Try to import MT5
try:
    import MetaTrader5 as mt5
except ImportError:
    print("MetaTrader5 package not installed.")
    exit(1)

#Cloud DB Config
DB_URL = "postgresql://avnadmin:AVNS_EWyQlHMAjEZeCy03Npf@pg-2d252eaa-santiagonaranjofinanzas-058f.l.aivencloud.com:23503/defaultdb?sslmode=require"

def calculate_trade_physics(row):
    """Calcula MAE/MFE M1 via MT5"""
    if pd.isna(row['entrytime']) or pd.isna(row['exittime']):
        return None
    
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
    
    # SL lookup or estimate
    sl = float(row.get('sl', 0))
    risk_price = abs(row['entryprice'] - sl) if sl > 0 else (abs(row['netpnl']) if row['netpnl'] < 0 else (row['entryprice'] * 0.01))
    if risk_price == 0: risk_price = 0.0001
    
    return {
        'mae': float(mae),
        'mfe': float(mfe),
        'mae_r': float(mae / risk_price),
        'mfe_r': float(mfe / risk_price),
        'efficiency': float(row['netpnl'] / (mfe * row['volume'] * 100)) if mfe > 0 and row['volume'] > 0 else 0.0
    }

def main():
    if not mt5.initialize():
        print(f"MT5 Initialize failed: {mt5.last_error()}")
        return

    print("Connected to MT5. Starting Cloud Direct Sync...")
    
    acc = mt5.account_info()
    if not acc:
        print("Could not get account info")
        return
        
    login = str(acc.login)
    server = acc.server
    
    # Sync Snapshots first to fix the balance
    balance = float(acc.balance)
    equity = float(acc.equity)
    
    with psycopg.connect(DB_URL) as conn:
        with conn.cursor() as cur:
            # 1. Update Balance Snapshot
            cur.execute(
                "INSERT INTO accountsnapshot (organization_id, account_login, server_name, balance, equity, captured_at, currency) "
                "VALUES (1, %s, %s, %s, %s, %s, %s)",
                (login, server, balance, equity, datetime.utcnow(), acc.currency)
            )
            print(f"Snapshot updated: Balance={balance}, Equity={equity}")
            
            # 2. Sync History
            to_date = datetime.now() + timedelta(days=1)
            from_date = datetime.now() - timedelta(days=30)
            
            deals = mt5.history_deals_get(from_date, to_date)
            if not deals:
                print("No deals found.")
            else:
                df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
                df_trades = df_deals[(df_deals['entry'].isin([0, 1])) & (df_deals['type'].isin([0, 1])) & (df_deals['symbol'].notna())].copy()
                
                # Positions
                positions = df_trades.groupby('position_id').agg({
                    'symbol': 'first', 'time': ['first', 'last'], 'price': ['first', 'last'],
                    'profit': 'sum', 'commission': 'sum', 'swap': 'sum', 'volume': 'first', 'type': 'first',
                    'magic': 'first'
                })
                positions.columns = ['symbol', 'entrytime', 'exittime', 'entryprice', 'exitprice', 'gross_pnl', 'commission', 'swap', 'volume', 'type_op', 'magic_number']
                positions = positions.reset_index()
                
                print(f"Syncing {len(positions)} positions to Cloud...")
                
                for _, row in positions.iterrows():
                    pid = int(row['position_id'])
                    
                    # Calculate physics
                    physics = calculate_trade_physics({
                        'symbol': row['symbol'],
                        'entrytime': datetime.fromtimestamp(row['entrytime']),
                        'exittime': datetime.fromtimestamp(row['exittime']),
                        'entryprice': row['entryprice'],
                        'exitprice': row['exitprice'],
                        'type_op': row['type_op'],
                        'netpnl': row['gross_pnl'] + row['commission'] + row['swap'],
                        'volume': row['volume']
                    })
                    
                    # Insert or Update TradeArchive
                    # We use a trick to avoid duplicates but update data
                    cur.execute(
                        "INSERT INTO tradearchive (organization_id, position_id, symbol, account_login, server_name, entrytime, exittime, entryprice, exitprice, gross_pnl, commission, swap, volume, type_op, netpnl, direction, exit_reason, sl, risk_price, valid_sl, mae, mfe, mae_r, mfe_r, efficiency, magic_number) "
                        "VALUES (1, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0, 0, 0, false, %s, %s, %s, %s, %s, %s) "
                        "ON CONFLICT (organization_id, position_id) DO UPDATE SET "
                        "netpnl = EXCLUDED.netpnl, exittime = EXCLUDED.exittime, exitprice = EXCLUDED.exitprice, mae = EXCLUDED.mae, mfe = EXCLUDED.mfe",
                        (
                            pid, row['symbol'], login, server,
                            datetime.fromtimestamp(row['entrytime']), datetime.fromtimestamp(row['exittime']),
                            float(row['entryprice']), float(row['exitprice']),
                            float(row['gross_pnl']), float(row['commission']), float(row['swap']),
                            float(row['volume']), int(row['type_op']),
                            float(row['gross_pnl'] + row['commission'] + row['swap']),
                            "Buy" if row['type_op'] == 0 else "Sell",
                            physics['mae'] if physics else None,
                            physics['mfe'] if physics else None,
                            physics['mae_r'] if physics else None,
                            physics['mfe_r'] if physics else None,
                            physics['efficiency'] if physics else None,
                            int(row['magic_number'])
                        )
                    )
            
            conn.commit()
            print("Cloud Direct Sync Completed successfully.")
            
    mt5.shutdown()

if __name__ == "__main__":
    main()
