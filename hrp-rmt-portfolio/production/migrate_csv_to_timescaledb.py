"""Migrate existing F8 CSV append-only ledgers into TimescaleDB.

This is a persistence migration only. It does not alter trading decisions,
weights, OMS logic, or risk gates.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from production.db import apply_schema, connect
from production.io_utils import PROD_DATA, read_csv


def f(value: str) -> float  None:
    if value in {"", "None", "nan", None}:
        return None
    return float(value)


def i(value: str) -> int  None:
    if value in {"", "None", "nan", None}:
        return None
    return int(float(value))


def b(value: str) -> bool  None:
    if value in {"", None}:
        return None
    return str(value).lower() in {"true", "1", "yes"}


def migrate_market_prices(conn) -> int:
    count = 0
    for path in (PROD_DATA / "master_prices").glob("*.csv"):
        for row in read_csv(path):
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


def migrate_target_weights(conn) -> int:
    count = 0
    for row in read_csv(PROD_DATA / "target_weights.csv"):
        conn.execute(
            """
            INSERT INTO target_weights (
                ts, model_version, ticker, target_weight_raw, target_weight_capped,
                vol_scalar, final_target_weight, sigma_forecast, quality_status, rebalance_eligible
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ts, model_version, ticker) DO NOTHING
            """,
            (
                row["date"], row["model_version"], row["ticker"], f(row["target_weight_raw"]),
                f(row["target_weight_capped"]), f(row["vol_scalar"]), f(row["final_target_weight"]),
                f(row["sigma_forecast"]), row.get("quality_status"), row.get("rebalance_eligible"),
            ),
        )
        count += 1
    return count


def migrate_rebalance_decisions(conn) -> int:
    count = 0
    for row in read_csv(PROD_DATA / "ledger" / "rebalance_decisions.csv"):
        conn.execute(
            """
            INSERT INTO rebalance_decisions (ts, decision, turnover, is_month_end, message)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (ts, decision) DO NOTHING
            """,
            (row["date"], row["decision"], f(row["turnover"]), b(row["is_month_end"]), row.get("message")),
        )
        count += 1
    return count


def migrate_orders(conn) -> int:
    count = 0
    for row in read_csv(PROD_DATA / "ledger" / "orders.csv"):
        conn.execute(
            """
            INSERT INTO orders (
                ts, ticker, side, target_weight, current_weight, delta_weight, portfolio_value,
                trade_value, estimated_commission, estimated_slippage, estimated_spread_cost,
                estimated_total_cost, order_status
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (ts, ticker, order_status) DO NOTHING
            """,
            (
                row["date"], row["ticker"], row["side"], f(row["target_weight"]), f(row["current_weight"]),
                f(row["delta_weight"]), f(row["portfolio_value"]), f(row["trade_value"]),
                f(row["estimated_commission"]), f(row["estimated_slippage"]), f(row["estimated_spread_cost"]),
                f(row["estimated_total_cost"]), row["order_status"],
            ),
        )
        count += 1
    return count


def migrate_simple_tables(conn) -> dict[str, int]:
    counts: dict[str, int] = {}

    mappings: list[tuple[str, Path, str, list[str]]] = [
        ("fills", PROD_DATA / "ledger" / "fills.csv", "ts,ticker,side,weight_delta,fill_status,estimated_total_cost", []),
        ("positions", PROD_DATA / "ledger" / "positions.csv", "ts,ticker,weight,source", []),
        ("portfolio_nav", PROD_DATA / "ledger" / "portfolio_nav.csv", "ts,portfolio_value,daily_pnl,drawdown", []),
        ("tracking_error", PROD_DATA / "ledger" / "tracking_error.csv", "ts,weight_l1_tracking_error", []),
        ("costs", PROD_DATA / "ledger" / "costs.csv", "ts,estimated_total_cost,fills", []),
    ]

    for table, path, _, _ in mappings:
        rows = read_csv(path)
        counts[table] = 0
        for row in rows:
            if table == "fills":
                conn.execute(
                    "INSERT INTO fills (ts,ticker,side,weight_delta,fill_status,estimated_total_cost) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (ts,ticker,fill_status) DO NOTHING",
                    (row["date"], row["ticker"], row["side"], f(row["weight_delta"]), row["fill_status"], f(row["estimated_total_cost"])),
                )
            elif table == "positions":
                conn.execute(
                    "INSERT INTO positions (ts,ticker,weight,source) VALUES (%s,%s,%s,%s) ON CONFLICT (ts,ticker) DO NOTHING",
                    (row["date"], row["ticker"], f(row["weight"]), row.get("source")),
                )
            elif table == "portfolio_nav":
                conn.execute(
                    "INSERT INTO portfolio_nav (ts,portfolio_value,daily_pnl,drawdown) VALUES (%s,%s,%s,%s) ON CONFLICT (ts) DO NOTHING",
                    (row["date"], f(row["portfolio_value"]), f(row["daily_pnl"]), f(row["drawdown"])),
                )
            elif table == "tracking_error":
                conn.execute(
                    "INSERT INTO tracking_error (ts,weight_l1_tracking_error) VALUES (%s,%s) ON CONFLICT (ts) DO NOTHING",
                    (row["date"], f(row["weight_l1_tracking_error"])),
                )
            elif table == "costs":
                conn.execute(
                    "INSERT INTO costs (ts,estimated_total_cost,fills) VALUES (%s,%s,%s) ON CONFLICT (ts) DO NOTHING",
                    (row["date"], f(row["estimated_total_cost"]), i(row["fills"])),
                )
            counts[table] += 1
    return counts


def migrate_audit(conn) -> dict[str, int]:
    counts = {"data_quality_log": 0, "pipeline_status": 0, "risk_log": 0, "file_hashes": 0}
    for row in read_csv(PROD_DATA / "audit" / "data_quality_log.csv"):
        conn.execute(
            "INSERT INTO data_quality_log (event_time,asof_date,ticker,status,message) VALUES (%s,%s,%s,%s,%s)",
            (row["timestamp_utc"], row["date"] or None, row["ticker"], row["status"], row["message"]),
        )
        counts["data_quality_log"] += 1
    for row in read_csv(PROD_DATA / "audit" / "pipeline_status.csv"):
        conn.execute(
            "INSERT INTO pipeline_status (event_time,asof_date,stage,status,message) VALUES (%s,%s,%s,%s,%s)",
            (row["timestamp_utc"], row["date"] or None, row["stage"], row["status"], row["message"]),
        )
        counts["pipeline_status"] += 1
    for row in read_csv(PROD_DATA / "audit" / "risk_log.csv"):
        conn.execute(
            "INSERT INTO risk_log (event_time,asof_date,status,max_weight,tracking_error,alerts) VALUES (%s,%s,%s,%s,%s,%s)",
            (row["timestamp_utc"], row["date"] or None, row["status"], f(row["max_weight"]), f(row["tracking_error"]), row["alerts"]),
        )
        counts["risk_log"] += 1
    for row in read_csv(PROD_DATA / "audit" / "file_hashes.csv"):
        conn.execute(
            "INSERT INTO file_hashes (event_time,source,path,sha256,size_bytes) VALUES (%s,%s,%s,%s,%s)",
            (row["timestamp_utc"], row["source"], row["path"], row["sha256"], i(row["size_bytes"])),
        )
        counts["file_hashes"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate F8 CSV data to TimescaleDB.")
    parser.add_argument("--schema-only", action="store_true")
    args = parser.parse_args()

    apply_schema()
    if args.schema_only:
        print("schema=ok")
        return 0

    with connect() as conn:
        counts: dict[str, Any] = {
            "market_prices": migrate_market_prices(conn),
            "target_weights": migrate_target_weights(conn),
            "rebalance_decisions": migrate_rebalance_decisions(conn),
            "orders": migrate_orders(conn),
        }
        counts.update(migrate_simple_tables(conn))
        counts.update(migrate_audit(conn))
        conn.commit()
    for table, count in counts.items():
        print(f"{table}={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
