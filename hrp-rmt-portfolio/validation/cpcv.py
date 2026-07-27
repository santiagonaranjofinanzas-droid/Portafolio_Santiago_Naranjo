"""Module for Combinatorial Purged Cross-Validation (CPCV).

Implements §14.3 of the protocol.
"""

from __future__ import annotations
import itertools
from typing import Iterator
import pandas as pd
from validation.purge_embargo import purge_and_embargo_indices


class CombinatorialPurgedCV:
    """Combinatorial Purged Cross-Validation.

    Splits the rebalance dates into N blocks, chooses k blocks for testing,
    and applies purging and embargoing to train dates.
    Also groups folds into disjoint OOS paths.
    """

    def __init__(
        self,
        n_splits: int = 6,
        n_test_splits: int = 2,
        lookback: int = 252,
        min_embargo: int = 22,
    ):
        if n_splits <= n_test_splits:
            raise ValueError("n_splits must be greater than n_test_splits.")
        self.n_splits = n_splits
        self.n_test_splits = n_test_splits
        self.lookback = lookback
        self.min_embargo = min_embargo

    def _get_block_bounds(
        self,
        rebalance_dates: pd.DatetimeIndex,
    ) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
        """Divide rebalance dates into contiguos blocks and return their start/end dates."""
        n = len(rebalance_dates)
        block_size = n // self.n_splits
        bounds = []
        
        for i in range(self.n_splits):
            start_idx = i * block_size
            # The last block absorbs any remainder
            end_idx = (i + 1) * block_size - 1 if i < self.n_splits - 1 else n - 1
            bounds.append((rebalance_dates[start_idx], rebalance_dates[end_idx]))
            
        return bounds

    def split(
        self,
        rebalance_dates: pd.DatetimeIndex  list[pd.Timestamp],
        all_daily_dates: pd.DatetimeIndex,
    ) -> list[dict]:
        """Generate CPCV folds.

        Each fold is a dictionary:
        {
            "fold_idx": int,
            "train_dates": list[pd.Timestamp],
            "test_dates": list[pd.Timestamp],
            "test_intervals": list[tuple[pd.Timestamp, pd.Timestamp]],
            "test_blocks": list[int]
        }
        """
        rebalance_dates = pd.DatetimeIndex(rebalance_dates).sort_values()
        all_daily_dates = pd.DatetimeIndex(all_daily_dates).sort_values()
        
        # Get start/end dates of each block
        block_bounds = self._get_block_bounds(rebalance_dates)
        
        # We also need to map each block index to its rebalance dates
        n_obs = len(rebalance_dates)
        block_size = n_obs // self.n_splits
        block_dates_list = []
        for i in range(self.n_splits):
            start_idx = i * block_size
            end_idx = (i + 1) * block_size - 1 if i < self.n_splits - 1 else n_obs - 1
            block_dates_list.append(rebalance_dates[start_idx : end_idx + 1].tolist())
            
        # Generate all combinations of test blocks of size n_test_splits
        block_indices = list(range(self.n_splits))
        combinations = list(itertools.combinations(block_indices, self.n_test_splits))
        
        folds = []
        for fold_idx, test_blocks in enumerate(combinations):
            # Test dates are the union of dates in the chosen test blocks
            test_dates_set = set()
            test_intervals = []
            for b_idx in test_blocks:
                test_dates_set.update(block_dates_list[b_idx])
                test_intervals.append(block_bounds[b_idx])
                
            test_dates = sorted(list(test_dates_set))
            
            # Apply purging and embargoing to the remaining training dates
            train_dates = purge_and_embargo_indices(
                all_rebalance_dates=rebalance_dates,
                test_intervals=test_intervals,
                all_daily_dates=all_daily_dates,
                lookback=self.lookback,
                min_embargo=self.min_embargo,
            )
            
            folds.append({
                "fold_idx": fold_idx,
                "train_dates": train_dates,
                "test_dates": test_dates,
                "test_intervals": test_intervals,
                "test_blocks": list(test_blocks),
            })
            
        return folds

    def generate_paths(self, folds: list[dict]) -> list[list[int]]:
        """Group folds into disjoint OOS paths.

        Each path is represented as a list of fold indices.
        A path must cover all blocks 0..N-1 exactly once.
        Returns a list of paths (each path is a list of fold_idx).
        """
        # Find all possible partitions of block_indices into blocks of size n_test_splits
        n_blocks_per_path = self.n_splits // self.n_test_splits
        block_set = set(range(self.n_splits))
        
        # Helper to recursively find partitions of folds
        partitions = []
        
        def find_partitions(current_partition, remaining_folds):
            # If partition covers all blocks, add it
            covered = set()
            for f in current_partition:
                covered.update(f["test_blocks"])
            if covered == block_set:
                partitions.append(current_partition.copy())
                return
                
            if len(current_partition) >= n_blocks_per_path:
                return
                
            for i, f in enumerate(remaining_folds):
                # Check if f's test blocks are disjoint from current_partition's covered blocks
                f_set = set(f["test_blocks"])
                if covered.isdisjoint(f_set):
                    find_partitions(current_partition + [f], remaining_folds[i + 1:])
                    
        find_partitions([], folds)
        
        # Now we need to select a subset of these partitions such that each fold is used
        # exactly once.
        # This is an exact cover problem. Since the number of folds is small (e.g. 15),
        # we can do a simple backtracking search over the found partitions.
        path_count = len(folds) // n_blocks_per_path
        
        exact_cover_partitions = []
        
        def find_exact_cover(current_paths, remaining_partitions, used_folds):
            if len(current_paths) == path_count:
                exact_cover_partitions.append(current_paths.copy())
                return True
                
            for i, part in enumerate(remaining_partitions):
                part_fold_ids = {f["fold_idx"] for f in part}
                if used_folds.isdisjoint(part_fold_ids):
                    success = find_exact_cover(
                        current_paths + [part],
                        remaining_partitions[i + 1:],
                        used_folds.union(part_fold_ids)
                    )
                    if success:
                        return True
            return False
            
        find_exact_cover([], partitions, set())
        
        if not exact_cover_partitions:
            # Fallback if no exact cover partition is found:
            # just return a subset of partitions that cover all blocks (some folds might be reused)
            # but for N=6, k=2, it will always find an exact cover.
            return [[f["fold_idx"] for f in part] for part in partitions[:path_count]]
            
        selected_partitions = exact_cover_partitions[0]
        paths = []
        for part in selected_partitions:
            paths.append([f["fold_idx"] for f in part])
            
        return paths
