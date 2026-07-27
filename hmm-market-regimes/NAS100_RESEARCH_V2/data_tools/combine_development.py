"""Combine sealed HistData development bars with consumed Axi bars."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.governance.integrity import canonical_sha256, sha256_file, utc_now


def _read_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    supplied = value.get("manifest_sha256")
    body = dict(value)
    body.pop("manifest_sha256", None)
    if supplied != canonical_sha256(body):
        raise ValueError(f"manifest hash mismatch: {path}")
    if value.get("classification") != "DEVELOPMENT_CONSUMED" or not value.get("quality_passed"):
        raise ValueError(f"source is not approved development-consumed data: {path}")
    return value


def combine_development(
    hist_manifest_path: str  Path,
    axi_manifest_path: str  Path,
    output_dir: str  Path,
) -> dict[str, Any]:
    hist_path, axi_path = Path(hist_manifest_path), Path(axi_manifest_path)
    hist_manifest, axi_manifest = _read_manifest(hist_path), _read_manifest(axi_path)
    output = Path(output_dir)
    bars_path = output / "NAS100_M15_COMBINED_DEVELOPMENT_UTC.parquet"
    manifest_path = output / "canonical_data_manifest.json"
    profile_path = output / "axi_spread_hour_profile.csv"
    if any(item.exists() for item in (bars_path, manifest_path, profile_path)):
        raise FileExistsError("refusing to overwrite combined development artifacts")
    output.mkdir(parents=True, exist_ok=True)

    hist_bars_path = hist_path.parent / hist_manifest["artifact_files"]["canonical_bars"]["path"]
    axi_bars_path = axi_path.parent / axi_manifest["artifact_files"]["canonical_bars"]["path"]
    hist = pd.read_parquet(hist_bars_path)
    axi_raw = pd.read_parquet(axi_bars_path)
    for frame, label in ((hist, "HistData"), (axi_raw, "Axi")):
        if frame.index.tz is None or str(frame.index.tz).upper() != "UTC":
            raise ValueError(f"{label} source is not explicit UTC")
    axi = axi_raw.rename(
        columns={"bid_open": "open", "bid_high": "high", "bid_low": "low", "bid_close": "close"}
    )
    required = ["open", "high", "low", "close", "tick_count"]
    if not set(required).issubset(hist.columns) or not set(required).issubset(axi.columns):
        raise ValueError("combined sources require Bid OHLC and tick_count")
    if hist.index[-1] >= axi.index[0]:
        raise ValueError("provider windows overlap or are out of chronological order")

    hourly = (
        axi.assign(utc_hour=axi.index.hour)
        .groupby("utc_hour")["spread_median"]
        .agg(observations="size", median="median", p95=lambda value: value.quantile(0.95), maximum="max")
        .reindex(range(24))
    )
    global_median = float(axi["spread_median"].median())
    global_p95 = float(axi["spread_median"].quantile(0.95))
    hourly["median"] = hourly["median"].fillna(global_median)
    hourly["p95"] = hourly["p95"].fillna(global_p95)
    hourly["maximum"] = hourly["maximum"].fillna(float(axi["spread_median"].max()))
    hourly["observations"] = hourly["observations"].fillna(0).astype(int)
    hourly.index.name = "utc_hour"
    hourly.to_csv(profile_path)

    hist_out = hist[required].copy()
    hist_out["axi_spread_profile"] = hist_out.index.hour.map(hourly["median"])
    hist_out["source"] = "HISTDATA_DEVELOPMENT"
    axi_out = axi[required].copy()
    axi_out["axi_spread_profile"] = axi["spread_median"].to_numpy(float)
    axi_out["source"] = "AXI_DEVELOPMENT_CONSUMED"
    combined = pd.concat([hist_out, axi_out]).sort_index()
    if combined.index.has_duplicates or not combined.index.is_monotonic_increasing:
        raise ValueError("combined index is invalid")
    combined["returns"] = np.log(combined["close"] / combined["close"].shift(1))
    combined.to_parquet(bars_path)
    manifest = {
        "schema_version": 1,
        "program": "NAS100_EDGE_RECOVERY_V2",
        "dataset_id": "NAS100_HISTDATA_PLUS_AXI_DEVELOPMENT_CONSUMED_V2",
        "classification": "DEVELOPMENT_CONSUMED",
        "release_evidence_eligible": False,
        "canonical_timezone": "UTC",
        "provider_boundary": {
            "histdata_last": hist.index[-1].isoformat(),
            "axi_first": axi.index[0].isoformat(),
            "price_gap": float(axi.iloc[0]["open"] - hist.iloc[-1]["close"]),
        },
        "source_manifests": {
            "histdata": hist_manifest["manifest_sha256"],
            "axi": axi_manifest["manifest_sha256"],
        },
        "spread_model": "Axi empirical UTC-hour median; actual consumed Axi spread where available",
        "canonical_bar_rows": int(len(combined)),
        "artifact_files": {
            "canonical_bars": {"path": bars_path.name, "sha256": sha256_file(bars_path)},
            "axi_spread_hour_profile": {"path": profile_path.name, "sha256": sha256_file(profile_path)},
        },
        "quality_passed": True,
        "created_utc": utc_now(),
    }
    manifest["manifest_sha256"] = canonical_sha256(manifest)
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"ok": True, "rows": len(combined), "manifest_sha256": manifest["manifest_sha256"]}


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hist-manifest", required=True, type=Path)
    parser.add_argument("--axi-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(combine_development(args.hist_manifest, args.axi_manifest, args.output_dir), indent=2))


if __name__ == "__main__":
    _main()
