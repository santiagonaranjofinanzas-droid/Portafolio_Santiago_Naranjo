"""Causal exhaustion/re-entry event generation for Mean Reversion V2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import CostConfig, SignalConfig
from .model import AR1Estimate


@dataclass(frozen=True)
class SignalGenerationResult:
    frame: pd.DataFrame
    events: pd.DataFrame


def _row_spread(frame: pd.DataFrame, costs: CostConfig) -> np.ndarray:
    for name in ("spread_price", "spread_median", "spread"):
        if name in frame.columns:
            spread = pd.to_numeric(frame[name], errors="coerce").to_numpy(dtype=float)
            if np.any(~np.isfinite(spread)) or np.any(spread < 0):
                raise ValueError(f"{name} must be finite and non-negative")
            return spread
    return np.full(len(frame), costs.spread_price, dtype=float)


def generate_reentry_signals(
    filtered: pd.DataFrame,
    signal_config: SignalConfig  None = None,
    costs: CostConfig  None = None,
    ar1: AR1Estimate  None = None,
    *,
    model_transform: str = "log",
) -> SignalGenerationResult:
    """Arm on an extreme and signal only after the residual re-enters.

    A signal at timestamp ``t`` is information available at that bar's close;
    the backtester is required to execute it at ``t+1`` open. Long and short
    state machines are independent and every blocked trigger is retained in the
    event audit table.
    """

    cfg = signal_config or SignalConfig()
    cost_cfg = costs or CostConfig()
    required = {"close", "level_price", "residual_scale", "z_residual"}
    missing = required.difference(filtered.columns)
    if missing:
        raise ValueError(f"filtered data missing columns: {sorted(missing)}")
    if filtered.index.has_duplicates or not filtered.index.is_monotonic_increasing:
        raise ValueError("filtered index must be unique and monotonically increasing")
    if model_transform not in {"log", "identity"}:
        raise ValueError("model_transform must be 'log' or 'identity'")

    result = filtered.copy()
    n = len(result)
    z = result["z_residual"].to_numpy(dtype=float)
    close = result["close"].to_numpy(dtype=float)
    target = result["level_price"].to_numpy(dtype=float)
    residual_scale = result["residual_scale"].to_numpy(dtype=float)
    structural_break = result.get(
        "structural_break", pd.Series(False, index=result.index)
    ).fillna(True).to_numpy(dtype=bool)
    phi_gate_column = result.get(
        "phi_gate_passed", pd.Series(False, index=result.index)
    ).fillna(False).to_numpy(dtype=bool)
    if ar1 is not None:
        phi_gate_column[:] = ar1.gate_passed
        half_life = ar1.half_life
    else:
        half_life = float("nan")
    spread = _row_spread(result, cost_cfg)
    round_trip_cost = (
        spread
        + 2.0 * cost_cfg.slippage_price_per_side
        + cost_cfg.commission_round_trip_price
    )

    long_signal = np.zeros(n, dtype=bool)
    short_signal = np.zeros(n, dtype=bool)
    long_armed_col = np.zeros(n, dtype=bool)
    short_armed_col = np.zeros(n, dtype=bool)
    setup_age_col = np.full(n, np.nan)
    expected_edge = np.full(n, np.nan)
    required_edge = np.full(n, np.nan)
    signal_target = np.full(n, np.nan)
    signal_scale = np.full(n, np.nan)
    signal_half_life = np.full(n, np.nan)
    events: list[dict] = []

    long_armed = False
    short_armed = False
    long_age = 0
    short_age = 0

    for i in range(n):
        timestamp = result.index[i]
        if not np.isfinite(z[i]) or not np.isfinite(close[i]) or not np.isfinite(target[i]):
            long_armed = short_armed = False
            continue
        if structural_break[i]:
            if long_armed or short_armed:
                events.append(
                    {
                        "time": timestamp,
                        "event": "SETUP_CANCELLED_STRUCTURAL_BREAK",
                        "side": "BOTH",
                        "z_residual": z[i],
                        "setup_age": max(long_age, short_age),
                        "eligible": False,
                        "reason": "STRUCTURAL_BREAK",
                    }
                )
            long_armed = short_armed = False
            long_age = short_age = 0
            continue

        if z[i] <= -cfg.extreme_z and "LONG" in cfg.allowed_sides:
            if not long_armed:
                events.append(
                    {
                        "time": timestamp,
                        "event": "EXTREME_ARMED",
                        "side": "LONG",
                        "z_residual": z[i],
                        "setup_age": 0,
                        "eligible": True,
                        "reason": "LOWER_EXTREME",
                    }
                )
            long_armed, long_age = True, 0
            short_armed, short_age = False, 0
        elif z[i] >= cfg.extreme_z and "SHORT" in cfg.allowed_sides:
            if not short_armed:
                events.append(
                    {
                        "time": timestamp,
                        "event": "EXTREME_ARMED",
                        "side": "SHORT",
                        "z_residual": z[i],
                        "setup_age": 0,
                        "eligible": True,
                        "reason": "UPPER_EXTREME",
                    }
                )
            short_armed, short_age = True, 0
            long_armed, long_age = False, 0
        else:
            if long_armed:
                long_age += 1
            if short_armed:
                short_age += 1

        if long_armed and long_age > cfg.max_setup_bars:
            events.append(
                {
                    "time": timestamp,
                    "event": "SETUP_EXPIRED",
                    "side": "LONG",
                    "z_residual": z[i],
                    "setup_age": long_age,
                    "eligible": False,
                    "reason": "MAX_SETUP_BARS",
                }
            )
            long_armed, long_age = False, 0
        if short_armed and short_age > cfg.max_setup_bars:
            events.append(
                {
                    "time": timestamp,
                    "event": "SETUP_EXPIRED",
                    "side": "SHORT",
                    "z_residual": z[i],
                    "setup_age": short_age,
                    "eligible": False,
                    "reason": "MAX_SETUP_BARS",
                }
            )
            short_armed, short_age = False, 0

        previous_z = z[i - 1] if i > 0 else np.nan
        long_cross = long_armed and i > 0 and previous_z < -cfg.reentry_z <= z[i]
        short_cross = short_armed and i > 0 and previous_z > cfg.reentry_z >= z[i]

        for side, crossed, age in (
            ("LONG", long_cross, long_age),
            ("SHORT", short_cross, short_age),
        ):
            if not crossed:
                continue
            gross_edge = target[i] - close[i] if side == "LONG" else close[i] - target[i]
            edge_required = cfg.min_expected_cost_multiple * round_trip_cost[i]
            gate_reasons: list[str] = []
            if cfg.require_phi_gate and not phi_gate_column[i]:
                gate_reasons.append("PHI_GATE_FAILED")
            if cfg.block_on_structural_break and structural_break[i]:
                gate_reasons.append("STRUCTURAL_BREAK")
            if gross_edge <= 0:
                gate_reasons.append("TARGET_NOT_FAVORABLE")
            if gross_edge < edge_required:
                gate_reasons.append("EXPECTED_EDGE_BELOW_COST_MULTIPLE")
            eligible = not gate_reasons

            events.append(
                {
                    "time": timestamp,
                    "event": "REENTRY_TRIGGER",
                    "side": side,
                    "z_residual": z[i],
                    "setup_age": age,
                    "eligible": eligible,
                    "reason": "PASS" if eligible else "".join(gate_reasons),
                    "target_price": target[i],
                    "gross_edge_price": gross_edge,
                    "required_edge_price": edge_required,
                    "round_trip_cost_price": round_trip_cost[i],
                }
            )
            expected_edge[i] = gross_edge
            required_edge[i] = edge_required
            if eligible:
                if side == "LONG":
                    long_signal[i] = True
                else:
                    short_signal[i] = True
                signal_target[i] = target[i]
                signal_scale[i] = residual_scale[i]
                signal_half_life[i] = half_life

            if side == "LONG":
                long_armed, long_age = False, 0
            else:
                short_armed, short_age = False, 0

        long_armed_col[i] = long_armed
        short_armed_col[i] = short_armed
        if long_armed:
            setup_age_col[i] = long_age
        elif short_armed:
            setup_age_col[i] = short_age

        # Once the residual reaches/crosses the mean there is no stale setup.
        if z[i] >= 0 and long_armed:
            long_armed, long_age = False, 0
        if z[i] <= 0 and short_armed:
            short_armed, short_age = False, 0

    result["mr_long_armed"] = long_armed_col
    result["mr_short_armed"] = short_armed_col
    result["mr_setup_age"] = setup_age_col
    result["mr_long_signal"] = long_signal
    result["mr_short_signal"] = short_signal
    result["mr_signal"] = np.where(long_signal, 1, np.where(short_signal, -1, 0)).astype(np.int8)
    result["mr_signal_target_price"] = signal_target
    result["mr_signal_residual_scale"] = signal_scale
    result["mr_signal_half_life"] = signal_half_life
    result["mr_expected_gross_edge_price"] = expected_edge
    result["mr_required_edge_price"] = required_edge
    result["mr_model_transform"] = model_transform
    result["round_trip_cost_price"] = round_trip_cost

    event_columns = [
        "time",
        "event",
        "side",
        "z_residual",
        "setup_age",
        "eligible",
        "reason",
        "target_price",
        "gross_edge_price",
        "required_edge_price",
        "round_trip_cost_price",
    ]
    event_frame = pd.DataFrame(events).reindex(columns=event_columns)
    return SignalGenerationResult(frame=result, events=event_frame)
