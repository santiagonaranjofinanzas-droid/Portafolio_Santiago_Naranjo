"""Fetch daily Tiingo bars into a dated staging file."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, load_dotenv, log_file_hash, read_universe, utc_now, write_csv


FIELDS = [
    "date", "ticker", "open", "high", "low", "close", "adjOpen", "adjHigh", "adjLow",
    "adjClose", "adjVolume", "volume", "divCash", "splitFactor", "source", "fetch_timestamp",
]


def fetch_tiingo_bar(ticker: str, date: str, api_key: str) -> list[dict]:
    query = urlencode({"startDate": date, "endDate": date})
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?{query}"
    request = Request(url, headers={"Authorization": f"Token {api_key}"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("Unexpected Tiingo payload")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch one daily Tiingo bar per ETF into staging.")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--tickers", nargs="*")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        raise SystemExit("Missing TIINGO_API_KEY")

    tickers = [ticker.upper() for ticker in args.tickers] if args.tickers else read_universe()
    fetch_timestamp = utc_now()
    rows: list[dict] = []
    failures = 0

    for ticker in tickers:
        try:
            bars = fetch_tiingo_bar(ticker, args.date, api_key)
            if not bars:
                failures += 1
                append_csv_row(
                    PROD_DATA / "audit" / "fetch_log.csv",
                    ["timestamp_utc", "date", "ticker", "status", "message"],
                    {"timestamp_utc": fetch_timestamp, "date": args.date, "ticker": ticker, "status": "MISSING", "message": "no_bar"},
                )
                continue
            for bar in bars:
                rows.append({**bar, "ticker": ticker, "source": "tiingo", "fetch_timestamp": fetch_timestamp})
        except Exception as exc:  # noqa: BLE001 - audit script must log vendor failures
            failures += 1
            append_csv_row(
                PROD_DATA / "audit" / "fetch_log.csv",
                ["timestamp_utc", "date", "ticker", "status", "message"],
                {"timestamp_utc": fetch_timestamp, "date": args.date, "ticker": ticker, "status": "ERROR", "message": str(exc)[:300]},
            )

    staging_path = PROD_DATA / "staging" / f"daily_prices_{args.date}.csv"
    write_csv(staging_path, FIELDS, rows)
    log_file_hash(staging_path, "fetch_daily")
    print(f"staging_file={staging_path}")
    print(f"rows={len(rows)} failures={failures}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
