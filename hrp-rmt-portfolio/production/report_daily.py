"""Generate a compact daily text report for F8."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, log_file_hash, read_csv, utc_now


def last_for_date(path, date: str) -> dict[str, str]  None:
    rows = [row for row in read_csv(path) if row.get("date") == date]
    return rows[-1] if rows else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily F8 report.")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    pipeline = last_for_date(PROD_DATA / "audit" / "pipeline_status.csv", args.date)
    decision = last_for_date(PROD_DATA / "ledger" / "rebalance_decisions.csv", args.date)
    risk = last_for_date(PROD_DATA / "audit" / "risk_log.csv", args.date)
    tracking = last_for_date(PROD_DATA / "ledger" / "tracking_error.csv", args.date)
    orders = [row for row in read_csv(PROD_DATA / "ledger" / "orders.csv") if row.get("date") == args.date]
    executable_orders = [row for row in orders if row.get("order_status") == "CREATED"]

    report_path = PROD_DATA / "reports" / f"daily_report_{args.date}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = [
        f"# F8 Daily Report - {args.date}",
        "",
        f"Generated UTC: {utc_now()}",
        f"Pipeline status: {pipeline.get('status') if pipeline else 'UNKNOWN'}",
        f"Pipeline detail: {pipeline.get('message') if pipeline else ''}",
        f"OMS decision: {decision.get('decision') if decision else 'UNKNOWN'}",
        f"Turnover: {decision.get('turnover') if decision else ''}",
        f"OMS records: {len(orders)}",
        f"Executable simulated orders: {len(executable_orders)}",
        f"Risk status: {risk.get('status') if risk else 'UNKNOWN'}",
        f"Risk alerts: {risk.get('alerts') if risk else ''}",
        f"Weight tracking error: {tracking.get('weight_l1_tracking_error') if tracking else ''}",
        "",
        "Configuration: HRP_UNCONDITIONAL_CORE_V1, daily calculation, monthly ordinary execution.",
    ]
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    log_file_hash(report_path, "report_daily")
    print(f"report={report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
