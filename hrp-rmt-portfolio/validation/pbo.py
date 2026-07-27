"""Module for calculating Probability of Backtest Overfitting (PBO).

Implements §16 and §25.4 of the protocol.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_pbo(
    trial_returns: pd.DataFrame,
    folds: list[dict],
) -> dict:
    """Calculate the Probability of Backtest Overfitting (PBO) using CPCV folds.

    Parameters
    ----------
    trial_returns : pd.DataFrame
        DataFrame of daily returns for all trials (dates × n_trials).
    folds : list of dict
        CPCV folds list containing 'train_dates' and 'test_dates'.

    Returns
    -------
    dict
        Dictionary with keys:
        - 'PBO': float (probability value, between 0.0 and 1.0)
        - 'rank_OOS_mean': float (mean percentile rank of selected trial OOS)
        - 'ranks_OOS': list of float (percentile ranks per fold)
    """
    n_trials = trial_returns.shape[1]
    if n_trials < 2:
        return {"PBO": 0.0, "rank_OOS_mean": 1.0, "ranks_OOS": []}
        
    overfit_count = 0
    ranks = []
    
    for fold in folds:
        train_dates = fold["train_dates"]
        test_dates = fold["test_dates"]
        
        # Slices
        rets_is = trial_returns.loc[train_dates]
        rets_oos = trial_returns.loc[test_dates]
        
        # Calculate daily Sharpe ratios
        mean_is = rets_is.mean()
        std_is = rets_is.std(ddof=1)
        # Avoid division by zero
        std_is = std_is.replace(0.0, np.nan)
        srs_is = (mean_is / std_is).fillna(-1000.0)
        
        mean_oos = rets_oos.mean()
        std_oos = rets_oos.std(ddof=1)
        std_oos = std_oos.replace(0.0, np.nan)
        srs_oos = (mean_oos / std_oos).fillna(-1000.0)
        
        # Find best trial in-sample
        best_trial_name = srs_is.idxmax()
        best_sr_oos = srs_oos[best_trial_name]
        
        # Percentile rank of the selected trial's OOS Sharpe ratio
        # How many trials had OOS Sharpe < best_sr_oos?
        smaller_count = (srs_oos < best_sr_oos).sum()
        rank = float(smaller_count) / (n_trials - 1)
        ranks.append(rank)
        
        # Overfitted if its OOS Sharpe is below the median OOS Sharpe
        median_oos = srs_oos.median()
        if best_sr_oos < median_oos:
            overfit_count += 1
            
    pbo = float(overfit_count) / len(folds) if len(folds) > 0 else 0.0
    
    return {
        "PBO": pbo,
        "rank_OOS_mean": float(np.mean(ranks)),
        "ranks_OOS": ranks,
    }
