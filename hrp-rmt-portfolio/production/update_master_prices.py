"""Validate staged daily bars and append them to per-ticker master CSVs."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, log_file_hash, read_csv, utc_now, write_csv


FIELDS = [
    "date", "ticker", "open", "high", "low", "close", "adjOpen", "adjHigh", "adjLow",
    "adjClose", "adjVolume", "volume", "divCash", "splitFactor", "source", "fetch_timestamp",
]


def validate_bar(row: dict[str, str]) -> list[str]:
    errors: list[str] = []
    if row.get("date", "")[:10] > date.today().isoformat():
        errors.append("future_date")
    for field in ["open", "high", "low", "close", "adjClose", "volume"]:
        if row.get(field, "") in {"", "None", "nan"}:
            errors.append(f"missing_{field}")
    try:
        low = float(row["low"])
        high = float(row["high"])
        open_ = float(row["open"])
        close = float(row["close"])
        if low > high or open_ < low or open_ > high or close < low or close > high:
            errors.append("ohlc_inconsistent")
    except Exception:
        errors.append("ohlc_parse_error")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Append staged prices to master files with audit logs.")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    staging_path = PROD_DATA / "staging" / f"daily_prices_{args.date}.csv"
    rows = read_csv(staging_path)
    if not rows:
        raise SystemExit(f"No staged rows found: {staging_path}")

    appended = 0
    skipped = 0
    blocked = 0
    for row in rows:
        ticker = row["ticker"].upper()
        errors = validate_bar(row)
        if errors:
            blocked += 1
            append_csv_row(
                PROD_DATA / "audit" / "data_quality_log.csv",
                ["timestamp_utc", "date", "ticker", "status", "message"],
                {"timestamp_utc": utc_now(), "date": row["date"][:10], "ticker": ticker, "status": "BLOCKED", "message": "".join(errors)},
            )
            continue

        master_path = PROD_DATA / "master_prices" / f"{ticker}.csv"
        existing = read_csv(master_path)
        existing_by_date = {item["date"][:10]: item for item in existing}
        row_date = row["date"][:10]
        normalized = {field: row.get(field, "") for field in FIELDS}
        normalized["date"] = row_date

        if row_date in existing_by_date:
            if all(str(existing_by_date[row_date].get(field, "")) == str(normalized.get(field, "")) for field in FIELDS):
                skipped += 1
            else:
                skipped += 1
                append_csv_row(
                    PROD_DATA / "audit" / "corrections_log.csv",
                    ["timestamp_utc", "date", "ticker", "status", "message"],
                    {"timestamp_utc": utc_now(), "date": row_date, "ticker": ticker, "status": "DUPLICATE_CONFLICT", "message": "master_not_overwritten"},
                )
            continue

        append_csv_row(master_path, FIELDS, normalized)
        log_file_hash(master_path, "update_master_prices")
        appended += 1

    print(f"appended={appended} skipped={skipped} blocked={blocked}")
    return 0 if blocked == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
