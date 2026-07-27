"""Causal shock and H18 coexistence features for Mean Reversion V3."""

from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.trend_v2.config import SlowTrendConfig
from NAS100_RESEARCH_V2.trend_v2.signals import (
    build_slow_trend_features,
    generate_slow_trend_signals,
)

from .config import MRV3Config


def _require_bars(bars: pd.DataFrame) -> None:
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("MR V3 requires a timezone-aware DatetimeIndex")
    if str(bars.index.tz).upper() != "UTC":
        raise ValueError("MR V3 requires UTC bars")
    missing = {"open", "high", "low", "close"}.difference(bars.columns)
    if missing:
        raise ValueError(f"MR V3 missing OHLC columns: {sorted(missing)}")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("MR V3 bars must be unique and increasing")


def _h18_state(bars: pd.DataFrame, horizons: tuple[int, int, int]) -> pd.DataFrame:
    cfg = SlowTrendConfig(momentum_horizons_h1=horizons)
    features = build_slow_trend_features(bars, cfg)
    signals = generate_slow_trend_signals(features, cfg)
    return pd.DataFrame(
        {
            "score": signals["slow_momentum_score"].ffill(),
            "position": signals["logical_position"].astype(bool),
        },
        index=bars.index,
    )


def build_mr_v3_features(
    bars: pd.DataFrame, config: MRV3Config  None = None
) -> pd.DataFrame:
    """Build prefix-invariant features using only information known at each close."""

    cfg = config or MRV3Config()
    _require_bars(bars)
    out = bars.copy()
    log_close = np.log(out["close"].astype(float))
    returns = log_close.diff()
    past = returns.shift(1)
    center = past.rolling(cfg.return_scale_window, min_periods=cfg.return_scale_window).mean()
    scale = past.rolling(cfg.return_scale_window, min_periods=cfg.return_scale_window).std(ddof=1)
    out["mr_return"] = returns
    out["mr_return_center"] = center
    out["mr_return_scale"] = scale
    out["mr_shock_z"] = (returns - center) / scale.replace(0.0, np.nan)

    previous_close = out["close"].shift(1)
    true_range = pd.concat(
        [
            out["high"] - out["low"],
            (out["high"] - previous_close).abs(),
            (out["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    past_atr = true_range.shift(1).rolling(
        cfg.atr_window, min_periods=cfg.atr_window
    ).mean()
    out["mr_true_range"] = true_range
    out["mr_atr"] = past_atr
    out["mr_range_atr"] = true_range / past_atr.replace(0.0, np.nan)

    medium = _h18_state(out, (12, 24, 48))
    ultra = _h18_state(out, (24, 48, 96))
    out["mr_h18_medium_score"] = medium["score"]
    out["mr_h18_ultra_score"] = ultra["score"]
    out["mr_h18_medium_position"] = medium["position"]
    out["mr_h18_ultra_position"] = ultra["position"]
    scores_valid = medium["score"].notna() & ultra["score"].notna()
    weak_trend = (
        medium["score"].abs().le(cfg.trend_score_veto)
        & ultra["score"].abs().le(cfg.trend_score_veto)
    )
    out["mr_trend_block"] = (
        ~scores_valid  medium["position"]  ultra["position"]  ~weak_trend
    )
    out["mr_shock"] = (
        out["mr_shock_z"].abs().ge(cfg.shock_z)
        & out["mr_range_atr"].ge(cfg.minimum_range_atr)
        & ~out["mr_trend_block"]
    )
    return out
