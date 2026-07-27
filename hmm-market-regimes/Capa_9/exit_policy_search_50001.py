from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_4.audit_oos_stability_30001 import metrics_for_trades, write_table


@dataclass(frozen=True)
class ExitPolicy:
    name: str
    min_hold_bars: int
    max_hold_bars: int
    weak_strength_cutoff: float
    weak_tp_capture: float
    be_mae_ratio: float


def policy_grid() -> list[ExitPolicy]:
    return [
        ExitPolicy("baseline_observed", 0, 10_000, 0.0, 1.0, 10.0),
        ExitPolicy("time_12_96", 12, 96, 0.0, 1.0, 10.0),
        ExitPolicy("time_24_96", 24, 96, 0.0, 1.0, 10.0),
        ExitPolicy("weak_tp_70_time_12_96", 12, 96, 0.70, 0.70, 10.0),
        ExitPolicy("weak_tp_60_time_12_72", 12, 72, 0.70, 0.60, 10.0),
        ExitPolicy("be_selective_time_12_96", 12, 96, 0.0, 1.0, 0.45),
    ]


def simulate_policy(trades: pd.DataFrame, policy: ExitPolicy) -> pd.DataFrame:
    out = trades.copy()
    pnl = out["pnl"].astype(float).copy()

    too_fast = out["bars_held"].astype(float) < policy.min_hold_bars
    pnl.loc[too_fast] = pnl.loc[too_fast] * 0.35

    too_late = out["bars_held"].astype(float) > policy.max_hold_bars
    pnl.loc[too_late] = np.where(pnl.loc[too_late] > 0.0, pnl.loc[too_late] * 0.75, pnl.loc[too_late] * 0.60)

    weak = out["ML_Master_Strength"].astype(float) < policy.weak_strength_cutoff
    profitable = pnl > 0.0
    pnl.loc[weak & profitable] = np.minimum(pnl.loc[weak & profitable], out.loc[weak & profitable, "mfe_money"] * policy.weak_tp_capture)

    be_candidates = (
        (out["mfe_money"].astype(float) > 0.0)
        & (out["mae_money"].astype(float) / out["mfe_money"].replace(0.0, np.nan).astype(float) <= policy.be_mae_ratio)
        & (pnl < 0.0)
    )
    pnl.loc[be_candidates] = 0.0

    out["pnl"] = pnl
    out["return_on_initial_balance"] = pnl / 10_000.0
    out["balance"] = 10_000.0 + pnl.cumsum()
    out["exit_policy"] = policy.name
    return out


def split_walk_forward(trades: pd.DataFrame, folds: int = 5) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    periods = pd.period_range(trades["entry_time"].min().to_period("M"), trades["entry_time"].max().to_period("M"), freq="M")
    chunks = np.array_split(periods, folds + 1)
    windows = []
    for i in range(1, len(chunks)):
        train_periods = chunks[i - 1]
        test_periods = chunks[i]
        windows.append((
            pd.Timestamp(train_periods[0].start_time),
            pd.Timestamp(train_periods[-1].end_time),
            pd.Timestamp(test_periods[0].start_time),
            pd.Timestamp(test_periods[-1].end_time),
        ))
    return windows


def score(metrics: dict) -> float:
    pf = float(metrics.get("profit_factor", 0.0))
    ret = float(metrics.get("return_pct_on_initial", 0.0))
    dd = abs(float(metrics.get("max_drawdown_pct", 0.0)))
    trades = int(metrics.get("trades", 0))
    if trades < 20:
        return -1e9
    return pf + max(ret, -50.0) / 100.0 - dd / 80.0


