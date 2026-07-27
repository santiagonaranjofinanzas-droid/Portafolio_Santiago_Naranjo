"""Module for HRP portfolio weight allocation, recursive bisection, and cap redistribution."""

from __future__ import annotations
import numpy as np
import pandas as pd
from portfolio.clustering import correlation_to_distance, generate_linkage_matrix, get_quasi_diag_order


def get_cluster_var(cov: np.ndarray, cluster_indices: list[int]) -> float:
    """Calculate the variance of a cluster using inverse variance weights of its constituents."""
    cov_slice = cov[np.ix_(cluster_indices, cluster_indices)]
    diag = np.diag(cov_slice).copy()
    
    # Handle zero variance assets
    diag[diag == 0.0] = 1e-8
    
    inv_var = 1.0 / diag
    w = inv_var / np.sum(inv_var)
    return float(w.T @ cov_slice @ w)


def calculate_hrp_weights(
    cov: pd.DataFrame,
    linkage_method: str = "single",
    cap: float = 0.15,
    redistribution_method: str = "hierarchical",
    cash_ticker: str = "BIL",
) -> pd.DataFrame:
    """Calculate HRP weights from a covariance matrix.
    
    Returns a DataFrame with:
    - 'weights_pure': Pure HRP weights.
    - 'weights_restricted': HRP weights restricted by caps (15% by default) and redistributed.
    """
    if cov.empty:
        return pd.DataFrame(columns=["weights_pure", "weights_restricted"])

    tickers = cov.columns.tolist()
    n = len(tickers)

    # 1. Distance and Linkage
    # Compute correlation from covariance
    std_devs = np.sqrt(np.diag(cov.values))
    std_devs[std_devs == 0.0] = 1e-8
    corr = cov.values / np.outer(std_devs, std_devs)
    corr_df = pd.DataFrame(corr, index=tickers, columns=tickers)
    
    dist = correlation_to_distance(corr_df)
    linkage_matrix = generate_linkage_matrix(dist.values, method=linkage_method)
    
    # 2. Quasi-diagonalization order
    ordered_indices = get_quasi_diag_order(linkage_matrix)
    ordered_tickers = [tickers[i] for i in ordered_indices]

    # 3. Recursive Bisection Weight Allocation
    weights_pure = pd.Series(1.0, index=ordered_tickers)
    
    def recursive_bisection(leaves: list[str]) -> None:
        if len(leaves) <= 1:
            return

        # Split current leaves in half
        split_idx = len(leaves) // 2
        left_leaves = leaves[:split_idx]
        right_leaves = leaves[split_idx:]

        # Map leaves to positions in the original covariance matrix
        left_idx = [tickers.index(t) for t in left_leaves]
        right_idx = [tickers.index(t) for t in right_leaves]

        # Calculate cluster variances
        var_left = get_cluster_var(cov.values, left_idx)
        var_right = get_cluster_var(cov.values, right_idx)

        # Allocate weights between clusters
        # If both variances are 0, allocate 50/50
        if var_left + var_right == 0.0:
            alpha = 0.5
        else:
            alpha = 1.0 - var_left / (var_left + var_right)

        # Apply allocation factors to all constituents of the sub-clusters
        weights_pure.loc[left_leaves] *= alpha
        weights_pure.loc[right_leaves] *= (1.0 - alpha)

        # Recurse
        recursive_bisection(left_leaves)
        recursive_bisection(right_leaves)

    recursive_bisection(ordered_tickers)
    
    # Re-align weights_pure with the original order of tickers
    weights_pure = weights_pure.loc[tickers]

    # 4. Cap Redistribution
    if redistribution_method == "hierarchical":
        weights_restricted = redistribute_weights_hierarchical(
            weights_pure, linkage_matrix, cap=cap, cash_ticker=cash_ticker
        )
    elif redistribution_method == "proportional":
        weights_restricted = redistribute_weights_proportional(
            weights_pure, cap=cap, cash_ticker=cash_ticker
        )
    elif redistribution_method == "none":
        weights_restricted = redistribute_weights_none(
            weights_pure, cap=cap, cash_ticker=cash_ticker
        )
    else:
        raise ValueError(f"Unknown redistribution method: {redistribution_method}")

    # 5. Output DataFrame
    result = pd.DataFrame(index=tickers)
    result["weights_pure"] = weights_pure
    result["weights_restricted"] = weights_restricted
    return result


