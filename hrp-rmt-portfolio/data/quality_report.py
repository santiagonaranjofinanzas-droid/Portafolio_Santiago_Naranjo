"""Generate a comprehensive Point-In-Time data quality report for the ingested ETF prices."""

from __future__ import annotations
import argparse
import csv
from pathlib import Path
import pandas as pd
from data.stale_price_detector import detect_stale_prices

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
DEFAULT_PRICE_DIR = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"
DEFAULT_REPORT_CSV = PROJECT_ROOT / "data" / "quality" / "tiingo_quality_report.csv"


def read_universe(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def inspect_quality(file_path: Path) -> dict[str, object]:
    """Inspects the quality of a single price CSV file and returns statistics."""
    if not file_path.exists():
        return {
            "file_exists": False,
            "total_rows": 0,
            "start_date": "",
            "end_date": "",
            "missing_values": 0,
            "stale_rows": 0,
            "stale_ratio": 0.0,
            "max_daily_return": 0.0,
            "min_daily_return": 0.0,
            "average_adv_usd": 0.0,
            "date_gaps": False,
        }

    # Load data
    df = pd.read_csv(file_path)
    if df.empty:
        return {
            "file_exists": True,
            "total_rows": 0,
            "start_date": "",
            "end_date": "",
            "missing_values": 0,
            "stale_rows": 0,
            "stale_ratio": 0.0,
            "max_daily_return": 0.0,
            "min_daily_return": 0.0,
            "average_adv_usd": 0.0,
            "date_gaps": False,
        }

    # Format dates
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()
    df = df.sort_values("date").reset_index(drop=True)

    # Core checks
    total_rows = len(df)
    start_date = df["date"].iloc[0].strftime("%Y-%m-%d")
    end_date = df["date"].iloc[-1].strftime("%Y-%m-%d")

    # Missing core values
    core_cols = ["open", "high", "low", "close", "volume", "adjClose", "adjVolume"]
    missing_values = int(df[core_cols].isna().sum().sum())

    # Detect stale prices
    is_stale = detect_stale_prices(df)
    stale_rows = int(is_stale.sum())
    stale_ratio = stale_rows / total_rows if total_rows > 0 else 0.0

    # Calculate returns to check for extreme values/outliers
    returns = df["adjClose"].pct_change()
    max_return = float(returns.max()) if total_rows > 1 else 0.0
    min_return = float(returns.min()) if total_rows > 1 else 0.0

    # Calculate ADV in USD (over all historical periods)
    usd_volume = df["adjVolume"] * df["adjClose"]
    avg_adv = float(usd_volume.mean())

    # Check for date gaps (duplicate or out-of-order dates, or large gap > 10 days)
    date_diffs = df["date"].diff()
    # Check if there are negative or zero diffs (means out of order or duplicate timestamps)
    duplicates_or_unsorted = (date_diffs <= pd.Timedelta(0)).any()
    # Check for large gaps > 10 days (excluding weekends, but 10 calendar days is safe to flag)
    large_gaps = (date_diffs > pd.Timedelta(days=10)).any()
    date_gaps = bool(duplicates_or_unsorted or large_gaps)

    return {
        "file_exists": True,
        "total_rows": total_rows,
        "start_date": start_date,
        "end_date": end_date,
        "missing_values": missing_values,
        "stale_rows": stale_rows,
        "stale_ratio": stale_ratio,
        "max_daily_return": max_return,
        "min_daily_return": min_return,
        "average_adv_usd": avg_adv,
        "date_gaps": date_gaps,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ETF data quality report.")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--price-dir", type=Path, default=DEFAULT_PRICE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_CSV)
    args = parser.parse_args()

    universe = read_universe(args.universe)
    quality_rows = []

    print(f"Analyzing {len(universe)} universe assets...")
    for asset in universe:
        ticker = asset["ticker"].upper()
        stats = inspect_quality(args.price_dir / f"{ticker}.csv")
        quality_rows.append({
            "ticker": ticker,
            "name": asset.get("name", ""),
            "asset_class": asset.get("asset_class", ""),
            **stats,
        })

    # Write report
    args.report.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(quality_rows[0].keys()) if quality_rows else []
    with args.report.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(quality_rows)

    print(f"Data quality report saved to {args.report}")
    
    # Summary printing
    total_assets = len(quality_rows)
    missing_files = sum(1 for row in quality_rows if not row["file_exists"])
    total_gaps = sum(1 for row in quality_rows if row["date_gaps"])
    high_stale = sum(1 for row in quality_rows if row["stale_ratio"] > 0.05)
    print(f"Report Summary:")
    print(f"- Total assets analyzed: {total_assets}")
    print(f"- Missing files: {missing_files}")
    print(f"- Assets with date gaps (>10 days or unsorted): {total_gaps}")
    print(f"- Assets with >5% stale prices: {high_stale}")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
