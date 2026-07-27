"""Unit tests for Phase F6 (CPCV Validation).

Follows TDD as mandated by §4 of .agent rules.
"""

from __future__ import annotations
import pytest
import pandas as pd
import numpy as np
from validation.purge_embargo import get_embargo_days, purge_and_embargo_indices
from validation.cpcv import CombinatorialPurgedCV
from validation.dsr import calculate_dsr
from validation.pbo import calculate_pbo


def test_get_embargo_days():
    """Verify that embargo is max(22, 5% of OOS daily dates)."""
    assert get_embargo_days(100) == 22
    assert get_embargo_days(500) == 25  # 5% of 500 is 25
    assert get_embargo_days(0) == 22


def test_purge_and_embargo_boundaries():
    """Verify purging and embargo boundaries on a small synthetic series.

    Assume lookback L = 3 daily days, embargo H = 2 daily days.
    """
    daily_dates = pd.date_range("2020-01-01", periods=15, freq="D")
    rebalance_dates = pd.date_range("2020-01-01", periods=15, freq="2D")  # rebalances every 2 days
    
    # Let's say test interval is from Day 6 to Day 8
    # 2020-01-06 (index 5) to 2020-01-08 (index 7)
    test_intervals = [(pd.Timestamp("2020-01-06"), pd.Timestamp("2020-01-08"))]
    
    train_dates = purge_and_embargo_indices(
        all_rebalance_dates=rebalance_dates,
        test_intervals=test_intervals,
        all_daily_dates=daily_dates,
        lookback=3,
        min_embargo=2,
    )
    
    # Candidates in rebalance_dates (every 2 days starting Jan 1):
    # Jan 01 (idx 0), Jan 03 (idx 2), Jan 05 (idx 4), Jan 07 (idx 6) -> in test block
    # Jan 09 (idx 8), Jan 11 (idx 10), Jan 13 (idx 12), Jan 15 (idx 14)
    #
    # Test block: Jan 6 to Jan 8.
    # Rebalance Jan 7 is in test block -> Excluded.
    # Rebalances before test block:
    # Jan 01: lookback [Dec 29, Dec 31] -> no overlap -> Train
    # Jan 03: lookback [Dec 31, Jan 02] -> no overlap -> Train
    # Jan 05: lookback [Jan 02, Jan 04] -> no overlap -> Train
    #
    # Rebalances after test block (end_test = Jan 8, index 7):
    # Purge window: L = 3 daily days after end_test -> Jan 9, Jan 10, Jan 11 (indices 8, 9, 10).
    # Embargo window: H = 2 daily days after purge -> Jan 12, Jan 13 (indices 11, 12).
    # Total excluded region after end_test: up to index 7 + 3 + 2 = 12 (Jan 13).
    # So any rebalance date <= Jan 13 is excluded.
    # Let's check rebalance dates:
    # Jan 09 (idx 8) -> Excluded
    # Jan 11 (idx 10) -> Excluded
    # Jan 13 (idx 12) -> Excluded
    # Jan 15 (idx 14) -> Train (starts lookback at Jan 12, which is end_test + H + 1, index 11. Wait, lookback of Jan 15 is [Jan 12, Jan 14]. Since Jan 12 >= end_test + H + 1, index 7+2+1 = 10 (Jan 11), yes it's valid!)
    # Actually, let's verify if Jan 15 is in train_dates.
    
    expected_train = [
        pd.Timestamp("2020-01-01"),
        pd.Timestamp("2020-01-03"),
        pd.Timestamp("2020-01-05"),
        pd.Timestamp("2020-01-15"),
        pd.Timestamp("2020-01-17"),
        pd.Timestamp("2020-01-19"),
        pd.Timestamp("2020-01-21"),
        pd.Timestamp("2020-01-23"),
        pd.Timestamp("2020-01-25"),
        pd.Timestamp("2020-01-27"),
        pd.Timestamp("2020-01-29"),
    ]
    assert train_dates == expected_train


