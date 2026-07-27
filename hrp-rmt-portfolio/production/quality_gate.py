"""Daily data quality gate for F8 shadow paper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, read_csv, read_universe, utc_now


def inspect_ticker(ticker: str, asof_date: str, min_rows: int) -> tuple[str, str]:
    rows = read_csv(PROD_DATA / "master_prices" / f"{ticker}.csv")
    if len(rows) < min_rows:
        return "BLOCKED", f"insufficient_window:{len(rows)}"
    latest = rows[-1]
    if latest.get("date", "") > asof_date:
        return "BLOCKED", "future_date"
    if latest.get("date", "") < asof_date:
        return "WARN", f"missing_asof_latest={latest.get('date', '')}"
    if latest.get("volume") in {"", "0", "0.0"}:
        return "WARN", "zero_volume"
    try:
        low = float(latest["low"])
        high = float(latest["high"])
        close = float(latest["close"])
        if low > high or close < low or close > high:
            return "BLOCKED", "ohlc_inconsistent"
    except Exception:
        return "BLOCKED", "parse_error"
    return "OK", "ok"


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate whether the daily pipeline is operable.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--min-rows", type=int, default=504)
    parser.add_argument("--min-valid", type=int, default=40)
    args = parser.parse_args()

    valid = 0
    blocked = 0
    warnings = 0
    for ticker in read_universe():
        status, message = inspect_ticker(ticker, args.date, args.min_rows)
        if status == "OK":
            valid += 1
        elif status == "WARN":
            warnings += 1
        else:
            blocked += 1
        append_csv_row(
            PROD_DATA / "audit" / "data_quality_log.csv",
            ["timestamp_utc", "date", "ticker", "status", "message"],
            {"timestamp_utc": utc_now(), "date": args.date, "ticker": ticker, "status": status, "message": message},
        )

    pipeline_status = "OK" if valid >= args.min_valid and blocked == 0 else "BLOCKED"
    append_csv_row(
        PROD_DATA / "audit" / "pipeline_status.csv",
        ["timestamp_utc", "date", "stage", "status", "message"],
        {
            "timestamp_utc": utc_now(),
            "date": args.date,
            "stage": "quality_gate",
            "status": pipeline_status,
            "message": f"valid={valid}; warnings={warnings}; blocked={blocked}",
        },
    )
    print(f"status={pipeline_status} valid={valid} warnings={warnings} blocked={blocked}")
    return 0 if pipeline_status == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
