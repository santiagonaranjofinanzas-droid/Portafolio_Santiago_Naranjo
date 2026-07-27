"""Unit tests for covariance estimators, RMT spectral filtering, clustering, and HRP weights allocation."""

from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from risk.cov_estimators import (
    is_psd,
    calculate_empirical_covariance,
    calculate_ewma_covariance,
    calculate_ledoit_wolf_covariance,
    calculate_oas_covariance,
)
from risk.rmt_filter import calculate_tie_rate, rmt_filter_correlation, calculate_rmt_covariance
from risk.forecast_risk_error import calculate_matrix_fre, calculate_portfolio_fre
from portfolio.clustering import correlation_to_distance, generate_linkage_matrix, get_quasi_diag_order
from portfolio.hrp import calculate_hrp_weights


@pytest.fixture
def sample_returns() -> pd.DataFrame:
    """Fixture containing a small DataFrame of mock daily simple returns."""
    np.random.seed(42)
    dates = pd.date_range("2026-01-01", periods=100)
    # Generate 5 assets returns with correlation
    factor = np.random.normal(0, 0.01, 100)
    data = {}
    for i in range(5):
        noise = np.random.normal(0, 0.01, 100)
        # Add factor to induce positive correlation
        data[f"Asset_{i}"] = 0.5 * factor + noise
        
    df = pd.DataFrame(data, index=dates)
    # Insert first row as NaN since returns are computed from prices
    df.iloc[0] = np.nan
    return df


def test_covariance_estimators(sample_returns):
    """Verify that all covariance estimators return symmetric, PSD, and valid matrices."""
    # Test empirical
    emp = calculate_empirical_covariance(sample_returns)
    assert emp.shape == (5, 5)
    assert is_psd(emp.values)

    # Test EWMA
    ewma = calculate_ewma_covariance(sample_returns)
    assert ewma.shape == (5, 5)
    assert is_psd(ewma.values)

    # Test Ledoit-Wolf
    lw = calculate_ledoit_wolf_covariance(sample_returns)
    assert lw.shape == (5, 5)
    assert is_psd(lw.values)

    # Test OAS
    oas = calculate_oas_covariance(sample_returns)
    assert oas.shape == (5, 5)
    assert is_psd(oas.values)


def test_rmt_clipping():
    """Verify Marchenko-Pastur bulk clipping preserves trace and changes only bulk eigenvalues."""
    # Create correlation matrix with 1 strong factor (eigenval ~ 4) and 4 noise factors
    np.random.seed(42)
    n = 5
    corr = np.eye(n)
    corr[0, 1] = corr[1, 0] = 0.8
    corr[0, 2] = corr[2, 0] = 0.8
    corr[1, 2] = corr[2, 1] = 0.8

    # Make it positive definite
    corr = corr + np.eye(n) * 0.1
    d = np.diag(corr)
    corr = corr / np.sqrt(np.outer(d, d))
    
    # Run Marchenko-Pastur bulk filter (q = T/N = 100/5 = 20)
    filtered_corr = rmt_filter_correlation(corr, q=20.0, method="constant")
    
    assert filtered_corr.shape == (5, 5)
    assert np.allclose(np.diag(filtered_corr), 1.0)
    assert is_psd(filtered_corr)


def test_tie_rate():
    """Verify that the tie rate calculation works correctly."""
    # Create correlation matrix with duplicate values (identical off-diagonal elements)
    corr = np.array([
        [1.0, 0.5, 0.5],
        [0.5, 1.0, 0.5],
        [0.5, 0.5, 1.0]
    ])
    
    # Off-diagonal elements are all 0.5, so distance is sqrt(0.5*(1-0.5)) = 0.5
    # Since all 3 distances are identical, all 3 pairwise differences are 0 (< tolerance)
    # The number of unique pairs is M = 3. The number of pairs of distances is M*(M-1)/2 = 3.
    # All 3 pairs have diff = 0. So tie rate should be 1.0.
    rate = calculate_tie_rate(corr, tolerance=1e-10)
    assert rate == 1.0


def test_forecast_risk_error():
    """Verify that Forecast Risk Error (FRE) calculations output correct types and dimensions."""
    cov_f = np.eye(3) * 0.01
    cov_r = np.eye(3) * 0.012
    
    # Matrix FRE
    m_fre = calculate_matrix_fre(cov_f, cov_r)
    assert isinstance(m_fre, float)
    assert m_fre == pytest.approx(np.sqrt(3 * (0.002**2)) / 3)
    
    # Portfolio FRE
    weights = np.array([0.5, 0.3, 0.2])
    p_fre = calculate_portfolio_fre(cov_f, cov_r, weights)
    assert isinstance(p_fre, float)
    # w^T * Sigma_f * w = 0.01 * (0.5^2 + 0.3^2 + 0.2^2) = 0.01 * 0.38 = 0.0038
    # w^T * Sigma_r * w = 0.012 * 0.38 = 0.00456
    # p_fre = 0.0038 - 0.00456 = 0.00076
    assert p_fre == pytest.approx(0.00076)


def test_clustering_and_linkage(sample_returns):
    """Verify correlation-to-distance conversion and leaf ordering tree properties."""
    emp_cov = calculate_empirical_covariance(sample_returns)
    std_devs = np.sqrt(np.diag(emp_cov.values))
    corr = emp_cov.values / np.outer(std_devs, std_devs)
    
    dist = correlation_to_distance(corr)
    assert dist.shape == (5, 5)
    assert np.allclose(np.diag(dist), 0.0)
    assert np.all(dist >= 0.0)
    
    linkage_matrix = generate_linkage_matrix(dist, method="single")
    # Z has shape (N-1, 4)
    assert linkage_matrix.shape == (4, 4)
    
    order = get_quasi_diag_order(linkage_matrix)
    assert len(order) == 5
    assert set(order) == {0, 1, 2, 3, 4}


def test_hrp_weights_allocation(sample_returns):
    """Verify HRP weight sum, non-negativity, and cap compliance."""
    emp_cov = calculate_empirical_covariance(sample_returns)
    
    # Run HRP with Ward linkage and hierarchical cap redistribution
    res = calculate_hrp_weights(
        emp_cov,
        linkage_method="ward",
        cap=0.15,
        redistribution_method="hierarchical",
        cash_ticker="Asset_0",
    )
    
    assert res.shape == (5, 2)
    assert "weights_pure" in res.columns
    assert "weights_restricted" in res.columns
    
    # Verify pure HRP weights sum to 1.0 (within tolerance)
    assert res["weights_pure"].sum() == pytest.approx(1.0, abs=1e-7)
    assert np.all(res["weights_pure"] >= 0.0)
    
    # Verify restricted HRP weights sum to 1.0
    assert res["weights_restricted"].sum() == pytest.approx(1.0, abs=1e-7)
    assert np.all(res["weights_restricted"] >= 0.0)
    
    # Verify that all non-cash assets are strictly capped at 15%
    non_cash_assets = res.index[res.index != "Asset_0"]
    assert np.all(res.loc[non_cash_assets, "weights_restricted"] <= 0.15 + 1e-12)