class TestCPCV:
    @pytest.fixture
    def sample_dates(self):
        daily_dates = pd.bdate_range("2015-01-01", "2025-12-31")
        # Rebalances on the last business day of each month
        rebalance_dates = pd.DatetimeIndex(
            daily_dates.to_series().groupby([daily_dates.year, daily_dates.month]).last()
        )
        return rebalance_dates, daily_dates

    def test_cpcv_combinatorics(self, sample_dates):
        """Verify that CPCV generates exactly 15 folds for N=6, k=2."""
        rebalance_dates, daily_dates = sample_dates
        cv = CombinatorialPurgedCV(n_splits=6, n_test_splits=2, lookback=252, min_embargo=22)
        folds = cv.split(rebalance_dates, daily_dates)
        
        assert len(folds) == 15  # 6 choose 2 = 15
        
        # Check fold structure
        for fold in folds:
            assert "train_dates" in fold
            assert "test_dates" in fold
            assert "test_intervals" in fold
            assert "test_blocks" in fold
            assert len(fold["test_blocks"]) == 2

    def test_no_leakage_and_overlap(self, sample_dates):
        """Verify that in all folds, there is no overlap between train and test dates."""
        rebalance_dates, daily_dates = sample_dates
        cv = CombinatorialPurgedCV(n_splits=6, n_test_splits=2, lookback=252, min_embargo=22)
        folds = cv.split(rebalance_dates, daily_dates)
        
        for fold in folds:
            train_set = set(fold["train_dates"])
            test_set = set(fold["test_dates"])
            
            # Intersection must be empty
            assert train_set.isdisjoint(test_set), f"Fold {fold['fold_idx']} has overlapping train/test dates"

    def test_oos_paths(self, sample_dates):
        """Verify CPCV out-of-sample path generation."""
        rebalance_dates, daily_dates = sample_dates
        cv = CombinatorialPurgedCV(n_splits=6, n_test_splits=2, lookback=252, min_embargo=22)
        folds = cv.split(rebalance_dates, daily_dates)
        
        paths = cv.generate_paths(folds)
        
        # For N=6, k=2, there must be exactly 5 paths of 3 folds each
        assert len(paths) == 5
        
        all_fold_ids = []
        for path in paths:
            assert len(path) == 3
            all_fold_ids.extend(path)
            
            # Each path must partition blocks 0..5 (union is all blocks, no duplicates)
            blocks_in_path = []
            for f_idx in path:
                blocks_in_path.extend(folds[f_idx]["test_blocks"])
            assert sorted(blocks_in_path) == [0, 1, 2, 3, 4, 5]
            
        # Check that each fold is used exactly once across all paths
        assert sorted(all_fold_ids) == list(range(15))


def test_dsr_calculation():
    """Verify DSR calculation with synthetic return series."""
    np.random.seed(42)
    rets = pd.Series(np.random.normal(0.0002, 0.01, 500))
    all_srs_daily = np.random.normal(0.02, 0.005, 336)
    
    dsr = calculate_dsr(
        strategy_returns=rets,
        all_trials_srs_daily=all_srs_daily,
        n_trials=336,
        periods_per_year=252,
    )
    assert 0.0 <= dsr <= 1.0
    
    # High Sharpe strategy should have higher DSR
    high_rets = pd.Series(np.random.normal(0.05, 0.01, 500))
    dsr_high = calculate_dsr(
        strategy_returns=high_rets,
        all_trials_srs_daily=all_srs_daily,
        n_trials=336,
        periods_per_year=252,
    )
    assert dsr_high > dsr


def test_pbo_calculation():
    """Verify PBO calculation with synthetic trial returns."""
    np.random.seed(123)
    dates = pd.date_range("2020-01-01", periods=186, freq="ME")
    
    trial_returns = pd.DataFrame(
        np.random.normal(0.001, 0.05, (186, 5)),
        index=dates,
        columns=[f"T{i}" for i in range(5)]
    )
    
    folds = [
        {"train_dates": dates[:100], "test_dates": dates[100:150]},
        {"train_dates": dates[20:120], "test_dates": dates[120:170]},
        {"train_dates": dates[36:136], "test_dates": dates[136:186]},
    ]
    
    res = calculate_pbo(trial_returns, folds)
    assert "PBO" in res
    assert 0.0 <= res["PBO"] <= 1.0
    assert "rank_OOS_mean" in res
    assert 0.0 <= res["rank_OOS_mean"] <= 1.0
    assert len(res["ranks_OOS"]) == len(folds)
