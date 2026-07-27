"""Module for calculating Forecast Risk Error (FRE) of covariance estimators."""

from __future__ import annotations
import numpy as np
import pandas as pd


def calculate_matrix_fre(
    forecast_cov: pd.DataFrame  np.ndarray,
    realized_cov: pd.DataFrame  np.ndarray,
) -> float:
    """Calculate the matrix-level Forecast Risk Error using the Frobenius norm of the difference.
    
    FRE_matrix = sqrt( sum( (Sigma_f - Sigma_r)^2 ) / N^2 )
    """
    if isinstance(forecast_cov, pd.DataFrame):
        forecast_cov = forecast_cov.values
    if isinstance(realized_cov, pd.DataFrame):
        # Align columns and index if they are DataFrames
        common = forecast_cov.columns.intersection(realized_cov.columns)
        if len(common) < len(forecast_cov.columns):
            f_aligned = forecast_cov.loc[common, common].values
            r_aligned = realized_cov.loc[common, common].values
        else:
            f_aligned = forecast_cov.values
            r_aligned = realized_cov.values
    else:
        f_aligned = forecast_cov
        r_aligned = realized_cov

    n = f_aligned.shape[0]
    if n == 0:
        return 0.0
        
    diff = f_aligned - r_aligned
    frobenius_norm = np.sqrt(np.sum(diff ** 2))
    # Normalized by the number of elements
    return float(frobenius_norm / n)


def calculate_portfolio_fre(
    forecast_cov: pd.DataFrame  np.ndarray,
    realized_cov: pd.DataFrame  np.ndarray,
    weights: dict[str, float]  np.ndarray  pd.Series,
) -> float:
    """Calculate the portfolio-level Forecast Risk Error.
    
    FRE_portfolio =  w^T Sigma_f w - w^T Sigma_r w 
    """
    if isinstance(forecast_cov, pd.DataFrame):
        # Align weights with covariance DataFrame
        if isinstance(weights, dict):
            w_series = pd.Series(weights)
        elif isinstance(weights, np.ndarray):
            w_series = pd.Series(weights, index=forecast_cov.columns)
        else:
            w_series = weights
            
        common = forecast_cov.columns.intersection(w_series.index)
        f_mat = forecast_cov.loc[common, common].values
        if isinstance(realized_cov, pd.DataFrame):
            r_mat = realized_cov.loc[common, common].values
        else:
            r_mat = realized_cov
            
        w_vec = w_series.loc[common].values
    else:
        f_mat = forecast_cov
        r_mat = realized_cov
        w_vec = weights

    if len(w_vec) == 0:
        return 0.0

    # Ensure weights are normalized for variance comparison
    w_sum = np.sum(w_vec)
    if w_sum > 0:
        w_vec = w_vec / w_sum

    f_variance = w_vec.T @ f_mat @ w_vec
    r_variance = w_vec.T @ r_mat @ w_vec
    
    return float(np.abs(f_variance - r_variance))
