"""Module for calculating Probabilistic Sharpe Ratio (PSR) and Deflated Sharpe Ratio (DSR).

Implements §16 and §25.4 of the protocol.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy import stats


def calculate_psr(
    observed_sr_daily: float,
    benchmark_sr_daily: float,
    n_obs: int,
    skewness: float,
    kurtosis: float,
) -> float:
    """Calculate the Probabilistic Sharpe Ratio (PSR) for daily returns.

    Note: kurtosis is expected as Pearson kurtosis (normal=3, excess=0 is kurtosis-3).
    """
    if n_obs < 3:
        return 0.0
    
    # Calculate the variance of the Sharpe Ratio estimator
    # Formula: σ_SR^2 = (1 / (T-1)) * (1 + 0.5 * SR^2 - skew * SR + ((kurt - 3) / 4) * SR^2)
    excess_kurt = kurtosis - 3.0
    sr_var = (1.0 / (n_obs - 1)) * (
        1.0 + 0.5 * observed_sr_daily**2 - skewness * observed_sr_daily + (excess_kurt / 4.0) * observed_sr_daily**2
    )
    
    if sr_var <= 0:
        return 0.0
        
    sr_std = np.sqrt(sr_var)
    z_stat = (observed_sr_daily - benchmark_sr_daily) / sr_std
    return float(stats.norm.cdf(z_stat))


def calculate_expected_max_sr(
    all_srs_daily: list[float]  np.ndarray,
    n_trials: int,
) -> float:
    """Approximate the expected maximum Sharpe Ratio under multiple testing.

    Uses Bailey and López de Prado's extreme value theory approximation.
    """
    if n_trials == 1:
        return 0.0
        
    srs = np.array(all_srs_daily)
    mean_sr = np.mean(srs)
    std_sr = np.std(srs, ddof=1) if len(srs) > 1 else 0.0
    
    if std_sr == 0.0:
        return mean_sr
        
    gamma = 0.5772156649  # Euler-Mascheroni constant
    
    # Z^-1(1 - 1/N) and Z^-1(1 - 1/(N*e))
    n_term1 = 1.0 - 1.0 / n_trials
    n_term2 = 1.0 - 1.0 / (n_trials * np.e)
    
    # Clamp to avoid division by zero or domain errors
    n_term1 = np.clip(n_term1, 1e-12, 1.0 - 1e-12)
    n_term2 = np.clip(n_term2, 1e-12, 1.0 - 1e-12)
    
    z1 = stats.norm.ppf(n_term1)
    z2 = stats.norm.ppf(n_term2)
    
    expected_max = mean_sr + std_sr * ((1.0 - gamma) * z1 + gamma * z2)
    return float(expected_max)


def calculate_dsr(
    strategy_returns: pd.Series,
    all_trials_srs_daily: list[float]  np.ndarray,
    n_trials: int,
    periods_per_year: int = 252,
) -> float:
    """Calculate the Deflated Sharpe Ratio (DSR) for a strategy.

    Parameters
    ----------
    strategy_returns : pd.Series
        Daily return series of the selected strategy.
    all_trials_srs_daily : list or ndarray
        List of daily Sharpe Ratios for all N_trials.
    n_trials : int
        Total number of configurations in the parameter grid (e.g. 336).
    periods_per_year : int
        Trading sessions per year (default 252).

    Returns
    -------
    float
        DSR value (between 0.0 and 1.0).
    """
    clean_rets = strategy_returns.dropna()
    n_obs = len(clean_rets)
    if n_obs < 3:
        return 0.0
        
    # Calculate daily Sharpe of the strategy
    mean_ret = clean_rets.mean()
    std_ret = clean_rets.std(ddof=1)
    if std_ret == 0.0:
        return 0.0
        
    observed_sr_daily = mean_ret / std_ret
    
    # Calculate moments
    skewness = stats.skew(clean_rets)
    # scipy kurtosis defaults to excess kurtosis (Fisher), Pearson = excess + 3
    excess_kurt = stats.kurtosis(clean_rets, fisher=True)
    kurtosis = excess_kurt + 3.0
    
    # Calculate expected max Sharpe Ratio as the benchmark
    expected_max_sr_daily = calculate_expected_max_sr(all_trials_srs_daily, n_trials)
    
    # Calculate DSR as PSR using expected_max_sr as the benchmark
    return calculate_psr(
        observed_sr_daily=observed_sr_daily,
        benchmark_sr_daily=expected_max_sr_daily,
        n_obs=n_obs,
        skewness=skewness,
        kurtosis=kurtosis,
    )
