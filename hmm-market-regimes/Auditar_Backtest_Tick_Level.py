import json
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
from Capa_4.backtest_metrics import BacktestAssumptions
from Capa_4.tick_backtest import TickBacktestConfig, run_tick_backtest_with_metrics


def load_candidate(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def main():
    dataset_path = Path(os.environ.get("TICK_AUDIT_DATASET", ROOT / "Capa_5" / "XAUUSD_M15_OOS_202405.parquet"))
    params_path = Path(os.environ.get("SOVEREIGN_PARAMS_PATH", ROOT / "HMM_Params_15M.csv"))
    candidate_path = Path(os.environ.get("TICK_AUDIT_CANDIDATE", ROOT / "Capa_6" / "resultados_optimizacion" / "best_params.json"))
    out_dir = Path(os.environ.get("TICK_AUDIT_OUT", ROOT / "Capa_4" / "tick_audit"))
    max_trades_env = os.environ.get("TICK_AUDIT_MAX_TRADES", "120")
    max_trades = None if max_trades_env.strip().lower() in {"", "none", "all", "full"} else int(max_trades_env)
    dsr_trials = int(os.environ.get("DSR_TRIALS", "81"))

    out_dir.mkdir(parents=True, exist_ok=True)
    candidate = load_candidate(candidate_path)
    df = pd.read_parquet(dataset_path)
    signals = run_sovereign_signal_engine(
        df,
        params_csv=str(params_path),
        threshold=float(candidate["threshold"]),
        min_strength=float(candidate["min_strength"]),
        kalman_gate=bool(candidate.get("kalman_gate", True)),
        point=0.01,
    )
    assumptions = BacktestAssumptions(
        min_strength=float(candidate["min_strength"]),
        vol_multiplier=float(candidate["vol_multiplier"]),
        reward_risk=float(candidate["reward_risk"]),
    )
    config = TickBacktestConfig(
        data_root=ROOT / "gold_data_parquet",
        max_holding_bars=int(os.environ.get("TICK_AUDIT_MAX_HOLDING_BARS", "500")),
        entry_delay_bars=1,
        max_trades=max_trades,
    )
    metrics, trades, cashflows, equity = run_tick_backtest_with_metrics(signals, assumptions, config, dsr_trials=dsr_trials)
    pd.DataFrame([{**candidate, **metrics}]).to_csv(out_dir / "tick_metrics.csv", index=False)
    trades.to_csv(out_dir / "tick_trades.csv", index=False)
    cashflows.to_csv(out_dir / "tick_cashflows.csv", index=False)
    equity.to_frame().to_csv(out_dir / "tick_equity.csv")

    print("=========================================================================")
    print("AUDITORIA TICK-LEVEL BID/ASK")
    print("=========================================================================")
    print(f"Dataset: {dataset_path}")
    print(f"Candidato: {candidate_path}")
    print(f"Max trades: {max_trades if max_trades is not None else 'FULL'}")
    print(f"Closed trades: {metrics['closed_trades']}")
    print(f"Return: {metrics['total_return_pct']:.2f}%")
    print(f"Win rate: {metrics['win_rate_pct']:.2f}%")
    print(f"Profit factor: {metrics['profit_factor']:.3f}")
    print(f"Max DD: {metrics['max_drawdown_pct']:.2f}%")
    print(f"Sharpe: {metrics['sharpe_ratio']:.3f}")
    print(f"DSR: {metrics['deflated_sharpe_probability']:.3f}")
    print(f"Reportes: {out_dir}")
    print("=========================================================================")


if __name__ == "__main__":
    main()
