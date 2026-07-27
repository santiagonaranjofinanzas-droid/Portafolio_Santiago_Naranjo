from __future__ import annotations

import numpy as np
import pandas as pd


def local_level_filter(
    price: pd.Series, process_variance: float = 1e-6, observation_variance: float = 1e-4
) -> pd.DataFrame:
    """One-sided local-level Kalman filter on log price."""
    values = np.log(price.astype(float).to_numpy())
    level = np.full(len(values), np.nan)
    variance = np.full(len(values), np.nan)
    innovation = np.full(len(values), np.nan)
    gain = np.full(len(values), np.nan)
    finite = np.flatnonzero(np.isfinite(values))
    if not len(finite):
        return pd.DataFrame(index=price.index)
    state = values[finite[0]]
    p = observation_variance
    for i, value in enumerate(values):
        if not np.isfinite(value):
            continue
        p_pred = p + process_variance
        innovation[i] = value - state
        gain[i] = p_pred / (p_pred + observation_variance)
        state = state + gain[i] * innovation[i]
        p = (1.0 - gain[i]) * p_pred
        level[i] = state
        variance[i] = p
    result = pd.DataFrame(index=price.index)
    result["equilibrium_log"] = level
    result["equilibrium"] = np.exp(level)
    result["kalman_innovation"] = innovation
    result["kalman_gain"] = gain
    result["equilibrium_variance"] = variance
    result["residual"] = np.log(price.astype(float)) - result.equilibrium_log
    return result


def causal_zscore(series: pd.Series, window: int, min_periods: int  None = None) -> pd.Series:
    min_periods = min_periods or max(10, window // 3)
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std(ddof=1).clip(lower=1e-12)
    return (series - mean) / std


def add_equilibrium(bars: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    ecfg = cfg["equilibrium"]
    result = bars.join(
        local_level_filter(
            bars.mid_close,
            process_variance=float(ecfg["kalman_process_variance"]),
            observation_variance=float(ecfg["kalman_observation_variance"]),
        )
    )
    z_window = int(ecfg["z_window"])
    min_periods = max(10, z_window // 3)
    residual_mean = result.residual.rolling(z_window, min_periods=min_periods).mean()
    residual_std = (
        result.residual.rolling(z_window, min_periods=min_periods).std(ddof=1).clip(lower=1e-12)
    )
    result["residual_z"] = (result.residual - residual_mean) / residual_std
    result["residual_z_high"] = (
        np.log(result.mid_high.astype(float)) - result.equilibrium_log - residual_mean
    ) / residual_std
    result["residual_z_low"] = (
        np.log(result.mid_low.astype(float)) - result.equilibrium_log - residual_mean
    ) / residual_std
    result["residual_center"] = residual_mean
    result["residual_scale"] = residual_std
    result["ewma_equilibrium"] = bars.mid_close.ewm(
        span=int(ecfg["ewma_span"]), adjust=False
    ).mean()
    result["equilibrium_stability"] = 1.0 / (
        1.0 + result.equilibrium_log.diff().abs().rolling(32, min_periods=8).mean() * 1e4
    )
    return result
