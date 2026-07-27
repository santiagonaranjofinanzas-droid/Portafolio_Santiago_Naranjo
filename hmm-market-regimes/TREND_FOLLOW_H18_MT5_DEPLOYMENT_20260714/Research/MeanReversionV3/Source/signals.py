"""Causal shock-rejection setup state machine."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MRV3Config


def generate_mr_v3_signals(
    features: pd.DataFrame, config: MRV3Config  None = None
) -> pd.DataFrame:
    cfg = config or MRV3Config()
    required = {
        "open", "high", "low", "close", "mr_atr", "mr_shock_z",
        "mr_shock", "mr_trend_block",
    }
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"MR V3 features missing columns: {sorted(missing)}")
    out = features.copy()
    n = len(out)
    entries = np.zeros(n, dtype=np.int8)
    targets = np.full(n, np.nan)
    stops = np.full(n, np.nan)
    shock_rows = np.full(n, -1, dtype=np.int64)
    reasons = np.full(n, "", dtype=object)

    setup_side = 0
    setup_row = -1
    setup_mid = np.nan
    setup_target = np.nan
    setup_stop = np.nan
    cooldown_until = -1
    opens = out["open"].to_numpy(float)
    highs = out["high"].to_numpy(float)
    lows = out["low"].to_numpy(float)
    closes = out["close"].to_numpy(float)
    atr = out["mr_atr"].to_numpy(float)
    shock_z = out["mr_shock_z"].to_numpy(float)
    shock = out["mr_shock"].fillna(False).to_numpy(bool)
    blocked = out["mr_trend_block"].fillna(True).to_numpy(bool)

    for row in range(n):
        if setup_side != 0:
            age = row - setup_row
            if age > cfg.maximum_rejection_bars or blocked[row]:
                setup_side = 0
            elif age >= 1:
                rejected = bool(
                    (setup_side == 1 and closes[row] >= setup_mid and closes[row] > opens[row])
                    or (setup_side == -1 and closes[row] <= setup_mid and closes[row] < opens[row])
                )
                if rejected:
                    risk = setup_side * (closes[row] - setup_stop)
                    reward = setup_side * (setup_target - closes[row])
                    if risk > 0.0 and reward / risk >= cfg.minimum_reward_risk:
                        entries[row] = setup_side
                        targets[row] = setup_target
                        stops[row] = setup_stop
                        shock_rows[row] = setup_row
                        reasons[row] = "shock_rejection_confirmed"
                        cooldown_until = row + cfg.maximum_holding_bars
                    setup_side = 0
        if setup_side == 0 and row > cooldown_until and shock[row] and row > 0:
            value_atr = atr[row]
            if np.isfinite(value_atr) and value_atr > 0.0 and np.isfinite(shock_z[row]):
                setup_side = -1 if shock_z[row] > 0.0 else 1
                setup_row = row
                setup_mid = (highs[row] + lows[row]) / 2.0
                setup_target = closes[row - 1]
                setup_stop = (
                    lows[row] - cfg.stop_atr * value_atr
                    if setup_side == 1
                    else highs[row] + cfg.stop_atr * value_atr
                )

    out["entry_signal"] = entries
    out["exit_signal"] = False
    out["mr_target_reference"] = targets
    out["mr_stop_reference"] = stops
    out["mr_shock_row"] = shock_rows
    out["signal_reason"] = reasons
    return out
