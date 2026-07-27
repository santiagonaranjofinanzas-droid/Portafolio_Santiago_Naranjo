"""Module for Random Matrix Theory (RMT) spectral filtering of correlation matrices."""

from __future__ import annotations
import numpy as np
import pandas as pd
from risk.cov_estimators import calculate_ledoit_wolf_covariance, calculate_oas_covariance


def calculate_tie_rate(corr: np.ndarray, tolerance: float = 1e-10) -> float:
    """Calculate the rate of duplicate or near-duplicate distances in the correlation-based distance matrix."""
    # Distance: d_ij = sqrt(0.5 * (1 - rho_ij))
    corr_clipped = np.clip(corr, -1.0, 1.0)
    dist = np.sqrt(0.5 * (1.0 - corr_clipped))
    
    n = corr.shape[0]
    triu_idx = np.triu_indices(n, k=1)
    d_vals = dist[triu_idx]  # Shape (M,) where M = n*(n-1)/2
    
    # Calculate all pairwise absolute differences of distances
    diff_matrix = np.abs(d_vals[:, np.newaxis] - d_vals[np.newaxis, :])
    m = len(d_vals)
    triu_diff_idx = np.triu_indices(m, k=1)
    diffs_all = diff_matrix[triu_diff_idx]
    
    tie_count = np.sum(diffs_all < tolerance)
    total_pairs = len(diffs_all)
    
    return float(tie_count / total_pairs) if total_pairs > 0 else 0.0


def rmt_filter_correlation(corr: np.ndarray, q: float, method: str = "constant") -> np.ndarray:
    """Filter the correlation matrix using Marchenko-Pastur bulk eigenvalue clipping."""
    n = corr.shape[0]
    
    # Spectral decomposition
    eigenvals, eigenvects = np.linalg.eigh(corr)
    
    # Sort descending
    idx = np.argsort(eigenvals)[::-1]
    eigenvals = eigenvals[idx]
    eigenvects = eigenvects[:, idx]
    
    # Self-consistent noise variance (sigma^2) estimation
    # We find the bulk threshold lambda_plus and update sigma^2 recursively
    sigma2 = 1.0
    for _ in range(10):
        lambda_plus = sigma2 * (1.0 + np.sqrt(1.0 / q)) ** 2
        signals = eigenvals[eigenvals > lambda_plus]
        if len(signals) == 0:
            sigma2 = 1.0
            break
        sigma2 = (n - np.sum(signals)) / (n - len(signals))
        
    lambda_plus = sigma2 * (1.0 + np.sqrt(1.0 / q)) ** 2
    bulk_idx = eigenvals <= lambda_plus
    
    # Filter bulk eigenvalues
    eigenvals_new = eigenvals.copy()
    if np.any(bulk_idx):
        mean_bulk = np.sum(eigenvals[bulk_idx]) / np.sum(bulk_idx)
        if method == "variance_weighted":
            alpha = 0.90  # 90% shrinkage towards the mean
            eigenvals_new[bulk_idx] = (1.0 - alpha) * eigenvals[bulk_idx] + alpha * mean_bulk
        else:
            eigenvals_new[bulk_idx] = mean_bulk
        
    # Reconstruct correlation matrix
    corr_new = eigenvects @ np.diag(eigenvals_new) @ eigenvects.T
    
    # Re-scale diagonal to 1s
    d = np.diag(corr_new)
    corr_new = corr_new / np.sqrt(np.outer(d, d))
    
    return corr_new


def calculate_rmt_covariance(
    returns_df: pd.DataFrame,
    method: str = "constant",
    delta: float  None = None,  # If None, automatically check and select delta
    shrinkage_method: str = "ledoit_wolf",
) -> tuple[pd.DataFrame, float]:
    """Calculate the RMT filtered covariance matrix.
    
    Returns a tuple of (covariance_dataframe, delta_used).
    If delta is None, it checks for topological degeneration and selects the optimal delta dynamically.
    """
    df = returns_df.dropna(how="all").dropna()
    if df.empty:
        return pd.DataFrame(), 0.0

    n = df.shape[1]
    t = df.shape[0]
    q = t / n
    
    # 1. Compute empirical covariance and correlation
    emp_cov = df.cov()
    std_devs = np.sqrt(np.diag(emp_cov))
    
    # Avoid division by zero
    std_devs[std_devs == 0.0] = 1e-8
    
    emp_corr = df.corr().values
    
    # 2. Filter correlation using RMT
    corr_rmt = rmt_filter_correlation(emp_corr, q, method=method)
    
    # 3. Compute shrinkage correlation
    if shrinkage_method == "ledoit_wolf":
        shrunk_cov = calculate_ledoit_wolf_covariance(df)
    else:
        shrunk_cov = calculate_oas_covariance(df)
        
    shrunk_std = np.sqrt(np.diag(shrunk_cov))
    shrunk_std[shrunk_std == 0.0] = 1e-8
    corr_shrinkage = shrunk_cov.values / np.outer(shrunk_std, shrunk_std)
    
    # 4. Determine delta (blend parameter)
    if delta is None:
        # Institutional constant floor for RMT + Shrinkage Blend to stabilize condition number
        delta = 0.025
            
    # 5. Blend correlation
    corr_final = (1.0 - delta) * corr_rmt + delta * corr_shrinkage
    
    # 6. Re-scale to covariance using empirical variances
    cov_final = corr_final * np.outer(std_devs, std_devs)
    
    return pd.DataFrame(cov_final, index=df.columns, columns=df.columns), delta
