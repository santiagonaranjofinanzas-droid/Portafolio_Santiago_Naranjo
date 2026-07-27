"""Recompute presentation/risk metrics from frozen trades on the 100k basis."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from NAS100_RESEARCH_V2.validation.gates import evaluate_gates, load_policy
from NAS100_RESEARCH_V2.validation.metrics import performance_summary


def correct_trend(directory: str  Path) -> dict:
    path = Path(directory)
    original = json.loads((path / "nested_decision.json").read_text(encoding="utf-8"))
    trades = pd.read_csv(path / "nested_outer_oos_trades.csv", parse_dates=["entry_time", "exit_time"])
    folds = pd.read_csv(path / "outer_folds.csv", parse_dates=["test_start", "test_end"])
    fold_metrics = []
    for row in folds.itertuples(index=False):
        selected = trades.loc[trades["fold_id"] == row.fold_id]
        metric = performance_summary(
            selected,
            initial_balance=100_000.0,
            trials=original["total_trials"],
            start=row.test_start,
            end=row.test_end,
        )
        metric["fold_id"] = int(row.fold_id)
        fold_metrics.append(metric)
    metrics = performance_summary(
        trades,
        initial_balance=100_000.0,
        trials=original["total_trials"],
        start=folds.iloc[0]["test_start"],
        end=folds.iloc[-1]["test_end"],
    )
    robustness = original["robustness"]
    research = evaluate_gates(metrics, robustness, fold_metrics, "research", load_policy())
    institutional = evaluate_gates(metrics, robustness, fold_metrics, "institutional", load_policy())
    corrected = {
        **original,
        "correction": {
            "reason": "Validation presentation used 10k while model backtests use 100k",
            "scope": "return, equity-relative drawdown, daily Sharpe and DSR only; frozen trades/PnL/PF/PBO unchanged",
            "authoritative_initial_balance": 100_000.0,
        },
        "metrics": metrics,
        "research_gate": {"approved": research.approved, "checks": list(research.checks)},
        "institutional_gate": {"approved": institutional.approved, "checks": list(institutional.checks)},
        "regime_selected_by_inner_cpcv": True,
        "regime_retained": bool(
            robustness.get("probability_improvement", 0.0) >= 0.95
            and robustness.get("delta_expectancy_p05", -1.0) > 0.0
        ),
        "status": "REJECTED_LIVE_LOCKED",
        "live_locked": True,
    }
    destination = path / "nested_decision_corrected_account_basis.json"
    destination.write_text(json.dumps(corrected, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    pd.DataFrame(fold_metrics).to_csv(path / "nested_fold_metrics_corrected_account_basis.csv", index=False)
    candidate_rows = []
    for candidate_path in sorted(path.glob("candidate_*_outer_oos_trades.csv")):
        candidate_id = candidate_path.name.removeprefix("candidate_").removesuffix("_outer_oos_trades.csv")
        candidate_trades = pd.read_csv(candidate_path, parse_dates=["entry_time", "exit_time"])
        row = performance_summary(
            candidate_trades,
            initial_balance=100_000.0,
            trials=original["total_trials"],
            start=folds.iloc[0]["test_start"],
            end=folds.iloc[-1]["test_end"],
        )
        candidate_rows.append({"candidate_id": candidate_id, **row})
    pd.DataFrame(candidate_rows).to_csv(path / "candidate_metrics_corrected_account_basis.csv", index=False)
    return corrected
