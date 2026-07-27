"""Decide whether F8 shadow paper may trade on a given date."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, read_csv, utc_now


def is_month_end(date_str: str) -> bool:
    day = datetime.strptime(date_str, "%Y-%m-%d").date()
    probe = day + timedelta(days=1)
    while probe.weekday() >= 5:
        probe += timedelta(days=1)
    return probe.month != day.month


def latest_target_weights(date: str) -> dict[str, float]:
    rows = [row for row in read_csv(PROD_DATA / "target_weights.csv") if row.get("date") == date]
    return {row["ticker"]: float(row["final_target_weight"]) for row in rows}


def latest_positions() -> dict[str, float]:
    rows = read_csv(PROD_DATA / "ledger" / "positions.csv")
    if not rows:
        return {}
    latest_date = max(row["date"] for row in rows)
    return {row["ticker"]: float(row["weight"]) for row in rows if row["date"] == latest_date}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an OMS rebalance decision.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--turnover-buffer", type=float, default=0.03)
    parser.add_argument("--sigma-forecast", type=float, default=0.0)
    parser.add_argument("--data-status", default="OK")
    parser.add_argument("--kill-switch", action="store_true")
    args = parser.parse_args()

    target = latest_target_weights(args.date)
    current = latest_positions() or target
    all_tickers = sorted(set(target)  set(current))
    turnover = sum(abs(target.get(t, 0.0) - current.get(t, 0.0)) for t in all_tickers)

    if args.data_status != "OK":
        decision = "DATA_BLOCK"
    elif args.kill_switch:
        decision = "KILL_SWITCH"
    elif args.sigma_forecast > 0.18:
        decision = "RISK_REDUCTION"
    elif is_month_end(args.date) and turnover >= args.turnover_buffer:
        decision = "MONTH_END_REBALANCE"
    else:
        decision = "NO_TRADE"

    append_csv_row(
        PROD_DATA / "ledger" / "rebalance_decisions.csv",
        ["timestamp_utc", "date", "decision", "turnover", "is_month_end", "message"],
        {
            "timestamp_utc": utc_now(),
            "date": args.date,
            "decision": decision,
            "turnover": turnover,
            "is_month_end": is_month_end(args.date),
            "message": "daily_calc_monthly_execution",
        },
    )
    print(f"decision={decision} turnover={turnover:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
