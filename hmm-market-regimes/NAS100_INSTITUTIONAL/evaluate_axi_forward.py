from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from Capa_2.sovereign_signal import run_sovereign_signal_engine
from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest
from Capa_4.tick_backtest import TickBacktestConfig, run_tick_backtest_with_metrics


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
FORWARD = HERE / "forward_axi"
OLD = ROOT / "Universo de activos" / "resultados" / "NSXUSD" / "NSXUSD_M15_OOS.parquet"
PARAMS = ROOT / "Universo de activos" / "resultados" / "NSXUSD" / "HMM_Params_15M_NSXUSD.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def assumptions() -> BacktestAssumptions:
    return BacktestAssumptions(
        initial_balance=10_000.0,
        risk_percent=1.0,
        min_strength=0.35,
        vol_multiplier=2.5,
        reward_risk=1.5,
        use_partials=True,
        max_lot=10.0,
        point=0.01,
        tick_size=0.01,
        tick_value=0.20,
        spread_price=2.50,
        slippage_price=0.10,
        commission_per_lot=3.0,
        min_lot=0.01,
        lot_step=0.01,
        periods_per_year=24 * 4 * 252,
        intrabar_mode="pessimistic",
    )


def main() -> None:
    bars_path = FORWARD / "NAS100_fs_M15_FORWARD.parquet"
    output = FORWARD / "evaluation"
    output.mkdir(parents=True, exist_ok=True)
    old = pd.read_parquet(OLD).tail(2500)[["open", "high", "low", "close"]]
    new = pd.read_parquet(bars_path)[["open", "high", "low", "close"]]
    combined = pd.concat([old, new])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    signals = run_sovereign_signal_engine(
        combined,
        params_csv=str(PARAMS),
        threshold=0.65,
        min_strength=0.35,
        kalman_gate=True,
        point=0.01,
    ).loc[new.index]
    signals.to_parquet(output / "forward_signals.parquet")
    cfg = assumptions()
    ohlc_trades, ohlc_cashflows, ohlc_equity = run_backtest(signals, cfg)
    ohlc_metrics = compute_backtest_metrics(ohlc_trades, ohlc_cashflows, ohlc_equity, cfg, dsr_trials=81)
    tick_metrics, tick_trades, tick_cashflows, tick_equity = run_tick_backtest_with_metrics(
        signals,
        cfg,
        TickBacktestConfig(FORWARD / "ticks", max_holding_bars=500),
        dsr_trials=81,
    )
    ohlc_trades.to_csv(output / "ohlc_trades.csv", index=False)
    tick_trades.to_csv(output / "tick_trades.csv", index=False)
    tick_cashflows.to_csv(output / "tick_cashflows.csv", index=False)
    tick_equity.to_frame().to_csv(output / "tick_equity.csv")
    result = {
        "status": "CONSUMED_ONCE_DO_NOT_OPTIMIZE",
        "model": "FROZEN_TREND_BASELINE",
        "parameters": {"threshold": 0.65, "min_strength": 0.35, "vol_multiplier": 2.5, "reward_risk": 1.5},
        "period_start": str(signals.index.min()),
        "period_end": str(signals.index.max()),
        "bars": int(len(signals)),
        "bars_sha256": sha256(bars_path),
        "params_sha256": sha256(PARAMS),
        "ohlc_metrics": ohlc_metrics,
        "tick_metrics": tick_metrics,
    }
    (output / "forward_evaluation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
