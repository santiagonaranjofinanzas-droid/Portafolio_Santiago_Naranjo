#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

import MetaTrader5 as mt5
import phase2_outbox_agent as agent


def load_local_env(path: str = "PHASE2_CREDENTIALS.local.md") -> None:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            os.environ[key.strip()] = value.strip()


def iso(ts: int) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


load_local_env()
settings = agent.load_settings()

if not mt5.initialize():
    raise SystemExit(f"MT5 initialize failed: {mt5.last_error()}")

account = mt5.account_info()
if account is None:
    raise SystemExit("MT5 account_info unavailable")

to_date = datetime.now() + timedelta(days=1)
from_date = datetime.now() - timedelta(days=90)
deals = mt5.history_deals_get(from_date, to_date)
orders = mt5.history_orders_get(from_date - timedelta(days=30), to_date)
if deals is None:
    raise SystemExit(f"history_deals_get failed: {mt5.last_error()}")

order_sl_by_pos: dict[int, float] = {}
if orders:
    for order in orders:
        data = order._asdict()
        pos_id = int(data.get("position_id") or 0)
        sl = float(data.get("sl") or 0.0)
        if pos_id > 0 and sl > 0:
            order_sl_by_pos[pos_id] = sl

by_pos: dict[int, list[dict]] = {}
for deal in deals:
    data = deal._asdict()
    if data.get("type") not in (0, 1):
        continue
    pos_id = int(data.get("position_id") or 0)
    if pos_id <= 0:
        continue
    by_pos.setdefault(pos_id, []).append(data)

sent = 0
failed = 0
for pos_id, rows in sorted(by_pos.items()):
    rows.sort(key=lambda row: row.get("time", 0))
    exits = [row for row in rows if row.get("entry") in (1, 2)]
    if not exits:
        continue

    entries = [row for row in rows if row.get("entry") == 0]
    entry = entries[0] if entries else rows[0]
    last_exit = exits[-1]
    closed_volume = sum(float(row.get("volume") or 0.0) for row in exits)
    gross = sum(float(row.get("profit") or 0.0) for row in rows)
    commission = sum(float(row.get("commission") or 0.0) for row in rows)
    swap = sum(float(row.get("swap") or 0.0) for row in rows)
    entry_type = int(entry.get("type") or 0)
    direction = "Buy" if entry_type == 0 else "Sell"
    sl = float(order_sl_by_pos.get(pos_id, 0.0))
    entry_price = float(entry.get("price") or 0.0)

    payload = {
        "position_id": pos_id,
        "deal_ticket": int(last_exit.get("ticket")),
        "account_login": int(account.login),
        "server_name": str(account.server),
        "symbol": str(entry.get("symbol") or last_exit.get("symbol")),
        "entrytime": iso(int(entry.get("time"))),
        "exittime": iso(int(last_exit.get("time"))),
        "entryprice": entry_price,
        "exitprice": float(last_exit.get("price") or 0.0),
        "gross_pnl": round(gross, 2),
        "commission": round(commission, 2),
        "swap": round(swap, 2),
        "volume": round(closed_volume, 2),
        "type_op": entry_type,
        "direction": direction,
        "exit_reason": int(last_exit.get("reason") or 0),
        "netpnl": round(gross + commission + swap, 2),
        "sl": sl,
        "risk_price": abs(entry_price - sl) if sl > 0 else 0.0,
        "valid_sl": sl > 0,
        "magic_number": int(entry.get("magic") or last_exit.get("magic") or 0),
        "entry_magic": int(entry.get("magic") or 0),
        "exit_magic": int(last_exit.get("magic") or 0),
    }

    event_id = agent.make_event_id(dict(payload))
    ok, detail = agent.send_event(settings, event_id, agent.canonical_json(payload))
    if ok:
        sent += 1
        print(f"[OK] pos={pos_id} net={payload['netpnl']} -> {detail[:160]}")
    else:
        failed += 1
        print(f"[FAIL] pos={pos_id} net={payload['netpnl']} -> {detail[:240]}")
        print(json.dumps(payload, indent=2))

print(f"[DONE] sent={sent} failed={failed}")
mt5.shutdown()
