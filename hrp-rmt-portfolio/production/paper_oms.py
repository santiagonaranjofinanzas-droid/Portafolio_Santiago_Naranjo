"""Simulated OMS for F8 shadow paper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.io_utils import PROD_DATA, append_csv_row, read_csv, utc_now


TRADE_DECISIONS = {"MONTH_END_REBALANCE", "RISK_REDUCTION"}


def rows_for_date(path, date: str) -> list[dict[str, str]]:
    return [row for row in read_csv(path) if row.get("date") == date]


def latest_positions() -> dict[str, float]:
    rows = read_csv(PROD_DATA / "ledger" / "positions.csv")
    if not rows:
        return {}
    latest_date = max(row["date"] for row in rows)
    return {row["ticker"]: float(row["weight"]) for row in rows if row["date"] == latest_date}


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate simulated orders from target weights.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--portfolio-value", type=float, default=1_000_000.0)
    args = parser.parse_args()

    decisions = rows_for_date(PROD_DATA / "ledger" / "rebalance_decisions.csv", args.date)
    decision = decisions[-1]["decision"] if decisions else "NO_TRADE"
    targets = rows_for_date(PROD_DATA / "target_weights.csv", args.date)
    target_weights = {row["ticker"]: float(row["final_target_weight"]) for row in targets}
    current_weights = latest_positions() or {ticker: 0.0 for ticker in target_weights}

    orders = 0
    for ticker in sorted(set(target_weights)  set(current_weights)):
        target = target_weights.get(ticker, 0.0)
        current = current_weights.get(ticker, 0.0)
        delta = target - current
        status = "CREATED" if decision in TRADE_DECISIONS and abs(delta) > 1e-8 else f"BLOCKED_{decision}"
        trade_value = delta * args.portfolio_value
        side = "BUY" if delta > 0 else "SELL" if delta < 0 else "NONE"
        if status == "CREATED":
            orders += 1
        append_csv_row(
            PROD_DATA / "ledger" / "orders.csv",
            [
                "timestamp_utc", "date", "ticker", "side", "target_weight", "current_weight",
                "delta_weight", "portfolio_value", "trade_value", "estimated_commission",
                "estimated_slippage", "estimated_spread_cost", "estimated_total_cost", "order_status",
            ],
            {
                "timestamp_utc": utc_now(),
                "date": args.date,
                "ticker": ticker,
                "side": side,
                "target_weight": target,
                "current_weight": current,
                "delta_weight": delta,
                "portfolio_value": args.portfolio_value,
                "trade_value": trade_value,
                "estimated_commission": 0.0,
                "estimated_slippage": abs(trade_value) * 0.0005,
                "estimated_spread_cost": abs(trade_value) * 0.0005,
                "estimated_total_cost": abs(trade_value) * 0.001,
                "order_status": status,
            },
        )
    print(f"decision={decision} simulated_orders={orders}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
