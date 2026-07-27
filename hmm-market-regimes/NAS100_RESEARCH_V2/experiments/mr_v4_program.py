"""Execute the frozen MR V4 trend-pullback falsification program."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.governance.integrity import canonical_sha256, sha256_file
from NAS100_RESEARCH_V2.mean_reversion_v2.config import CostConfig
from NAS100_RESEARCH_V2.mean_reversion_v4 import (
    CANDIDATE_ID, MAGIC, MRV4Config, apply_shock_thresholds, build_event_study,
    build_mr_v4_features, calibrate_session_thresholds, generate_mr_v4_signals,
    run_mr_v4_backtest, summarize_event_study,
)
from NAS100_RESEARCH_V2.validation.metrics import block_bootstrap, daily_pnl_from_trades, performance_summary
from NAS100_RESEARCH_V2.validation.splits import make_rolling_outer_folds


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "NAS100_RESEARCH_V2" / "data_tools" / "combined_development" / "canonical_data_manifest.json"
DEFAULT_OUTPUT = ROOT / "NAS100_RESEARCH_V2" / "experiments" / "results" / "mean_reversion_v4"
PREREG = ROOT / "NAS100_RESEARCH_V2" / "governance" / "config" / "mr_v4_preregistration_20260714.json"


def _load_bars(manifest_path: Path) -> tuple[dict, pd.DataFrame]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    body = dict(manifest)
    supplied = body.pop("manifest_sha256", None)
    if supplied != canonical_sha256(body):
        raise ValueError("canonical data manifest hash mismatch")
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if supplied != prereg["canonical_data_manifest_sha256"]:
        raise ValueError("MR V4 preregistration is not bound to this dataset")
    path = manifest_path.parent / manifest["artifact_files"]["canonical_bars"]["path"]
    if sha256_file(path) != manifest["artifact_files"]["canonical_bars"]["sha256"]:
        raise ValueError("canonical bar hash mismatch")
    bars = pd.read_parquet(path)
    if not isinstance(bars.index, pd.DatetimeIndex):
        column = next((c for c in ("time", "timestamp", "datetime") if c in bars), None)
        if column is None:
            raise ValueError("canonical bars have no time index")
        bars.index = pd.to_datetime(bars.pop(column), utc=True)
    if bars.index.tz is None:
        raise ValueError("canonical bars must be explicitly UTC")
    bars.index = bars.index.tz_convert("UTC")
    bars.columns = [str(c).lower() for c in bars.columns]
    return manifest, bars


def _cost_scenarios(base: CostConfig) -> dict[str, CostConfig]:
    return {
        "base": base,
        "adverse": replace(base, spread_price=max(3.5, base.spread_price), slippage_price_per_side=base.slippage_price_per_side * 1.5),
        "crisis": replace(base, spread_price=max(3.5, base.spread_price) * 1.5, slippage_price_per_side=base.slippage_price_per_side * 2.0, commission_per_lot_per_side=base.commission_per_lot_per_side * 1.5),
    }


def _trade_frame(frame: pd.DataFrame, fold_id: int) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["entry_time", "exit_time", "pnl", "fold_id", "candidate_id"])
    result = frame.copy()
    result["pnl"] = result["net_pnl"]
    result["fold_id"] = fold_id
    result["candidate_id"] = CANDIDATE_ID
    return result


def _apply_scenario_spread(signals: pd.DataFrame, scenario: CostConfig) -> pd.DataFrame:
    """Enforce each scenario's floor without discarding worse observed/profile spreads."""

    out = signals.copy()
    if "spread_price" in out:
        observed = pd.to_numeric(out["spread_price"], errors="coerce").fillna(scenario.spread_price)
        out["spread_price"] = np.maximum(observed.to_numpy(float), scenario.spread_price)
    else:
        out["spread_price"] = scenario.spread_price
    return out


def _prefix_audit(bars: pd.DataFrame, full: pd.DataFrame) -> None:
    end = max(500, int(len(bars) * 0.60))
    prefix = build_mr_v4_features(bars.iloc[:end])
    columns = [
        "v4_shock_z", "v4_atr", "v4_range_atr", "v4_h18_medium_score",
        "v4_h18_ultra_score", "v4_trend_aligned",
    ]
    for column in columns:
        left, right = full.loc[prefix.index, column], prefix[column]
        if pd.api.types.is_bool_dtype(left):
            if not left.equals(right):
                raise RuntimeError(f"LEAKAGE_DETECTED in {column}")
        elif not np.allclose(left.to_numpy(float), right.to_numpy(float), rtol=0.0, atol=1e-12, equal_nan=True):
            raise RuntimeError(f"LEAKAGE_DETECTED in {column}")


