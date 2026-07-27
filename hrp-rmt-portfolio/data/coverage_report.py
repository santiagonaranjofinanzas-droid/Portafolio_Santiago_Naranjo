"""Create a simple coverage report for downloaded Tiingo price files."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
DEFAULT_PRICE_DIR = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"
DEFAULT_REPORT = PROJECT_ROOT / "data" / "quality" / "tiingo_coverage_report.csv"


def read_universe(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def inspect_price_file(path: Path) -> dict[str, object]:
    if not path.exists():
        return {"exists": False, "rows": 0, "first_date": "", "last_date": "", "zero_volume_rows": 0}

    rows = 0
    first_date = ""
    last_date = ""
    zero_volume_rows = 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            rows += 1
            first_date = first_date or row.get("date", "")
            last_date = row.get("date", "")
            if row.get("volume") in {"0", "0.0", ""}:
                zero_volume_rows += 1
    return {
        "exists": True,
        "rows": rows,
        "first_date": first_date,
        "last_date": last_date,
        "zero_volume_rows": zero_volume_rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Tiingo local data coverage.")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--price-dir", type=Path, default=DEFAULT_PRICE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    universe = read_universe(args.universe)
    report_rows = []
    for asset in universe:
        ticker = asset["ticker"].upper()
        stats = inspect_price_file(args.price_dir / f"{ticker}.csv")
        report_rows.append({**asset, **stats})

    if args.json:
        print(json.dumps(report_rows, indent=2))
    else:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(report_rows[0].keys()) if report_rows else []
        with args.report.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(report_rows)
        missing = sum(1 for row in report_rows if not row["exists"])
        empty = sum(1 for row in report_rows if row["exists"] and row["rows"] == 0)
        print(f"coverage_report={args.report}")
        print(f"assets={len(report_rows)} missing_files={missing} empty_files={empty}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
