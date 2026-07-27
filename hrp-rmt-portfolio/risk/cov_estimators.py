"""Module for various covariance estimators, including empirical, EWMA, and shrinkage."""

from __future__ import annotations
import numpy as np
import pandas as pd
from sklearn.covariance import ledoit_wolf, OAS


def is_psd(matrix: np.ndarray, tol: float = 1e-8) -> bool:
    """Check if a matrix is symmetric and positive semi-definite (eigenvalues >= -tol)."""
    if matrix.shape[0] != matrix.shape[1]:
        return False
    # Check symmetry
    if not np.allclose(matrix, matrix.T, atol=1e-8):
        return False
    # Check eigenvalues
    eigenvals = np.linalg.eigvalsh(matrix)
    return bool(np.all(eigenvals >= -tol))


def calculate_empirical_covariance(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the standard empirical (sample) covariance matrix."""
    df = returns_df.dropna(how="all")
    if df.empty:
        return pd.DataFrame()
    cov = df.cov()
    return cov


def calculate_ewma_covariance(returns_df: pd.DataFrame, decay_factor: float = 0.94) -> pd.DataFrame:
    """Calculate the EWMA covariance matrix recursively.
    
    Uses zero-mean formulation (RiskMetrics standard):
    Sigma_t = lambda * Sigma_{t-1} + (1 - lambda) * r_t * r_t^T
    """
    df = returns_df.dropna(how="all")
    if df.empty:
        return pd.DataFrame()

    # Drop any row containing NaNs for historical recursion
    df_clean = df.dropna()
    if df_clean.empty:
        return pd.DataFrame()

    N = df_clean.shape[1]
    
    # Initialize with empirical covariance of the same series
    cov = df_clean.cov().values

    # Recursive update
    for i in range(len(df_clean)):
        r = df_clean.iloc[i].values.reshape(-1, 1)
        cov = decay_factor * cov + (1 - decay_factor) * (r @ r.T)

    return pd.DataFrame(cov, index=df_clean.columns, columns=df_clean.columns)


def calculate_ledoit_wolf_covariance(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the Ledoit-Wolf shrinkage covariance matrix."""
    df = returns_df.dropna(how="all").dropna()
    if df.empty:
        return pd.DataFrame()
    
    # ledoit_wolf returns (shrunk_covariance, shrinkage)
    cov_arr, _ = ledoit_wolf(df.values)
    return pd.DataFrame(cov_arr, index=df.columns, columns=df.columns)


def calculate_oas_covariance(returns_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate the OAS shrinkage covariance matrix."""
    df = returns_df.dropna(how="all").dropna()
    if df.empty:
        return pd.DataFrame()
    
    oas_estimator = OAS().fit(df.values)
    cov_arr = oas_estimator.covariance_
    return pd.DataFrame(cov_arr, index=df.columns, columns=df.columns)
