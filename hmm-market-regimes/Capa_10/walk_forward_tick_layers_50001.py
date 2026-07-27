from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_4.audit_oos_stability_30001 import metrics_for_trades


@dataclass(frozen=True)
class LayerCandidate:
    name: str
    min_strength: float
    session_mode: str
    sigma_min_q: float
    sigma_max_q: float


def candidate_grid() -> list[LayerCandidate]:
    return [
        LayerCandidate("base_no_layers", 0.35, "all", 0.00, 1.00),
        LayerCandidate("london_late_s050_sig20_95", 0.50, "london_late", 0.20, 0.95),
        LayerCandidate("london_late_s055_sig20_90", 0.55, "london_late", 0.20, 0.90),
        LayerCandidate("no_ny_s050_sig20_95", 0.50, "no_ny", 0.20, 0.95),
        LayerCandidate("london_late_s050_sig10_95", 0.50, "london_late", 0.10, 0.95),
    ]


def attach_entry_features(trades: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    signals_reset = signals.reset_index()
    idx = trades["entry_i"].astype(int).clip(0, len(signals_reset) - 1)
    features = signals_reset.loc[
        idx,
        ["timestamp", "HMM_Prob_Bull", "ML_Master_Strength", "Vol_Projected_Sigma", "Regime_Buffer_18"],
    ].reset_index(drop=True)
    out = pd.concat([trades.reset_index(drop=True), features], axis=1)
    out["hour"] = out["entry_time"].dt.hour
    return out


def filter_trades(trades: pd.DataFrame, candidate: LayerCandidate, reference: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    ref_sigma = reference["Vol_Projected_Sigma"].replace([np.inf, -np.inf], np.nan).dropna()
    sigma_min = float(ref_sigma.quantile(candidate.sigma_min_q)) if not ref_sigma.empty else 0.0
    sigma_max = float(ref_sigma.quantile(candidate.sigma_max_q)) if not ref_sigma.empty else np.inf

    if candidate.session_mode == "london_late":
        session_ok = ((trades["hour"] >= 7) & (trades["hour"] < 13))  ((trades["hour"] >= 20) & (trades["hour"] < 24))
    elif candidate.session_mode == "no_ny":
        session_ok = ~((trades["hour"] >= 13) & (trades["hour"] < 20))
    else:
        session_ok = pd.Series(True, index=trades.index)

    mask = (
        session_ok
        & (trades["ML_Master_Strength"] >= candidate.min_strength)
        & (trades["Vol_Projected_Sigma"] >= sigma_min)
        & (trades["Vol_Projected_Sigma"] <= sigma_max)
    )
    return trades[mask].copy(), {"sigma_min": sigma_min, "sigma_max": sigma_max}


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
    return pf + max(ret, -50.0) / 100.0 - dd / 100.0


def main() -> None:
    source = ROOT / "Capa_4" / "comparacion_oos_30001_40001_accel18"
    outdir = ROOT / "Capa_10" / "walk_forward_tick_layers_50001"
    outdir.mkdir(parents=True, exist_ok=True)

    trades = pd.read_csv(source / "tick_trades_oos_40001.csv", parse_dates=["entry_time", "exit_time"])
    signals = pd.read_parquet(source / "signals_oos_40001.parquet")
    trades = attach_entry_features(trades, signals)

    rows = []
    for fold, (train_start, train_end, test_start, test_end) in enumerate(split_walk_forward(trades, folds=5), start=1):
        train = trades[(trades["entry_time"] >= train_start) & (trades["entry_time"] <= train_end)].copy()
        test = trades[(trades["entry_time"] >= test_start) & (trades["entry_time"] <= test_end)].copy()
        train_results = []
        for candidate in candidate_grid():
            filtered_train, layer_info = filter_trades(train, candidate, train)
            train_metrics = metrics_for_trades(filtered_train, candidate.name)
            train_results.append((score(train_metrics), candidate, train_metrics, layer_info))
            rows.append({
                "fold": fold,
                "phase": "train",
                "candidate": candidate.name,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                **layer_info,
                **train_metrics,
            })

        train_results.sort(key=lambda item: item[0], reverse=True)
        _, best_candidate, _, train_layer_info = train_results[0]
        filtered_test, test_layer_info = filter_trades(test, best_candidate, train)
        test_metrics = metrics_for_trades(filtered_test, best_candidate.name)
        rows.append({
            "fold": fold,
            "phase": "test",
            "candidate": best_candidate.name,
            "train_start": train_start,
            "train_end": train_end,
            "test_start": test_start,
            "test_end": test_end,
            **test_layer_info,
            **test_metrics,
        })

    result = pd.DataFrame(rows)
    result.to_csv(outdir / "walk_forward_tick_layers_50001.csv", index=False)
    tests = result[result["phase"] == "test"].copy()
    summary = {
        "folds": int(len(tests)),
        "median_test_pf": float(tests["profit_factor"].median()) if not tests.empty else 0.0,
        "min_test_pf": float(tests["profit_factor"].min()) if not tests.empty else 0.0,
        "mean_test_return_pct": float(tests["return_pct_on_initial"].mean()) if not tests.empty else 0.0,
        "worst_test_dd_pct": float(tests["max_drawdown_pct"].min()) if not tests.empty else 0.0,
        "total_test_trades": int(tests["trades"].sum()) if not tests.empty else 0,
        "pass_pf_110_all": bool((tests["profit_factor"] >= 1.10).all()) if not tests.empty else False,
        "pass_min_trades": bool((tests["trades"] >= 20).all()) if not tests.empty else False,
    }
    pd.DataFrame([summary]).to_csv(outdir / "walk_forward_summary_50001.csv", index=False)
    tests.to_csv(outdir / "walk_forward_test_folds_50001.csv", index=False)

    report = f"""# Walk-forward tick-level capas 50001

Este protocolo usa el ledger de trades tick bid/ask ya generado para el 50001 base equivalente al 40001. En cada paso selecciona filtros sobre la ventana train y evalua esa misma eleccion en la ventana test siguiente.

Limitacion explicita: valida filtros de entrada con ejecucion tick-level ya realizada. Las salidas intratrade nuevas del EA 50001, como flip de regimen y pausa por racha live, se validan en forward live-shadow.

##Resumen

- Folds test: {summary['folds']}
- PF mediano test: {summary['median_test_pf']:.3f}
- PF minimo test: {summary['min_test_pf']:.3f}
- Retorno medio test: {summary['mean_test_return_pct']:.2f}%
- Peor DD test: {summary['worst_test_dd_pct']:.2f}%
- Trades test totales: {summary['total_test_trades']}
- Gate PF>=1.10 en todos los folds: {summary['pass_pf_110_all']}
- Gate minimo 20 trades por fold: {summary['pass_min_trades']}

##Decision

Si `pass_pf_110_all` es falso, el 50001 Layered V1 no se considera robusto final. Puede correr en demo/live-shadow, pero no pasa a real.
"""
    (outdir / "REPORTE_WALK_FORWARD_TICK_50001.md").write_text(report, encoding="utf-8")
    print(f"OK: {outdir}")
    print(summary)


if __name__ == "__main__":
    main()
