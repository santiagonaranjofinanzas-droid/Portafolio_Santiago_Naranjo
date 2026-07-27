"""Read-only FastAPI monitoring API for HRP-RMT F9.

This service does not calculate weights or make trading decisions. It only
exposes TimescaleDB state for monitoring.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import HTMLResponse

from production.db import connect
from production.io_utils import PROJECT_ROOT


app = FastAPI(title="HRP-RMT Monitoring API", version="1.0.0")


def rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as conn:
        cur = conn.execute(query, params)
        cols = [desc.name for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any]  None:
    result = rows(query, params)
    return result[0] if result else None


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        db = one("SELECT now() AS db_time, current_database() AS database")
        ext = one("SELECT extversion FROM pg_extension WHERE extname='timescaledb'")
        return {"status": "ok", "database": db, "timescaledb": ext["extversion"] if ext else None}
    except Exception as exc:  # noqa: BLE001 - health endpoint should report failure
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/status")
def status() -> dict[str, Any]:
    latest_pipeline = one("SELECT asof_date, stage, status, message, event_time FROM pipeline_status ORDER BY event_time DESC LIMIT 1")
    latest_risk = one("SELECT asof_date, status, max_weight, tracking_error, alerts, event_time FROM risk_log ORDER BY event_time DESC LIMIT 1")
    latest_decision = one("SELECT ts::date AS date, decision, turnover, is_month_end, message FROM rebalance_decisions ORDER BY ts DESC LIMIT 1")
    counts = rows(
        """
        SELECT 'market_prices' AS table_name, count(*) AS rows FROM market_prices
        UNION ALL SELECT 'target_weights', count(*) FROM target_weights
        UNION ALL SELECT 'orders', count(*) FROM orders
        UNION ALL SELECT 'positions', count(*) FROM positions
        """
    )
    return {
        "pipeline": latest_pipeline,
        "risk": latest_risk,
        "decision": latest_decision,
        "counts": counts,
    }


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    state = status()
    pipeline = state.get("pipeline") or {}
    risk = state.get("risk") or {}
    decision = state.get("decision") or {}
    counts = state.get("counts") or []
    latest_backup = backup_latest()
    rows_html = "".join(
        f"<tr><td>{item['table_name']}</td><td>{item['rows']}</td></tr>" for item in counts
    )
    return f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>HRP-RMT Monitoring</title>
      <style>
        body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1f2937; }}
        h1 {{ margin-bottom: 4px; }}
        .grid {{ display: grid; grid-template-columns: repeat(3, minmax(220px, 1fr)); gap: 16px; margin: 24px 0; }}
        .card {{ border: 1px solid #d1d5db; border-radius: 8px; padding: 16px; background: #fff; }}
        .ok {{ color: #047857; font-weight: 700; }}
        .warn {{ color: #b45309; font-weight: 700; }}
        table {{ border-collapse: collapse; width: 100%; max-width: 560px; }}
        td, th {{ border: 1px solid #e5e7eb; padding: 8px; text-align: left; }}
        code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
      </style>
    </head>
    <body>
      <h1>HRP-RMT Monitoring</h1>
      <div>Read-only F9 monitoring over TimescaleDB</div>
      <div class="grid">
        <div class="card"><h3>Pipeline</h3><div class="ok">{pipeline.get('status', 'UNKNOWN')}</div><p>{pipeline.get('message', '')}</p><code>{pipeline.get('asof_date', '')}</code></div>
        <div class="card"><h3>Risk</h3><div class="ok">{risk.get('status', 'UNKNOWN')}</div><p>{risk.get('alerts', '')}</p><code>max_weight={risk.get('max_weight', '')}</code></div>
        <div class="card"><h3>OMS</h3><div>{decision.get('decision', 'UNKNOWN')}</div><p>turnover={decision.get('turnover', '')}</p><code>{decision.get('date', '')}</code></div>
        <div class="card"><h3>Backup</h3><div>{latest_backup.get('status', 'UNKNOWN')}</div><p>{latest_backup.get('path', '')}</p><code>{latest_backup.get('timestamp_utc', '')}</code></div>
      </div>
      <h2>Database Counts</h2>
      <table><tr><th>Table</th><th>Rows</th></tr>{rows_html}</table>
      <p>API docs: <a href="/docs">/docs</a></p>
    </body>
    </html>
    """


