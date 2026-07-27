"""Edge-existence tests and an auditable MR V2 falsification report."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .config import CostConfig, FalsificationConfig, SignalConfig
from .model import RobustLocalLinearTrend


def _mad(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    if values.size == 0:
        return float("nan")
    center = np.median(values)
    return float(1.4826 * np.median(np.abs(values - center)))


def moving_block_bootstrap_mean(
    values: np.ndarray,
    samples: int,
    rng: np.random.Generator,
    block_length: int  None = None,
    confidence: float = 0.95,
) -> tuple[float, float, float]:
    """Return lower CI, upper CI, and bootstrap P(mean > 0)."""

    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    n = len(values)
    if n < 2:
        return float("nan"), float("nan"), float("nan")
    length = block_length or max(2, int(round(n ** (1.0 / 3.0))))
    length = min(max(1, length), n)
    starts = np.arange(0, n - length + 1)
    blocks_needed = int(np.ceil(n / length))
    means = np.empty(samples, dtype=float)
    for b in range(samples):
        chosen = rng.choice(starts, size=blocks_needed, replace=True)
        draw = np.concatenate([values[start : start + length] for start in chosen])[:n]
        means[b] = float(np.mean(draw))
    alpha = (1.0 - confidence) / 2.0
    return (
        float(np.quantile(means, alpha)),
        float(np.quantile(means, 1.0 - alpha)),
        float(np.mean(means > 0.0)),
    )


@dataclass(frozen=True)
class EdgeExistenceResult:
    horizon_table: pd.DataFrame
    block_table: pd.DataFrame
    event_responses: pd.DataFrame
    side_summary: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "side_summary": self.side_summary,
            "horizon_table": self.horizon_table.to_dict(orient="records"),
            "block_table": self.block_table.to_dict(orient="records"),
        }


def _cost_price(frame: pd.DataFrame, costs: CostConfig) -> np.ndarray:
    spread = np.full(len(frame), costs.spread_price, dtype=float)
    for column in ("spread_price", "spread_median", "spread"):
        if column in frame.columns:
            spread = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            break
    if np.any(~np.isfinite(spread)) or np.any(spread < 0):
        raise ValueError("spread must be finite and non-negative")
    return spread + 2.0 * costs.slippage_price_per_side + costs.commission_round_trip_price


def evaluate_edge_existence(
    bars: pd.DataFrame,
    filtered: pd.DataFrame,
    signal_config: SignalConfig  None = None,
    costs: CostConfig  None = None,
    config: FalsificationConfig  None = None,
) -> EdgeExistenceResult:
    """Map conditional 1/2/4/8/16-bar reversal, separately by side.

    Events are selected only from contemporaneous ``z_residual`` extremes.
    Dependence from overlapping horizons is retained and handled with a moving
    block bootstrap.  Chronological stability requires a monotone net response
    in the pre-registered number of time blocks.
    """

    signal_cfg = signal_config or SignalConfig()
    cost_cfg = costs or CostConfig()
    cfg = config or FalsificationConfig()
    if not bars.index.equals(filtered.index):
        raise ValueError("bars and filtered must have exactly equal indices")
    if "close" not in bars.columns or "z_residual" not in filtered.columns:
        raise ValueError("bars.close and filtered.z_residual are required")
    if len(bars) <= max(cfg.horizons):
        raise ValueError("sample is shorter than the maximum response horizon")

    close = bars["close"].to_numpy(dtype=float)
    z = filtered["z_residual"].to_numpy(dtype=float)
    costs_price = _cost_price(bars, cost_cfg)
    n = len(bars)
    max_horizon = max(cfg.horizons)
    rows: list[dict[str, Any]] = []
    for i in range(n - max_horizon):
        if not np.isfinite(z[i]) or not np.isfinite(close[i]) or close[i] <= 0:
            continue
        if z[i] <= -signal_cfg.extreme_z and "LONG" in signal_cfg.allowed_sides:
            side, direction = "LONG", 1.0
        elif z[i] >= signal_cfg.extreme_z and "SHORT" in signal_cfg.allowed_sides:
            side, direction = "SHORT", -1.0
        else:
            continue
        time_block = min(cfg.chronological_blocks - 1, int(i * cfg.chronological_blocks / n))
        for horizon in cfg.horizons:
            gross_price = direction * (close[i + horizon] - close[i])
            gross_return = gross_price / close[i]
            cost_return = costs_price[i] / close[i]
            rows.append(
                {
                    "event_time": bars.index[i],
                    "event_i": i,
                    "side": side,
                    "time_block": time_block,
                    "horizon": horizon,
                    "z_residual": z[i],
                    "gross_response_price": gross_price,
                    "cost_price": costs_price[i],
                    "net_response_price": gross_price - costs_price[i],
                    "gross_response_return": gross_return,
                    "cost_return": cost_return,
                    "net_response_return": gross_return - cost_return,
                }
            )
    responses = pd.DataFrame(rows)
    response_columns = [
        "event_time",
        "event_i",
        "side",
        "time_block",
        "horizon",
        "z_residual",
        "gross_response_price",
        "cost_price",
        "net_response_price",
        "gross_response_return",
        "cost_return",
        "net_response_return",
    ]
    responses = responses.reindex(columns=response_columns)

    rng = np.random.default_rng(cfg.random_seed)
    horizon_rows: list[dict[str, Any]] = []
    block_rows: list[dict[str, Any]] = []
    side_summary: dict[str, dict[str, Any]] = {}
    for side in ("LONG", "SHORT"):
        side_data = responses[responses["side"] == side]
        for horizon in cfg.horizons:
            data = side_data[side_data["horizon"] == horizon].sort_values("event_i")
            net = data["net_response_return"].to_numpy(dtype=float)
            ci_low, ci_high, p_positive = moving_block_bootstrap_mean(
                net,
                cfg.bootstrap_samples,
                rng,
                cfg.bootstrap_block_length,
                cfg.bootstrap_confidence,
            )
            horizon_rows.append(
                {
                    "side": side,
                    "horizon": horizon,
                    "events": int(len(data)),
                    "mean_gross_price": float(data["gross_response_price"].mean()) if len(data) else np.nan,
                    "mean_cost_price": float(data["cost_price"].mean()) if len(data) else np.nan,
                    "mean_net_price": float(data["net_response_price"].mean()) if len(data) else np.nan,
                    "mean_gross_return": float(data["gross_response_return"].mean()) if len(data) else np.nan,
                    "mean_net_return": float(data["net_response_return"].mean()) if len(data) else np.nan,
                    "median_net_return": float(data["net_response_return"].median()) if len(data) else np.nan,
                    "net_return_mad": _mad(net),
                    "bootstrap_ci_low": ci_low,
                    "bootstrap_ci_high": ci_high,
                    "bootstrap_probability_positive": p_positive,
                }
            )

        monotonic_passes = 0
        eligible_blocks = 0
        for block in range(cfg.chronological_blocks):
            block_data = side_data[side_data["time_block"] == block]
            response_curve: list[float] = []
            event_counts: list[int] = []
            row: dict[str, Any] = {"side": side, "time_block": block}
            for horizon in cfg.horizons:
                data = block_data[block_data["horizon"] == horizon]
                mean_net = float(data["net_response_return"].mean()) if len(data) else np.nan
                response_curve.append(mean_net)
                event_counts.append(len(data))
                row[f"net_h{horizon}"] = mean_net
            enough = bool(event_counts and min(event_counts) >= cfg.min_events_per_time_block)
            monotonic = bool(
                enough
                and np.all(np.isfinite(response_curve))
                and np.all(np.diff(response_curve) >= -cfg.monotonic_tolerance)
                and response_curve[-1] > 0.0
            )
            row["events"] = int(min(event_counts)) if event_counts else 0
            row["eligible_block"] = enough
            row["monotonic_positive"] = monotonic
            block_rows.append(row)
            eligible_blocks += int(enough)
            monotonic_passes += int(monotonic)

        horizon_frame_side = pd.DataFrame(horizon_rows)
        terminal = horizon_frame_side[
            (horizon_frame_side["side"] == side)
            & (horizon_frame_side["horizon"] == max_horizon)
        ]
        if terminal.empty:
            terminal_record: dict[str, Any] = {}
            event_count = 0
        else:
            terminal_record = terminal.iloc[0].to_dict()
            event_count = int(terminal_record["events"])
        gross_cost_gate = bool(
            terminal_record
            and np.isfinite(terminal_record["mean_gross_price"])
            and terminal_record["mean_gross_price"]
            >= cfg.gross_cost_multiple * terminal_record["mean_cost_price"]
        )
        bootstrap_gate = bool(
            terminal_record
            and np.isfinite(terminal_record["bootstrap_ci_low"])
            and terminal_record["bootstrap_ci_low"] > 0.0
        )
        sample_gate = event_count >= cfg.min_events_per_side
        stability_gate = monotonic_passes >= cfg.minimum_monotonic_blocks
        reasons: list[str] = []
        if not sample_gate:
            reasons.append("INSUFFICIENT_EXTREME_EVENTS")
        if eligible_blocks < cfg.minimum_monotonic_blocks:
            reasons.append("INSUFFICIENT_CHRONOLOGICAL_BLOCKS")
        if not stability_gate:
            reasons.append("MONOTONIC_RESPONSE_FAILED")
        if not bootstrap_gate:
            reasons.append("TERMINAL_BOOTSTRAP_CI_NOT_POSITIVE")
        if not gross_cost_gate:
            reasons.append("GROSS_EDGE_BELOW_COST_MULTIPLE")
        side_summary[side] = {
            "events": event_count,
            "eligible_blocks": eligible_blocks,
            "monotonic_positive_blocks": monotonic_passes,
            "minimum_monotonic_blocks": cfg.minimum_monotonic_blocks,
            "terminal_horizon": max_horizon,
            "sample_gate": sample_gate,
            "stability_gate": stability_gate,
            "bootstrap_gate": bootstrap_gate,
            "gross_cost_gate": gross_cost_gate,
            "existence_passed": not reasons,
            "failure_reasons": reasons,
        }

    return EdgeExistenceResult(
        horizon_table=pd.DataFrame(horizon_rows),
        block_table=pd.DataFrame(block_rows),
        event_responses=responses,
        side_summary=side_summary,
    )


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


@dataclass(frozen=True)
class FalsificationReport:
    summary: dict[str, Any]
    horizon_table: pd.DataFrame
    block_table: pd.DataFrame
    event_responses: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        return _json_safe(
            {
                **self.summary,
                "horizon_table": self.horizon_table.to_dict(orient="records"),
                "block_table": self.block_table.to_dict(orient="records"),
            }
        )

    def write(self, directory: str  Path) -> dict[str, Path]:
        path = Path(directory)
        path.mkdir(parents=True, exist_ok=True)
        files = {
            "json": path / "mr_v2_falsification_report.json",
            "horizons": path / "mr_v2_edge_horizons.csv",
            "blocks": path / "mr_v2_edge_time_blocks.csv",
            "events": path / "mr_v2_edge_event_responses.parquet",
        }
        files["json"].write_text(
            json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False),
            encoding="utf-8",
        )
        self.horizon_table.to_csv(files["horizons"], index=False)
        self.block_table.to_csv(files["blocks"], index=False)
        self.event_responses.to_parquet(files["events"], index=False)
        return files


def build_falsification_report(
    model: RobustLocalLinearTrend,
    bars: pd.DataFrame,
    filtered: pd.DataFrame,
    signal_config: SignalConfig  None = None,
    costs: CostConfig  None = None,
    config: FalsificationConfig  None = None,
) -> FalsificationReport:
    edge = evaluate_edge_existence(bars, filtered, signal_config, costs, config)
    model_summary = model.summary()
    phi_gate = bool(model.ar1_.gate_passed)
    approved_sides = [
        side
        for side, result in edge.side_summary.items()
        if phi_gate and result["existence_passed"]
    ]
    side_decisions = {
        side: {
            "approved_for_nested_validation": side in approved_sides,
            "model_phi_gate": phi_gate,
            **result,
        }
        for side, result in edge.side_summary.items()
    }
    summary = {
        "schema_version": 1,
        "purpose": "research_falsification_not_live_release",
        "model": model_summary,
        "side_decisions": side_decisions,
        "approved_sides": approved_sides,
        "overall_passed": bool(approved_sides),
        "verdict": "RESEARCH_GATE_PASS" if approved_sides else "FALSIFIED_OR_INSUFFICIENT",
    }
    return FalsificationReport(
        summary=summary,
        horizon_table=edge.horizon_table,
        block_table=edge.block_table,
        event_responses=edge.event_responses,
    )
