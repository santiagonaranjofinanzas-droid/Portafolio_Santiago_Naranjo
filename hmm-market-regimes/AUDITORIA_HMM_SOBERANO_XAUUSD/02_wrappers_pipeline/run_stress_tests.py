import os
import sys
import pandas as pd
from pathlib import Path

#Setup paths
ruta_actual = os.path.dirname(os.path.abspath(__file__))
if ruta_actual not in sys.path:
    sys.path.insert(0, ruta_actual)

from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest

def run_stress_test(ruta_signals: str, spread: float, slippage: float, out_path: str):
    df_sig = pd.read_csv(ruta_signals, index_col=0, parse_dates=True)
    
    cfg = BacktestAssumptions(
        point=0.01,
        tick_size=0.01,
        tick_value=1.0,
        spread_price=spread,
        slippage_price=slippage,
        initial_balance=10000.0,
        risk_percent=1.0,
        commission_per_lot=3.0,
    )
    
    trades, cashflows, equity = run_backtest(df_sig, cfg)
    metrics = compute_backtest_metrics(trades, cashflows, equity, cfg, dsr_trials=81)
    pd.DataFrame([metrics]).to_csv(out_path, index=False)
    print(f"Stress test guardado en {out_path} (Spread={spread}, Slippage={slippage})")

if __name__ == "__main__":
    base_spread = 0.15
    base_slippage = 0.05
    
    ruta_sig_oos = os.path.join(ruta_actual, "Universo de activos", "resultados", "XAUUSD", "XAUUSD_signals_OOS.csv")
    
    if not os.path.exists(ruta_sig_oos):
        print(f"Error: {ruta_sig_oos} no existe aún.")
        sys.exit(1)
        
    run_stress_test(ruta_sig_oos, base_spread * 1, base_slippage, "stress_spread_x1.csv")
    run_stress_test(ruta_sig_oos, base_spread * 2, base_slippage, "stress_spread_x2.csv")
    run_stress_test(ruta_sig_oos, base_spread * 3, base_slippage, "stress_spread_x3.csv")
    run_stress_test(ruta_sig_oos, base_spread, base_slippage * 2, "stress_slippage.csv")
