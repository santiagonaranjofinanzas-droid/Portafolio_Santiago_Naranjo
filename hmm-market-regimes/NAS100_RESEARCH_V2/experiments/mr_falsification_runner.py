"""Outer-walk-forward existence test that must precede every MR grid."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v2 import (
    MeanReversionV2,
    MeanReversionV2Config,
    evaluate_edge_existence,
)
from NAS100_RESEARCH_V2.validation.splits import make_rolling_outer_folds


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def run_mr_falsification(
    bars: pd.DataFrame,
    output_dir: str  Path,
    config: MeanReversionV2Config  None = None,
    *,
    purge_bars: int = 500,
) -> dict[str, Any]:
    cfg = config or MeanReversionV2Config()
    if bars.index.tz is None or str(bars.index.tz).upper() != "UTC":
        raise ValueError("MR falsification requires explicit UTC bars")
    folds = make_rolling_outer_folds(bars.index, purge_bars=purge_bars, min_folds=6)
    filtered_parts: list[pd.DataFrame] = []
    bar_parts: list[pd.DataFrame] = []
    fold_rows: list[dict[str, Any]] = []
    horizon = max(cfg.falsification.horizons)
    for fold in folds:
        train = bars.iloc[fold.train_indices].copy()
        test = bars.iloc[fold.test_indices].copy()
        model = MeanReversionV2(cfg).fit(train)
        filtered = model.filter(test)
        # Events in the last horizon bars of a fold may not borrow prices from
        # the next fold, which was filtered by a different trained state.
        filtered = filtered.copy()
        filtered.loc[filtered.index[-horizon:], "z_residual"] = np.nan
        test = test.copy()
        test["spread_price"] = test.get("axi_spread_profile", cfg.backtest.costs.spread_price)
        filtered_parts.append(filtered)
        bar_parts.append(test)
        estimate = model.model.ar1_
        fold_rows.append(
            {
                "fold_id": fold.fold_id,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "phi": estimate.phi,
                "phi_ci_low": estimate.ci_low,
                "phi_ci_high": estimate.ci_high,
                "half_life": estimate.half_life,
                "phi_gate_passed": estimate.gate_passed,
                "model_summary": model.model.summary(),
            }
        )
    combined_bars = pd.concat(bar_parts).sort_index()
    combined_filtered = pd.concat(filtered_parts).sort_index()
    if not combined_bars.index.equals(combined_filtered.index) or combined_bars.index.has_duplicates:
        raise RuntimeError("outer OOS falsification path is not one-to-one")
    edge = evaluate_edge_existence(
        combined_bars,
        combined_filtered,
        cfg.signal,
        cfg.backtest.costs,
        cfg.falsification,
    )
    phi_passes = sum(bool(item["phi_gate_passed"]) for item in fold_rows)
    minimum_phi_folds = max(6, int(np.ceil(0.80 * len(folds))))
    approved_sides = [
        side for side, decision in edge.side_summary.items()
        if decision["existence_passed"] and phi_passes >= minimum_phi_folds
    ]
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    edge.horizon_table.to_csv(output / "mr_edge_horizons.csv", index=False)
    edge.block_table.to_csv(output / "mr_edge_time_blocks.csv", index=False)
    edge.event_responses.to_parquet(output / "mr_edge_events.parquet", index=False)
    pd.DataFrame([{key: value for key, value in row.items() if key != "model_summary"} for row in fold_rows]).to_csv(
        output / "mr_phi_by_outer_fold.csv", index=False
    )
    summary = {
        "schema_version": 1,
        "purpose": "PREREGISTERED_EDGE_EXISTENCE_BEFORE_GRID",
        "outer_folds": len(folds),
        "purge_bars": purge_bars,
        "response_horizons": list(cfg.falsification.horizons),
        "phi_gate_pass_folds": phi_passes,
        "minimum_phi_gate_folds": minimum_phi_folds,
        "side_summary": edge.side_summary,
        "approved_sides_for_nested": approved_sides,
        "overall_passed": bool(approved_sides),
        "verdict": "PROCEED_TO_NESTED_MR" if approved_sides else "RETIRE_MEAN_REVERSION",
        "fold_diagnostics": fold_rows,
    }
    (output / "mr_falsification_decision.json").write_text(
        json.dumps(_safe(summary), indent=2, sort_keys=True), encoding="utf-8"
    )
    return _safe(summary)
