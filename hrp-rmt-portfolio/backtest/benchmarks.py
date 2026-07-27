"""Benchmark portfolio strategies as defined in §15.1 of the protocol.

All benchmarks return pd.Series with weights that sum to 1.0, are long-only (>= 0),
and are subject to the same cap constraint (15% max per ETF) as the HRP engine.

Institutional review note: Applying identical constraints to all benchmarks ensures
mathematically homogeneous comparison of contribution marginal (§15.2).  If benchmarks
operated unconstrained while HRP suffers constraint drag (§13.4), the layer-6 comparison
would be invalid.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from risk.cov_estimators import calculate_ledoit_wolf_covariance
from portfolio.hrp import calculate_hrp_weights, redistribute_weights_proportional


#---------------------------------------------------------------------------
#Common cap enforcement (§13.1 — applied uniformly to all strategies)
#---------------------------------------------------------------------------
def _apply_cap(weights: pd.Series, cap: float = 0.15, cash_ticker: str = "BIL") -> pd.Series:
    """Enforce the 15% per-ETF cap and redistribute excess proportionally.

    This ensures all benchmarks face the same constraint drag as HRP,
    making the contribution marginal comparison (§15.2) mathematically fair.
    """
    return redistribute_weights_proportional(weights, cap=cap, cash_ticker=cash_ticker)


#---------------------------------------------------------------------------
#1/N Equal Weight (§15.1)
#---------------------------------------------------------------------------
def equal_weight(tickers: list[str], cap: float = 0.15, cash_ticker: str = "BIL") -> pd.Series:
    """Assign equal weight to all tickers, subject to cap."""
    n = len(tickers)
    if n == 0:
        return pd.Series(dtype=float)
    w = pd.Series(1.0 / n, index=tickers)
    return _apply_cap(w, cap=cap, cash_ticker=cash_ticker)


#---------------------------------------------------------------------------
#Inverse Volatility Portfolio — IVP (§15.1)
#---------------------------------------------------------------------------
def inverse_volatility(
    cov: pd.DataFrame,
    cap: float = 0.15,
    cash_ticker: str = "BIL",
) -> pd.Series:
    """Weight inversely proportional to individual asset volatility, subject to cap."""
    variances = np.diag(cov.values)
    variances = np.maximum(variances, 1e-12)  # guard zero variance
    inv_vol = 1.0 / np.sqrt(variances)
    weights = inv_vol / inv_vol.sum()
    w = pd.Series(weights, index=cov.columns)
    return _apply_cap(w, cap=cap, cash_ticker=cash_ticker)


#---------------------------------------------------------------------------
#Equal Risk Contribution — ERC (§15.1)
#---------------------------------------------------------------------------
def equal_risk_contribution(
    cov: pd.DataFrame,
    cap: float = 0.15,
    cash_ticker: str = "BIL",
    max_iter: int = 500,
    tol: float = 1e-8,
) -> pd.Series:
    """Iterative solver for the Equal Risk Contribution portfolio, subject to cap.

    Each asset contributes equally to total portfolio risk:
        w_i * (Σw)_i / (w^T Σ w) = 1/N  for all i
    """
    n = cov.shape[0]
    sigma = cov.values

    # Initialize with inverse volatility
    variances = np.diag(sigma)
    variances = np.maximum(variances, 1e-12)
    w = 1.0 / np.sqrt(variances)
    w = w / w.sum()

    for _ in range(max_iter):
        sigma_w = sigma @ w
        port_var = w @ sigma_w
        if port_var <= 0:
            break

        # Risk contributions
        rc = w * sigma_w / port_var
        target_rc = 1.0 / n

        # Update step: Newton-like adjustment
        w_new = w.copy()
        for i in range(n):
            if sigma_w[i] > 0:
                w_new[i] = w[i] * (target_rc / rc[i]) ** 0.5

        w_new = np.maximum(w_new, 0.0)
        w_new = w_new / w_new.sum()

        if np.max(np.abs(w_new - w)) < tol:
            w = w_new
            break
        w = w_new

    result = pd.Series(w, index=cov.columns)
    return _apply_cap(result, cap=cap, cash_ticker=cash_ticker)


#---------------------------------------------------------------------------
#Minimum Variance with Ledoit-Wolf (§15.1)
#---------------------------------------------------------------------------
def min_variance_lw(
    returns_df: pd.DataFrame,
    cap: float = 0.15,
    cash_ticker: str = "BIL",
) -> pd.Series:
    """Minimum variance portfolio using Ledoit-Wolf shrinkage covariance, subject to cap.

    Solves: min w^T Σ w  s.t. Σw_i = 1, w_i >= 0, w_i <= cap
    Uses closed-form for unconstrained, then clips to long-only and applies cap.
    """
    cov_lw = calculate_ledoit_wolf_covariance(returns_df)
    if cov_lw.empty:
        return pd.Series(dtype=float)

    sigma_inv = np.linalg.inv(cov_lw.values)
    ones = np.ones(sigma_inv.shape[0])
    w = sigma_inv @ ones / (ones @ sigma_inv @ ones)

    # Clip to long-only and re-normalize
    w = np.maximum(w, 0.0)
    if w.sum() > 0:
        w = w / w.sum()
    else:
        w = np.ones(len(w)) / len(w)

    result = pd.Series(w, index=cov_lw.columns)
    return _apply_cap(result, cap=cap, cash_ticker=cash_ticker)


#---------------------------------------------------------------------------
#HRP Empirical — no spectral cleaning (§15.1)
#---------------------------------------------------------------------------
def hrp_empirical(
    cov: pd.DataFrame,
    linkage_method: str = "single",
    cap: float = 0.15,
    cash_ticker: str = "BIL",
    redistribution_method: str = "hierarchical",
) -> pd.Series:
    """HRP with empirical covariance (no RMT cleaning)."""
    result = calculate_hrp_weights(
        cov,
        linkage_method=linkage_method,
        cap=cap,
        redistribution_method=redistribution_method,
        cash_ticker=cash_ticker,
    )
    return result["weights_restricted"]


#---------------------------------------------------------------------------
#HRP + Ledoit-Wolf (§15.1)
#---------------------------------------------------------------------------
def hrp_lw(
    returns_df: pd.DataFrame,
    linkage_method: str = "single",
    cap: float = 0.15,
    cash_ticker: str = "BIL",
    redistribution_method: str = "hierarchical",
) -> pd.Series:
    """HRP using Ledoit-Wolf shrinkage covariance."""
    cov_lw = calculate_ledoit_wolf_covariance(returns_df)
    if cov_lw.empty:
        return pd.Series(dtype=float)
    result = calculate_hrp_weights(
        cov_lw,
        linkage_method=linkage_method,
        cap=cap,
        redistribution_method=redistribution_method,
        cash_ticker=cash_ticker,
    )
    return result["weights_restricted"]


#---------------------------------------------------------------------------
#60/40 Global Benchmark (§15.1)
#---------------------------------------------------------------------------
def benchmark_60_40(
    equity_ticker: str = "SPY",
    bond_ticker: str = "AGG",
) -> pd.Series:
    """Simple 60% equity / 40% bond benchmark.

    Note: 60/40 is inherently within the 15% cap (max weight is 60%),
    but since it only holds 2 assets, the cap does not apply meaningfully.
    This benchmark is exempt from cap enforcement by design as it represents
    a passive external reference, not a candidate strategy.
    """
    return pd.Series({equity_ticker: 0.60, bond_ticker: 0.40})


#---------------------------------------------------------------------------
#Benchmark compuesto — Equal-weight of selectable universe (§15.1)
#---------------------------------------------------------------------------
def benchmark_composite(
    tickers: list[str],
    cap: float = 0.15,
    cash_ticker: str = "BIL",
) -> pd.Series:
    """Equal-weight benchmark matching the selectable universe, subject to cap."""
    return equal_weight(tickers, cap=cap, cash_ticker=cash_ticker)
