from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PurgedFold:
    fold_id: int
    test_start: int
    test_end: int
    train_indices: np.ndarray
    test_indices: np.ndarray
    purged_count: int
    embargoed_count: int


@dataclass(frozen=True)
class FixedOOSSplit:
    oos_start: int
    oos_end: int
    train_indices: np.ndarray
    test_indices: np.ndarray
    purged_count: int
    embargoed_count: int


def make_event_intervals(n_samples: int, horizon: int) -> tuple[np.ndarray, np.ndarray]:
    """Crea intervalos [t_start, t_end] para eventos con horizonte futuro fijo."""
    starts = np.arange(n_samples, dtype=int)
    ends = np.minimum(starts + int(horizon), n_samples - 1)
    return starts, ends


def purged_embargo_train_mask(
    n_samples: int,
    test_start: int,
    test_end: int,
    event_starts: np.ndarray,
    event_ends: np.ndarray,
    embargo: int = 120,
) -> tuple[np.ndarray, int, int]:
    """Aplica purga por solape de etiquetas y embargo posterior al bloque OOS."""
    all_idx = np.arange(n_samples)
    test_mask = (all_idx >= test_start) & (all_idx <= test_end)

    purge_mask = (event_starts <= test_end) & (event_ends >= test_start)
    embargo_mask = (event_starts >= test_end) & (event_starts <= min(n_samples - 1, test_end + embargo))

    remove_mask = test_mask  purge_mask  embargo_mask
    train_mask = ~remove_mask
    return train_mask, int(np.sum(purge_mask & ~test_mask)), int(np.sum(embargo_mask & ~test_mask & ~purge_mask))


def build_purged_embargo_folds(
    index: pd.Index,
    n_splits: int = 5,
    label_horizon: int = 120,
    embargo: int = 120,
) -> list[PurgedFold]:
    """Construye folds OOS cronologicos con purga y embargo."""
    n_samples = len(index)
    if n_splits < 2:
        raise ValueError("n_splits debe ser >= 2")
    if n_samples < n_splits:
        raise ValueError("n_samples debe ser >= n_splits")

    event_starts, event_ends = make_event_intervals(n_samples, label_horizon)
    fold_edges = np.linspace(0, n_samples, n_splits + 1, dtype=int)
    folds: list[PurgedFold] = []

    for fold_id in range(n_splits):
        test_start = int(fold_edges[fold_id])
        test_end = int(fold_edges[fold_id + 1] - 1)
        train_mask, purged_count, embargoed_count = purged_embargo_train_mask(
            n_samples, test_start, test_end, event_starts, event_ends, embargo
        )
        test_indices = np.arange(test_start, test_end + 1, dtype=int)
        train_indices = np.flatnonzero(train_mask)
        folds.append(PurgedFold(
            fold_id=fold_id,
            test_start=test_start,
            test_end=test_end,
            train_indices=train_indices,
            test_indices=test_indices,
            purged_count=purged_count,
            embargoed_count=embargoed_count,
        ))
    return folds


def summarize_folds(folds: list[PurgedFold], index: pd.Index) -> pd.DataFrame:
    rows = []
    for fold in folds:
        rows.append({
            "fold_id": fold.fold_id,
            "test_start_i": fold.test_start,
            "test_end_i": fold.test_end,
            "test_start_time": index[fold.test_start],
            "test_end_time": index[fold.test_end],
            "train_count": len(fold.train_indices),
            "test_count": len(fold.test_indices),
            "purged_count": fold.purged_count,
            "embargoed_count": fold.embargoed_count,
        })
    return pd.DataFrame(rows)


def build_fixed_oos_split(
    index: pd.Index,
    oos_start_time,
    label_horizon: int = 120,
    embargo: int = 120,
) -> FixedOOSSplit:
    """Construye el split IS/OOS fijo usando OOS desde una fecha concreta."""
    n_samples = len(index)
    oos_start = int(index.searchsorted(pd.Timestamp(oos_start_time), side="left"))
    if oos_start >= n_samples:
        raise ValueError("oos_start_time queda fuera del indice")
    oos_end = n_samples - 1
    event_starts, event_ends = make_event_intervals(n_samples, label_horizon)

    all_idx = np.arange(n_samples)
    test_mask = all_idx >= oos_start
    train_candidate = all_idx < oos_start
    purge_mask = (event_starts <= oos_end) & (event_ends >= oos_start)
    embargo_mask = (event_starts >= oos_end) & (event_starts <= min(n_samples - 1, oos_end + embargo))
    train_mask = train_candidate & ~purge_mask & ~embargo_mask

    return FixedOOSSplit(
        oos_start=oos_start,
        oos_end=oos_end,
        train_indices=np.flatnonzero(train_mask),
        test_indices=np.flatnonzero(test_mask),
        purged_count=int(np.sum(train_candidate & purge_mask)),
        embargoed_count=int(np.sum(train_candidate & ~purge_mask & embargo_mask)),
    )


def summarize_fixed_oos_split(split: FixedOOSSplit, index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame([{
        "oos_start_i": split.oos_start,
        "oos_end_i": split.oos_end,
        "oos_start_time": index[split.oos_start],
        "oos_end_time": index[split.oos_end],
        "train_count": len(split.train_indices),
        "test_count": len(split.test_indices),
        "purged_count": split.purged_count,
        "embargoed_count": split.embargoed_count,
    }])
