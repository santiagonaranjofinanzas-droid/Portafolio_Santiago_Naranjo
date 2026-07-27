"""Rebuild and seal development-only NSXUSD M15 bars from HistData tick ZIPs.

HistData timestamps are fixed EST (UTC-05:00) without daylight-saving
adjustments.  This module makes that conversion explicit, refuses partial
month inventories, validates Bid/Ask microstructure and compares the rebuilt
Bid OHLC against the legacy training parquet.  HistData remains classified as
DEVELOPMENT_CONSUMED and can never satisfy a final Axi release gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.governance.integrity import canonical_sha256, sha256_file, utc_now


ZIP_RE = re.compile(r"^DAT_ASCII_NSXUSD_T_(\d{6})\.zip$")
TICK_NAMES = ["timestamp", "bid", "ask", "volume"]


def _month_range(first: str, last: str) -> list[str]:
    return [item.strftime("%Y%m") for item in pd.period_range(first, last, freq="M")]


def _read_month(path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    with zipfile.ZipFile(path, "r") as archive:
        # HistData ZIPs also include a licence/readme TXT; only the single CSV
        # is market data.
        members = [
            item for item in archive.namelist()
            if not item.endswith("/") and item.lower().endswith(".csv")
        ]
        if len(members) != 1:
            raise ValueError(f"{path.name}: expected exactly one CSV member")
        with archive.open(members[0]) as handle:
            ticks = pd.read_csv(
                handle,
                header=None,
                names=TICK_NAMES,
                dtype={"timestamp": "string", "bid": "float64", "ask": "float64"},
                usecols=[0, 1, 2],
            )
    if ticks.empty:
        raise ValueError(f"{path.name}: empty tick file")
    timestamps = pd.to_datetime(
        ticks.pop("timestamp"), format="%Y%m%d %H%M%S%f", errors="raise"
    )
    # HistData specifies EST without DST: fixed UTC-05, therefore +5 hours.
    timestamps = timestamps.dt.tz_localize("Etc/GMT+5").dt.tz_convert("UTC")
    bid = ticks["bid"].to_numpy(float)
    ask = ticks["ask"].to_numpy(float)
    if not np.isfinite(np.column_stack([bid, ask])).all() or np.any(bid <= 0) or np.any(ask <= 0):
        raise ValueError(f"{path.name}: non-finite or non-positive quotes")
    crossed = int(np.sum(ask < bid))
    if crossed:
        raise ValueError(f"{path.name}: {crossed} crossed quotes")
    duplicate = int(timestamps.duplicated().sum())
    negative_positions = np.flatnonzero(np.diff(timestamps.astype("int64")) < 0)
    out_of_order = int(len(negative_positions))
    excluded_dst_anomaly_rows = 0
    dst_anomaly_dates: list[str] = []
    if out_of_order:
        # Some NSXUSD archives contradict the vendor's fixed-EST specification
        # and repeat 19:00-19:59 on the last Sunday of October.  The two copies
        # are not disambiguated, so choosing either would manufacture ordering.
        # Remove the entire ambiguous local hour and record it explicitly.
        local = timestamps.dt.tz_convert("Etc/GMT+5").dt.tz_localize(None)
        anomaly_dates = sorted({local.iloc[int(position) + 1].date() for position in negative_positions})
        mask = np.zeros(len(local), dtype=bool)
        for day in anomaly_dates:
            mask = (local.dt.date == day) & (local.dt.hour == 19)
        excluded_dst_anomaly_rows = int(mask.sum())
        dst_anomaly_dates = [str(day) for day in anomaly_dates]
        if excluded_dst_anomaly_rows == 0:
            raise ValueError(f"{path.name}: unexplained out-of-order ticks")
        timestamps = timestamps.loc[~mask].reset_index(drop=True)
        ticks = ticks.loc[~mask].reset_index(drop=True)
        bid = ticks["bid"].to_numpy(float)
        ask = ticks["ask"].to_numpy(float)
    frame = pd.DataFrame({"bid": bid}, index=pd.DatetimeIndex(timestamps))
    spread = ask - bid
    grouped = frame.groupby(frame.index.floor("15min"), sort=True)
    bars = grouped.agg(
        open=("bid", "first"),
        high=("bid", "max"),
        low=("bid", "min"),
        close=("bid", "last"),
        tick_count=("bid", "size"),
    )
    bars.index.name = "timestamp_utc"
    record = {
        "filename": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "rows": int(len(frame)),
        "bars": int(len(bars)),
        "first_tick_utc": timestamps.iloc[0].isoformat(),
        "last_tick_utc": timestamps.iloc[-1].isoformat(),
        "duplicate_timestamps": duplicate,
        "out_of_order_rows": out_of_order,
        "dst_anomaly_dates": dst_anomaly_dates,
        "excluded_dst_anomaly_rows": excluded_dst_anomaly_rows,
        "crossed_rows": crossed,
        "locked_rows": int(np.sum(ask == bid)),
        "spread_median": float(np.median(spread)),
        "spread_p95": float(np.quantile(spread, 0.95)),
        "spread_max": float(np.max(spread)),
    }
    return bars, record


def rebuild_histdata(
    source_dir: str  Path,
    legacy_bars_path: str  Path,
    output_dir: str  Path,
    *,
    first_month: str = "2020-01",
    last_month: str = "2026-06",
) -> dict[str, Any]:
    source = Path(source_dir).resolve()
    legacy_path = Path(legacy_bars_path).resolve()
    output = Path(output_dir).resolve()
    paths = sorted(source.glob("*.zip"))
    observed: dict[str, Path] = {}
    for path in paths:
        match = ZIP_RE.fullmatch(path.name)
        if match:
            if match.group(1) in observed:
                raise ValueError(f"duplicate month: {match.group(1)}")
            observed[match.group(1)] = path
    expected = _month_range(first_month, last_month)
    if sorted(observed) != expected:
        missing = sorted(set(expected).difference(observed))
        extra = sorted(set(observed).difference(expected))
        raise ValueError(f"monthly inventory mismatch; missing={missing}, extra={extra}")

    targets = {
        "bars": output / "NSXUSD_M15_HISTDATA_DEVELOPMENT_UTC.parquet",
        "sources": output / "source_zip_manifest.jsonl",
        "qa": output / "histdata_qa_report.json",
        "manifest": output / "canonical_data_manifest.json",
    }
    if any(path.exists() for path in targets.values()):
        raise FileExistsError("refusing to overwrite sealed HistData artifacts")
    output.mkdir(parents=True, exist_ok=True)

    cache = output / ".monthly_cache"
    cache.mkdir(parents=True, exist_ok=True)
    monthly_bars: list[pd.DataFrame] = []
    records: list[dict[str, Any]] = []
    for month in expected:
        cache_bars = cache / f"{month}.parquet"
        cache_record = cache / f"{month}.json"
        if cache_bars.exists() and cache_record.exists():
            record = json.loads(cache_record.read_text(encoding="utf-8"))
            if record.get("sha256") != sha256_file(observed[month]):
                raise ValueError(f"cached source hash mismatch: {month}")
            bars = pd.read_parquet(cache_bars)
        else:
            bars, record = _read_month(observed[month])
            bars.to_parquet(cache_bars)
            cache_record.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")
        monthly_bars.append(bars)
        records.append(record)
    canonical = pd.concat(monthly_bars).sort_index()
    if canonical.index.has_duplicates or not canonical.index.is_monotonic_increasing:
        raise ValueError("rebuilt M15 index is not unique and monotonic")
    ohlc = canonical[["open", "high", "low", "close"]]
    if (
        (ohlc["high"] < ohlc[["open", "close"]].max(axis=1)).any()
        or (ohlc["low"] > ohlc[["open", "close"]].min(axis=1)).any()
    ):
        raise ValueError("rebuilt bars violate OHLC geometry")
    canonical["returns"] = np.log(canonical["close"] / canonical["close"].shift(1))

    legacy = pd.read_parquet(legacy_path)
    if not isinstance(legacy.index, pd.DatetimeIndex):
        raise ValueError("legacy training parquet requires DatetimeIndex")
    legacy = legacy.copy()
    if legacy.index.tz is None:
        legacy.index = (legacy.index + pd.Timedelta(hours=5)).tz_localize("UTC")
    else:
        legacy.index = legacy.index.tz_convert("UTC")
    common = canonical.index.intersection(legacy.index)
    parity_coverage = len(common) / len(legacy)
    if parity_coverage < 0.995:
        raise ValueError(
            f"legacy/rebuild parity coverage too low: {parity_coverage:.6f}"
        )
    delta = np.abs(
        canonical.loc[common, ["open", "high", "low", "close"]].to_numpy(float)
        - legacy.loc[common, ["open", "high", "low", "close"]].to_numpy(float)
    )
    mismatches = int(np.sum(delta > 1e-9))
    if mismatches:
        raise ValueError(f"legacy Bid OHLC parity failed in {mismatches} cells")

    canonical.to_parquet(targets["bars"])
    with targets["sources"].open("x", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    report = {
        "schema_version": 1,
        "classification": "DEVELOPMENT_CONSUMED",
        "source_vendor": "HistData",
        "source_symbol": "NSXUSD",
        "source_timezone": "EST_FIXED_UTC_MINUS_5_NO_DST",
        "canonical_timezone": "UTC",
        "months": len(records),
        "tick_rows": int(sum(item["rows"] for item in records)),
        "bar_rows": int(len(canonical)),
        "first_bar_utc": canonical.index[0].isoformat(),
        "last_bar_utc": canonical.index[-1].isoformat(),
        "legacy_common_rows": int(len(common)),
        "legacy_parity_coverage": float(parity_coverage),
        "legacy_rows_excluded_by_documented_dst_correction": int(len(legacy) - len(common)),
        "legacy_ohlc_mismatch_cells": mismatches,
        "duplicate_tick_timestamps": int(sum(item["duplicate_timestamps"] for item in records)),
        "source_out_of_order_rows": int(sum(item["out_of_order_rows"] for item in records)),
        "excluded_dst_anomaly_rows": int(sum(item["excluded_dst_anomaly_rows"] for item in records)),
        "crossed_rows": int(sum(item["crossed_rows"] for item in records)),
        "quality_passed": True,
    }
    targets["qa"].write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    artifacts = {
        "canonical_bars": {"path": targets["bars"].name, "sha256": sha256_file(targets["bars"])},
        "source_zip_manifest": {"path": targets["sources"].name, "sha256": sha256_file(targets["sources"])},
        "qa_report": {"path": targets["qa"].name, "sha256": sha256_file(targets["qa"])},
    }
    manifest = {
        "schema_version": 1,
        "program": "NAS100_EDGE_RECOVERY_V2",
        "dataset_id": "HISTDATA_NSXUSD_202001_202606_DEVELOPMENT_UTC_V2",
        "classification": "DEVELOPMENT_CONSUMED",
        "release_evidence_eligible": False,
        "timezone_conversion": "EST_FIXED_UTC_MINUS_5_TO_UTC",
        "source_inventory_sha256": canonical_sha256(records),
        "canonical_bar_rows": int(len(canonical)),
        "artifact_files": artifacts,
        "quality_passed": True,
        "created_utc": utc_now(),
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    targets["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, **report, "manifest_sha256": manifest["manifest_sha256"]}


def _main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild development HistData NSXUSD M15")
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--legacy-bars", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--first-month", default="2020-01")
    parser.add_argument("--last-month", default="2026-06")
    args = parser.parse_args()
    result = rebuild_histdata(
        args.source_dir,
        args.legacy_bars,
        args.output_dir,
        first_month=args.first_month,
        last_month=args.last_month,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
