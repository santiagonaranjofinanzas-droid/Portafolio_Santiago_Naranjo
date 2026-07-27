"""Daily paper performance and tracking diagnostics."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, read_csv, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Track paper NAV and target-vs-position drift.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--portfolio-value", type=float, default=1_000_000.0)
    args = parser.parse_args()

    positions = [row for row in read_csv(PROD_DATA / "ledger" / "positions.csv") if row.get("date") == args.date]
    targets = [row for row in read_csv(PROD_DATA / "target_weights.csv") if row.get("date") == args.date]
    pos = {row["ticker"]: float(row["weight"]) for row in positions}
    tgt = {row["ticker"]: float(row["final_target_weight"]) for row in targets}
    tracking_error_weight = sum(abs(tgt.get(t, 0.0) - pos.get(t, 0.0)) for t in set(pos)  set(tgt))

    append_csv_row(
        PROD_DATA / "ledger" / "tracking_error.csv",
        ["timestamp_utc", "date", "weight_l1_tracking_error"],
        {"timestamp_utc": utc_now(), "date": args.date, "weight_l1_tracking_error": tracking_error_weight},
    )
    append_csv_row(
        PROD_DATA / "ledger" / "portfolio_nav.csv",
        ["timestamp_utc", "date", "portfolio_value", "daily_pnl", "drawdown"],
        {"timestamp_utc": utc_now(), "date": args.date, "portfolio_value": args.portfolio_value, "daily_pnl": 0.0, "drawdown": 0.0},
    )
    print(f"weight_l1_tracking_error={tracking_error_weight:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
