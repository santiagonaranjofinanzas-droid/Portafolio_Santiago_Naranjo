"""Module for purging and embargoing training observations to prevent leakage.

Implements §14.4 and §14.5 of the protocol.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def get_embargo_days(oos_days_count: int, min_embargo: int = 22, prop_pct: float = 0.05) -> int:
    """Calculate embargo duration in business days per §14.5.

    Embargo = max(22 business days, 5% of OOS block size)
    """
    prop_embargo = int(np.ceil(oos_days_count * prop_pct))
    return max(min_embargo, prop_embargo)


def purge_and_embargo_indices(
    all_rebalance_dates: pd.DatetimeIndex  list[pd.Timestamp],
    test_intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
    all_daily_dates: pd.DatetimeIndex,
    lookback: int = 252,
    min_embargo: int = 22,
) -> list[pd.Timestamp]:
    """Determine the training rebalance dates after purging and embargoing.

    Parameters
    ----------
    all_rebalance_dates : DatetimeIndex or list of pd.Timestamp
        All candidate rebalance dates in the backtest.
    test_intervals : list of tuples (start_test, end_test)
        Test intervals for the current fold.
    all_daily_dates : DatetimeIndex
        Complete daily business dates index from the returns panel.
    lookback : int
        Lookback window size (L) in business days.
    min_embargo : int
        Minimum embargo days (H), default 22.

    Returns
    -------
    list of pd.Timestamp
        Cleaned list of training rebalance dates.
    """
    rebalance_dates = pd.DatetimeIndex(all_rebalance_dates).sort_values()
    daily_dates = pd.DatetimeIndex(all_daily_dates).sort_values()
    
    # Start with all rebalance dates as candidates
    train_dates = set(rebalance_dates)
    
    for start_test, end_test in test_intervals:
        # 1. Exclude the test block itself
        # Any rebalance date t falling in [start_test, end_test] is test data
        test_rebalances = rebalance_dates[(rebalance_dates >= start_test) & (rebalance_dates <= end_test)]
        train_dates.difference_update(test_rebalances)
        
        # 2. Purging: exclude training dates whose lookback window overlaps with the test block
        # For a rebalance date t, its lookback window of L business days is [t - L, t - 1] (daily index).
        # We must purge t if any date in [t - L, t - 1] falls in [start_test, end_test].
        #
        # Let's count daily dates to find the purged region:
        # A rebalance date t has its lookback window start at the index (pos_t - L).
        # We need to find all t after end_test where the lookback window starts on or before end_test.
        #
        # Let's find the position of end_test in daily_dates
        if end_test in daily_dates:
            end_test_idx = daily_dates.get_loc(end_test)
        else:
            # Find the last daily date <= end_test
            past_dates = daily_dates[daily_dates <= end_test]
            if past_dates.empty:
                continue
            end_test_idx = daily_dates.get_loc(past_dates[-1])
            
        # The purged region after end_test ends L business days after end_test.
        # So any daily date up to end_test_idx + L must be purged.
        max_purged_idx = min(len(daily_dates) - 1, end_test_idx + lookback)
        max_purged_date = daily_dates[max_purged_idx]
        
        # Any rebalance date t in (end_test, max_purged_date] is purged
        purged_rebalances = rebalance_dates[(rebalance_dates > end_test) & (rebalance_dates <= max_purged_date)]
        train_dates.difference_update(purged_rebalances)
        
        # 3. Embargo: exclude training dates within H business days after the test block
        # H = max(22, 5% of OOS daily dates count)
        # First find the number of daily dates in the test block
        oos_daily_dates = daily_dates[(daily_dates >= start_test) & (daily_dates <= end_test)]
        embargo_days = get_embargo_days(len(oos_daily_dates), min_embargo=min_embargo)
        
        # The embargoed region ends embargo_days after the purged region (since purging is L days,
        # and embargo starts at end_test + H, but wait: the embargo region is [end_test + 1, end_test + H].
        # Since the first daily date we can use for lookback is end_test + H + 1,
        # the training observation t must have its lookback window start on or after end_test + H + 1.
        # Thus, t - L >= end_test + H + 1 (in business days).
        # Which means pos_t - L >= end_test_idx + embargo_days + 1.
        # So pos_t >= end_test_idx + lookback + embargo_days + 1.
        # Thus, any t where pos_t <= end_test_idx + lookback + embargo_days is excluded.
        max_embargo_idx = min(len(daily_dates) - 1, end_test_idx + lookback + embargo_days)
        max_embargo_date = daily_dates[max_embargo_idx]
        
        # Any rebalance date t in (end_test, max_embargo_date] is excluded (covers both purge and embargo)
        excluded_rebalances = rebalance_dates[(rebalance_dates > end_test) & (rebalance_dates <= max_embargo_date)]
        train_dates.difference_update(excluded_rebalances)

    return sorted(list(train_dates))
