from __future__ import annotations

from importlib import import_module
from pathlib import Path

import numpy as np
import pandas as pd

from Capa_2.sovereign_signal import run_sovereign_signal_engine
from Capa_4.backtest_metrics import BacktestAssumptions, run_backtest


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
OUT = HERE / "results" / "trend_defensive_ensemble_walk_forward"
DATA = ROOT / "Universo de activos" / "resultados" / "NSXUSD" / "NSXUSD_M15_IS_PURGED.parquet"
PARAM_ROOT = HERE / "results" / "trend_nested_walk_forward"
VARIANTS = {
    "A_2.5_1.5": (2.5, 1.5),
    "B_1.5_2.0": (1.5, 2.0),
    "C_3.0_3.0": (3.0, 3.0),
    "D_2.5_2.5": (2.5, 2.5),
}


def assumptions(vol_multiplier: float, reward_risk: float) -> BacktestAssumptions:
    return BacktestAssumptions(
        initial_balance=10_000.0,
        risk_percent=1.0,
        min_strength=0.35,
        vol_multiplier=vol_multiplier,
        reward_risk=reward_risk,
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


def session_filter(signals: pd.DataFrame) -> pd.DataFrame:
    result = signals.copy()
    ny = pd.DatetimeIndex(result.index).tz_localize("UTC").tz_convert("America/New_York")
    allowed = (ny.hour >= 3) & (ny.hour < 17) & (ny.dayofweek < 4)
    result.loc[~allowed, "Regime_Buffer_18"] = 0
    return result


def main() -> None:
    module = import_module("Universo de activos.Capa_6_WalkForward.walk_forward_activo")
    data = pd.read_parquet(DATA)
    folds = module.make_walk_forward_folds(data.index, n_folds=4, purge_bars=120)
    OUT.mkdir(parents=True, exist_ok=True)
    summary = []
    for fold in folds:
        fold_id = int(fold["fold_id"])
        fold_out = OUT / f"fold_{fold_id}"
        fold_out.mkdir(parents=True, exist_ok=True)
        params_path = PARAM_ROOT / f"fold_{fold_id}" / "HMM_Params_fold.csv"
        if not params_path.exists():
            train = data.iloc[: int(fold["train_end"]) + 1]
            params_path = fold_out / "HMM_Params_fold.csv"
            module.make_hmm_params_csv_from_train(train, params_path)
        signals_path = fold_out / "signals.parquet"
        if signals_path.exists():
            signals = pd.read_parquet(signals_path)
        else:
            train = data.iloc[: int(fold["train_end"]) + 1]
            validation = data.iloc[int(fold["val_start"]): int(fold["val_end"]) + 1]
            engine_input = pd.concat([train.tail(2000), validation])
            signals = run_sovereign_signal_engine(
                engine_input,
                params_csv=str(params_path),
                threshold=0.65,
                min_strength=0.35,
                kalman_gate=True,
                point=0.01,
            ).loc[validation.index]
            signals.to_parquet(signals_path)
        signals = session_filter(signals)
        daily_parts = []
        variant_rows = []
        for name, (vol_multiplier, reward_risk) in VARIANTS.items():
            trades, cashflows, equity = run_backtest(signals, assumptions(vol_multiplier, reward_risk))
            trades.to_csv(fold_out / f"{name}_trades.csv", index=False)
            daily = pd.Series(
                trades["pnl"].to_numpy(float) / len(VARIANTS),
                index=pd.to_datetime(trades["exit_time"]),
            ).groupby(lambda value: value.floor("D")).sum()
            daily_parts.append(daily.rename(name))
            variant_rows.append({"variant": name, "trades": len(trades), "net_pnl": float(trades["pnl"].sum())})
        daily_frame = pd.concat(daily_parts, axis=1).fillna(0.0).sort_index()
        daily_frame["portfolio_pnl"] = daily_frame.sum(axis=1)
        daily_frame["equity"] = 10_000.0 + daily_frame["portfolio_pnl"].cumsum()
        values = daily_frame["portfolio_pnl"].to_numpy(float)
        gross_win = values[values > 0].sum()
        gross_loss = abs(values[values <= 0].sum())
        pf = float(gross_win / gross_loss) if gross_loss > 0 else float("inf")
        peak = daily_frame["equity"].cummax()
        dd_pct = ((daily_frame["equity"] - peak) / peak * 100.0).min()
        row = {
            "fold_id": fold_id,
            "validation_start": str(fold["val_start_time"]),
            "validation_end": str(fold["val_end_time"]),
            "profit_factor": pf,
            "return_pct": float(daily_frame["portfolio_pnl"].sum() / 100.0),
            "max_drawdown_pct": float(dd_pct),
            "active_days": int((daily_frame["portfolio_pnl"] != 0.0).sum()),
            "component_trades": int(sum(item["trades"] for item in variant_rows)),
        }
        daily_frame.to_csv(fold_out / "portfolio_daily.csv")
        pd.DataFrame(variant_rows).to_csv(fold_out / "variant_summary.csv", index=False)
        summary.append(row)
        print(f"Fold {fold_id}: PF={pf:.6f} return={row['return_pct']:.3f}%", flush=True)
    result = pd.DataFrame(summary).sort_values("fold_id")
    result.to_csv(OUT / "ensemble_walk_forward_summary.csv", index=False)
    aggregate = {
        "completed_folds": int(result["fold_id"].nunique()),
        "median_pf": float(result["profit_factor"].median()),
        "min_pf": float(result["profit_factor"].min()),
        "median_return_pct": float(result["return_pct"].median()),
        "min_return_pct": float(result["return_pct"].min()),
        "worst_drawdown_pct": float(result["max_drawdown_pct"].min()),
        "active_days": int(result["active_days"].sum()),
    }
    pd.DataFrame([aggregate]).to_csv(OUT / "ensemble_walk_forward_aggregate.csv", index=False)
    print(aggregate, flush=True)


if __name__ == "__main__":
    main()
