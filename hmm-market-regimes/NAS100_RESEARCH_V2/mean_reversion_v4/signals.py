"""Long-only shock rejection state machine for trend-aligned pullbacks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MRV4Config


def generate_mr_v4_signals(features: pd.DataFrame, config: MRV4Config  None = None) -> pd.DataFrame:
    cfg = config or MRV4Config()
    required = {"open", "high", "low", "close", "v4_atr", "v4_downside_shock", "v4_trend_aligned"}
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"MR V4 features missing columns: {sorted(missing)}")
    out = features.copy()
    n = len(out)
    entries = np.zeros(n, dtype=np.int8)
    targets = np.full(n, np.nan)
    stops = np.full(n, np.nan)
    shock_rows = np.full(n, -1, dtype=np.int64)
    reasons = np.full(n, "", dtype=object)
    opens = out["open"].to_numpy(float)
    highs = out["high"].to_numpy(float)
    lows = out["low"].to_numpy(float)
    closes = out["close"].to_numpy(float)
    atr = out["v4_atr"].to_numpy(float)
    shock = out["v4_downside_shock"].fillna(False).to_numpy(bool)
    aligned = out["v4_trend_aligned"].fillna(False).to_numpy(bool)
    setup_row = -1
    setup_close = np.nan
    setup_target = np.nan
    setup_stop = np.nan
    cooldown_until = -1
    for row in range(n):
        if setup_row >= 0:
            age = row - setup_row
            if age > cfg.maximum_confirmation_bars or not aligned[row]:
                setup_row = -1
            elif age >= 1:
                confirmed = closes[row] > setup_close and closes[row] > opens[row] and closes[row] > closes[row - 1]
                if confirmed:
                    risk = closes[row] - setup_stop
                    reward = setup_target - closes[row]
                    if risk > 0.0 and reward > 0.0 and reward / risk >= cfg.minimum_reward_risk:
                        entries[row] = 1
                        targets[row] = setup_target
                        stops[row] = setup_stop
                        shock_rows[row] = setup_row
                        reasons[row] = "trend_pullback_rejection_confirmed"
                        cooldown_until = row + cfg.maximum_holding_bars
                    setup_row = -1
        if setup_row < 0 and row > cooldown_until and row > 0 and shock[row]:
            if np.isfinite(atr[row]) and atr[row] > 0.0:
                setup_row = row
                setup_close = closes[row]
                setup_target = closes[row - 1]
                setup_stop = lows[row] - cfg.stop_atr * atr[row]
    out["entry_signal"] = entries
    out["exit_signal"] = False
    out["v4_target_reference"] = targets
    out["v4_stop_reference"] = stops
    out["v4_shock_row"] = shock_rows
    out["signal_reason"] = reasons
    return out
