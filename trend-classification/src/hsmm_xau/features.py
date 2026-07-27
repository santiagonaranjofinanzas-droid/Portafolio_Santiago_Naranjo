from __future__ import annotations

import numpy as np
import pandas as pd

from .equilibrium import causal_zscore


def rolling_acf1(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=max(10, window // 2)).corr(series.shift(1))


def variance_ratio(log_price: pd.Series, window: int, lag: int = 4) -> pd.Series:
    one = log_price.diff()
    multi = log_price.diff(lag)
    numerator = multi.rolling(window, min_periods=window // 2).var()
    denominator = lag * one.rolling(window, min_periods=window // 2).var()
    return numerator / denominator.replace(0, np.nan)


def rolling_half_life(residual: pd.Series, window: int) -> pd.Series:
    delta = residual.diff()
    lagged = residual.shift(1)
    cov = lagged.rolling(window, min_periods=window // 2).cov(delta)
    var = lagged.rolling(window, min_periods=window // 2).var()
    beta = cov / var.replace(0, np.nan)
    phi = (1.0 + beta).clip(lower=1e-6, upper=0.999999)
    half_life = -np.log(2.0) / np.log(phi)
    return half_life.where(beta < 0)


def efficiency_ratio(price: pd.Series, window: int) -> pd.Series:
    displacement = price.diff(window).abs()
    path = price.diff().abs().rolling(window, min_periods=window // 2).sum()
    return displacement / path.replace(0, np.nan)


def true_range(frame: pd.DataFrame) -> pd.Series:
    prev = frame.mid_close.shift(1)
    return pd.concat(
        [
            frame.mid_high - frame.mid_low,
            (frame.mid_high - prev).abs(),
            (frame.mid_low - prev).abs(),
        ],
        axis=1,
    ).max(axis=1)


def build_features(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    result = frame.copy()
    log_price = np.log(result.mid_close)
    returns = log_price.diff()
    windows = [int(w) for w in cfg["features"]["windows"]]
    for window in windows:
        result[f"return_acf1_{window}"] = rolling_acf1(returns, window)
        result[f"variance_ratio_{window}"] = variance_ratio(log_price, window)
        result[f"half_life_{window}"] = rolling_half_life(result.residual, window)
        result[f"efficiency_ratio_{window}"] = efficiency_ratio(result.mid_close, window)
        result[f"realized_vol_{window}"] = returns.rolling(window, min_periods=window // 2).std(
            ddof=1
        )
        result[f"range_atr_{window}"] = (
            true_range(result).rolling(window, min_periods=window // 2).mean() / result.mid_close
        )
    result["spread_z_96"] = causal_zscore(result.spread_mean, 96)
    result["tick_activity_z_96"] = causal_zscore(np.log1p(result.tick_count), 96)
    hour = result.index.hour + result.index.minute / 60.0
    result["session_sin"] = np.sin(2 * np.pi * hour / 24.0)
    result["session_cos"] = np.cos(2 * np.pi * hour / 24.0)
    result["weekday_sin"] = np.sin(2 * np.pi * result.index.dayofweek / 5.0)
    result["weekday_cos"] = np.cos(2 * np.pi * result.index.dayofweek / 5.0)
    for symbol in ("xagusd", "nsxusd"):
        col = f"{symbol}_close"
        if col in result:
            result[f"{symbol}_return_16"] = np.log(result[col]).diff(16)
    return result


def assert_causal(builder, frame: pd.DataFrame, cfg: dict, cut: int) -> None:
    """Prefix invariance test: adding future rows may not alter past features."""
    full = builder(frame, cfg).iloc[:cut]
    prefix = builder(frame.iloc[:cut], cfg)
    common = full.select_dtypes(include=[np.number]).columns.intersection(prefix.columns)
    if not np.allclose(full[common], prefix[common], equal_nan=True, rtol=1e-10, atol=1e-12):
        raise AssertionError("Feature builder changed past values after future rows were appended")