def main() -> None:
    source = ROOT / "Capa_7" / "edge_diagnostics_50001" / "tick_trades_50001_enriched_mae_mfe.csv"
    outdir = ROOT / "Capa_9" / "exit_policy_search_50001"
    outdir.mkdir(parents=True, exist_ok=True)
    trades = pd.read_csv(source, parse_dates=["entry_time", "exit_time"])

    rows = []
    selected_rows = []
    for fold, (train_start, train_end, test_start, test_end) in enumerate(split_walk_forward(trades), start=1):
        train = trades[(trades["entry_time"] >= train_start) & (trades["entry_time"] <= train_end)].copy()
        test = trades[(trades["entry_time"] >= test_start) & (trades["entry_time"] <= test_end)].copy()
        train_results = []
        for policy in policy_grid():
            sim_train = simulate_policy(train, policy)
            train_metrics = metrics_for_trades(sim_train, policy.name)
            train_results.append((score(train_metrics), policy, train_metrics))
            rows.append({
                "fold": fold,
                "phase": "train",
                "policy": policy.name,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                **train_metrics,
            })
        train_results.sort(key=lambda item: item[0], reverse=True)
        _, best_policy, _ = train_results[0]
        sim_test = simulate_policy(test, best_policy)
        test_metrics = metrics_for_trades(sim_test, best_policy.name)
        rows.append({
            "fold": fold,
            "phase": "test",
            "policy": best_policy.name,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            **test_metrics,
        })
        selected_rows.append({
            "fold": fold,
            "policy": best_policy.name,
            "min_hold_bars": best_policy.min_hold_bars,
            "max_hold_bars": best_policy.max_hold_bars,
            "weak_strength_cutoff": best_policy.weak_strength_cutoff,
            "weak_tp_capture": best_policy.weak_tp_capture,
            "be_mae_ratio": best_policy.be_mae_ratio,
        })

    result = pd.DataFrame(rows)
    result.to_csv(outdir / "exit_policy_walk_forward_50001.csv", index=False)
    selected = pd.DataFrame(selected_rows)
    selected.to_csv(outdir / "selected_exit_policies_50001.csv", index=False)
    tests = result[result["phase"] == "test"].copy()
    summary = {
        "folds": int(len(tests)),
        "median_test_pf": float(tests["profit_factor"].median()),
        "min_test_pf": float(tests["profit_factor"].min()),
        "mean_test_return_pct": float(tests["return_pct_on_initial"].mean()),
        "worst_test_dd_pct": float(tests["max_drawdown_pct"].min()),
        "total_test_trades": int(tests["trades"].sum()),
        "pass_pf_110_all": bool((tests["profit_factor"] >= 1.10).all()),
    }
    pd.DataFrame([summary]).to_csv(outdir / "exit_policy_summary_50001.csv", index=False)

    cols = ["fold", "phase", "policy", "trades", "return_pct_on_initial", "win_rate_pct", "profit_factor", "max_drawdown_pct", "max_consecutive_losses", "sharpe_trade"]
    report = f"""# Capa 9 - Optimizacion de salidas 50001

Este buscador usa trades tick enriquecidos con MAE/MFE. Es una simulacion de politica de salida sobre trades ya abiertos, por lo que no reemplaza el backtest intratrade completo; sirve para seleccionar candidatos antes de codificarlos en MQL/tick-engine.

##Resumen walk-forward

- PF mediano test: {summary['median_test_pf']:.3f}
- PF minimo test: {summary['min_test_pf']:.3f}
- Retorno medio test: {summary['mean_test_return_pct']:.2f}%
- Peor DD test: {summary['worst_test_dd_pct']:.2f}%
- Trades test totales: {summary['total_test_trades']}
- Gate PF>=1.10 todos los folds: {summary['pass_pf_110_all']}

##Folds test

{write_table(tests[cols], cols)}

##Politicas seleccionadas

{write_table(selected, list(selected.columns))}

##Decision

La politica solo puede pasar a MQL si mejora PF minimo y DD sin reducir muestra de forma artificial. Si el gate falla, se mantiene como investigacion y se prioriza forward demo.
"""
    (outdir / "REPORTE_EXIT_POLICY_50001.md").write_text(report, encoding="utf-8")
    print(f"OK: {outdir}")
    print(summary)


if __name__ == "__main__":
    main()
