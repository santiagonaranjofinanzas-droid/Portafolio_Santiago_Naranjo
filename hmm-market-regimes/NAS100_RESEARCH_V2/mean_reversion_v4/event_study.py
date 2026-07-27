"""Non-overlapping OOS event study for the buy-the-dip mechanism."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import MRV4Config


def build_event_study(features: pd.DataFrame, fold_id: int, config: MRV4Config  None = None) -> pd.DataFrame:
    cfg = config or MRV4Config()
    rows: list[dict] = []
    shocks = features["v4_downside_shock"].fillna(False).to_numpy(bool)
    opens = features["open"].to_numpy(float)
    highs = features["high"].to_numpy(float)
    lows = features["low"].to_numpy(float)
    closes = features["close"].to_numpy(float)
    if "spread_price" in features:
        spreads = pd.to_numeric(features["spread_price"], errors="coerce").fillna(cfg.costs.spread_price).to_numpy(float)
    else:
        spreads = np.full(len(features), cfg.costs.spread_price)
    last_event = -cfg.event_cooldown_bars - 1
    max_horizon = max(cfg.event_horizons_bars)
    for row in np.flatnonzero(shocks):
        if row - last_event <= cfg.event_cooldown_bars or row + max_horizon >= len(features) or row + 1 >= len(features):
            continue
        entry_row = row + 1
        entry = opens[entry_row] + spreads[entry_row] / 2.0 + cfg.costs.slippage_price_per_side
        record = {
            "fold_id": fold_id,
            "shock_time": features.index[row],
            "entry_time": features.index[entry_row],
            "session": features.iloc[row]["v4_session"],
            "shock_z": float(features.iloc[row]["v4_shock_z"]),
            "entry_price": float(entry),
        }
        for horizon in cfg.event_horizons_bars:
            exit_row = row + horizon
            exit_price = closes[exit_row] - spreads[exit_row] / 2.0 - cfg.costs.slippage_price_per_side
            net_price = exit_price - entry - cfg.costs.commission_round_trip_price
            window = slice(entry_row, exit_row + 1)
            record[f"net_price_h{horizon}"] = float(net_price)
            record[f"net_bps_h{horizon}"] = float(net_price / entry * 10_000.0)
            record[f"mfe_price_h{horizon}"] = float(np.max(highs[window]) - entry)
            record[f"mae_price_h{horizon}"] = float(np.min(lows[window]) - entry)
        rows.append(record)
        last_event = row
    return pd.DataFrame(rows)


def summarize_event_study(events: pd.DataFrame, horizons: tuple[int, ...], seed: int = 20260714) -> dict[str, dict]:
    result: dict[str, dict] = {}
    rng = np.random.default_rng(seed)
    for horizon in horizons:
        column = f"net_bps_h{horizon}"
        values = events[column].to_numpy(float) if not events.empty else np.array([], dtype=float)
        values = values[np.isfinite(values)]
        if len(values):
            means = np.empty(10_000)
            for i in range(len(means)):
                means[i] = rng.choice(values, size=len(values), replace=True).mean()
            probability = float((means > 0.0).mean())
            lower = float(np.quantile(means, 0.05))
        else:
            probability, lower = 0.0, 0.0
        fold_means = events.groupby("fold_id")[column].mean() if not events.empty else pd.Series(dtype=float)
        result[str(horizon)] = {
            "events": int(len(values)),
            "mean_net_bps": float(values.mean()) if len(values) else 0.0,
            "median_net_bps": float(np.median(values)) if len(values) else 0.0,
            "win_rate_pct": float((values > 0.0).mean() * 100.0) if len(values) else 0.0,
            "bootstrap_mean_p05_bps": lower,
            "bootstrap_probability_positive": probability,
            "positive_folds": int((fold_means > 0.0).sum()),
            "folds_with_events": int(len(fold_means)),
        }
    return result
