"""Module for calculating simple and log returns, and aggregating portfolio returns."""

from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_returns(
    df: pd.DataFrame,
    price_col: str = "adjClose",
    stale_col: str = "is_stale",
) -> pd.DataFrame:
    """Calculate simple and log returns for a given price series.
    
    If the date is marked as stale, the returns are set to 0.0 as per the protocol.
    """
    if df.empty:
        return pd.DataFrame(columns=["simple_return", "log_return", "raw_simple_return", "raw_log_return", "is_stale"])

    if price_col not in df.columns:
        raise ValueError(f"Price column '{price_col}' not found in DataFrame.")

    # Calculate raw returns
    raw_simple = df[price_col].pct_change()
    
    # Calculate log returns (safeguard against <= 0 prices)
    price_ratio = df[price_col] / df[price_col].shift(1)
    # If price is 0 or negative, set ratio to NaN to avoid math domain errors
    price_ratio = price_ratio.mask(df[price_col] <= 0)
    raw_log = np.log(price_ratio)

    is_stale = df[stale_col] if stale_col in df.columns else pd.Series(False, index=df.index)

    # Set returns to 0 on stale dates
    clean_simple = raw_simple.copy()
    clean_log = raw_log.copy()

    clean_simple[is_stale] = 0.0
    clean_log[is_stale] = 0.0

    # First row is always NaN for returns
    clean_simple.iloc[0] = np.nan
    clean_log.iloc[0] = np.nan

    out_df = pd.DataFrame(index=df.index)
    out_df["simple_return"] = clean_simple
    out_df["log_return"] = clean_log
    out_df["raw_simple_return"] = raw_simple
    out_df["raw_log_return"] = raw_log
    out_df["is_stale"] = is_stale

    return out_df


def calculate_portfolio_return(
    returns_df: pd.DataFrame,
    weights: dict[str, float]  pd.DataFrame,
) -> pd.Series:
    """Aggregate individual asset simple returns into portfolio simple returns.
    
    Weights can be:
    - A dictionary of {ticker: weight} for constant weights.
    - A pandas DataFrame with columns as tickers and dates as index for dynamic weights.
    """
    if returns_df.empty:
        return pd.Series(dtype=float)

    if isinstance(weights, dict):
        # Convert dictionary to Series
        w_series = pd.Series(weights)
        tickers = w_series.index.tolist()
        
        # Verify tickers exist in returns_df columns
        missing = [t for t in tickers if t not in returns_df.columns]
        if missing:
            raise ValueError(f"Assets {missing} specified in weights not found in returns DataFrame.")
            
        # Linear aggregation
        portfolio_ret = returns_df[tickers].dot(w_series)
        return portfolio_ret

    elif isinstance(weights, pd.DataFrame):
        # Align index (dates) and columns (tickers)
        common_dates = returns_df.index.intersection(weights.index)
        if common_dates.empty:
            raise ValueError("No common dates between returns DataFrame and weights DataFrame.")
            
        common_tickers = returns_df.columns.intersection(weights.columns)
        if common_tickers.empty:
            raise ValueError("No common tickers between returns DataFrame and weights DataFrame.")

        ret_aligned = returns_df.loc[common_dates, common_tickers]
        w_aligned = weights.loc[common_dates, common_tickers]
        
        # Element-wise product and sum across assets
        portfolio_ret = (ret_aligned * w_aligned).sum(axis=1)
        return portfolio_ret

    else:
        raise TypeError("Weights must be a dict or a pandas DataFrame.")
