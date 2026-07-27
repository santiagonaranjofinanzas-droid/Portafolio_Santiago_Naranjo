from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq


PRICE_COLUMNS = ("bid", "ask")


def parquet_files(root: Path, symbol: str) -> list[Path]:
    return sorted((root / symbol).rglob("*.parquet"))


def _to_naive_utc(values: pd.Series) -> pd.DatetimeIndex:
    result = pd.to_datetime(values, utc=True, errors="coerce")
    return pd.DatetimeIndex(result).tz_convert("UTC").tz_localize(None)


def inspect_file(path: Path, batch_size: int = 500_000) -> dict:
    pf = pq.ParquetFile(path)
    names = set(pf.schema_arrow.names)
    required = {"timestamp", "bid", "ask"}
    if not required.issubset(names):
        return {"file": str(path), "rows": pf.metadata.num_rows, "schema_ok": False}
    invalid = duplicate_adjacent = backward = 0
    min_ts = max_ts = None
    spread_min = np.inf
    spread_max = -np.inf
    last_tuple: tuple  None = None
    for batch in pf.iter_batches(columns=["timestamp", "bid", "ask"], batch_size=batch_size):
        frame = batch.to_pandas()
        ts = _to_naive_utc(frame["timestamp"])
        bid = frame["bid"].to_numpy(float)
        ask = frame["ask"].to_numpy(float)
        valid = np.isfinite(bid) & np.isfinite(ask) & (bid > 0) & (ask > 0) & (ask >= bid)
        invalid += int((~valid).sum()) + int(ts.isna().sum())
        if len(ts):
            min_ts = ts.min() if min_ts is None else min(min_ts, ts.min())
            max_ts = ts.max() if max_ts is None else max(max_ts, ts.max())
            ns = ts.asi8
            backward += int((np.diff(ns) < 0).sum())
            same = (np.diff(ns) == 0) & (np.diff(bid) == 0) & (np.diff(ask) == 0)
            duplicate_adjacent += int(same.sum())
            if last_tuple == (int(ns[0]), float(bid[0]), float(ask[0])):
                duplicate_adjacent += 1
            last_tuple = (int(ns[-1]), float(bid[-1]), float(ask[-1]))
        if valid.any():
            spread = ask[valid] - bid[valid]
            spread_min = min(spread_min, float(spread.min()))
            spread_max = max(spread_max, float(spread.max()))
    return {
        "file": str(path),
        "rows": pf.metadata.num_rows,
        "schema_ok": True,
        "timestamp_min": None if min_ts is None else min_ts.isoformat(),
        "timestamp_max": None if max_ts is None else max_ts.isoformat(),
        "invalid_quotes": invalid,
        "adjacent_duplicates": duplicate_adjacent,
        "backward_timestamps": backward,
        "spread_min": None if not np.isfinite(spread_min) else spread_min,
        "spread_max": None if not np.isfinite(spread_max) else spread_max,
    }


