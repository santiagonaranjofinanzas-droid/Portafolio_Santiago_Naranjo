"""Audit verification script to check for mathematical correctness and edge cases in F0-F4 modules."""

from __future__ import annotations
import numpy as np
import pandas as pd

from risk.cov_estimators import is_psd, calculate_empirical_covariance
from risk.rmt_filter import calculate_tie_rate, rmt_filter_correlation
from portfolio.clustering import correlation_to_distance, generate_linkage_matrix, get_quasi_diag_order
from portfolio.hrp import calculate_hrp_weights, redistribute_weights_proportional, redistribute_weights_hierarchical


def run_audit() -> dict[str, object]:
    results = {}
    
    # 1. Test PSD detector with boundary cases
    psd_matrix = np.array([[1.0, 0.5], [0.5, 1.0]])
    non_psd_matrix = np.array([[1.0, 1.5], [1.5, 1.0]]) # eigenvalues: 2.5 and -0.5
    asymmetric_matrix = np.array([[1.0, 0.4], [0.6, 1.0]])
    
    results["psd_check"] = {
        "psd_matrix_ok": is_psd(psd_matrix),
        "non_psd_matrix_caught": not is_psd(non_psd_matrix),
        "asymmetric_matrix_caught": not is_psd(asymmetric_matrix),
    }

    # 2. Test RMT trace preservation
    np.random.seed(42)
    t, n = 252, 45
    q = t / n
    # Generate random returns
    rets = np.random.normal(0, 0.01, (t, n))
    corr = np.corrcoef(rets, rowvar=False)
    
    filtered_corr = rmt_filter_correlation(corr, q, method="constant")
    
    results["rmt_check"] = {
        "filtered_shape_ok": filtered_corr.shape == (n, n),
        "filtered_diag_ones_ok": np.allclose(np.diag(filtered_corr), 1.0),
        "filtered_psd_ok": is_psd(filtered_corr),
        "filtered_trace_ok": np.allclose(np.trace(filtered_corr), n),
    }

    # 3. Test HRP weights sum and bounds
    cov = pd.DataFrame(np.cov(rets, rowvar=False))
    # Add index and columns
    tickers = [f"ETF_{i}" for i in range(n)]
    cov.index = tickers
    cov.columns = tickers
    
    hrp_res_hierarchical = calculate_hrp_weights(
        cov,
        linkage_method="ward",
        cap=0.15,
        redistribution_method="hierarchical",
        cash_ticker="ETF_0",
    )
    
    hrp_res_proportional = calculate_hrp_weights(
        cov,
        linkage_method="ward",
        cap=0.15,
        redistribution_method="proportional",
        cash_ticker="ETF_0",
    )
    
    results["hrp_check"] = {
        "pure_weights_sum_ok": np.allclose(hrp_res_hierarchical["weights_pure"].sum(), 1.0, atol=1e-6),
        "restricted_hierarchical_sum_ok": np.allclose(hrp_res_hierarchical["weights_restricted"].sum(), 1.0, atol=1e-6),
        "restricted_proportional_sum_ok": np.allclose(hrp_res_proportional["weights_restricted"].sum(), 1.0, atol=1e-6),
        "hierarchical_non_neg_ok": np.all(hrp_res_hierarchical["weights_restricted"] >= 0.0),
        "proportional_non_neg_ok": np.all(hrp_res_proportional["weights_restricted"] >= 0.0),
        "hierarchical_non_cash_capped_ok": np.all(hrp_res_hierarchical.loc[tickers[1:], "weights_restricted"] <= 0.15 + 1e-12),
        "proportional_non_cash_capped_ok": np.all(hrp_res_proportional.loc[tickers[1:], "weights_restricted"] <= 0.15 + 1e-12),
    }
    
    # 4. Cash Capping Sensitivity Check
    # What if we strictly cap the cash ticker as well?
    # Let's test capping all assets (including cash) to see if HRP can find a valid solution
    # when cash is capped at 15% too.
    w_pure = hrp_res_hierarchical["weights_pure"].copy()
    # We call proportional capping without a cash sink by setting cash_ticker to a dummy name not in weights
    w_restricted_all_capped = redistribute_weights_proportional(w_pure, cap=0.15, cash_ticker="DUMMY_NOT_IN_INDEX")
    
    results["cash_capping_check"] = {
        "all_capped_sum_ok": np.allclose(w_restricted_all_capped.sum(), 1.0, atol=1e-6),
        "all_capped_non_neg_ok": np.all(w_restricted_all_capped >= 0.0),
        "all_assets_under_15_ok": np.all(w_restricted_all_capped <= 0.15 + 1e-12),
    }

    return results


def make_serializable(obj):
    if isinstance(obj, dict):
        return {k: make_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_serializable(x) for x in obj]
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    return obj


if __name__ == "__main__":
    import json
    res = run_audit()
    print(json.dumps(make_serializable(res), indent=2))
