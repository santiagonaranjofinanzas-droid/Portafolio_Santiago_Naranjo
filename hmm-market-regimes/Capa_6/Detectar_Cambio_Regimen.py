import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_6.regime_monitor import RegimePolicy, classify_regime, write_regime_status


def main():
    result_dir = ROOT / "Capa_6" / "resultados_optimizacion"
    trades_path = result_dir / "best_oos_trades.csv"
    equity_path = result_dir / "best_oos_equity.csv"

    if not trades_path.exists() or not equity_path.exists():
        raise FileNotFoundError("Ejecuta primero Capa_6/Reentrenar_Modelo.py")

    trades = pd.read_csv(trades_path)
    equity_df = pd.read_csv(equity_path, index_col=0, parse_dates=True)
    equity = equity_df.iloc[:, 0]

    diagnostics, q_report = classify_regime(trades, equity, RegimePolicy())
    write_regime_status(diagnostics, q_report, result_dir)

    print("=========================================================================")
    print("CAPA 6: DETECTOR DE CAMBIO DE REGIMEN")
    print("=========================================================================")
    print(f"Estado: {diagnostics['status']}")
    print(f"PF ultimo trimestre: {diagnostics['last_quarter_profit_factor']:.3f}")
    print(f"PnL ultimo trimestre: {diagnostics['last_quarter_net_pnl']:.2f}")
    print(f"PF ventana reciente: {diagnostics['recent_window_profit_factor']:.3f}")
    print(f"Racha perdida ventana reciente: {diagnostics['recent_window_loss_streak']}")
    print(f"Drawdown OOS max: {diagnostics['full_oos_max_drawdown_pct']:.2f}%")
    print("Accion:")
    for key, value in diagnostics["action"].items():
        print(f"  {key}: {value}")
    print("Razones:")
    for reason in diagnostics["reasons"]:
        print(f"  - {reason}")
    print(f"Reporte JSON: {result_dir / 'regime_status.json'}")
    print(f"Reporte trimestral: {result_dir / 'regime_quarterly_diagnostics.csv'}")
    print("=========================================================================")


if __name__ == "__main__":
    main()
