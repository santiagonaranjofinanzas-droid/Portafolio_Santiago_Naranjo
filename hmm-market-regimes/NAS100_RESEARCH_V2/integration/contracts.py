"""Fail-closed contracts shared by the validation adapters.

The integration layer deliberately refuses to repair timestamps, OHLC values,
or candidate configuration.  Canonicalisation belongs upstream; silently
coercing research inputs here would make an invalid experiment look valid.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from datetime import timezone
from pathlib import Path
from typing import Any, TypeVar

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.validation.runner import CandidateSpec
from NAS100_RESEARCH_V2.validation.splits import OuterFold


NORMALIZED_TRADE_COLUMNS: tuple[str, ...] = (
    "entry_time",
    "exit_time",
    "net_pnl",
    "return_pct",
    "pnl",
)

_UTC_NAMES = {
    "UTC",
    "ETC/UTC",
    "GMT",
    "UTC+00:00",
    "TZUTC()",
    "DATETIME.TIMEZONE.UTC",
}

T = TypeVar("T")


def _timezone_is_explicit_utc(index: pd.DatetimeIndex) -> bool:
    if index.tz is None:
        return False
    if index.tz is timezone.utc:
        return True
    return str(index.tz).upper() in _UTC_NAMES


def require_utc_index(index: pd.Index, *, label: str) -> pd.DatetimeIndex:
    """Validate a canonical, explicitly UTC, increasing timestamp index."""

    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(f"{label} index must be a pandas DatetimeIndex")
    if not _timezone_is_explicit_utc(index):
        raise ValueError(f"{label} index timezone must be explicitly UTC")
    if index.has_duplicates:
        raise ValueError(f"{label} index contains duplicate timestamps")
    if not index.is_monotonic_increasing:
        raise ValueError(f"{label} index must be monotonically increasing")
    if index.hasnans:
        raise ValueError(f"{label} index cannot contain NaT")
    return index


def _require_utc_timestamp(value: Any, *, label: str) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is None:
        raise ValueError(f"{label} must be timezone-aware UTC")
    if str(result.tzinfo).upper() not in _UTC_NAMES and result.tzinfo is not timezone.utc:
        raise ValueError(f"{label} must be explicitly UTC")
    return result


def validate_bars(bars: pd.DataFrame, *, label: str) -> None:
    """Validate the market-data fields consumed by both research models."""

    if not isinstance(bars, pd.DataFrame):
        raise TypeError(f"{label} must be a pandas DataFrame")
    if bars.empty:
        raise ValueError(f"{label} cannot be empty")
    require_utc_index(bars.index, label=label)
    required = ("open", "high", "low", "close")
    missing = set(required).difference(bars.columns)
    if missing:
        raise ValueError(f"{label} missing OHLC columns: {sorted(missing)}")
    ohlc = bars.loc[:, required].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(ohlc).all():
        raise ValueError(f"{label} OHLC must be finite and cannot contain NaN")
    if np.any(ohlc <= 0.0):
        raise ValueError(f"{label} OHLC must be strictly positive")
    open_, high, low, close = ohlc.T
    if np.any(high < low):
        raise ValueError(f"{label} contains high below low")
    if np.any(high < np.maximum(open_, close)) or np.any(low > np.minimum(open_, close)):
        raise ValueError(f"{label} contains invalid OHLC geometry")

    # Optional inputs affect features or fills and therefore cannot be allowed
    # to fall back silently when present but malformed.
    for column in (
        "tick_count",
        "tick_volume",
        "volume",
        "real_volume",
        "spread_price",
        "spread_median",
        "spread",
    ):
        if column not in bars.columns:
            continue
        values = pd.to_numeric(bars[column], errors="coerce").to_numpy(float)
        if not np.isfinite(values).all() or np.any(values < 0.0):
            raise ValueError(f"{label}.{column} must be finite and non-negative")


def validate_fold_inputs(train: pd.DataFrame, test: pd.DataFrame, fold: OuterFold) -> None:
    """Bind the supplied frames exactly to the declared outer fold."""

    validate_bars(train, label="train")
    validate_bars(test, label="test")
    if train.index[-1] >= test.index[0]:
        raise ValueError("training data must end strictly before OOS test data")
    if train.index.intersection(test.index).size:
        raise ValueError("training and OOS test data overlap")

    expected = {
        "train_start": (train.index[0], fold.train_start),
        "train_end": (train.index[-1], fold.train_end),
        "test_start": (test.index[0], fold.test_start),
        "test_end": (test.index[-1], fold.test_end),
    }
    for name, (observed, declared) in expected.items():
        declared_utc = _require_utc_timestamp(declared, label=f"fold.{name}")
        if observed != declared_utc:
            raise ValueError(
                f"fold boundary mismatch for {name}: observed={observed}, "
                f"declared={declared_utc}"
            )


def dataframe_fingerprint(frame: pd.DataFrame) -> str:
    """Content fingerprint used to prevent cache reuse across different data."""

    require_utc_index(frame.index, label="fingerprint frame")
    digest = hashlib.sha256()
    digest.update(str(frame.index.tz).encode("utf-8"))
    for column in sorted(map(str, frame.columns)):
        series = frame[column]
        digest.update(column.encode("utf-8"))
        digest.update(str(series.dtype).encode("utf-8"))
        hashed = pd.util.hash_pandas_object(series, index=True, categorize=True)
        digest.update(hashed.to_numpy(np.uint64, copy=False).tobytes())
    return digest.hexdigest()


def stable_data(value: Any) -> Any:
    """Convert diagnostics/configuration to deterministic strict-JSON data."""

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return stable_data(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {
            str(key): stable_data(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        values = list(value)
        if isinstance(value, (set, frozenset)):
            values = sorted(values, key=repr)
        return [stable_data(item) for item in values]
    if isinstance(value, np.ndarray):
        return stable_data(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        result = float(value)
        if math.isnan(result):
            return "NaN"
        if math.isinf(result):
            return "+Infinity" if result > 0 else "-Infinity"
        return result
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, pd.Timestamp):
        timestamp = value
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC")
        return timestamp.isoformat()
    if isinstance(value, pd.Timedelta):
        return value.isoformat()
    if isinstance(value, Path):
        return value.as_posix()
    if value is None or isinstance(value, (str, int)):
        return value
    raise TypeError(f"unsupported diagnostics value: {type(value).__name__}")


def stable_json_dumps(value: Any) -> str:
    return json.dumps(
        stable_data(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def config_digest(value: Any) -> str:
    return hashlib.sha256(stable_json_dumps(value).encode("utf-8")).hexdigest()


def strict_dataclass_override(instance: T, overrides: Mapping[str, Any], *, path: str) -> T:
    """Recursively apply JSON-like overrides while rejecting unknown keys."""

    if not dataclasses.is_dataclass(instance) or isinstance(instance, type):
        raise TypeError(f"{path} target must be a dataclass instance")
    if not isinstance(overrides, Mapping):
        raise TypeError(f"{path} overrides must be an object")
    fields = {field.name: field for field in dataclasses.fields(instance)}
    unknown = set(overrides).difference(fields)
    if unknown:
        raise ValueError(f"unknown {path} keys: {sorted(unknown)}")
    changes: dict[str, Any] = {}
    for name, supplied in overrides.items():
        current = getattr(instance, name)
        child_path = f"{path}.{name}"
        if dataclasses.is_dataclass(current) and not isinstance(current, type):
            changes[name] = strict_dataclass_override(current, supplied, path=child_path)
        elif isinstance(current, tuple):
            if isinstance(supplied, (str, bytes)) or not isinstance(supplied, Sequence):
                raise TypeError(f"{child_path} must be an array")
            changes[name] = tuple(supplied)
        else:
            changes[name] = supplied
    return dataclasses.replace(instance, **changes)


def validate_candidate(candidate: CandidateSpec, *, allowed_top_level: set[str]) -> None:
    if not isinstance(candidate, CandidateSpec):
        raise TypeError("candidate must be validation.runner.CandidateSpec")
    if not candidate.candidate_id or candidate.candidate_id.strip() != candidate.candidate_id:
        raise ValueError("candidate_id must be a non-empty trimmed string")
    if not isinstance(candidate.parameters, dict):
        raise TypeError("candidate.parameters must be a dictionary")
    unknown = set(candidate.parameters).difference(allowed_top_level)
    if unknown:
        raise ValueError(f"unknown candidate parameter groups: {sorted(unknown)}")
    # This also proves the parameter tree is stable-serialisable before any fit.
    stable_json_dumps(candidate.parameters)


def assert_prefix_invariant(
    full: pd.DataFrame,
    prefix: pd.DataFrame,
    *,
    columns: Sequence[str],
    atol: float = 1e-10,
) -> None:
    """Fail when future rows alter an already-computed OOS prefix."""

    missing = set(columns).difference(full.columns)  set(columns).difference(prefix.columns)
    if missing:
        raise ValueError(f"causal diagnostic missing columns: {sorted(missing)}")
    if not prefix.index.equals(full.index[: len(prefix)]):
        raise ValueError("causal diagnostic prefix index mismatch")
    left = full.loc[prefix.index, list(columns)].to_numpy(dtype=float)
    right = prefix.loc[:, list(columns)].to_numpy(dtype=float)
    if not np.allclose(left, right, equal_nan=True, rtol=0.0, atol=atol):
        raise RuntimeError("LEAKAGE_DETECTED: OOS transformation is not prefix invariant")


def require_finite_columns(frame: pd.DataFrame, columns: Sequence[str], *, label: str) -> None:
    missing = set(columns).difference(frame.columns)
    if missing:
        raise ValueError(f"{label} missing columns: {sorted(missing)}")
    values = frame.loc[:, list(columns)].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(values).all():
        raise ValueError(f"{label} contains NaN or non-finite values in {list(columns)}")


def normalize_trades(
    trades: pd.DataFrame,
    *,
    return_pct: pd.Series  np.ndarray  None = None,
) -> pd.DataFrame:
    """Return the runner contract plus model-specific audit columns."""

    if not isinstance(trades, pd.DataFrame):
        raise TypeError("backtest trades must be a pandas DataFrame")
    if trades.empty:
        return pd.DataFrame(columns=list(NORMALIZED_TRADE_COLUMNS))
    required = {"entry_time", "exit_time", "net_pnl"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"backtest trades missing columns: {sorted(missing)}")
    result = trades.copy()
    result["entry_time"] = pd.to_datetime(result["entry_time"], errors="raise")
    result["exit_time"] = pd.to_datetime(result["exit_time"], errors="raise")
    require_utc_index(pd.DatetimeIndex(result["entry_time"]), label="trade entry_time")
    require_utc_index(pd.DatetimeIndex(result["exit_time"]), label="trade exit_time")
    result["net_pnl"] = pd.to_numeric(result["net_pnl"], errors="coerce").astype(float)
    if not np.isfinite(result["net_pnl"].to_numpy()).all():
        raise ValueError("trade net_pnl must be finite")
    if return_pct is None:
        if "return_pct" not in result.columns:
            raise ValueError("per-trade return_pct is required for normalization")
        normalized_returns = pd.to_numeric(result["return_pct"], errors="coerce").to_numpy(float)
    else:
        normalized_returns = np.asarray(return_pct, dtype=float)
    if normalized_returns.shape != (len(result),) or not np.isfinite(normalized_returns).all():
        raise ValueError("trade return_pct must be finite and match trade count")
    result["return_pct"] = normalized_returns
    result["pnl"] = result["net_pnl"]
    if (result["exit_time"] < result["entry_time"]).any():
        raise ValueError("trade exit precedes entry")
    front = list(NORMALIZED_TRADE_COLUMNS)
    return result.loc[:, front + [column for column in result.columns if column not in front]]


def validate_next_open_trades(
    trades: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    signal_column: str,
    side_encoding: str,
) -> None:
    """Prove each reported fill uses exactly the bar after its source signal."""

    if trades.empty:
        return
    required = {"entry_time", "entry_i", "side"}
    missing = required.difference(trades.columns)
    if missing:
        raise ValueError(f"cannot audit next-open execution; missing {sorted(missing)}")
    for row in trades.itertuples(index=False):
        entry_i = int(row.entry_i)
        if entry_i < 1 or entry_i >= len(signals):
            raise RuntimeError("NEXT_OPEN_VIOLATION: invalid entry bar index")
        entry_time = pd.Timestamp(row.entry_time)
        if entry_time != signals.index[entry_i]:
            raise RuntimeError("NEXT_OPEN_VIOLATION: entry timestamp/index mismatch")
        source = signals.index[entry_i - 1]
        if not source < entry_time:
            raise RuntimeError("NEXT_OPEN_VIOLATION: source signal is not earlier than fill")
        signal = int(np.sign(signals.iloc[entry_i - 1][signal_column]))
        if side_encoding == "numeric":
            side = int(np.sign(row.side))
        elif side_encoding == "text":
            side = 1 if row.side == "LONG" else -1 if row.side == "SHORT" else 0
        else:
            raise ValueError(f"unknown side encoding: {side_encoding}")
        if signal == 0 or signal != side:
            raise RuntimeError("NEXT_OPEN_VIOLATION: fill side has no matching prior-bar signal")

