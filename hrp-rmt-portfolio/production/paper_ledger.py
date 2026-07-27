"""Append-only paper ledger updater."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, read_csv, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert simulated filled orders into paper positions.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--cash-ticker", default="BIL")
    args = parser.parse_args()

    orders = [row for row in read_csv(PROD_DATA / "ledger" / "orders.csv") if row.get("date") == args.date]
    filled = [row for row in orders if row.get("order_status") == "CREATED"]
    targets = [row for row in read_csv(PROD_DATA / "target_weights.csv") if row.get("date") == args.date]

    if filled:
        for order in filled:
            append_csv_row(
                PROD_DATA / "ledger" / "fills.csv",
                ["timestamp_utc", "date", "ticker", "side", "weight_delta", "fill_status", "estimated_total_cost"],
                {
                    "timestamp_utc": utc_now(),
                    "date": args.date,
                    "ticker": order["ticker"],
                    "side": order["side"],
                    "weight_delta": order["delta_weight"],
                    "fill_status": "SIMULATED_FILLED",
                    "estimated_total_cost": order["estimated_total_cost"],
                },
            )
        for target in targets:
            append_csv_row(
                PROD_DATA / "ledger" / "positions.csv",
                ["timestamp_utc", "date", "ticker", "weight", "source"],
                {
                    "timestamp_utc": utc_now(),
                    "date": args.date,
                    "ticker": target["ticker"],
                    "weight": target["final_target_weight"],
                    "source": "simulated_fill",
                },
            )
    elif not read_csv(PROD_DATA / "ledger" / "positions.csv") and targets:
        for target in targets:
            append_csv_row(
                PROD_DATA / "ledger" / "positions.csv",
                ["timestamp_utc", "date", "ticker", "weight", "source"],
                {
                    "timestamp_utc": utc_now(),
                    "date": args.date,
                    "ticker": target["ticker"],
                    "weight": target["final_target_weight"],
                    "source": "initial_shadow_position",
                },
            )

    total_cost = sum(float(row.get("estimated_total_cost", 0.0)) for row in filled)
    append_csv_row(
        PROD_DATA / "ledger" / "costs.csv",
        ["timestamp_utc", "date", "estimated_total_cost", "fills"],
        {"timestamp_utc": utc_now(), "date": args.date, "estimated_total_cost": total_cost, "fills": len(filled)},
    )
    print(f"fills={len(filled)} estimated_total_cost={total_cost:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
