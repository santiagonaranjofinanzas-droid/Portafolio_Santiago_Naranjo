"""Orchestrate the F8 shadow paper daily pipeline."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_step(args: list[str], allow_failure: bool = False) -> int:
    print("RUN", " ".join(args))
    result = subprocess.run([sys.executable, *args], cwd=ROOT)
    if result.returncode != 0 and not allow_failure:
        raise SystemExit(result.returncode)
    return result.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run F8 shadow paper daily pipeline.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--skip-fetch", action="store_true")
    args = parser.parse_args()

    if not args.skip_fetch:
        run_step(["production/fetch_daily.py", "--date", args.date], allow_failure=True)
        run_step(["production/update_master_prices.py", "--date", args.date], allow_failure=True)
    run_step(["production/quality_gate.py", "--date", args.date])
    run_step(["production/generate_daily_weights.py", "--date", args.date])
    run_step(["production/rebalance_decision.py", "--date", args.date])
    run_step(["production/paper_oms.py", "--date", args.date])
    run_step(["production/paper_ledger.py", "--date", args.date])
    run_step(["production/performance_tracker.py", "--date", args.date])
    run_step(["production/risk_monitor.py", "--date", args.date], allow_failure=True)
    run_step(["production/report_daily.py", "--date", args.date])
    run_step(["production/sync_daily_to_timescaledb.py", "--date", args.date], allow_failure=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
