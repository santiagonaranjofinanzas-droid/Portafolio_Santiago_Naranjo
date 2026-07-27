"""Causal features and train-only shock calibration for MR V4."""

from __future__ import annotations

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v3.features import _h18_state, _require_bars

from .config import MRV4Config, SESSIONS


def _utc_session(index: pd.DatetimeIndex) -> pd.Series:
    hour = index.hour
    values = np.select(
        [hour < 8, hour < 14, hour < 22],
        ["ASIA", "EUROPE", "US"],
        default="ROLLOVER",
    )
    return pd.Series(values, index=index, dtype="object")


def build_mr_v4_features(bars: pd.DataFrame, config: MRV4Config  None = None) -> pd.DataFrame:
    """Build prefix-invariant fields using information available at each close."""

    cfg = config or MRV4Config()
    _require_bars(bars)
    out = bars.copy()
    log_close = np.log(out["close"].astype(float))
    returns = log_close.diff()
    past = returns.shift(1)
    center = past.rolling(cfg.return_scale_window, min_periods=cfg.return_scale_window).mean()
    scale = past.rolling(cfg.return_scale_window, min_periods=cfg.return_scale_window).std(ddof=1)
    out["v4_return"] = returns
    out["v4_return_center"] = center
    out["v4_return_scale"] = scale
    out["v4_shock_z"] = (returns - center) / scale.replace(0.0, np.nan)

    previous_close = out["close"].shift(1)
    true_range = pd.concat(
        [out["high"] - out["low"], (out["high"] - previous_close).abs(), (out["low"] - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    out["v4_atr"] = true_range.shift(1).rolling(cfg.atr_window, min_periods=cfg.atr_window).mean()
    out["v4_range_atr"] = true_range / out["v4_atr"].replace(0.0, np.nan)
    out["v4_session"] = _utc_session(out.index)

    medium = _h18_state(out, (12, 24, 48))
    ultra = _h18_state(out, (24, 48, 96))
    out["v4_h18_medium_score"] = medium["score"]
    out["v4_h18_ultra_score"] = ultra["score"]
    out["v4_h18_medium_position"] = medium["position"]
    out["v4_h18_ultra_position"] = ultra["position"]
    out["v4_trend_aligned"] = (
        medium["position"]
        & ultra["position"]
        & medium["score"].ge(cfg.trend_score_floor)
        & ultra["score"].ge(cfg.trend_score_floor)
    )
    if "spread_price" not in out and "axi_spread_profile" in out:
        out["spread_price"] = pd.to_numeric(out["axi_spread_profile"], errors="coerce")
    return out


def calibrate_session_thresholds(train: pd.DataFrame, config: MRV4Config  None = None) -> dict[str, float]:
    """Estimate fixed-quantile shock cutoffs exclusively from a training slice."""

    cfg = config or MRV4Config()
    required = {"v4_shock_z", "v4_session"}
    if not required.issubset(train.columns):
        raise ValueError(f"training features missing {sorted(required.difference(train.columns))}")
    thresholds: dict[str, float] = {}
    clean = pd.to_numeric(train["v4_shock_z"], errors="coerce")
    global_values = clean[np.isfinite(clean)]
    if len(global_values) < 100:
        raise ValueError("insufficient training observations for shock calibration")
    global_q = float(global_values.quantile(cfg.session_lower_quantile))
    for session in SESSIONS:
        values = clean[(train["v4_session"] == session) & np.isfinite(clean)]
        estimate = float(values.quantile(cfg.session_lower_quantile)) if len(values) >= 100 else global_q
        thresholds[session] = min(estimate, cfg.maximum_shock_z_threshold)
    return thresholds


def apply_shock_thresholds(features: pd.DataFrame, thresholds: dict[str, float], config: MRV4Config  None = None) -> pd.DataFrame:
    cfg = config or MRV4Config()
    missing = set(SESSIONS).difference(thresholds)
    if missing:
        raise ValueError(f"missing session thresholds: {sorted(missing)}")
    out = features.copy()
    out["v4_shock_threshold"] = out["v4_session"].map(thresholds).astype(float)
    out["v4_downside_shock"] = (
        out["v4_shock_z"].le(out["v4_shock_threshold"])
        & out["v4_range_atr"].ge(cfg.minimum_range_atr)
        & out["v4_trend_aligned"]
    )
    return out
