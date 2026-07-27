"""Canonical, session-aware QA for Axi NAS100.fs Bid/Ask tick data.

The source is treated as immutable.  The tool hashes every selected parquet,
validates quote microstructure, aggregates only complete M15 bars and writes a
content-addressed manifest.  It never writes beneath the legacy input tree.
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

try:
    from NAS100_RESEARCH_V2.governance.access_manifest import HoldoutAccessController
    from NAS100_RESEARCH_V2.governance.integrity import (
        GovernanceError,
        IntegrityError,
        PolicyError,
        canonical_json_bytes,
        canonical_sha256,
        parse_utc,
        sha256_file,
        utc_now,
    )
    from NAS100_RESEARCH_V2.governance.preregistration import Preregistration
except ModuleNotFoundError:  # Support direct execution from NAS100_RESEARCH_V2.
    from governance.access_manifest import HoldoutAccessController
    from governance.integrity import (
        GovernanceError,
        IntegrityError,
        PolicyError,
        canonical_json_bytes,
        canonical_sha256,
        parse_utc,
        sha256_file,
        utc_now,
    )
    from governance.preregistration import Preregistration


CONFIG_FIELDS = {
    "schema_version",
    "dataset_id",
    "symbol",
    "broker",
    "source_timezone",
    "source_root",
    "source_glob",
    "reference_bar_path",
    "audit_start_utc",
    "audit_end_exclusive_utc",
    "development_cutoff_exclusive_utc",
    "bar_frequency",
    "tick_size",
    "expected_file_count",
    "session_calendar",
    "quality_gates",
    "canonical_bar_filename",
}
GATE_FIELDS = {
    "minimum_complete_bar_coverage",
    "maximum_active_tick_gap_seconds",
    "maximum_active_gap_count",
    "maximum_stale_quote_seconds",
    "maximum_stale_run_count",
    "maximum_spread_price",
    "maximum_crossed_rows",
    "maximum_locked_rows",
    "maximum_duplicate_timestamps",
    "maximum_out_of_order_rows",
    "maximum_invalid_price_rows",
    "maximum_off_grid_rows",
}
REQUIRED_TICK_COLUMNS = {"timestamp", "bid", "ask"}


def _load_config(path: str  Path) -> tuple[dict[str, Any], str]:
    source = Path(path)
    try:
        config = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyError(f"QA config does not exist: {source}") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise PolicyError(f"QA config is not valid UTF-8 JSON: {source}") from exc
    if not isinstance(config, dict) or set(config) != CONFIG_FIELDS:
        raise PolicyError("QA config fields differ from the frozen schema")
    if config["schema_version"] != 1:
        raise PolicyError("Only QA schema_version=1 is supported")
    for field in ("dataset_id", "symbol", "broker", "source_root", "source_glob"):
        if not isinstance(config[field], str) or not config[field].strip():
            raise PolicyError(f"{field} must be a non-empty string")
    if config["source_timezone"] != "UTC":
        raise PolicyError("Axi canonical source_timezone must be UTC")
    start = parse_utc(config["audit_start_utc"], field="audit_start_utc")
    end = parse_utc(config["audit_end_exclusive_utc"], field="audit_end_exclusive_utc")
    cutoff = parse_utc(
        config["development_cutoff_exclusive_utc"],
        field="development_cutoff_exclusive_utc",
    )
    if not start < end <= cutoff:
        raise PolicyError("QA interval must be non-empty and end at or before the development cutoff")
    try:
        frequency = pd.Timedelta(config["bar_frequency"])
    except ValueError as exc:
        raise PolicyError("bar_frequency is invalid") from exc
    if frequency <= pd.Timedelta(0) or pd.Timedelta(days=1) % frequency != pd.Timedelta(0):
        raise PolicyError("bar_frequency must divide one day exactly")
    if not isinstance(config["tick_size"], (int, float)) or config["tick_size"] <= 0:
        raise PolicyError("tick_size must be positive")
    if type(config["expected_file_count"]) is not int or config["expected_file_count"] <= 0:
        raise PolicyError("expected_file_count must be a positive integer")
    gates = config["quality_gates"]
    if not isinstance(gates, dict) or set(gates) != GATE_FIELDS:
        raise PolicyError("quality_gates fields differ from the frozen schema")
    if not 0 < gates["minimum_complete_bar_coverage"] <= 1:
        raise PolicyError("minimum_complete_bar_coverage must be in (0,1]")
    for field in GATE_FIELDS - {"minimum_complete_bar_coverage"}:
        if not isinstance(gates[field], (int, float)) or gates[field] < 0:
            raise PolicyError(f"quality_gates.{field} must be non-negative")
    calendar = config["session_calendar"]
    if not isinstance(calendar, dict) or set(calendar) != {
        "timezone",
        "weekdays",
        "regular_start",
        "regular_end",
        "exceptions",
    }:
        raise PolicyError("session_calendar fields differ from the frozen schema")
    if calendar["timezone"] != "UTC":
        raise PolicyError("session calendar must use UTC")
    if not isinstance(calendar["weekdays"], list) or any(
        type(day) is not int or day < 0 or day > 6 for day in calendar["weekdays"]
    ):
        raise PolicyError("session_calendar.weekdays is invalid")
    _parse_clock(calendar["regular_start"], allow_24=False)
    _parse_clock(calendar["regular_end"], allow_24=True)
    for date_text, exception in calendar["exceptions"].items():
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
        except ValueError as exc:
            raise PolicyError(f"Invalid session exception date: {date_text}") from exc
        if not isinstance(exception, dict) or set(exception) != {"start", "end", "reason"}:
            raise PolicyError(f"Invalid session exception schema: {date_text}")
        _parse_clock(exception["start"], allow_24=False)
        _parse_clock(exception["end"], allow_24=True)
    return config, canonical_sha256(config)


def _parse_clock(value: str, *, allow_24: bool) -> tuple[int, int, int]:
    if allow_24 and value == "24:00":
        return (24, 0, 0)
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise PolicyError(f"Invalid session clock: {value!r}") from exc
    if parsed.tzinfo is not None:
        raise PolicyError("Session clocks must not contain a timezone")
    return parsed.hour, parsed.minute, parsed.second


def _clock_on_date(day: pd.Timestamp, value: str) -> pd.Timestamp:
    hour, minute, second = _parse_clock(value, allow_24=True)
    base = day.normalize()
    if hour == 24:
        return base + pd.Timedelta(days=1)
    return base + pd.Timedelta(hours=hour, minutes=minute, seconds=second)


def _session_bounds(day: pd.Timestamp, calendar: Mapping[str, Any]) -> tuple[pd.Timestamp, pd.Timestamp]  None:
    date_text = day.strftime("%Y-%m-%d")
    exception = calendar["exceptions"].get(date_text)
    if exception is None and int(day.weekday()) not in calendar["weekdays"]:
        return None
    start_text = exception["start"] if exception else calendar["regular_start"]
    end_text = exception["end"] if exception else calendar["regular_end"]
    start = _clock_on_date(day, start_text)
    end = _clock_on_date(day, end_text)
    if end <= start:
        raise PolicyError(f"Session end must follow start for {date_text}")
    return start, end


def _expected_slots(config: Mapping[str, Any]) -> pd.DatetimeIndex:
    start = pd.Timestamp(parse_utc(config["audit_start_utc"]))
    end = pd.Timestamp(parse_utc(config["audit_end_exclusive_utc"]))
    frequency = pd.Timedelta(config["bar_frequency"])
    calendar = config["session_calendar"]
    days = pd.date_range(start.normalize(), end.normalize(), freq="D", tz="UTC")
    values: list[pd.Timestamp] = []
    for day in days:
        bounds = _session_bounds(day, calendar)
        if bounds is None:
            continue
        session_start, session_end = bounds
        cursor = session_start
        while cursor + frequency <= session_end:
            if cursor >= start and cursor + frequency <= end:
                values.append(cursor)
            cursor += frequency
    return pd.DatetimeIndex(values, tz="UTC")


def _timestamp_in_same_session(
    left: pd.Timestamp,
    right: pd.Timestamp,
    calendar: Mapping[str, Any],
) -> bool:
    if left.date() != right.date():
        return False
    bounds = _session_bounds(left, calendar)
    return bool(bounds and bounds[0] <= left < right < bounds[1])


def _weighted_quantile(counter: Counter[int], quantile: float, scale: float) -> float  None:
    total = sum(counter.values())
    if total == 0:
        return None
    rank = max(1, math.ceil(quantile * total))
    cumulative = 0
    for value, count in sorted(counter.items()):
        cumulative += count
        if cumulative >= rank:
            return float(value * scale)
    raise AssertionError("unreachable weighted quantile")


def _aggregate_file(frame: pd.DataFrame, frequency: str) -> pd.DataFrame:
    work = frame.sort_values("timestamp", kind="mergesort").copy()
    work["slot"] = work["timestamp"].dt.floor(frequency)
    work["spread"] = work["ask"] - work["bid"]
    grouped = work.groupby("slot", sort=True, observed=True)
    bars = grouped.agg(
        bid_open=("bid", "first"),
        bid_high=("bid", "max"),
        bid_low=("bid", "min"),
        bid_close=("bid", "last"),
        ask_open=("ask", "first"),
        ask_high=("ask", "max"),
        ask_low=("ask", "min"),
        ask_close=("ask", "last"),
        spread_median=("spread", "median"),
        spread_p95=("spread", lambda values: values.quantile(0.95)),
        spread_max=("spread", "max"),
        tick_count=("bid", "size"),
        first_tick_utc=("timestamp", "first"),
        last_tick_utc=("timestamp", "last"),
    )
    bars.index.name = "timestamp_utc"
    return bars


def _reference_comparison(
    reference_path: Path,
    bars: pd.DataFrame,
    expected_slots: pd.DatetimeIndex,
    tick_size: float,
) -> dict[str, Any]:
    if not reference_path.exists():
        return {
            "available": False,
            "path": str(reference_path),
            "common_complete_bars": 0,
            "ohlc_mismatch_cells": None,
            "missing_canonical_slots_in_reference": None,
        }
    reference = pd.read_parquet(reference_path)
    if not {"open", "high", "low", "close"}.issubset(reference.columns):
        raise IntegrityError(f"Reference bars do not contain Bid OHLC columns: {reference_path}")
    if "timestamp" in reference.columns:
        index = pd.to_datetime(reference.pop("timestamp"), errors="raise")
    else:
        index = pd.to_datetime(reference.index, errors="raise")
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    reference.index = index
    reference = reference[~reference.index.duplicated(keep=False)].sort_index()
    expected = set(expected_slots)
    canonical_index = [timestamp for timestamp in bars.index if timestamp in expected]
    common = pd.DatetimeIndex(canonical_index).intersection(reference.index)
    mismatches = 0
    mapping = {
        "bid_open": "open",
        "bid_high": "high",
        "bid_low": "low",
        "bid_close": "close",
    }
    for canonical_column, reference_column in mapping.items():
        left = bars.loc[common, canonical_column].to_numpy(dtype=float)
        right = reference.loc[common, reference_column].to_numpy(dtype=float)
        mismatches += int((~np.isclose(left, right, rtol=0.0, atol=tick_size / 100.0)).sum())
    missing = len(set(canonical_index) - set(reference.index))
    return {
        "available": True,
        "path": str(reference_path),
        "common_complete_bars": int(len(common)),
        "ohlc_mismatch_cells": mismatches,
        "missing_canonical_slots_in_reference": int(missing),
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def audit_axi_dataset(
    *,
    config_path: str  Path,
    workspace_root: str  Path,
    output_dir: str  Path,
    preregistration_path: str  Path  None = None,
    access_manifest_path: str  Path  None = None,
    actor: str = "axi_qa",
) -> dict[str, Any]:
    """Audit Axi tick partitions and produce deterministic canonical bars.

    Existing output files are never replaced.  Use a fresh output directory for
    a new dataset version; this keeps released manifests immutable.
    """

    config, config_sha256 = _load_config(config_path)
    root = Path(workspace_root).resolve()
    source_root = (root / config["source_root"]).resolve()
    reference_path = (root / config["reference_bar_path"]).resolve()
    output = Path(output_dir).resolve()
    outputs = {
        "bars": output / config["canonical_bar_filename"],
        "file_manifest": output / "source_file_manifest.jsonl",
        "qa_report": output / "axi_tick_bar_qa_report.json",
        "canonical_manifest": output / "canonical_data_manifest.json",
    }
    if any(path.exists() for path in outputs.values()):
        existing = [str(path) for path in outputs.values() if path.exists()]
        raise IntegrityError(f"Refusing to overwrite canonical artifacts: {existing}")
    output.mkdir(parents=True, exist_ok=True)

    if preregistration_path is not None:
        prereg = Preregistration.load(preregistration_path)
        configured_cutoff = parse_utc(config["development_cutoff_exclusive_utc"])
        if configured_cutoff != prereg.development_end_exclusive_utc:
            raise PolicyError("QA cutoff does not match the frozen preregistration")
        if access_manifest_path is None:
            raise PolicyError("access_manifest_path is required when preregistration_path is supplied")
        HoldoutAccessController(access_manifest_path, preregistration_path).request_access(
            actor=actor,
            dataset_id=config["dataset_id"],
            experiment_id="DATA_QA_V2",
            purpose="QA_METADATA",
            requested_start_utc=config["audit_start_utc"],
            requested_end_exclusive_utc=config["audit_end_exclusive_utc"],
            source_reference=config["source_root"] + "/" + config["source_glob"],
        )

    files = sorted(source_root.glob(config["source_glob"]), key=lambda path: path.as_posix())
    if not files:
        raise IntegrityError(f"No source files matched {source_root / config['source_glob']}")
    audit_start = pd.Timestamp(parse_utc(config["audit_start_utc"]))
    audit_end = pd.Timestamp(parse_utc(config["audit_end_exclusive_utc"]))
    tick_size = float(config["tick_size"])
    gates = config["quality_gates"]
    frequency = pd.Timedelta(config["bar_frequency"])

    file_records: list[dict[str, Any]] = []
    bar_frames: list[pd.DataFrame] = []
    spread_histogram: Counter[int] = Counter()
    total_rows = included_rows = invalid_price_rows = crossed_rows = locked_rows = 0
    duplicate_timestamps = out_of_order_rows = off_grid_rows = 0
    same_quote_rows = stale_run_count = active_gap_count = 0
    maximum_stale_seconds = maximum_active_gap_seconds = 0.0
    previous_file_last: pd.Timestamp  None = None
    previous_file_last_bid: float  None = None
    previous_file_last_ask: float  None = None
    overlapping_file_count = 0
    excluded_before = excluded_after = 0

    for path in files:
        file_hash = sha256_file(path)
        try:
            frame = pd.read_parquet(path)
        except Exception as exc:
            raise IntegrityError(f"Cannot read source parquet: {path}") from exc
        if not REQUIRED_TICK_COLUMNS.issubset(frame.columns):
            raise IntegrityError(
                f"Missing tick columns in {path}: {sorted(REQUIRED_TICK_COLUMNS - set(frame.columns))}"
            )
        raw_rows = len(frame)
        total_rows += raw_rows
        try:
            timestamps = pd.to_datetime(frame["timestamp"], errors="raise")
        except Exception as exc:
            raise IntegrityError(f"Invalid timestamp column in {path}") from exc
        if timestamps.dt.tz is None:
            timestamps = timestamps.dt.tz_localize(config["source_timezone"])
        else:
            timestamps = timestamps.dt.tz_convert("UTC")
        frame = frame.assign(timestamp=timestamps)
        before_mask = frame["timestamp"] < audit_start
        after_mask = frame["timestamp"] >= audit_end
        excluded_before += int(before_mask.sum())
        excluded_after += int(after_mask.sum())
        frame = frame.loc[~before_mask & ~after_mask, ["timestamp", "bid", "ask"]].copy()
        if frame.empty:
            file_records.append(
                {
                    "relative_path": path.relative_to(source_root).as_posix(),
                    "sha256": file_hash,
                    "size_bytes": path.stat().st_size,
                    "raw_rows": raw_rows,
                    "included_rows": 0,
                    "min_timestamp_utc": None,
                    "max_timestamp_utc": None,
                }
            )
            continue
        for column in ("bid", "ask"):
            if not pd.api.types.is_numeric_dtype(frame[column]):
                raise IntegrityError(f"{column} is not numeric in {path}")
            frame[column] = frame[column].astype(float)
        included_rows += len(frame)

        timestamp_ns = frame["timestamp"].astype("int64").to_numpy()
        diffs_ns = np.diff(timestamp_ns)
        duplicate_timestamps += int((diffs_ns == 0).sum())
        out_of_order_rows += int((diffs_ns < 0).sum())
        current_min = frame["timestamp"].min()
        current_max = frame["timestamp"].max()
        if previous_file_last is not None:
            if current_min < previous_file_last:
                overlapping_file_count += 1
            elif current_min == previous_file_last:
                duplicate_timestamps += 1

        bid = frame["bid"].to_numpy(dtype=float)
        ask = frame["ask"].to_numpy(dtype=float)
        finite = np.isfinite(bid) & np.isfinite(ask)
        valid = finite & (bid > 0.0) & (ask > 0.0)
        invalid_price_rows += int((~valid).sum())
        crossed_rows += int((valid & (ask < bid)).sum())
        locked_rows += int((valid & (ask == bid)).sum())
        grid_bid = np.abs(bid / tick_size - np.rint(bid / tick_size))
        grid_ask = np.abs(ask / tick_size - np.rint(ask / tick_size))
        off_grid_rows += int((valid & ((grid_bid > 1e-6)  (grid_ask > 1e-6))).sum())
        valid_spread = ask[valid] - bid[valid]
        spread_ticks = np.rint(valid_spread / tick_size).astype(np.int64)
        values, counts = np.unique(spread_ticks, return_counts=True)
        spread_histogram.update({int(value): int(count) for value, count in zip(values, counts)})

        ordered = frame.sort_values("timestamp", kind="mergesort")
        obid = ordered["bid"].to_numpy(dtype=float)
        oask = ordered["ask"].to_numpy(dtype=float)
        ots = ordered["timestamp"].astype("int64").to_numpy()
        if len(ordered):
            changes = np.empty(len(ordered), dtype=bool)
            changes[0] = True
            changes[1:] = (obid[1:] != obid[:-1])  (oask[1:] != oask[:-1])
            run_starts = np.flatnonzero(changes)
            run_ends = np.r_[run_starts[1:] - 1, len(ordered) - 1]
            durations = (ots[run_ends] - ots[run_starts]) / 1_000_000_000.0
            same_quote_rows += int(len(ordered) - len(run_starts))
            if durations.size:
                maximum_stale_seconds = max(maximum_stale_seconds, float(durations.max()))
                stale_run_count += int((durations > gates["maximum_stale_quote_seconds"]).sum())

            sorted_timestamps = ordered["timestamp"].reset_index(drop=True)
            sorted_diffs = sorted_timestamps.diff().dt.total_seconds().to_numpy()
            candidates = np.flatnonzero(sorted_diffs > gates["maximum_active_tick_gap_seconds"])
            for index in candidates:
                left = sorted_timestamps.iloc[index - 1]
                right = sorted_timestamps.iloc[index]
                if _timestamp_in_same_session(left, right, config["session_calendar"]):
                    active_gap_count += 1
                    maximum_active_gap_seconds = max(
                        maximum_active_gap_seconds, float(sorted_diffs[index])
                    )

        bar_frames.append(_aggregate_file(frame, config["bar_frequency"]))
        previous_file_last = current_max
        previous_file_last_bid = float(ordered["bid"].iloc[-1])
        previous_file_last_ask = float(ordered["ask"].iloc[-1])
        file_records.append(
            {
                "relative_path": path.relative_to(source_root).as_posix(),
                "sha256": file_hash,
                "size_bytes": path.stat().st_size,
                "raw_rows": raw_rows,
                "included_rows": int(len(frame)),
                "min_timestamp_utc": current_min.isoformat().replace("+00:00", "Z"),
                "max_timestamp_utc": current_max.isoformat().replace("+00:00", "Z"),
            }
        )

    if not bar_frames or included_rows == 0:
        raise IntegrityError("No ticks fall inside the declared audit interval")
    all_bars = pd.concat(bar_frames).sort_index(kind="mergesort")
    overlapping_bar_slots = int(all_bars.index.duplicated(keep=False).sum())
    if overlapping_bar_slots:
        # Combining percentile estimates from overlapping partitions is not
        # exact, so fail instead of silently manufacturing bars.
        raise IntegrityError(f"Source partitions overlap in {overlapping_bar_slots} bar rows")

    expected_slots = _expected_slots(config)
    expected_set = set(expected_slots)
    complete_mask = all_bars.index.to_series().map(
        lambda timestamp: timestamp in expected_set and timestamp + frequency <= audit_end
    ).to_numpy()
    canonical_bars = all_bars.loc[complete_mask].copy()
    canonical_bars.index.name = "timestamp_utc"
    observed_set = set(canonical_bars.index)
    missing_slots = sorted(expected_set - observed_set)
    extra_complete_slots = sorted(observed_set - expected_set)
    coverage = len(observed_set & expected_set) / len(expected_set) if expected_set else 0.0
    partial_or_outside_bars = int(len(all_bars) - len(canonical_bars))

    ohlc_invariant_violations = 0
    for prefix in ("bid", "ask"):
        open_values = canonical_bars[f"{prefix}_open"]
        high_values = canonical_bars[f"{prefix}_high"]
        low_values = canonical_bars[f"{prefix}_low"]
        close_values = canonical_bars[f"{prefix}_close"]
        invalid = (
            (high_values < open_values)
             (high_values < close_values)
             (low_values > open_values)
             (low_values > close_values)
             (high_values < low_values)
        )
        ohlc_invariant_violations += int(invalid.sum())

    reference = _reference_comparison(reference_path, canonical_bars, expected_slots, tick_size)
    spread_max_ticks = max(spread_histogram) if spread_histogram else None
    spread_statistics = {
        "median": _weighted_quantile(spread_histogram, 0.50, tick_size),
        "p95": _weighted_quantile(spread_histogram, 0.95, tick_size),
        "p99": _weighted_quantile(spread_histogram, 0.99, tick_size),
        "max": float(spread_max_ticks * tick_size) if spread_max_ticks is not None else None,
    }
    gate_results = {
        "source_file_count": len(files) == config["expected_file_count"],
        "complete_bar_coverage": coverage >= gates["minimum_complete_bar_coverage"],
        "active_gap_count": active_gap_count <= gates["maximum_active_gap_count"],
        "stale_run_count": stale_run_count <= gates["maximum_stale_run_count"],
        "spread_max": spread_statistics["max"] is not None
        and spread_statistics["max"] <= gates["maximum_spread_price"],
        "crossed_rows": crossed_rows <= gates["maximum_crossed_rows"],
        "locked_rows": locked_rows <= gates["maximum_locked_rows"],
        "duplicate_timestamps": duplicate_timestamps <= gates["maximum_duplicate_timestamps"],
        "out_of_order_rows": out_of_order_rows <= gates["maximum_out_of_order_rows"],
        "invalid_price_rows": invalid_price_rows <= gates["maximum_invalid_price_rows"],
        "off_grid_rows": off_grid_rows <= gates["maximum_off_grid_rows"],
        "non_overlapping_partitions": overlapping_file_count == 0,
        "bar_ohlc_invariants": ohlc_invariant_violations == 0,
        "reference_bid_ohlc_parity": reference["available"]
        and reference["ohlc_mismatch_cells"] == 0
        and reference["missing_canonical_slots_in_reference"] == 0,
    }
    quality_passed = all(gate_results.values())

    canonical_bars.to_parquet(outputs["bars"], index=True)
    with outputs["file_manifest"].open("x", encoding="utf-8", newline="\n") as handle:
        for record in file_records:
            handle.write(canonical_json_bytes(record).decode("utf-8") + "\n")
    source_dataset_sha256 = canonical_sha256(file_records)
    report = {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "dataset_id": config["dataset_id"],
        "symbol": config["symbol"],
        "broker": config["broker"],
        "config_sha256": config_sha256,
        "source_dataset_sha256": source_dataset_sha256,
        "audit_interval": {
            "start_utc": config["audit_start_utc"],
            "end_exclusive_utc": config["audit_end_exclusive_utc"],
            "development_cutoff_exclusive_utc": config[
                "development_cutoff_exclusive_utc"
            ],
        },
        "source": {
            "root": config["source_root"],
            "glob": config["source_glob"],
            "file_count": len(files),
            "raw_rows": total_rows,
            "included_rows": included_rows,
            "excluded_before_interval": excluded_before,
            "excluded_after_interval": excluded_after,
            "overlapping_file_count": overlapping_file_count,
        },
        "tick_quality": {
            "invalid_price_rows": invalid_price_rows,
            "crossed_rows": crossed_rows,
            "locked_rows": locked_rows,
            "off_grid_rows": off_grid_rows,
            "duplicate_timestamps": duplicate_timestamps,
            "out_of_order_rows": out_of_order_rows,
            "same_quote_rows": same_quote_rows,
            "stale_run_count": stale_run_count,
            "maximum_stale_quote_seconds": maximum_stale_seconds,
            "active_gap_count": active_gap_count,
            "maximum_active_gap_seconds": maximum_active_gap_seconds,
            "spread_price": spread_statistics,
        },
        "bar_quality": {
            "frequency": config["bar_frequency"],
            "all_observed_slots": len(all_bars),
            "canonical_complete_bars": len(canonical_bars),
            "partial_or_outside_bars_excluded": partial_or_outside_bars,
            "expected_complete_bars": len(expected_slots),
            "complete_bar_coverage": coverage,
            "missing_complete_slots": [item.isoformat() for item in missing_slots],
            "extra_complete_slots": [item.isoformat() for item in extra_complete_slots],
            "ohlc_invariant_violations": ohlc_invariant_violations,
            "first_bar_utc": canonical_bars.index.min().isoformat(),
            "last_bar_utc": canonical_bars.index.max().isoformat(),
        },
        "reference_bar_comparison": reference,
        "quality_gates": gates,
        "gate_results": gate_results,
        "quality_passed": quality_passed,
    }
    _write_json(outputs["qa_report"], report)
    artifact_hashes = {
        "canonical_bars": {
            "path": outputs["bars"].name,
            "sha256": sha256_file(outputs["bars"]),
        },
        "source_file_manifest": {
            "path": outputs["file_manifest"].name,
            "sha256": sha256_file(outputs["file_manifest"]),
        },
        "qa_report": {
            "path": outputs["qa_report"].name,
            "sha256": sha256_file(outputs["qa_report"]),
        },
    }
    manifest = {
        "schema_version": 1,
        "program": "NAS100_EDGE_RECOVERY_V2",
        "dataset_id": config["dataset_id"],
        "classification": "DEVELOPMENT_CONSUMED",
        "symbol": config["symbol"],
        "broker": config["broker"],
        "audit_start_utc": config["audit_start_utc"],
        "audit_end_exclusive_utc": config["audit_end_exclusive_utc"],
        "config_sha256": config_sha256,
        "source_root": config["source_root"],
        "source_dataset_sha256": source_dataset_sha256,
        "source_file_count": len(files),
        "source_rows": included_rows,
        "canonical_bar_rows": len(canonical_bars),
        "artifact_files": artifact_hashes,
        "quality_passed": quality_passed,
        "created_utc": utc_now(),
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    _write_json(outputs["canonical_manifest"], manifest)
    verification = verify_canonical_manifest(outputs["canonical_manifest"])
    return {
        "ok": quality_passed and verification["ok"],
        "quality_passed": quality_passed,
        "canonical_data_manifest": str(outputs["canonical_manifest"]),
        "canonical_data_manifest_sha256": manifest["manifest_sha256"],
        "canonical_bar_rows": len(canonical_bars),
        "source_rows": included_rows,
        "gate_results": gate_results,
    }


def verify_canonical_manifest(path: str  Path) -> dict[str, Any]:
    source = Path(path)
    try:
        manifest = json.loads(source.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise IntegrityError(f"Cannot read canonical data manifest: {source}") from exc
    if not isinstance(manifest, dict) or "manifest_sha256" not in manifest:
        raise IntegrityError("Canonical data manifest schema is invalid")
    body = dict(manifest)
    supplied_hash = body.pop("manifest_sha256")
    if canonical_sha256(body) != supplied_hash:
        raise IntegrityError("Canonical data manifest content hash mismatch")
    artifact_files = manifest.get("artifact_files")
    if not isinstance(artifact_files, dict) or not artifact_files:
        raise IntegrityError("Canonical data manifest has no artifact files")
    for name, item in artifact_files.items():
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise IntegrityError(f"Artifact binding is invalid: {name}")
        artifact = (source.parent / item["path"]).resolve()
        try:
            artifact.relative_to(source.parent.resolve())
        except ValueError as exc:
            raise IntegrityError(f"Artifact escapes manifest directory: {artifact}") from exc
        if not artifact.exists() or sha256_file(artifact) != item["sha256"]:
            raise IntegrityError(f"Artifact hash mismatch: {name}")
    return {
        "ok": True,
        "manifest_sha256": supplied_hash,
        "quality_passed": manifest.get("quality_passed") is True,
        "artifact_count": len(artifact_files),
    }


def _main() -> None:
    parser = argparse.ArgumentParser(description="Audit and aggregate canonical Axi NAS100 ticks")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--config", required=True, type=Path)
    audit.add_argument("--workspace-root", required=True, type=Path)
    audit.add_argument("--output-dir", required=True, type=Path)
    audit.add_argument("--preregistration", type=Path)
    audit.add_argument("--access-manifest", type=Path)
    audit.add_argument("--actor", default="axi_qa")
    verify = sub.add_parser("verify")
    verify.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    if args.command == "audit":
        result = audit_axi_dataset(
            config_path=args.config,
            workspace_root=args.workspace_root,
            output_dir=args.output_dir,
            preregistration_path=args.preregistration,
            access_manifest_path=args.access_manifest,
            actor=args.actor,
        )
    else:
        result = verify_canonical_manifest(args.manifest)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    try:
        _main()
    except GovernanceError as exc:
        raise SystemExit(f"FAIL_CLOSED: {exc}") from exc

