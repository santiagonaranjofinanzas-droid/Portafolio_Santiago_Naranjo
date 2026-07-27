"""Summarize recent F8 shadow paper runs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, read_csv


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize recent F8 pipeline status.")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    pipeline = read_csv(PROD_DATA / "audit" / "pipeline_status.csv")
    decisions = read_csv(PROD_DATA / "ledger" / "rebalance_decisions.csv")
    risk = read_csv(PROD_DATA / "audit" / "risk_log.csv")

    decision_by_date = {row["date"]: row for row in decisions}
    risk_by_date = {row["date"]: row for row in risk}
    recent = pipeline[-args.limit :]

    print("date,pipeline_status,decision,risk_status,message")
    for row in recent:
        date = row.get("date", "")
        decision = decision_by_date.get(date, {}).get("decision", "")
        risk_status = risk_by_date.get(date, {}).get("status", "")
        message = row.get("message", "").replace(",", ";")
        print(f"{date},{row.get('status', '')},{decision},{risk_status},{message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
