from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol

import numpy as np
import pandas as pd

from .costs import AxiCostModel, CostScenario
from .gates import evaluate_gates, load_policy
from .metrics import (
    block_bootstrap,
    daily_pnl_from_trades,
    paired_block_bootstrap,
    performance_summary,
    probability_backtest_overfitting,
)
from .splits import OuterFold, make_rolling_outer_folds


@dataclass(frozen=True)
class CandidateSpec:
    candidate_id: str
    parameters: dict[str, Any]
    complexity: int = 1
    neighbor_ids: tuple[str, ...] = ()
    is_baseline: bool = False


@dataclass
class FoldRun:
    trades: pd.DataFrame
    diagnostics: dict[str, Any] = field(default_factory=dict)


class FoldEvaluator(Protocol):
    def __call__(self, train: pd.DataFrame, test: pd.DataFrame, candidate: CandidateSpec,
                 costs: CostScenario, fold: OuterFold) -> FoldRun: ...


def _json_default(value: Any):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    raise TypeError(type(value).__name__)


def _validate_fold_trades(trades: pd.DataFrame, fold: OuterFold) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["entry_time", "exit_time", "pnl"])
    required = {"entry_time", "exit_time", "pnl"}
    if not required.issubset(trades.columns):
        raise ValueError(f"evaluator trades require {sorted(required)}")
    result = trades.copy()
    result["entry_time"] = pd.to_datetime(result["entry_time"], errors="raise")
    result["exit_time"] = pd.to_datetime(result["exit_time"], errors="raise")
    if (result["entry_time"] < fold.test_start).any() or (result["entry_time"] > fold.test_end).any():
        raise ValueError("fold evaluator emitted entries outside the outer test interval")
    if (result["exit_time"] < result["entry_time"]).any():
        raise ValueError("trade exits precede entries")
    return result


def _pbo_matrix(daily_by_candidate: dict[str, pd.Series], blocks: int = 12) -> np.ndarray:
    if blocks % 2:
        raise ValueError("PBO blocks must be even")
    calendar = pd.DatetimeIndex(sorted(set().union(*(series.index for series in daily_by_candidate.values()))))
    if len(calendar) < blocks:
        raise ValueError("insufficient daily observations for PBO blocks")
    groups = np.array_split(np.arange(len(calendar)), blocks)
    matrix = np.empty((len(daily_by_candidate), blocks), dtype=float)
    for row, series in enumerate(daily_by_candidate.values()):
        values = series.reindex(calendar, fill_value=0.0).to_numpy(float)
        for column, positions in enumerate(groups):
            block = values[positions]
            std = np.std(block, ddof=1) if len(block) > 1 else 0.0
            matrix[row, column] = float(np.mean(block) / std) if std > 0.0 else float(np.mean(block))
    return matrix


