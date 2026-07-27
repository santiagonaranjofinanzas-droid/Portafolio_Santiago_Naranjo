"""Seed production master prices from downloaded Tiingo historical CSVs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, PROJECT_ROOT, log_file_hash, read_csv, read_universe, write_csv


FIELDS = [
    "date", "ticker", "open", "high", "low", "close", "adjOpen", "adjHigh", "adjLow",
    "adjClose", "adjVolume", "volume", "divCash", "splitFactor", "source", "fetch_timestamp",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize production master prices from raw Tiingo files.")
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    initialized = 0
    skipped = 0
    for ticker in read_universe():
        raw_path = args.raw_dir / f"{ticker}.csv"
        master_path = PROD_DATA / "master_prices" / f"{ticker}.csv"
        if master_path.exists() and not args.overwrite:
            skipped += 1
            continue
        raw_rows = read_csv(raw_path)
        rows = []
        for row in raw_rows:
            rows.append(
                {
                    "date": row.get("date", "")[:10],
                    "ticker": ticker,
                    "open": row.get("open", ""),
                    "high": row.get("high", ""),
                    "low": row.get("low", ""),
                    "close": row.get("close", ""),
                    "adjOpen": row.get("adjOpen", ""),
                    "adjHigh": row.get("adjHigh", ""),
                    "adjLow": row.get("adjLow", ""),
                    "adjClose": row.get("adjClose", ""),
                    "adjVolume": row.get("adjVolume", ""),
                    "volume": row.get("volume", ""),
                    "divCash": row.get("divCash", ""),
                    "splitFactor": row.get("splitFactor", ""),
                    "source": "tiingo_historical_seed",
                    "fetch_timestamp": "",
                }
            )
        write_csv(master_path, FIELDS, rows)
        log_file_hash(master_path, "initialize_master_prices")
        initialized += 1
    print(f"initialized={initialized} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