def redistribute_weights_proportional(
    weights: pd.Series,
    cap: float = 0.15,
    cash_ticker: str = "BIL",
) -> pd.Series:
    """Redistribute excess weights above cap proportionally to other non-saturated assets."""
    w = weights.copy()
    tickers = w.index.tolist()
    
    # We loop up to 100 times to handle cascade saturations
    for _ in range(100):
        # Exclude cash_ticker from the cap checks since it is the residual cash sink
        exceeding = w[w.index != cash_ticker]
        exceeding = exceeding[exceeding > cap]
        if exceeding.empty:
            break
            
        for ticker in exceeding.index:
            excess = w[ticker] - cap
            w[ticker] = cap
            
            # Find all non-saturated assets (excluding cash_ticker and self)
            non_saturated = [t for t in tickers if t != ticker and t != cash_ticker and w[t] < cap]
            if non_saturated:
                sum_ns = w[non_saturated].sum()
                if sum_ns > 0:
                    allocations = (w[non_saturated] / sum_ns) * excess
                else:
                    allocations = pd.Series(excess / len(non_saturated), index=non_saturated)
                    
                for t in non_saturated:
                    space = cap - w[t]
                    allocated = min(space, allocations[t])
                    w[t] += allocated
                    excess -= allocated
                    if excess <= 1e-12:
                        break
                        
            if excess > 1e-12:
                # Add remainder to cash
                if cash_ticker in w.index:
                    w[cash_ticker] += excess
                else:
                    w[cash_ticker] = excess
                excess = 0.0
                
    return w


def redistribute_weights_hierarchical(
    weights: pd.Series,
    linkage_matrix: np.ndarray,
    cap: float = 0.15,
    cash_ticker: str = "BIL",
) -> pd.Series:
    """Redistribute excess weights walking up the tree structure to find sibling/cousin clusters."""
    w = weights.copy()
    n = len(w)
    tickers = w.index.tolist()
    ticker_to_idx = {ticker: i for i, ticker in enumerate(tickers)}
    idx_to_ticker = {i: ticker for i, ticker in enumerate(tickers)}
    
    if not (w > cap).any():
        return w
        
    # Build tree parent and sibling maps
    parent = {}
    children = {}
    for i, row in enumerate(linkage_matrix):
        left, right = int(row[0]), int(row[1])
        parent_node = n + i
        parent[left] = parent_node
        parent[right] = parent_node
        children[parent_node] = [left, right]
        
    def get_leaves(node: int) -> list[int]:
        if node < n:
            return [node]
        left, right = children[node]
        return get_leaves(left) + get_leaves(right)
        
    for _ in range(100):
        exceeding = w[w.index != cash_ticker]
        exceeding = exceeding[exceeding > cap]
        if exceeding.empty:
            break
            
        for ticker in exceeding.index:
            excess = w[ticker] - cap
            w[ticker] = cap
            idx = ticker_to_idx[ticker]
            
            # Walk up tree to distribute excess
            curr_node = idx
            excess_remaining = excess
            
            while curr_node in parent and excess_remaining > 1e-12:
                parent_node = parent[curr_node]
                left, right = children[parent_node]
                sibling_node = right if curr_node == left else left
                
                sibling_leaves_idx = get_leaves(sibling_node)
                sibling_tickers = [idx_to_ticker[i] for i in sibling_leaves_idx if idx_to_ticker[i] != cash_ticker]
                
                non_saturated = [t for t in sibling_tickers if w[t] < cap]
                if non_saturated:
                    non_saturated_weights = w[non_saturated]
                    sum_ns_weights = non_saturated_weights.sum()
                    
                    if sum_ns_weights > 0:
                        allocations = (non_saturated_weights / sum_ns_weights) * excess_remaining
                    else:
                        allocations = pd.Series(excess_remaining / len(non_saturated), index=non_saturated)
                        
                    for t in non_saturated:
                        space = cap - w[t]
                        allocated = min(space, allocations[t])
                        w[t] += allocated
                        excess_remaining -= allocated
                        if excess_remaining <= 1e-12:
                            break
                
                curr_node = parent_node
                
            # If we reached the root and still have excess, assign to cash
            if excess_remaining > 1e-12:
                if cash_ticker in w.index:
                    w[cash_ticker] += excess_remaining
                else:
                    # If cash ticker doesn't exist, distribute proportional to HRP weights
                    non_saturated_all = [t for t in tickers if w[t] < cap]
                    if non_saturated_all:
                        alloc = excess_remaining / len(non_saturated_all)
                        for t in non_saturated_all:
                            w[t] += alloc
                    else:
                        w[cash_ticker] = excess_remaining
    return w


def redistribute_weights_none(
    weights: pd.Series,
    cap: float = 0.15,
    cash_ticker: str = "BIL",
) -> pd.Series:
    """Clip weights to cap and assign excess directly to the cash sink without redistribution."""
    w = weights.copy()
    excess = 0.0
    for ticker in w.index:
        if ticker != cash_ticker and w[ticker] > cap:
            excess += w[ticker] - cap
            w[ticker] = cap
    if excess > 0.0:
        if cash_ticker in w.index:
            w[cash_ticker] += excess
        else:
            w[cash_ticker] = excess
    return w
