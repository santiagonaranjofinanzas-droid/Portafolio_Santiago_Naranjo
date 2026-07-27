"""Institutional performance metrics as defined in §22.1 of the protocol.

All metrics are calculated over arithmetic (simple) returns per §8.3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_metrics(
    returns: pd.Series,
    rf: float = 0.0,
    periods_per_year: int = 252,
) -> dict:
    """Calculate the full set of institutional metrics from §22.1.

    Parameters
    ----------
    returns : pd.Series
        Daily simple (arithmetic) returns of the portfolio.
    rf : float
        Annualized risk-free rate (default 0.0).
    periods_per_year : int
        Trading days per year (default 252).

    Returns
    -------
    dict
        Dictionary with all metric names as keys.
    """
    clean = returns.dropna()
    n = len(clean)

    if n < 2:
        return _empty_metrics()

    # Daily risk-free rate
    rf_daily = (1 + rf) ** (1 / periods_per_year) - 1
    excess = clean - rf_daily

    # ---------------------------------------------------------------------------
    # Cumulative / NAV
    # ---------------------------------------------------------------------------
    cum = (1 + clean).cumprod()
    total_return = cum.iloc[-1] / cum.iloc[0] - 1
    years = n / periods_per_year

    # ---------------------------------------------------------------------------
    # CAGR
    # ---------------------------------------------------------------------------
    if years > 0 and cum.iloc[-1] > 0:
        cagr = (cum.iloc[-1] / cum.iloc[0]) ** (1 / years) - 1
    else:
        cagr = 0.0

    # ---------------------------------------------------------------------------
    # Volatility (annualized)
    # ---------------------------------------------------------------------------
    vol = clean.std() * np.sqrt(periods_per_year)

    # ---------------------------------------------------------------------------
    # Sharpe Ratio
    # ---------------------------------------------------------------------------
    sharpe = (cagr - rf) / vol if vol > 0 else 0.0

    # ---------------------------------------------------------------------------
    # Sortino Ratio
    # ---------------------------------------------------------------------------
    downside = clean[clean < rf_daily] - rf_daily
    downside_std = np.sqrt((downside ** 2).mean()) * np.sqrt(periods_per_year)
    sortino = (cagr - rf) / downside_std if downside_std > 0 else 0.0

    # ---------------------------------------------------------------------------
    # Drawdown series
    # ---------------------------------------------------------------------------
    dd_series = cum / cum.cummax() - 1
    mdd = float(dd_series.min())

    # ---------------------------------------------------------------------------
    # Calmar Ratio
    # ---------------------------------------------------------------------------
    calmar = cagr / abs(mdd) if mdd != 0 else 0.0

    # ---------------------------------------------------------------------------
    # Drawdown Duration (max number of consecutive business days in drawdown)
    # ---------------------------------------------------------------------------
    in_drawdown = dd_series < -1e-8
    dd_groups = (~in_drawdown).cumsum()
    if in_drawdown.any():
        dd_durations = in_drawdown.groupby(dd_groups).sum()
        max_dd_duration = int(dd_durations.max())
    else:
        max_dd_duration = 0

    # ---------------------------------------------------------------------------
    # Tail Ratio (ratio of 95th percentile gain to abs 5th percentile loss)
    # ---------------------------------------------------------------------------
    p95 = clean.quantile(0.95)
    p05 = clean.quantile(0.05)
    tail_ratio = abs(p95 / p05) if p05 != 0 else 0.0

    # ---------------------------------------------------------------------------
    # Higher moments
    # ---------------------------------------------------------------------------
    skewness = float(clean.skew())
    kurtosis = float(clean.kurtosis())

    # ---------------------------------------------------------------------------
    # CVaR (Conditional Value at Risk at 5%)
    # ---------------------------------------------------------------------------
    var_05 = clean.quantile(0.05)
    cvar = float(clean[clean <= var_05].mean())

    # ---------------------------------------------------------------------------
    # Herfindahl Index (computed over weights if available — placeholder based on returns)
    # ---------------------------------------------------------------------------
    # Note: Herfindahl and effective positions are weight-based metrics.
    # They are computed by the simulator using weights_history, not from returns alone.
    # We include placeholders here; the simulator will fill them in.
    herfindahl = np.nan
    n_effective = np.nan

    return {
        "CAGR": cagr,
        "Sharpe": sharpe,
        "Sortino": sortino,
        "Calmar": calmar,
        "MDD": mdd,
        "Max_DD_Duration_Days": max_dd_duration,
        "Volatility_Ann": vol,
        "Tail_Ratio": tail_ratio,
        "Skewness": skewness,
        "Kurtosis": kurtosis,
        "CVaR_5pct": cvar,
        "Total_Return": total_return,
        "N_Observations": n,
        "Years": years,
        "Herfindahl": herfindahl,
        "N_Effective_Positions": n_effective,
    }


def calculate_weight_metrics(weights_history: pd.DataFrame) -> dict:
    """Calculate weight-based metrics: Herfindahl, effective positions, turnover.

    Parameters
    ----------
    weights_history : pd.DataFrame
        Weights per rebalance date (dates × tickers).

    Returns
    -------
    dict
        Weight-based metrics.
    """
    if weights_history.empty:
        return {
            "Herfindahl_Mean": np.nan,
            "N_Effective_Mean": np.nan,
            "Turnover_Mean": np.nan,
            "Turnover_Total": np.nan,
            "N_Rebalances": 0,
        }

    # Herfindahl per rebalance
    herf = (weights_history ** 2).sum(axis=1)
    n_eff = 1.0 / herf

    # Turnover between consecutive rebalances
    turnovers = weights_history.diff().abs().sum(axis=1).iloc[1:]

    return {
        "Herfindahl_Mean": float(herf.mean()),
        "N_Effective_Mean": float(n_eff.mean()),
        "Turnover_Mean": float(turnovers.mean()) if len(turnovers) > 0 else 0.0,
        "Turnover_Total": float(turnovers.sum()) if len(turnovers) > 0 else 0.0,
        "N_Rebalances": len(weights_history),
    }


def _empty_metrics() -> dict:
    """Return empty metrics dict when data is insufficient."""
    return {
        "CAGR": np.nan,
        "Sharpe": np.nan,
        "Sortino": np.nan,
        "Calmar": np.nan,
        "MDD": np.nan,
        "Max_DD_Duration_Days": np.nan,
        "Volatility_Ann": np.nan,
        "Tail_Ratio": np.nan,
        "Skewness": np.nan,
        "Kurtosis": np.nan,
        "CVaR_5pct": np.nan,
        "Total_Return": np.nan,
        "N_Observations": 0,
        "Years": 0.0,
        "Herfindahl": np.nan,
        "N_Effective_Positions": np.nan,
    }
