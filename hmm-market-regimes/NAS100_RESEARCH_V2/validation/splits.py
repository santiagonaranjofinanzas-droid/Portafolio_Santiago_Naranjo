from __future__ import annotations

from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Iterator

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OuterFold:
    fold_id: int
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    train_indices: np.ndarray
    test_indices: np.ndarray
    purge_bars: int

    def record(self) -> dict:
        payload = asdict(self)
        payload["train_indices"] = len(self.train_indices)
        payload["test_indices"] = len(self.test_indices)
        return payload


def _clean_index(index: pd.Index) -> pd.DatetimeIndex:
    result = pd.DatetimeIndex(pd.to_datetime(index, errors="raise"))
    if result.has_duplicates:
        raise ValueError("index contains duplicate timestamps")
    if not result.is_monotonic_increasing:
        raise ValueError("index must be monotonic increasing")
    return result


def make_rolling_outer_folds(
    index: pd.Index,
    train_months: int = 36,
    test_months: int = 6,
    step_months: int = 6,
    purge_bars: int = 500,
    min_folds: int = 6,
) -> list[OuterFold]:
    """Create rolling calendar folds with a causal purge before every test window."""
    idx = _clean_index(index)
    if len(idx) < 2:
        raise ValueError("at least two observations are required")
    if min(train_months, test_months, step_months) <= 0 or purge_bars < 0:
        raise ValueError("months must be positive and purge_bars non-negative")
    first_test = idx[0] + pd.DateOffset(months=train_months)
    folds: list[OuterFold] = []
    fold_id = 0
    test_start = first_test
    while test_start <= idx[-1]:
        test_end_exclusive = test_start + pd.DateOffset(months=test_months)
        # A nominal six-month fold must be fully observable. Treating a few
        # trailing days as another fold inflates the fold count and violates
        # the preregistered test horizon.
        if idx[-1] < test_end_exclusive:
            break
        test_positions = np.flatnonzero((idx >= test_start) & (idx < test_end_exclusive))
        if len(test_positions) == 0:
            test_start += pd.DateOffset(months=step_months)
            continue
        train_calendar_start = test_start - pd.DateOffset(months=train_months)
        first_test_pos = int(test_positions[0])
        train_end_pos = first_test_pos - purge_bars - 1
        train_positions = np.flatnonzero((idx >= train_calendar_start) & (np.arange(len(idx)) <= train_end_pos))
        if len(train_positions) > 0:
            folds.append(
                OuterFold(
                    fold_id=fold_id,
                    train_start=idx[int(train_positions[0])],
                    train_end=idx[int(train_positions[-1])],
                    test_start=idx[int(test_positions[0])],
                    test_end=idx[int(test_positions[-1])],
                    train_indices=train_positions,
                    test_indices=test_positions,
                    purge_bars=purge_bars,
                )
            )
            fold_id += 1
        test_start += pd.DateOffset(months=step_months)
    if len(folds) < min_folds:
        raise ValueError(f"only {len(folds)} outer folds available; policy requires {min_folds}")
    return folds


class PurgedCombinatorialCV:
    """Contiguous combinatorial CV with event-overlap purge and post-test embargo."""

    def __init__(self, n_groups: int = 8, test_groups: int = 2, purge_bars: int = 500, embargo_bars: int = 500):
        if n_groups < 3 or not 1 <= test_groups < n_groups:
            raise ValueError("invalid CPCV group configuration")
        if purge_bars < 0 or embargo_bars < 0:
            raise ValueError("purge and embargo must be non-negative")
        self.n_groups = int(n_groups)
        self.test_groups = int(test_groups)
        self.purge_bars = int(purge_bars)
        self.embargo_bars = int(embargo_bars)

    @property
    def n_splits(self) -> int:
        from math import comb

        return comb(self.n_groups, self.test_groups)

    def split(self, index: pd.Index, event_end: pd.Series  pd.Index  None = None) -> Iterator[tuple[np.ndarray, np.ndarray]]:
        idx = _clean_index(index)
        n = len(idx)
        if n < self.n_groups:
            raise ValueError("fewer observations than CPCV groups")
        if event_end is None:
            ends = idx
        else:
            ends = pd.DatetimeIndex(pd.to_datetime(event_end, errors="raise"))
            if len(ends) != n:
                raise ValueError("event_end length mismatch")
        groups = [np.asarray(group, dtype=int) for group in np.array_split(np.arange(n), self.n_groups)]
        for selected in combinations(range(self.n_groups), self.test_groups):
            test = np.sort(np.concatenate([groups[group] for group in selected]))
            train_mask = np.ones(n, dtype=bool)
            train_mask[test] = False
            for group in selected:
                block = groups[group]
                left = int(block[0])
                right = int(block[-1])
                test_start = idx[left]
                test_end = idx[right]
                overlap = (idx <= test_end) & (ends >= test_start)
                train_mask[overlap] = False
                purge_left = max(0, left - self.purge_bars)
                embargo_right = min(n, right + self.embargo_bars + 1)
                train_mask[purge_left:left] = False
                train_mask[right + 1:embargo_right] = False
            train = np.flatnonzero(train_mask)
            if np.intersect1d(train, test).size:
                raise RuntimeError("CPCV produced overlapping train/test indices")
            yield train, test
