"""Module for detecting stale price observations in market data series."""

from __future__ import annotations
import pandas as pd


def detect_stale_prices(
    df: pd.DataFrame,
    volume_col: str = "adjVolume",
    price_col: str = "adjClose",
    min_volume_threshold: float = 100.0,
) -> pd.Series:
    """Detect stale price observations.
    
    A row is marked as stale (True) if:
    - The volume column is NaN, 0, or missing.
    - The price is identical to the previous session AND the volume is below the min_volume_threshold.
    """
    if df.empty:
        return pd.Series(dtype=bool)

    if volume_col not in df.columns:
        raise ValueError(f"Volume column '{volume_col}' not found in DataFrame.")
    if price_col not in df.columns:
        raise ValueError(f"Price column '{price_col}' not found in DataFrame.")

    # 1. Volume is 0 or NaN
    vol_stale = df[volume_col].isna()  (df[volume_col] == 0)

    # 2. Price is identical to previous price and volume is low
    price_diff = df[price_col].diff()
    price_frozen = price_diff == 0.0
    low_vol = df[volume_col] < min_volume_threshold
    price_frozen_stale = price_frozen & low_vol

    is_stale = vol_stale  price_frozen_stale
    
    # Fill first row's price_frozen check to be False since diff() is NaN
    is_stale.iloc[0] = vol_stale.iloc[0]

    return is_stale.astype(bool)
