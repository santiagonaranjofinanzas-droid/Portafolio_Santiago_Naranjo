"""Execute the frozen one-shot MR V3 falsification and coexistence audit."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.governance.integrity import canonical_sha256, sha256_file
from NAS100_RESEARCH_V2.mean_reversion_v2.config import CostConfig
from NAS100_RESEARCH_V2.mean_reversion_v3 import (
    CANDIDATE_ID,
    MAGIC,
    MRV3Config,
    build_mr_v3_features,
    generate_mr_v3_signals,
    run_mr_v3_backtest,
)
from NAS100_RESEARCH_V2.validation.metrics import (
    block_bootstrap,
    daily_pnl_from_trades,
    performance_summary,
)
from NAS100_RESEARCH_V2.validation.splits import make_rolling_outer_folds


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = (
    ROOT / "NAS100_RESEARCH_V2" / "data_tools" / "combined_development"
    / "canonical_data_manifest.json"
)
DEFAULT_OUTPUT = ROOT / "NAS100_RESEARCH_V2" / "experiments" / "results" / "mean_reversion_v3"
PREREG = ROOT / "NAS100_RESEARCH_V2" / "governance" / "config" / "mr_v3_preregistration_20260714.json"


def _load_bars(manifest_path: Path) -> tuple[dict, pd.DataFrame]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    body = dict(manifest)
    supplied = body.pop("manifest_sha256", None)
    if supplied != canonical_sha256(body):
        raise ValueError("canonical data manifest hash mismatch")
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if supplied != prereg["canonical_data_manifest_sha256"]:
        raise ValueError("MR V3 preregistration is not bound to this dataset")
    path = manifest_path.parent / manifest["artifact_files"]["canonical_bars"]["path"]
    if sha256_file(path) != manifest["artifact_files"]["canonical_bars"]["sha256"]:
        raise ValueError("canonical bar hash mismatch")
    bars = pd.read_parquet(path)
    if not isinstance(bars.index, pd.DatetimeIndex):
        time_column = next((c for c in ("time", "timestamp", "datetime") if c in bars), None)
        if time_column is None:
            raise ValueError("canonical bars have no DatetimeIndex/time column")
        bars.index = pd.to_datetime(bars.pop(time_column), utc=True)
    if bars.index.tz is None:
        raise ValueError("canonical bars must be explicitly UTC")
    bars.index = bars.index.tz_convert("UTC")
    bars.columns = [str(c).lower() for c in bars.columns]
    return manifest, bars


def _cost_scenarios(base: CostConfig) -> dict[str, CostConfig]:
    return {
        "base": base,
        "adverse": replace(
            base,
            spread_price=max(3.5, base.spread_price),
            slippage_price_per_side=base.slippage_price_per_side * 1.5,
        ),
        "crisis": replace(
            base,
            spread_price=max(3.5, base.spread_price) * 1.5,
            slippage_price_per_side=base.slippage_price_per_side * 2.0,
            commission_per_lot_per_side=base.commission_per_lot_per_side * 1.5,
        ),
    }


def _trade_frame(frame: pd.DataFrame, fold_id: int) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["entry_time", "exit_time", "pnl", "fold_id"])
    result = frame.copy()
    result["pnl"] = result["net_pnl"]
    result["fold_id"] = fold_id
    result["candidate_id"] = CANDIDATE_ID
    return result


def _prefix_audit(bars: pd.DataFrame, full: pd.DataFrame) -> None:
    end = max(500, int(len(bars) * 0.60))
    prefix = build_mr_v3_features(bars.iloc[:end])
    columns = [
        "mr_shock_z", "mr_atr", "mr_range_atr", "mr_h18_medium_score",
        "mr_h18_ultra_score", "mr_trend_block", "mr_shock",
    ]
    left = full.loc[prefix.index, columns]
    right = prefix.loc[:, columns]
    for column in columns:
        if pd.api.types.is_bool_dtype(left[column]):
            if not left[column].equals(right[column]):
                raise RuntimeError(f"LEAKAGE_DETECTED in {column}")
        elif not np.allclose(
            left[column].to_numpy(float), right[column].to_numpy(float),
            rtol=0.0, atol=1e-12, equal_nan=True,
        ):
            raise RuntimeError(f"LEAKAGE_DETECTED in {column}")


def _coexistence_metrics(mr: pd.DataFrame, start, end) -> dict:
    result: dict[str, dict] = {}
    h18_root = ROOT / "NAS100_RESEARCH_V2" / "experiments" / "results" / "trend_h18"
    names = {
        "TREND10_6001": "candidate_TREND_10_MEDIUM_LONG_outer_oos_trades.csv",
        "TREND11_6002": "candidate_TREND_11_ULTRASLOW_LONG_outer_oos_trades.csv",
    }
    for label, filename in names.items():
        path = h18_root / filename
        if not path.exists():
            continue
        trend = pd.read_csv(path, parse_dates=["entry_time", "exit_time"])
        trend = trend.rename(columns={"pnl": "_old_pnl"}) if "pnl" in trend else trend
        if "net_pnl" in trend:
            trend["pnl"] = pd.to_numeric(trend["net_pnl"])
        elif "_old_pnl" in trend:
            trend["pnl"] = pd.to_numeric(trend["_old_pnl"])
        combined = pd.concat(
            [trend.loc[:, ["entry_time", "exit_time", "pnl"]], mr.loc[:, ["entry_time", "exit_time", "pnl"]]],
            ignore_index=True,
        ).sort_values("exit_time")
        result[label] = {
            "trend_only": performance_summary(trend, trials=142, start=start, end=end),
            "trend_plus_mr_independent_ledger": performance_summary(
                combined, trials=142, start=start, end=end
            ),
            "warning": "independent-ledger overlay; not shared-balance portfolio sizing",
        }
    return result


def run(manifest_path: Path = DEFAULT_MANIFEST, output: Path = DEFAULT_OUTPUT) -> dict:
    manifest, bars = _load_bars(manifest_path)
    cfg = MRV3Config()
    output.mkdir(parents=True, exist_ok=True)
    features = build_mr_v3_features(bars, cfg)
    _prefix_audit(bars, features)
    folds = make_rolling_outer_folds(bars.index, purge_bars=500, min_folds=6)
    pd.DataFrame([fold.record() for fold in folds]).to_csv(output / "outer_folds.csv", index=False)
    costs = _cost_scenarios(cfg.costs)
    trades_by_scenario: dict[str, list[pd.DataFrame]] = {name: [] for name in costs}
    fold_rows: list[dict] = []
    signal_rows: list[dict] = []
    for fold in folds:
        test_features = features.iloc[fold.test_indices].copy()
        signals = generate_mr_v3_signals(test_features, cfg)
        signal_rows.append(
            {
                "fold_id": fold.fold_id,
                "shocks": int(signals["mr_shock"].sum()),
                "confirmed_signals": int((signals["entry_signal"] != 0).sum()),
                "signals_while_trend_blocked": int(
                    ((signals["entry_signal"] != 0) & signals["mr_trend_block"]).sum()
                ),
            }
        )
        base_trades = None
        for name, scenario_cost in costs.items():
            scenario_cfg = replace(cfg, costs=scenario_cost)
            result = run_mr_v3_backtest(signals, scenario_cfg)
            normalized = _trade_frame(result.trades, fold.fold_id)
            trades_by_scenario[name].append(normalized)
            if name == "base":
                base_trades = normalized
        summary = performance_summary(
            base_trades, trials=142, start=fold.test_start, end=fold.test_end
        )
        fold_rows.append({"fold_id": fold.fold_id, **summary})

    combined = {}
    for name, parts in trades_by_scenario.items():
        nonempty = [frame for frame in parts if not frame.empty]
        combined[name] = pd.concat(nonempty, ignore_index=True) if nonempty else pd.DataFrame()
    for name, frame in combined.items():
        frame.to_csv(output / f"mr_v3_{name}_outer_oos_trades.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(output / "fold_metrics.csv", index=False)
    pd.DataFrame(signal_rows).to_csv(output / "fold_signal_counts.csv", index=False)
    start, end = folds[0].test_start, folds[-1].test_end
    metrics = performance_summary(combined["base"], trials=142, start=start, end=end)
    adverse = performance_summary(combined["adverse"], trials=142, start=start, end=end)
    crisis = performance_summary(combined["crisis"], trials=142, start=start, end=end)
    daily = daily_pnl_from_trades(combined["base"], start=start, end=end)
    bootstrap = block_bootstrap(daily.to_numpy(float), samples=10_000, block_size=5, seed=20260714)
    fold_frame = pd.DataFrame(fold_rows)
    positive_folds = int((fold_frame["profit_factor"] > 1.0).sum())
    minimum_fold_trades = int(fold_frame["closed_trades"].min())
    checks = [
        {"name": "minimum_trades", "value": metrics["closed_trades"], "required": 200, "passed": metrics["closed_trades"] >= 200},
        {"name": "profit_factor", "value": metrics["profit_factor"], "required": 1.2, "passed": metrics["profit_factor"] >= 1.2},
        {"name": "positive_outer_folds", "value": positive_folds, "required": 5, "passed": positive_folds >= 5},
        {"name": "minimum_fold_trades", "value": minimum_fold_trades, "required": 20, "passed": minimum_fold_trades >= 20},
        {"name": "dsr", "value": metrics["dsr_probability"], "required": 0.95, "passed": metrics["dsr_probability"] >= 0.95},
        {"name": "drawdown", "value": abs(metrics["max_drawdown_pct"]), "required_max": 15.0, "passed": abs(metrics["max_drawdown_pct"]) <= 15.0},
        {"name": "bootstrap_pf_p05", "value": bootstrap["pf_p05"], "required": 1.0, "passed": bootstrap["pf_p05"] > 1.0},
        {"name": "bootstrap_probability_positive", "value": bootstrap["probability_positive"], "required": 0.95, "passed": bootstrap["probability_positive"] >= 0.95},
        {"name": "adverse_cost_pf", "value": adverse["profit_factor"], "required": 1.05, "passed": adverse["profit_factor"] >= 1.05},
        {"name": "crisis_cost_pf", "value": crisis["profit_factor"], "required": 1.0, "passed": crisis["profit_factor"] >= 1.0},
    ]
    approved = bool(all(item["passed"] for item in checks))
    document = {
        "schema_version": 1,
        "candidate_id": CANDIDATE_ID,
        "magic_reserved": MAGIC,
        "status": "APPROVED_FOR_MT5_DEMO_PORT" if approved else "REJECTED_RESEARCH_ONLY_NO_EA",
        "approved": approved,
        "live_authorized": False,
        "data_manifest_sha256": manifest["manifest_sha256"],
        "preregistration_sha256": sha256_file(PREREG),
        "config": asdict(cfg),
        "outer_folds": len(folds),
        "historical_trials_in_dsr": 142,
        "metrics": metrics,
        "adverse_metrics": adverse,
        "crisis_metrics": crisis,
        "bootstrap": bootstrap,
        "positive_outer_folds": positive_folds,
        "minimum_fold_trades": minimum_fold_trades,
        "checks": checks,
        "pbo": "NOT_APPLICABLE_SINGLE_PREREGISTERED_CANDIDATE",
        "prefix_invariance": "PASSED",
        "coexistence": _coexistence_metrics(combined["base"], start, end),
    }
    (output / "mr_v3_decision.json").write_text(
        json.dumps(document, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return document


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    result = run(args.manifest, args.output)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    _main()
