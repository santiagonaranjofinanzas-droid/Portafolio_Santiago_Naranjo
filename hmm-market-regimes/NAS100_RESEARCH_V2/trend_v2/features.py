"""Strictly causal market features used by Trend V2."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .config import FeatureConfig


REGIME_FEATURES: tuple[str, ...] = (
    "trend_strength_16",
    "efficiency_ratio_32",
    "log_vol_ratio_16_96",
    "jump_score_96",
    "hour_range_log_ratio",
    "hour_activity_log_ratio",
)


def _validate_bars(bars: pd.DataFrame) -> None:
    missing = {"open", "high", "low", "close"}.difference(bars.columns)
    if missing:
        raise ValueError(f"Missing required bar columns: {sorted(missing)}")
    if not bars.index.is_monotonic_increasing:
        raise ValueError("Bar index must be monotonic increasing")
    if bars.index.has_duplicates:
        raise ValueError("Bar index must be unique")
    if len(bars) and (bars[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("OHLC prices must be strictly positive")


def _hour_key(index: pd.Index) -> np.ndarray:
    if isinstance(index, pd.DatetimeIndex):
        # The caller owns timezone normalization. We only use the supplied clock.
        return index.hour.to_numpy()
    # A deterministic fallback for synthetic/range-indexed M15 data.
    return (np.arange(len(index), dtype=int) // 4) % 24


def _causal_seasonal_median(
    values: pd.Series,
    hour: np.ndarray,
    window: int,
    minimum: int,
) -> pd.Series:
    """Median of prior observations in the same hour, never the current bar."""

    frame = pd.DataFrame({"value": values.to_numpy(dtype=float), "hour": hour}, index=values.index)

    def prior_rolling(group: pd.Series) -> pd.Series:
        return group.shift(1).rolling(window=window, min_periods=minimum).median()

    seasonal = frame.groupby("hour", sort=False, group_keys=False)["value"].transform(prior_rolling)
    # Before enough same-hour history exists, use an explicitly lagged global
    # baseline. This keeps warm-up finite without introducing a future value.
    global_baseline = values.shift(1).rolling(
        window=max(24, window), min_periods=minimum
    ).median()
    return seasonal.fillna(global_baseline)


def _select_activity(bars: pd.DataFrame, cfg: FeatureConfig) -> pd.Series:
    for name in cfg.volume_columns:
        if name in bars.columns:
            activity = pd.to_numeric(bars[name], errors="coerce").astype(float)
            return activity.where(activity >= 0.0)
    # Absence of tick activity is represented by a neutral constant. It is not
    # inferred from price and cannot leak information.
    return pd.Series(1.0, index=bars.index, dtype=float, name="synthetic_activity")


def build_causal_features(
    bars: pd.DataFrame,
    config: FeatureConfig  None = None,
) -> pd.DataFrame:
    """Return OHLC plus causal regime, momentum and execution features.

    All rolling statistics include observations no later than the current bar.
    Signals derived from this frame must be executed at the next bar open.
    Seasonal normalizers are lagged by one observation, so the current range or
    activity never contributes to its own denominator.
    """

    cfg = config or FeatureConfig()
    _validate_bars(bars)
    out = bars.copy()
    close = pd.to_numeric(out["close"], errors="coerce").astype(float)
    high = pd.to_numeric(out["high"], errors="coerce").astype(float)
    low = pd.to_numeric(out["low"], errors="coerce").astype(float)
    log_close = np.log(close)
    log_return = log_close.diff()

    rv_fast = log_return.rolling(cfg.fast_vol_window, min_periods=cfg.fast_vol_window).std(ddof=1)
    rv_slow = log_return.rolling(cfg.slow_vol_window, min_periods=cfg.slow_vol_window).std(ddof=1)
    trend_return = log_close.diff(cfg.trend_horizon).abs()
    out["log_return_1"] = log_return
    out["realized_vol_fast"] = rv_fast
    out["realized_vol_slow"] = rv_slow
    out["trend_strength_16"] = trend_return / (
        rv_slow * np.sqrt(cfg.trend_horizon) + cfg.epsilon
    )

    absolute_move = close.diff().abs()
    path_length = absolute_move.rolling(
        cfg.efficiency_window, min_periods=cfg.efficiency_window
    ).sum()
    out["efficiency_ratio_32"] = close.diff(cfg.efficiency_window).abs() / (
        path_length + cfg.epsilon
    )
    out["log_vol_ratio_16_96"] = np.log(
        (rv_fast + cfg.epsilon) / (rv_slow + cfg.epsilon)
    )
    out["jump_score_96"] = log_return.abs() / (rv_slow + cfg.epsilon)

    hour = _hour_key(out.index)
    relative_range = (high - low).clip(lower=0.0) / close
    range_baseline = _causal_seasonal_median(
        relative_range,
        hour,
        cfg.range_baseline_observations,
        cfg.range_baseline_min_observations,
    )
    out["hour_range_log_ratio"] = np.log(
        (relative_range + cfg.epsilon) / (range_baseline + cfg.epsilon)
    )

    activity = _select_activity(out, cfg)
    activity_baseline = _causal_seasonal_median(
        activity,
        hour,
        cfg.activity_baseline_observations,
        cfg.activity_baseline_min_observations,
    )
    out["hour_activity_log_ratio"] = np.log(
        (activity + cfg.epsilon) / (activity_baseline + cfg.epsilon)
    )

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            (high - low).abs(),
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    out["atr"] = true_range.rolling(cfg.atr_window, min_periods=cfg.atr_window).mean()

    momentum_columns: list[str] = []
    for horizon in cfg.momentum_horizons:
        name = f"momentum_{horizon}"
        out[name] = log_close.diff(horizon) / (
            rv_slow * np.sqrt(horizon) + cfg.epsilon
        )
        momentum_columns.append(name)
    out["momentum_score"] = out[momentum_columns].median(axis=1, skipna=False)
    out["feature_valid"] = np.isfinite(out[list(REGIME_FEATURES)]).all(axis=1)
    return out


def causal_prefix_invariant(
    bars: pd.DataFrame,
    prefix_length: int,
    config: FeatureConfig  None = None,
    atol: float = 1e-12,
) -> bool:
    """Diagnostic helper: later bars must not alter an earlier feature prefix."""

    if prefix_length <= 0 or prefix_length > len(bars):
        raise ValueError("prefix_length must lie inside the supplied bars")
    full = build_causal_features(bars, config).iloc[:prefix_length]
    prefix = build_causal_features(bars.iloc[:prefix_length], config)
    columns = list(REGIME_FEATURES) + ["momentum_score", "atr"]
    return bool(
        np.allclose(
            full[columns].to_numpy(dtype=float),
            prefix[columns].to_numpy(dtype=float),
            equal_nan=True,
            atol=atol,
            rtol=0.0,
        )
    )
