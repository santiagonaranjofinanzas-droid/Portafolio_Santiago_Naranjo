"""Fast, auditable sealing of the legacy HistData M15 development dataset.

This route is intentionally development-only.  It binds every raw monthly ZIP
by SHA-256, converts the vendor-documented fixed EST clock to UTC and removes
the ambiguous repeated October hour observed in NSXUSD archives.  It does not
claim broker parity or eligibility as final release evidence.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.governance.integrity import canonical_sha256, sha256_file, utc_now


PATTERN = re.compile(r"DAT_ASCII_NSXUSD_T_(\d{6})\.zip")


def seal_legacy(source_dir: str  Path, legacy_path: str  Path, output_dir: str  Path) -> dict:
    source, legacy, output = Path(source_dir), Path(legacy_path), Path(output_dir)
    bars_path = output / "NSXUSD_M15_HISTDATA_DEVELOPMENT_UTC.parquet"
    sources_path = output / "source_zip_manifest.jsonl"
    qa_path = output / "histdata_qa_report.json"
    manifest_path = output / "canonical_data_manifest.json"
    if any(path.exists() for path in (bars_path, sources_path, qa_path, manifest_path)):
        raise FileExistsError("refusing to overwrite sealed legacy artifacts")
    paths = sorted(source.glob("*.zip"))
    months = []
    records = []
    for path in paths:
        match = PATTERN.fullmatch(path.name)
        if match:
            months.append(match.group(1))
            records.append({"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    expected = [item.strftime("%Y%m") for item in pd.period_range("2020-01", "2026-06", freq="M")]
    if months != expected:
        raise ValueError("raw ZIP month inventory is not contiguous 202001-202606")
    bars = pd.read_parquet(legacy)
    required = ["open", "high", "low", "close"]
    if not set(required).issubset(bars.columns) or not isinstance(bars.index, pd.DatetimeIndex):
        raise ValueError("legacy parquet schema is invalid")
    if bars.index.tz is not None:
        raise ValueError("legacy index unexpectedly has a timezone; policy requires explicit review")
    local = bars.index
    # Repeated 19:00 hour occurs on the final Sunday of October in the source
    # sequence.  Aggregated legacy bars cannot disambiguate the two copies.
    last_sunday_october = set()
    for year in range(2020, 2027):
        days = pd.date_range(f"{year}-10-25", f"{year}-10-31", freq="D")
        last_sunday_october.add(next(day.date() for day in days if day.weekday() == 6))
    ambiguous = np.array(
        [timestamp.date() in last_sunday_october and timestamp.hour == 19 for timestamp in local],
        dtype=bool,
    )
    excluded = int(ambiguous.sum())
    bars = bars.loc[~ambiguous].copy()
    bars.index = (bars.index + pd.Timedelta(hours=5)).tz_localize("UTC")
    bars.index.name = "timestamp_utc"
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValueError("canonicalized legacy index is invalid")
    ohlc = bars[required].to_numpy(float)
    if not np.isfinite(ohlc).all() or np.any(ohlc <= 0):
        raise ValueError("legacy OHLC contains invalid prices")
    if np.any(ohlc[:, 1] < np.maximum(ohlc[:, 0], ohlc[:, 3])) or np.any(ohlc[:, 2] > np.minimum(ohlc[:, 0], ohlc[:, 3])):
        raise ValueError("legacy OHLC geometry failed")
    # Existing raw tick partitions provide activity for the recent segment;
    # older legacy bars have no preserved count and use a neutral positive
    # placeholder.  This is disclosed and never final evidence.
    if "tick_count" not in bars:
        bars["tick_count"] = 1.0
    bars["returns"] = np.log(bars["close"] / bars["close"].shift(1))
    output.mkdir(parents=True, exist_ok=True)
    bars.to_parquet(bars_path)
    with sources_path.open("x", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")
    report = {
        "schema_version": 1,
        "classification": "DEVELOPMENT_CONSUMED",
        "release_evidence_eligible": False,
        "source_vendor": "HistData",
        "raw_zip_files": len(records),
        "legacy_parquet_sha256": sha256_file(legacy),
        "bar_rows": len(bars),
        "first_bar_utc": bars.index[0].isoformat(),
        "last_bar_utc": bars.index[-1].isoformat(),
        "excluded_ambiguous_october_bars": excluded,
        "timezone_policy": "VENDOR_DOCUMENTED_FIXED_EST_PLUS_5H_TO_UTC",
        "timezone_warning": "Empirical October rollback contradicts fixed-EST documentation; ambiguous hour excluded",
        "tick_count_policy": "NEUTRAL_PLACEHOLDER_FOR_LEGACY_BARS",
        "quality_passed": True,
    }
    qa_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": 1,
        "program": "NAS100_EDGE_RECOVERY_V2",
        "dataset_id": "HISTDATA_NSXUSD_LEGACY_M15_SEALED_DEVELOPMENT_V2",
        "classification": "DEVELOPMENT_CONSUMED",
        "release_evidence_eligible": False,
        "quality_passed": True,
        "canonical_bar_rows": len(bars),
        "source_inventory_sha256": canonical_sha256(records),
        "artifact_files": {
            "canonical_bars": {"path": bars_path.name, "sha256": sha256_file(bars_path)},
            "source_zip_manifest": {"path": sources_path.name, "sha256": sha256_file(sources_path)},
            "qa_report": {"path": qa_path.name, "sha256": sha256_file(qa_path)},
        },
        "created_utc": utc_now(),
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, **report, "manifest_sha256": manifest["manifest_sha256"]}


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--legacy-bars", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(seal_legacy(args.source_dir, args.legacy_bars, args.output_dir), indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
