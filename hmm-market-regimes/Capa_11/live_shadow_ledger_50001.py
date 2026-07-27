from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTDIR = ROOT / "Capa_11" / "forward_50001"
LEDGER = OUTDIR / "live_shadow_ledger_50001.csv"
STATUS = OUTDIR / "forward_status_50001.csv"


LEDGER_COLUMNS = [
    "bot_id",
    "magic",
    "symbol",
    "entry_time",
    "exit_time",
    "side",
    "volume",
    "entry_price",
    "exit_price",
    "expected_entry_price",
    "slippage_points",
    "pnl",
    "commission",
    "swap",
    "net_pnl",
    "exit_reason",
    "layer_status",
    "source",
]


def empty_ledger() -> pd.DataFrame:
    return pd.DataFrame(columns=LEDGER_COLUMNS)


def max_streak(flags: list[bool], value: bool) -> int:
    best = 0
    current = 0
    for flag in flags:
        if bool(flag) == value:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def normalize_source(path: Path) -> pd.DataFrame:
    raw = pd.read_csv(path)
    lower = {c.lower().strip(): c for c in raw.columns}

    def pick(*names: str, default=None):
        for name in names:
            if name.lower() in lower:
                return raw[lower[name.lower()]]
        return default

    pnl = pd.to_numeric(pick("profit", "pnl", default=0.0), errors="coerce").fillna(0.0)
    commission = pd.to_numeric(pick("commission", default=0.0), errors="coerce").fillna(0.0)
    swap = pd.to_numeric(pick("swap", default=0.0), errors="coerce").fillna(0.0)
    df = pd.DataFrame({
        "bot_id": 50001,
        "magic": pd.to_numeric(pick("magic", default=50001), errors="coerce").fillna(50001).astype(int),
        "symbol": pick("symbol", default="XAUUSD"),
        "entry_time": pick("entry_time", "time", "open_time", default=""),
        "exit_time": pick("exit_time", "close_time", "time", default=""),
        "side": pick("side", "type", default=""),
        "volume": pd.to_numeric(pick("volume", "lots", default=0.0), errors="coerce").fillna(0.0),
        "entry_price": pd.to_numeric(pick("entry_price", "price_open", "open_price", default=0.0), errors="coerce").fillna(0.0),
        "exit_price": pd.to_numeric(pick("exit_price", "price", "close_price", default=0.0), errors="coerce").fillna(0.0),
        "expected_entry_price": pd.to_numeric(pick("expected_entry_price", "signal_price", "requested_price", default=0.0), errors="coerce").fillna(0.0),
        "slippage_points": pd.to_numeric(pick("slippage_points", default=0.0), errors="coerce").fillna(0.0),
        "pnl": pnl,
        "commission": commission,
        "swap": swap,
        "net_pnl": pnl + commission + swap,
        "exit_reason": pick("reason", "comment", default=""),
        "layer_status": pick("layer_status", default="UNKNOWN"),
        "source": str(path),
    })
    return df[LEDGER_COLUMNS]


def write_status(ledger: pd.DataFrame) -> None:
    if ledger.empty:
        status = {
            "bot_id": 50001,
            "closed_trades": 0,
            "net_pnl": 0.0,
            "profit_factor": 0.0,
            "win_rate_pct": 0.0,
            "max_consecutive_losses": 0,
            "max_drawdown_money": 0.0,
            "max_drawdown_pct": 0.0,
            "avg_slippage_points": 0.0,
            "start_time": "",
            "end_time": "",
            "monitor_state": "WAITING_FOR_FORWARD_DATA",
        }
    else:
        pnl = ledger["net_pnl"].astype(float)
        wins = pnl > 0.0
        gross_profit = float(pnl[wins].sum())
        gross_loss = float(pnl[pnl < 0.0].sum())
        max_losses = max_streak(wins.tolist(), False)
        equity = pnl.cumsum()
        peak = equity.cummax()
        dd_money = equity - peak
        dd_pct = dd_money / (10_000.0 + peak).replace(0.0, pd.NA)
        pf = gross_profit / abs(gross_loss) if gross_loss < 0.0 else float("inf") if gross_profit > 0.0 else 0.0
        monitor_state = "ACTIVE_FORWARD"
        if max_losses >= 6 or pf < 0.90:
            monitor_state = "PAUSE_AND_REVIEW"
        status = {
            "bot_id": 50001,
            "closed_trades": int(len(ledger)),
            "net_pnl": float(pnl.sum()),
            "profit_factor": float(pf),
            "win_rate_pct": float(wins.mean() * 100.0),
            "max_consecutive_losses": int(max_losses),
            "max_drawdown_money": float(dd_money.min()) if not dd_money.empty else 0.0,
            "max_drawdown_pct": float(dd_pct.min() * 100.0) if not dd_pct.dropna().empty else 0.0,
            "avg_slippage_points": float(ledger["slippage_points"].astype(float).mean()) if "slippage_points" in ledger else 0.0,
            "start_time": str(ledger["entry_time"].min()),
            "end_time": str(ledger["exit_time"].max()),
            "monitor_state": monitor_state,
        }
    pd.DataFrame([status]).to_csv(STATUS, index=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=None, help="CSV exportado desde MT5 con historial demo.")
    parser.add_argument("--reset", action="store_true", help="Recrear ledger vacio.")
    args = parser.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    if args.reset or not LEDGER.exists():
        ledger = empty_ledger()
    else:
        ledger = pd.read_csv(LEDGER)

    if args.source:
        new_rows = normalize_source(args.source)
        ledger = pd.concat([ledger, new_rows], ignore_index=True)
        ledger = ledger.drop_duplicates(subset=["magic", "symbol", "entry_time", "exit_time", "side", "net_pnl"], keep="last")

    ledger = ledger[LEDGER_COLUMNS]
    ledger.to_csv(LEDGER, index=False)
    write_status(ledger)
    print(f"Ledger: {LEDGER}")
    print(f"Status: {STATUS}")


if __name__ == "__main__":
    main()