def run_outer_research(
    bars: pd.DataFrame,
    candidates: list[CandidateSpec],
    evaluator: FoldEvaluator,
    output_dir: str  Path,
    historical_trials: int,
    cost_model: AxiCostModel  None = None,
    policy: dict  None = None,
    purge_bars: int = 500,
) -> dict:
    """Evaluate preregistered candidates without allowing candidate code to compute its own gates."""
    if not candidates:
        raise ValueError("at least one preregistered candidate is required")
    ids = [candidate.candidate_id for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate_id values must be unique")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("canonical bars require a unique monotonic index")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    costs = (cost_model or AxiCostModel()).scenarios()
    folds = make_rolling_outer_folds(bars.index, purge_bars=purge_bars, min_folds=6)
    pd.DataFrame([fold.record() for fold in folds]).to_csv(output / "outer_folds.csv", index=False)
    total_trials = int(historical_trials) + len(candidates)
    raw: dict[str, dict] = {}
    daily_by_candidate: dict[str, pd.Series] = {}
    for candidate in candidates:
        candidate_dir = output / candidate.candidate_id
        candidate_dir.mkdir(parents=True, exist_ok=True)
        fold_metrics = []
        base_trades = []
        fold_diagnostics = []
        stress_pf: dict[str, list[float]] = {"adverse": [], "crisis": []}
        for fold in folds:
            train = bars.iloc[fold.train_indices].copy()
            test = bars.iloc[fold.test_indices].copy()
            base_run = evaluator(train, test, candidate, costs["base"], fold)
            trades = _validate_fold_trades(base_run.trades, fold)
            trades["fold_id"] = fold.fold_id
            trades.to_csv(candidate_dir / f"fold_{fold.fold_id}_trades.csv", index=False)
            metrics = performance_summary(trades, trials=total_trials, start=fold.test_start, end=fold.test_end)
            metrics["fold_id"] = fold.fold_id
            fold_metrics.append(metrics)
            fold_diagnostics.append({"fold_id": fold.fold_id, **base_run.diagnostics})
            base_trades.append(trades)
            for scenario_name in ("adverse", "crisis"):
                stress_run = evaluator(train, test, candidate, costs[scenario_name], fold)
                stress_trades = _validate_fold_trades(stress_run.trades, fold)
                stress_metrics = performance_summary(stress_trades, trials=total_trials, start=fold.test_start, end=fold.test_end)
                stress_pf[scenario_name].append(float(stress_metrics["profit_factor"]))
        combined = pd.concat(base_trades, ignore_index=True) if base_trades else pd.DataFrame(columns=["entry_time", "exit_time", "pnl"])
        combined.to_csv(candidate_dir / "outer_oos_trades.csv", index=False)
        summary = performance_summary(combined, trials=total_trials, start=folds[0].test_start, end=folds[-1].test_end)
        daily = daily_pnl_from_trades(combined, start=folds[0].test_start, end=folds[-1].test_end)
        daily.to_frame().to_csv(candidate_dir / "outer_oos_daily_pnl.csv")
        daily_by_candidate[candidate.candidate_id] = daily
        bootstrap = block_bootstrap(daily.to_numpy(float), samples=10_000, block_size=5, seed=50001)
        raw[candidate.candidate_id] = {
            "candidate": candidate,
            "metrics": summary,
            "fold_metrics": fold_metrics,
            "diagnostics": fold_diagnostics,
            "robustness": {
                **bootstrap,
                "adverse_cost_pf": float(np.median(stress_pf["adverse"])),
                "crisis_cost_pf": float(np.median(stress_pf["crisis"])),
            },
        }
        pd.DataFrame(fold_metrics).to_csv(candidate_dir / "fold_metrics.csv", index=False)
        (candidate_dir / "diagnostics.json").write_text(json.dumps(fold_diagnostics, indent=2, default=_json_default), encoding="utf-8")

    pbo = probability_backtest_overfitting(_pbo_matrix(daily_by_candidate, blocks=12)) if len(candidates) >= 2 else {"pbo": 1.0, "partitions": 0, "logit_median": 0.0}
    baseline = next((candidate for candidate in candidates if candidate.is_baseline), None)
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    decisions = []
    for candidate_id, item in raw.items():
        candidate = item["candidate"]
        neighbor_ids = [neighbor for neighbor in candidate.neighbor_ids if neighbor in raw]
        item["robustness"]["neighbor_positive_fraction"] = (
            float(np.mean([raw[neighbor]["metrics"]["profit_factor"] > 1.0 for neighbor in neighbor_ids]))
            if neighbor_ids else 0.0
        )
        item["robustness"].update(pbo)
        if baseline is not None and not candidate.is_baseline:
            paired = paired_block_bootstrap(
                daily_by_candidate[candidate_id].to_numpy(float),
                daily_by_candidate[baseline.candidate_id].to_numpy(float),
                samples=10_000,
                block_size=5,
                seed=50001,
            )
            item["robustness"].update(paired)
        gate = evaluate_gates(item["metrics"], item["robustness"], item["fold_metrics"], stage="research", policy=policy or load_policy())
        approved = bool(gate.approved and not candidate.is_baseline)
        decisions.append({
            "candidate_id": candidate_id,
            "approved_research": approved,
            "is_baseline": candidate.is_baseline,
            "complexity": candidate.complexity,
            **item["metrics"],
            "median_fold_pf": float(np.median([fold["profit_factor"] for fold in item["fold_metrics"]])),
            "minimum_fold_pf": float(min(fold["profit_factor"] for fold in item["fold_metrics"])),
            "pbo": item["robustness"]["pbo"],
            "bootstrap_pf_p05": item["robustness"]["pf_p05"],
            "adverse_cost_pf": item["robustness"]["adverse_cost_pf"],
            "crisis_cost_pf": item["robustness"]["crisis_cost_pf"],
        })
        serializable = {
            "candidate": asdict(candidate),
            "metrics": item["metrics"],
            "fold_metrics": item["fold_metrics"],
            "diagnostics": item["diagnostics"],
            "robustness": item["robustness"],
            "gate": {"stage": gate.stage, "approved": approved, "checks": list(gate.checks)},
        }
        (output / candidate_id / "evaluation.json").write_text(json.dumps(serializable, indent=2, default=_json_default), encoding="utf-8")
    ranking = pd.DataFrame(decisions).sort_values(
        ["approved_research", "median_fold_pf", "profit_factor", "complexity"],
        ascending=[False, False, False, True],
    )
    ranking.to_csv(output / "candidate_ranking.csv", index=False)
    champions = ranking.loc[ranking["approved_research"]]
    result = {
        "status": "CANDIDATE_APPROVED" if not champions.empty else "NO_CANDIDATE_PASSED",
        "champion": str(champions.iloc[0]["candidate_id"]) if not champions.empty else None,
        "total_trials": total_trials,
        "outer_folds": len(folds),
        "pbo": pbo,
    }
    (output / "research_decision.json").write_text(json.dumps(result, indent=2, default=_json_default), encoding="utf-8")
    return result