def audit_ticks(root: Path, symbols: Iterable[str], output: Path) -> dict:
    report: dict = {"symbols": {}, "limitations": []}
    for symbol in symbols:
        files = parquet_files(root, symbol)
        details = [inspect_file(path) for path in files]
        valid_details = [item for item in details if item.get("timestamp_min")]
        report["symbols"][symbol] = {
            "files": len(files),
            "rows": sum(item["rows"] for item in details),
            "start": min((item["timestamp_min"] for item in valid_details), default=None),
            "end": max((item["timestamp_max"] for item in valid_details), default=None),
            "invalid_quotes": sum(item.get("invalid_quotes", 0) for item in details),
            "adjacent_duplicates": sum(item.get("adjacent_duplicates", 0) for item in details),
            "backward_timestamps": sum(item.get("backward_timestamps", 0) for item in details),
            "schema_variants": sorted({str(pq.ParquetFile(path).schema_arrow) for path in files}),
            "details": details,
        }
    xau = report["symbols"].get("XAUUSD", {})
    if xau.get("start") and xau["start"][:4] > "2012":
        report["limitations"].append("XAUUSD history starts after the protocol target of 2012.")
    report["limitations"].extend(
        [
            "No second independent XAUUSD provider is present.",
            "No macro release history is present.",
        ]
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def _batch_bar_parts(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    frame = frame[["timestamp", "bid", "ask"]].copy()
    frame["timestamp"] = _to_naive_utc(frame["timestamp"])
    frame = (
        frame.dropna()
        .sort_values("timestamp", kind="stable")
        .drop_duplicates(["timestamp", "bid", "ask"], keep="last")
    )
    frame = frame[(frame.bid > 0) & (frame.ask >= frame.bid)]
    if frame.empty:
        return pd.DataFrame()
    frame["mid"] = (frame.bid + frame.ask) / 2.0
    frame["spread"] = frame.ask - frame.bid
    frame["bar_time"] = frame.timestamp.dt.ceil(frequency)
    grouped = frame.groupby("bar_time", sort=True)
    parts = pd.DataFrame(index=grouped.size().index)
    for col in ("bid", "ask", "mid"):
        parts[f"{col}_open"] = grouped[col].first()
        parts[f"{col}_high"] = grouped[col].max()
        parts[f"{col}_low"] = grouped[col].min()
        parts[f"{col}_close"] = grouped[col].last()
    parts["spread_sum"] = grouped.spread.sum()
    parts["spread_median_num"] = grouped.spread.median()
    parts["spread_max"] = grouped.spread.max()
    parts["tick_count"] = grouped.size()
    parts["first_tick"] = grouped.timestamp.first()
    parts["last_tick"] = grouped.timestamp.last()
    return parts.reset_index()


def build_bars_for_symbol(
    root: Path, symbol: str, output: Path, frequency: str = "15min", batch_size: int = 750_000
) -> pd.DataFrame:
    partial: list[pd.DataFrame] = []
    for path in parquet_files(root, symbol):
        pf = pq.ParquetFile(path)
        for batch in pf.iter_batches(columns=["timestamp", "bid", "ask"], batch_size=batch_size):
            bars = _batch_bar_parts(batch.to_pandas(), frequency)
            if not bars.empty:
                partial.append(bars)
    if not partial:
        raise ValueError(f"No usable ticks for {symbol}")
    raw = pd.concat(partial, ignore_index=True).sort_values(["bar_time", "first_tick"])
    grouped = raw.groupby("bar_time", sort=True)
    result = pd.DataFrame(index=grouped.size().index)
    for col in ("bid", "ask", "mid"):
        result[f"{col}_open"] = grouped[f"{col}_open"].first()
        result[f"{col}_high"] = grouped[f"{col}_high"].max()
        result[f"{col}_low"] = grouped[f"{col}_low"].min()
        result[f"{col}_close"] = grouped[f"{col}_close"].last()
    result["tick_count"] = grouped.tick_count.sum()
    result["spread_mean"] = grouped.spread_sum.sum() / result.tick_count
    # Medians of chunks are approximate; retained as a robust diagnostic, not an emission.
    result["spread_median_approx"] = grouped.spread_median_num.median()
    result["spread_max"] = grouped.spread_max.max()
    result["first_tick"] = grouped.first_tick.min()
    result["last_tick"] = grouped.last_tick.max()
    result["symbol"] = symbol
    result.index.name = "timestamp"
    result = result[~result.index.duplicated(keep="last")].sort_index()
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_parquet(output, index=True)
    return result


def join_context(primary: pd.DataFrame, contexts: dict[str, pd.DataFrame]) -> pd.DataFrame:
    result = primary.sort_index().copy()
    for symbol, frame in contexts.items():
        context = frame[["mid_close"]].rename(columns={"mid_close": f"{symbol.lower()}_close"})
        result = pd.merge_asof(
            result.reset_index().sort_values("timestamp"),
            context.reset_index().sort_values("timestamp"),
            on="timestamp",
            direction="backward",
            allow_exact_matches=True,
        ).set_index("timestamp")
    return result


def bar_quality(bars: pd.DataFrame, frequency: str = "15min") -> dict:
    delta = bars.index.to_series().diff()
    expected = pd.Timedelta(frequency)
    return {
        "bars": int(len(bars)),
        "start": bars.index.min().isoformat(),
        "end": bars.index.max().isoformat(),
        "gaps_over_one_bar": int((delta > expected).sum()),
        "max_gap_hours": float(delta.max().total_seconds() / 3600),
        "zero_tick_bars": int((bars.tick_count <= 0).sum()),
        "crossed_quotes": int((bars.ask_close < bars.bid_close).sum()),
    }


def add_gap_segments(frame: pd.DataFrame, frequency: str, max_gap_bars: int) -> pd.DataFrame:
    result = frame.sort_index().copy()
    boundary = result.index.to_series().diff() > pd.Timedelta(frequency) * max_gap_bars
    result["segment_id"] = boundary.cumsum().astype(int).to_numpy()
    return result
