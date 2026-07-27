"""Risk monitor for F8 shadow paper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, read_csv, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate daily risk state.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--max-weight", type=float, default=0.15)
    parser.add_argument("--tracking-error-limit", type=float, default=0.01)
    args = parser.parse_args()

    positions = [row for row in read_csv(PROD_DATA / "ledger" / "positions.csv") if row.get("date") == args.date]
    tracking = [row for row in read_csv(PROD_DATA / "ledger" / "tracking_error.csv") if row.get("date") == args.date]
    max_weight = max((float(row["weight"]) for row in positions if row["ticker"] != "BIL"), default=0.0)
    te = float(tracking[-1]["weight_l1_tracking_error"]) if tracking else 0.0

    status = "OK"
    alerts = []
    if max_weight > args.max_weight + 1e-8:
        status = "BLOCKED"
        alerts.append("MAX_WEIGHT")
    if te > args.tracking_error_limit:
        status = "WARN" if status == "OK" else status
        alerts.append("TRACKING_ERROR")

    append_csv_row(
        PROD_DATA / "audit" / "risk_log.csv",
        ["timestamp_utc", "date", "status", "max_weight", "tracking_error", "alerts"],
        {
            "timestamp_utc": utc_now(),
            "date": args.date,
            "status": status,
            "max_weight": max_weight,
            "tracking_error": te,
            "alerts": "".join(alerts) if alerts else "none",
        },
    )
    print(f"risk_status={status} alerts={alerts if alerts else 'none'}")
    return 0 if status != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
