"""Nested rolling research with fixed-model inner CPCV and untouched outer OOS.

The HMM/local-trend specification is preregistered and is never selected by
PnL.  Inner CPCV (N=8, k=2) ranks only signal/execution candidates using their
filtered training paths.  The selected specification is then evaluated once
on each causal six-month outer fold.  All registered candidates are also
recorded outer-OOS solely for PBO/multiple-testing diagnostics.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from typing import Any, Protocol

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
    profit_factor,
)
from .runner import CandidateSpec, FoldRun, _validate_fold_trades
from .splits import OuterFold, make_rolling_outer_folds


class NestedEvaluator(Protocol):
    def __call__(self, train: pd.DataFrame, test: pd.DataFrame, candidate: CandidateSpec,
                 costs: CostScenario, fold: OuterFold) -> FoldRun: ...
    def training_run(self, bars: pd.DataFrame, candidate: CandidateSpec,
                     costs: CostScenario) -> FoldRun: ...


def _json_default(value: Any):
    if isinstance(value, (np.integer, np.floating)):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (pd.Timestamp, Path)):
        return str(value)
    raise TypeError(type(value).__name__)


def _group_trade_values(trades: pd.DataFrame, index: pd.DatetimeIndex, groups: int = 8) -> tuple[list[np.ndarray], list[int]]:
    positions = np.array_split(np.arange(len(index)), groups)
    if trades.empty:
        return [np.array([], dtype=float) for _ in positions], [0] * groups
    exits = pd.DatetimeIndex(pd.to_datetime(trades["exit_time"], utc=True))
    values = trades["pnl"].to_numpy(float)
    output: list[np.ndarray] = []
    counts: list[int] = []
    for block in positions:
        start, end = index[int(block[0])], index[int(block[-1])]
        selected = values[(exits >= start) & (exits <= end)]
        output.append(selected)
        counts.append(int(len(selected)))
    return output, counts


def _inner_cpcv_rank(
    bars: pd.DataFrame,
    candidates: list[CandidateSpec],
    evaluator: NestedEvaluator,
    costs: CostScenario,
) -> tuple[pd.DataFrame, dict[str, FoldRun]]:
    splits = list(combinations(range(8), 2))
    if len(splits) != 28:
        raise AssertionError("CPCV N=8,k=2 must produce 28 splits")
    rows: list[dict[str, Any]] = []
    runs: dict[str, FoldRun] = {}
    for candidate in candidates:
        try:
            run = evaluator.training_run(bars, candidate, costs)
            runs[candidate.candidate_id] = run
            block_values, block_counts = _group_trade_values(run.trades, bars.index, 8)
            split_pf: list[float] = []
            split_trades: list[int] = []
            for selected in splits:
                values = np.concatenate([block_values[item] for item in selected])
                split_pf.append(min(profit_factor(values), 10.0))
                split_trades.append(int(len(values)))
            eligible = [pf for pf, count in zip(split_pf, split_trades) if count >= 10]
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "cpcv_splits": 28,
                    "eligible_splits": len(eligible),
                    "median_test_pf": float(np.median(eligible)) if eligible else 0.0,
                    "positive_split_fraction": float(np.mean(np.asarray(eligible) > 1.0)) if eligible else 0.0,
                    "minimum_split_trades": min(split_trades),
                    "training_trades": int(len(run.trades)),
                    "complexity": candidate.complexity,
                    "error": "",
                }
            )
        except Exception as exc:
            rows.append(
                {
                    "candidate_id": candidate.candidate_id,
                    "cpcv_splits": 28,
                    "eligible_splits": 0,
                    "median_test_pf": 0.0,
                    "positive_split_fraction": 0.0,
                    "minimum_split_trades": 0,
                    "training_trades": 0,
                    "complexity": candidate.complexity,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    ranking = pd.DataFrame(rows).sort_values(
        ["eligible_splits", "positive_split_fraction", "median_test_pf", "complexity", "candidate_id"],
        ascending=[False, False, False, True, True],
    )
    return ranking.reset_index(drop=True), runs


def _pbo_matrix(daily: dict[str, pd.Series], blocks: int = 12) -> np.ndarray:
    calendar = pd.DatetimeIndex(sorted(set().union(*(series.index for series in daily.values()))))
    if len(calendar) < blocks:
        raise ValueError("insufficient calendar for PBO")
    partitions = np.array_split(np.arange(len(calendar)), blocks)
    matrix = np.zeros((len(daily), blocks), dtype=float)
    for row, series in enumerate(daily.values()):
        values = series.reindex(calendar, fill_value=0.0).to_numpy(float)
        for column, positions in enumerate(partitions):
            block = values[positions]
            std = np.std(block, ddof=1) if len(block) > 1 else 0.0
            matrix[row, column] = np.mean(block) / std if std > 0 else np.mean(block)
    return matrix


def run_nested_research(
    bars: pd.DataFrame,
    candidates: list[CandidateSpec],
    evaluator: NestedEvaluator,
    output_dir: str  Path,
    *,
    historical_trials: int,
    cost_model: AxiCostModel  None = None,
    policy: dict  None = None,
    purge_bars: int = 500,
    bootstrap_samples: int = 10_000,
) -> dict[str, Any]:
    if not candidates or len({item.candidate_id for item in candidates}) != len(candidates):
        raise ValueError("candidates must be non-empty with unique ids")
    if bars.index.tz is None or str(bars.index.tz).upper() != "UTC":
        raise ValueError("nested research requires canonical UTC bars")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("nested research requires unique monotonic bars")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    scenarios = (cost_model or AxiCostModel()).scenarios()
    folds = make_rolling_outer_folds(bars.index, purge_bars=purge_bars, min_folds=6)
    pd.DataFrame([fold.record() for fold in folds]).to_csv(output / "outer_folds.csv", index=False)
    by_id = {item.candidate_id: item for item in candidates}
    baseline = next((item for item in candidates if item.is_baseline), None)
    candidate_fold_trades: dict[str, list[pd.DataFrame]] = {item.candidate_id: [] for item in candidates}
    candidate_fold_metrics: dict[str, list[dict]] = {item.candidate_id: [] for item in candidates}
    nested_base: list[pd.DataFrame] = []
    nested_adverse: list[pd.DataFrame] = []
    nested_crisis: list[pd.DataFrame] = []
    nested_fold_metrics: list[dict] = []
    selections: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    total_trials = int(historical_trials) + len(candidates)

    for fold in folds:
        train = bars.iloc[fold.train_indices].copy()
        test = bars.iloc[fold.test_indices].copy()
        inner, _ = _inner_cpcv_rank(train, candidates, evaluator, scenarios["base"])
        inner.to_csv(output / f"inner_cpcv_fold_{fold.fold_id}.csv", index=False)
        viable = inner.loc[inner["error"] == ""]
        if viable.empty:
            raise RuntimeError(f"all candidates failed inner CPCV in fold {fold.fold_id}")
        selected_id = str(viable.iloc[0]["candidate_id"])
        selected = by_id[selected_id]
        outer_runs: dict[str, FoldRun] = {}
        for candidate in candidates:
            try:
                run = evaluator(train, test, candidate, scenarios["base"], fold)
                trades = _validate_fold_trades(run.trades, fold)
                trades["fold_id"] = fold.fold_id
                trades["candidate_id"] = candidate.candidate_id
                metrics = performance_summary(
                    trades, trials=total_trials, start=fold.test_start, end=fold.test_end
                )
                metrics["fold_id"] = fold.fold_id
                outer_runs[candidate.candidate_id] = FoldRun(trades, run.diagnostics)
            except Exception as exc:
                trades = pd.DataFrame(columns=["entry_time", "exit_time", "pnl", "fold_id", "candidate_id"])
                metrics = performance_summary(
                    trades, trials=total_trials, start=fold.test_start, end=fold.test_end
                )
                metrics.update({"fold_id": fold.fold_id, "error": f"{type(exc).__name__}: {exc}"})
            candidate_fold_trades[candidate.candidate_id].append(trades)
            candidate_fold_metrics[candidate.candidate_id].append(metrics)
        if selected_id not in outer_runs:
            raise RuntimeError(f"inner-selected candidate failed outer fold: {selected_id}/{fold.fold_id}")
        base_run = outer_runs[selected_id]
        adverse_run = evaluator(train, test, selected, scenarios["adverse"], fold)
        crisis_run = evaluator(train, test, selected, scenarios["crisis"], fold)
        adverse_trades = _validate_fold_trades(adverse_run.trades, fold)
        crisis_trades = _validate_fold_trades(crisis_run.trades, fold)
        for frame in (adverse_trades, crisis_trades):
            frame["fold_id"] = fold.fold_id
            frame["candidate_id"] = selected_id
        nested_base.append(base_run.trades)
        nested_adverse.append(adverse_trades)
        nested_crisis.append(crisis_trades)
        fold_metric = performance_summary(
            base_run.trades, trials=total_trials, start=fold.test_start, end=fold.test_end
        )
        fold_metric["fold_id"] = fold.fold_id
        fold_metric["selected_candidate"] = selected_id
        nested_fold_metrics.append(fold_metric)
        selections.append(
            {
                "fold_id": fold.fold_id,
                "selected_candidate": selected_id,
                "inner_median_test_pf": float(viable.iloc[0]["median_test_pf"]),
                "inner_positive_split_fraction": float(viable.iloc[0]["positive_split_fraction"]),
                "inner_cpcv_splits": 28,
            }
        )
        diagnostics.append({"fold_id": fold.fold_id, "candidate_id": selected_id, **base_run.diagnostics})

    start, end = folds[0].test_start, folds[-1].test_end
    candidate_daily: dict[str, pd.Series] = {}
    candidate_metrics: dict[str, dict] = {}
    for candidate in candidates:
        trades = pd.concat(candidate_fold_trades[candidate.candidate_id], ignore_index=True)
        trades.to_csv(output / f"candidate_{candidate.candidate_id}_outer_oos_trades.csv", index=False)
        candidate_daily[candidate.candidate_id] = daily_pnl_from_trades(trades, start=start, end=end)
        candidate_metrics[candidate.candidate_id] = performance_summary(
            trades, trials=total_trials, start=start, end=end
        )
    pbo = probability_backtest_overfitting(_pbo_matrix(candidate_daily, 12)) if len(candidates) >= 2 else {"pbo": 1.0, "partitions": 0, "logit_median": 0.0}
    combined = pd.concat(nested_base, ignore_index=True)
    adverse = pd.concat(nested_adverse, ignore_index=True)
    crisis = pd.concat(nested_crisis, ignore_index=True)
    combined.to_csv(output / "nested_outer_oos_trades.csv", index=False)
    adverse.to_csv(output / "nested_adverse_trades.csv", index=False)
    crisis.to_csv(output / "nested_crisis_trades.csv", index=False)
    pd.DataFrame(selections).to_csv(output / "outer_selections.csv", index=False)
    pd.DataFrame(nested_fold_metrics).to_csv(output / "nested_fold_metrics.csv", index=False)
    (output / "diagnostics.json").write_text(json.dumps(diagnostics, indent=2, default=_json_default), encoding="utf-8")

    metrics = performance_summary(combined, trials=total_trials, start=start, end=end)
    daily = daily_pnl_from_trades(combined, start=start, end=end)
    robustness = block_bootstrap(daily.to_numpy(float), samples=bootstrap_samples, block_size=5, seed=20260710)
    robustness.update(pbo)
    robustness["adverse_cost_pf"] = profit_factor(adverse["pnl"].to_numpy(float)) if not adverse.empty else 0.0
    robustness["crisis_cost_pf"] = profit_factor(crisis["pnl"].to_numpy(float)) if not crisis.empty else 0.0
    selected_ids = [item["selected_candidate"] for item in selections]
    only_baseline = baseline is not None and set(selected_ids) == {baseline.candidate_id}
    robustness["paired_comparison_required"] = not only_baseline
    baseline_daily = (
        candidate_daily[baseline.candidate_id]
        if baseline is not None
        else pd.Series(0.0, index=daily.index)
    )
    robustness.update(
        paired_block_bootstrap(
            daily.to_numpy(float), baseline_daily.reindex(daily.index, fill_value=0.0).to_numpy(float),
            samples=bootstrap_samples, block_size=5, seed=20260710,
        )
    )
    neighbor_checks: list[bool] = []
    for fold_id, selected_id in enumerate(selected_ids):
        selected = by_id[selected_id]
        if selected.is_baseline:
            continue
        for neighbor in selected.neighbor_ids:
            if neighbor in candidate_fold_metrics:
                neighbor_checks.append(candidate_fold_metrics[neighbor][fold_id]["profit_factor"] > 1.0)
    robustness["neighbor_positive_fraction"] = float(np.mean(neighbor_checks)) if neighbor_checks else (1.0 if only_baseline else 0.0)
    policy_doc = policy or load_policy()
    research_gate = evaluate_gates(metrics, robustness, nested_fold_metrics, "research", policy_doc)
    institutional_gate = evaluate_gates(metrics, robustness, nested_fold_metrics, "institutional", policy_doc)
    regime_selected = any(by_id[item].parameters.get("strategy") == "trend_v2" for item in selected_ids)
    regime_retained = bool(
        regime_selected
        and robustness.get("probability_improvement", 0.0) >= 0.95
        and robustness.get("delta_expectancy_p05", -1.0) > 0.0
    )
    result = {
        "status": "BACKTEST_APPROVED_LIVE_LOCKED" if institutional_gate.approved else "REJECTED_LIVE_LOCKED",
        "live_locked": True,
        "outer_folds": len(folds),
        "inner_cpcv_splits_per_fold": 28,
        "total_trials": total_trials,
        "selected_candidates": selected_ids,
        "regime_retained": regime_retained,
        "regime_selected_by_inner_cpcv": regime_selected,
        "metrics": metrics,
        "robustness": robustness,
        "research_gate": {"approved": research_gate.approved, "checks": list(research_gate.checks)},
        "institutional_gate": {"approved": institutional_gate.approved, "checks": list(institutional_gate.checks)},
        "candidate_metrics": candidate_metrics,
        "pbo": pbo,
    }
    (output / "nested_decision.json").write_text(
        json.dumps(result, indent=2, default=_json_default), encoding="utf-8"
    )
    return result
