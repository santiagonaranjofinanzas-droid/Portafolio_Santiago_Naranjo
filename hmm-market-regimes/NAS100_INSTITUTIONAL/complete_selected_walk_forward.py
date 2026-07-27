from __future__ import annotations

from importlib import import_module
from pathlib import Path

import pandas as pd

from Capa_6.optimizer import load_parameter_space


ROOT = Path(__file__).resolve().parents[1]
RESULTS = Path(__file__).resolve().parent / "results"
SOURCE_RESULTS = RESULTS / "trend_nested_walk_forward"
OUT = RESULTS / "trend_selected_walk_forward"
DATA = ROOT / "Universo de activos" / "resultados" / "NSXUSD" / "NSXUSD_M15_IS_PURGED.parquet"


def selected_row(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    return frame[
        (frame["threshold"].sub(0.65).abs() < 1e-12)
        & (frame["min_strength"].sub(0.35).abs() < 1e-12)
        & (frame["vol_multiplier"].sub(2.5).abs() < 1e-12)
        & (frame["reward_risk"].sub(1.5).abs() < 1e-12)
    ].head(1)


def main() -> None:
    module = import_module("Universo de activos.Capa_6_WalkForward.walk_forward_activo")
    data = pd.read_parquet(DATA)
    folds = module.make_walk_forward_folds(data.index, n_folds=4, purge_bars=120)
    candidate = {
        "threshold": 0.65,
        "min_strength": 0.35,
        "vol_multiplier": 2.5,
        "reward_risk": 1.5,
        "kalman_gate": True,
    }
    space = load_parameter_space(ROOT / "Capa_6" / "parameter_space.json")
    OUT.mkdir(parents=True, exist_ok=True)
    selected = []
    for fold in folds:
        fold_id = int(fold["fold_id"])
        existing = SOURCE_RESULTS / f"fold_{fold_id}" / "ranking_fold.csv"
        target = OUT / f"fold_{fold_id}" / "ranking_fold.csv"
        row = selected_row(existing) if existing.exists() else pd.DataFrame()
        if row.empty and target.exists():
            row = selected_row(target)
        if row.empty:
            print(f"Running selected candidate fold {fold_id}", flush=True)
            row = module.evaluate_fold_activo(
                data,
                fold,
                [candidate],
                space,
                81,
                OUT,
                0.01,
                0.01,
                0.20,
                2.50,
                0.10,
                3.00,
                0.01,
                0.01,
                "pessimistic",
            )
        selected.append(row.iloc[0].to_dict())
        print(f"Fold {fold_id} PF={float(row.iloc[0]['profit_factor']):.6f}", flush=True)
    result = pd.DataFrame(selected).sort_values("fold_id")
    result.to_csv(OUT / "selected_trend_walk_forward.csv", index=False)
    print(result[["fold_id", "profit_factor", "total_return_pct", "max_drawdown_pct", "closed_trades"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