@app.get("/weights/latest")
def latest_weights() -> dict[str, Any]:
    latest = one("SELECT max(ts) AS ts FROM target_weights")
    if not latest or latest["ts"] is None:
        return {"ts": None, "weights": []}
    weights = rows(
        """
        SELECT ts, model_version, ticker, final_target_weight, target_weight_capped, vol_scalar, sigma_forecast
        FROM target_weights
        WHERE ts = %s
        ORDER BY final_target_weight DESC
        """,
        (latest["ts"],),
    )
    return {"ts": latest["ts"], "weights": weights}


@app.get("/orders/latest")
def latest_orders() -> dict[str, Any]:
    latest = one("SELECT max(ts) AS ts FROM orders")
    if not latest or latest["ts"] is None:
        return {"ts": None, "orders": []}
    order_rows = rows(
        """
        SELECT ts, ticker, side, delta_weight, trade_value, estimated_total_cost, order_status
        FROM orders
        WHERE ts = %s
        ORDER BY ticker
        """,
        (latest["ts"],),
    )
    return {"ts": latest["ts"], "orders": order_rows}


@app.get("/risk/latest")
def latest_risk() -> dict[str, Any]  None:
    return one("SELECT * FROM risk_log ORDER BY event_time DESC LIMIT 1")


@app.get("/nav")
def nav(limit: int = 30) -> list[dict[str, Any]]:
    return rows(
        """
        SELECT ts, portfolio_value, daily_pnl, drawdown
        FROM portfolio_nav
        ORDER BY ts DESC
        LIMIT %s
        """,
        (limit,),
    )


@app.get("/prices/{ticker}/latest")
def latest_price(ticker: str) -> dict[str, Any]  None:
    result = one(
        """
        SELECT ts, ticker, close, adj_close, volume, source
        FROM market_prices
        WHERE ticker = %s
        ORDER BY ts DESC
        LIMIT 1
        """,
        (ticker.upper(),),
    )
    if result is None:
        raise HTTPException(status_code=404, detail="ticker not found")
    return result


@app.get("/backup/latest")
def backup_latest() -> dict[str, Any]:
    manifest = PROJECT_ROOT / "backups" / "timescaledb" / "backup_manifest.csv"
    if not manifest.exists():
        return {"status": "missing", "message": "no backup manifest found"}
    with manifest.open("r", encoding="utf-8", newline="") as handle:
        rows_ = list(csv.DictReader(handle))
    if not rows_:
        return {"status": "missing", "message": "backup manifest empty"}
    latest = {key.lstrip("\ufeff"): value for key, value in rows_[-1].items()}
    path = Path(latest["path"])
    latest["status"] = "ok" if path.exists() else "missing_file"
    return latest


@app.get("/metrics")
def metrics() -> Response:
    state = status()
    backup = backup_latest()
    counts = {item["table_name"]: item["rows"] for item in state.get("counts", [])}
    pipeline_ok = 1 if (state.get("pipeline") or {}).get("status") == "OK" else 0
    risk_ok = 1 if (state.get("risk") or {}).get("status") == "OK" else 0
    backup_ok = 1 if backup.get("status") == "ok" else 0
    lines = [
        "# HELP hrp_rmt_pipeline_ok Latest pipeline status is OK.",
        "# TYPE hrp_rmt_pipeline_ok gauge",
        f"hrp_rmt_pipeline_ok {pipeline_ok}",
        "# HELP hrp_rmt_risk_ok Latest risk status is OK.",
        "# TYPE hrp_rmt_risk_ok gauge",
        f"hrp_rmt_risk_ok {risk_ok}",
        "# HELP hrp_rmt_backup_ok Latest backup file exists.",
        "# TYPE hrp_rmt_backup_ok gauge",
        f"hrp_rmt_backup_ok {backup_ok}",
    ]
    for table, count in counts.items():
        lines.append(f'hrp_rmt_table_rows{{table="{table}"}} {count}')
    return Response("\n".join(lines) + "\n", media_type="text/plain")
