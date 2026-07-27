import os
import sys
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_2.sovereign_signal import run_sovereign_signal_engine
from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest


def evaluate_dataset(name: str, parquet_path: Path, params_path: Path, out_dir: Path, dsr_trials: int) -> dict:
    print(f"Procesando {name}: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    signals = run_sovereign_signal_engine(df, params_csv=str(params_path), point=0.01)
    trades, cashflows, equity = run_backtest(signals, BacktestAssumptions())
    metrics = compute_backtest_metrics(trades, cashflows, equity, BacktestAssumptions(), dsr_trials=dsr_trials)
    metrics["dataset"] = name
    metrics["start_time"] = str(df.index.min())
    metrics["end_time"] = str(df.index.max())
    metrics["bars"] = len(df)

    signals.to_parquet(out_dir / f"signals_{name}.parquet", engine="pyarrow", compression="snappy")
    trades.to_csv(out_dir / f"trades_{name}.csv", index=False)
    cashflows.to_csv(out_dir / f"cashflows_{name}.csv", index=False)
    equity.to_frame().to_csv(out_dir / f"equity_{name}.csv")
    return metrics


def main():
    out_dir = ROOT / "Capa_4" / "metricas_backtest"
    out_dir.mkdir(parents=True, exist_ok=True)

    params_path = Path(os.environ.get("SOVEREIGN_PARAMS_PATH", ROOT / "HMM_Params_15M.csv"))
    dsr_trials = int(os.environ.get("DSR_TRIALS", "1"))
    datasets = {
        "IS_PURGED": ROOT / "Capa_5" / "XAUUSD_M15_IS_PURGED.parquet",
        "OOS_202405": ROOT / "Capa_5" / "XAUUSD_M15_OOS_202405.parquet",
    }

    rows = []
    for name, path in datasets.items():
        if not path.exists():
            raise FileNotFoundError(f"No existe {path}")
        rows.append(evaluate_dataset(name, path, params_path, out_dir, dsr_trials))

    summary = pd.DataFrame(rows)
    first_cols = ["dataset", "start_time", "end_time", "bars", "closed_trades", "final_balance", "total_return_pct"]
    summary = summary[first_cols + [c for c in summary.columns if c not in first_cols]]
    summary.to_csv(out_dir / "resumen_metricas_is_oos.csv", index=False)

    print("\nResumen IS/OOS:")
    display_cols = [
        "dataset", "closed_trades", "total_return_pct", "win_rate_pct", "profit_factor",
        "max_drawdown_pct", "max_consecutive_wins", "max_consecutive_losses",
        "sharpe_ratio", "sortino_ratio", "deflated_sharpe_probability",
    ]
    print(summary[display_cols].to_string(index=False))
    print(f"\nReportes: {out_dir}")


if __name__ == "__main__":
    main()
