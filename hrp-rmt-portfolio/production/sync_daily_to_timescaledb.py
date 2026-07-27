"""Sync one F8 daily run from append-only CSV files to TimescaleDB.

This is an idempotent persistence sync. It does not calculate weights, make
trading decisions, or alter the paper ledger.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.db import apply_schema, connect
from production.io_utils import PROD_DATA, read_csv, read_universe
from production.migrate_csv_to_timescaledb import f, i, b


def sync_market_prices(conn, asof_date: str) -> int:
    count = 0
    for ticker in read_universe():
        for row in read_csv(PROD_DATA / "master_prices" / f"{ticker}.csv"):
            if row.get("date") != asof_date:
                continue
            conn.execute(
                """
                INSERT INTO market_prices (
                    ts, ticker, open, high, low, close, adj_open, adj_high, adj_low,
                    adj_close, adj_volume, volume, div_cash, split_factor, source, fetch_timestamp
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (ts, ticker) DO NOTHING
                """,
                (
                    row["date"], row["ticker"], f(row["open"]), f(row["high"]), f(row["low"]), f(row["close"]),
                    f(row["adjOpen"]), f(row["adjHigh"]), f(row["adjLow"]), f(row["adjClose"]),
                    f(row["adjVolume"]), f(row["volume"]), f(row["divCash"]), f(row["splitFactor"]),
                    row.get("source") or "tiingo", row.get("fetch_timestamp") or None,
                ),
            )
            count += 1
    return count


def sync_daily_tables(conn, asof_date: str) -> dict[str, int]:
    counts = {"target_weights": 0, "rebalance_decisions": 0, "orders": 0, "positions": 0, "portfolio_nav": 0, "tracking_error": 0, "costs": 0, "risk_log": 0, "pipeline_status": 0}

    for row in [r for r in read_csv(PROD_DATA / "target_weights.csv") if r.get("date") == asof_date]:
        conn.execute(
            """
            INSERT INTO target_weights (
                ts, model_version, ticker, target_weight_raw, target_weight_capped,
                vol_scalar, final_target_weight, sigma_forecast, quality_status, rebalance_eligible
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ts, model_version, ticker) DO NOTHING
            """,
            (row["date"], row["model_version"], row["ticker"], f(row["target_weight_raw"]), f(row["target_weight_capped"]), f(row["vol_scalar"]), f(row["final_target_weight"]), f(row["sigma_forecast"]), row.get("quality_status"), row.get("rebalance_eligible")),
        )
        counts["target_weights"] += 1

    for row in [r for r in read_csv(PROD_DATA / "ledger" / "rebalance_decisions.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO rebalance_decisions (ts, decision, turnover, is_month_end, message) VALUES (%s,%s,%s,%s,%s) ON CONFLICT (ts, decision) DO NOTHING",
            (row["date"], row["decision"], f(row["turnover"]), b(row["is_month_end"]), row.get("message")),
        )
        counts["rebalance_decisions"] += 1

    for row in [r for r in read_csv(PROD_DATA / "ledger" / "orders.csv") if r.get("date") == asof_date]:
        conn.execute(
            """
            INSERT INTO orders (
                ts, ticker, side, target_weight, current_weight, delta_weight, portfolio_value,
                trade_value, estimated_commission, estimated_slippage, estimated_spread_cost,
                estimated_total_cost, order_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ts, ticker, order_status) DO NOTHING
            """,
            (row["date"], row["ticker"], row["side"], f(row["target_weight"]), f(row["current_weight"]), f(row["delta_weight"]), f(row["portfolio_value"]), f(row["trade_value"]), f(row["estimated_commission"]), f(row["estimated_slippage"]), f(row["estimated_spread_cost"]), f(row["estimated_total_cost"]), row["order_status"]),
        )
        counts["orders"] += 1

    for row in [r for r in read_csv(PROD_DATA / "ledger" / "positions.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO positions (ts,ticker,weight,source) VALUES (%s,%s,%s,%s) ON CONFLICT (ts,ticker) DO NOTHING",
            (row["date"], row["ticker"], f(row["weight"]), row.get("source")),
        )
        counts["positions"] += 1

    for row in [r for r in read_csv(PROD_DATA / "ledger" / "portfolio_nav.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO portfolio_nav (ts,portfolio_value,daily_pnl,drawdown) VALUES (%s,%s,%s,%s) ON CONFLICT (ts) DO NOTHING",
            (row["date"], f(row["portfolio_value"]), f(row["daily_pnl"]), f(row["drawdown"])),
        )
        counts["portfolio_nav"] += 1

    for row in [r for r in read_csv(PROD_DATA / "ledger" / "tracking_error.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO tracking_error (ts,weight_l1_tracking_error) VALUES (%s,%s) ON CONFLICT (ts) DO NOTHING",
            (row["date"], f(row["weight_l1_tracking_error"])),
        )
        counts["tracking_error"] += 1

    for row in [r for r in read_csv(PROD_DATA / "ledger" / "costs.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO costs (ts,estimated_total_cost,fills) VALUES (%s,%s,%s) ON CONFLICT (ts) DO NOTHING",
            (row["date"], f(row["estimated_total_cost"]), i(row["fills"])),
        )
        counts["costs"] += 1

    for row in [r for r in read_csv(PROD_DATA / "audit" / "pipeline_status.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO pipeline_status (event_time,asof_date,stage,status,message) VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (row["timestamp_utc"], row["date"], row["stage"], row["status"], row["message"]),
        )
        counts["pipeline_status"] += 1

    for row in [r for r in read_csv(PROD_DATA / "audit" / "risk_log.csv") if r.get("date") == asof_date]:
        conn.execute(
            "INSERT INTO risk_log (event_time,asof_date,status,max_weight,tracking_error,alerts) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
            (row["timestamp_utc"], row["date"], row["status"], f(row["max_weight"]), f(row["tracking_error"]), row["alerts"]),
        )
        counts["risk_log"] += 1

    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync one F8 date to TimescaleDB.")
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    apply_schema()
    with connect() as conn:
        counts = {"market_prices": sync_market_prices(conn, args.date)}
        counts.update(sync_daily_tables(conn, args.date))
        conn.commit()
    for table, count in counts.items():
        print(f"{table}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