def run(manifest_path: Path = DEFAULT_MANIFEST, output: Path = DEFAULT_OUTPUT) -> dict:
    manifest, bars = _load_bars(manifest_path)
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    cfg = MRV4Config()
    output.mkdir(parents=True, exist_ok=True)
    features = build_mr_v4_features(bars, cfg)
    _prefix_audit(bars, features)
    folds = make_rolling_outer_folds(bars.index, purge_bars=500, min_folds=6)
    pd.DataFrame([fold.record() for fold in folds]).to_csv(output / "outer_folds.csv", index=False)
    scenarios = _cost_scenarios(cfg.costs)
    parts: dict[str, list[pd.DataFrame]] = {name: [] for name in scenarios}
    fold_rows: list[dict] = []
    count_rows: list[dict] = []
    calibration_rows: list[dict] = []
    event_parts: list[pd.DataFrame] = []
    for fold in folds:
        train = features.iloc[fold.train_indices]
        thresholds = calibrate_session_thresholds(train, cfg)
        for session, threshold in thresholds.items():
            calibration_rows.append({"fold_id": fold.fold_id, "session": session, "shock_z_threshold": threshold})
        test = apply_shock_thresholds(features.iloc[fold.test_indices].copy(), thresholds, cfg)
        event_parts.append(build_event_study(test, fold.fold_id, cfg))
        signals = generate_mr_v4_signals(test, cfg)
        count_rows.append({
            "fold_id": fold.fold_id,
            "trend_aligned_bars": int(test["v4_trend_aligned"].sum()),
            "downside_shocks": int(test["v4_downside_shock"].sum()),
            "confirmed_signals": int((signals["entry_signal"] == 1).sum()),
            "non_long_signals": int((signals["entry_signal"] < 0).sum()),
        })
        base_trades = pd.DataFrame()
        for name, costs in scenarios.items():
            scenario_signals = _apply_scenario_spread(signals, costs)
            result = run_mr_v4_backtest(scenario_signals, replace(cfg, costs=costs))
            normalized = _trade_frame(result.trades, fold.fold_id)
            parts[name].append(normalized)
            if name == "base":
                base_trades = normalized
        fold_rows.append({"fold_id": fold.fold_id, **performance_summary(base_trades, trials=143, start=fold.test_start, end=fold.test_end)})

    combined = {
        name: pd.concat([frame for frame in frames if not frame.empty], ignore_index=True)
        if any(not frame.empty for frame in frames) else pd.DataFrame()
        for name, frames in parts.items()
    }
    for name, frame in combined.items():
        frame.to_csv(output / f"mr_v4_{name}_outer_oos_trades.csv", index=False)
    events = pd.concat([frame for frame in event_parts if not frame.empty], ignore_index=True) if any(not x.empty for x in event_parts) else pd.DataFrame()
    events.to_csv(output / "event_study_outer_oos.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(output / "fold_metrics.csv", index=False)
    pd.DataFrame(count_rows).to_csv(output / "fold_signal_counts.csv", index=False)
    pd.DataFrame(calibration_rows).to_csv(output / "train_only_session_thresholds.csv", index=False)
    start, end = folds[0].test_start, folds[-1].test_end
    metrics = performance_summary(combined["base"], trials=143, start=start, end=end)
    adverse = performance_summary(combined["adverse"], trials=143, start=start, end=end)
    crisis = performance_summary(combined["crisis"], trials=143, start=start, end=end)
    daily = daily_pnl_from_trades(combined["base"], start=start, end=end)
    bootstrap = block_bootstrap(daily.to_numpy(float), samples=10_000, block_size=5, seed=20260714)
    event_summary = summarize_event_study(events, cfg.event_horizons_bars)
    fold_frame = pd.DataFrame(fold_rows)
    positive_folds = int((fold_frame["profit_factor"] > 1.0).sum())
    minimum_fold_trades = int(fold_frame["closed_trades"].min())
    event_gate = event_summary[str(prereg["gate"]["event_study_required_horizon_bars"])]
    gate = prereg["gate"]
    checks = [
        {"name": "minimum_trades", "value": metrics["closed_trades"], "required": gate["minimum_trades"], "passed": metrics["closed_trades"] >= gate["minimum_trades"]},
        {"name": "profit_factor", "value": metrics["profit_factor"], "required": gate["minimum_profit_factor"], "passed": metrics["profit_factor"] >= gate["minimum_profit_factor"]},
        {"name": "positive_outer_folds", "value": positive_folds, "required": gate["minimum_positive_outer_folds"], "passed": positive_folds >= gate["minimum_positive_outer_folds"]},
        {"name": "minimum_fold_trades", "value": minimum_fold_trades, "required": gate["minimum_fold_trades"], "passed": minimum_fold_trades >= gate["minimum_fold_trades"]},
        {"name": "dsr", "value": metrics["dsr_probability"], "required": gate["minimum_dsr"], "passed": metrics["dsr_probability"] >= gate["minimum_dsr"]},
        {"name": "drawdown", "value": abs(metrics["max_drawdown_pct"]), "required_max": gate["maximum_drawdown_pct"], "passed": abs(metrics["max_drawdown_pct"]) <= gate["maximum_drawdown_pct"]},
        {"name": "bootstrap_pf_p05", "value": bootstrap["pf_p05"], "required": gate["minimum_bootstrap_pf_p05"], "passed": bootstrap["pf_p05"] > gate["minimum_bootstrap_pf_p05"]},
        {"name": "bootstrap_probability_positive", "value": bootstrap["probability_positive"], "required": gate["minimum_bootstrap_probability_positive"], "passed": bootstrap["probability_positive"] >= gate["minimum_bootstrap_probability_positive"]},
        {"name": "adverse_cost_pf", "value": adverse["profit_factor"], "required": gate["minimum_adverse_cost_pf"], "passed": adverse["profit_factor"] >= gate["minimum_adverse_cost_pf"]},
        {"name": "crisis_cost_pf", "value": crisis["profit_factor"], "required": gate["minimum_crisis_cost_pf"], "passed": crisis["profit_factor"] >= gate["minimum_crisis_cost_pf"]},
        {"name": "event_study_events", "value": event_gate["events"], "required": gate["event_study_minimum_events"], "passed": event_gate["events"] >= gate["event_study_minimum_events"]},
        {"name": "event_study_probability_positive", "value": event_gate["bootstrap_probability_positive"], "required": gate["event_study_minimum_probability_positive"], "passed": event_gate["bootstrap_probability_positive"] >= gate["event_study_minimum_probability_positive"]},
        {"name": "event_study_positive_folds", "value": event_gate["positive_folds"], "required": gate["event_study_minimum_positive_folds"], "passed": event_gate["positive_folds"] >= gate["event_study_minimum_positive_folds"]},
    ]
    approved = bool(all(item["passed"] for item in checks))
    document = {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "magic_reserved": MAGIC,
        "status": "APPROVED_FOR_MT5_DEMO_PORT" if approved else "REJECTED_RESEARCH_ONLY_NO_EA",
        "approved": approved,
        "live_authorized": False,
        "release_evidence_eligible": bool(manifest.get("release_evidence_eligible", False)),
        "data_manifest_sha256": manifest["manifest_sha256"],
        "preregistration_sha256": sha256_file(PREREG),
        "config": asdict(cfg),
        "outer_folds": len(folds),
        "historical_trials_in_dsr": 143,
        "metrics": metrics,
        "adverse_metrics": adverse,
        "crisis_metrics": crisis,
        "bootstrap": bootstrap,
        "event_study": event_summary,
        "positive_outer_folds": positive_folds,
        "minimum_fold_trades": minimum_fold_trades,
        "checks": checks,
        "pbo": "NOT_APPLICABLE_SINGLE_PREREGISTERED_CANDIDATE",
        "prefix_invariance": "PASSED",
        "survivorship_bias": "NOT_APPLICABLE_SINGLE_CONTINUOUS_INSTRUMENT_NO_CONSTITUENT_SELECTION",
        "warning": "development dataset was consumed by prior research; approval can only authorize demo observation, never live deployment",
    }
    (output / "mr_v4_decision.json").write_text(json.dumps(document, indent=2, default=str) + "\n", encoding="utf-8")
    return document


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.manifest, args.output), indent=2, default=str))


if __name__ == "__main__":
    _main()
