"""Module for distance computation, hierarchical clustering, and seriation (leaves ordering)."""

from __future__ import annotations
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform


def correlation_to_distance(corr: np.ndarray  pd.DataFrame) -> np.ndarray  pd.DataFrame:
    """Calculate the correlation distance matrix.
    
    d_ij = sqrt(0.5 * (1 - rho_ij))
    """
    if isinstance(corr, pd.DataFrame):
        corr_val = corr.values
    else:
        corr_val = corr

    # Clip correlation to [-1.0, 1.0] to prevent tiny numerical rounding errors
    # yielding negative values before sqrt
    corr_clipped = np.clip(corr_val, -1.0, 1.0)
    dist = np.sqrt(0.5 * (1.0 - corr_clipped))

    # Enforce exact symmetry
    dist = 0.5 * (dist + dist.T)
    
    # Zero out diagonal elements
    np.fill_diagonal(dist, 0.0)

    if isinstance(corr, pd.DataFrame):
        return pd.DataFrame(dist, index=corr.index, columns=corr.columns)
    return dist


def generate_linkage_matrix(dist_matrix: np.ndarray, method: str = "single") -> np.ndarray:
    """Generate the linkage matrix from a square distance matrix.
    
    Supported methods: 'single', 'complete', 'average', 'ward'
    """
    # Convert square matrix to condensed form required by scipy linkage
    condensed_dist = squareform(dist_matrix)
    
    # Run linkage
    return linkage(condensed_dist, method=method)


def get_quasi_diag_order(linkage_matrix: np.ndarray) -> list[int]:
    """Retrieve the leaf ordering (seriation) from the linkage matrix using recursive tree traversal."""
    n = linkage_matrix.shape[0] + 1
    
    # Map parent node to children
    adj = {}
    for i in range(n - 1):
        left = int(linkage_matrix[i, 0])
        right = int(linkage_matrix[i, 1])
        adj[n + i] = [left, right]

    # Recursive traversal to collect leaves
    def traverse(node: int) -> list[int]:
        if node < n:
            return [node]
        left, right = adj[node]
        return traverse(left) + traverse(traverse_sort_helper(left, right, adj))
        
    # Standard depth-first search (DFS) traversal
    def get_leaves_recursive(node: int) -> list[int]:
        if node < n:
            return [node]
        left, right = adj[node]
        return get_leaves_recursive(left) + get_leaves_recursive(right)

    # The root node is index 2*n - 2 (since leaves are 0 to n-1 and merges are n to 2n-2)
    root = 2 * n - 2
    return get_leaves_recursive(root)


def traverse_sort_helper(left: int, right: int, adj: dict[int, list[int]]) -> int:
    """Helper function to keep traverse signature clean."""
    return right
