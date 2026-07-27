"""Causal portfolio backtest for the frozen H18 signals plus risk overlay."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .institutional import (
    InstitutionalRiskGovernor,
    InstitutionalRiskPolicy,
    InstrumentSpec,
    PortfolioPosition,
    RiskSnapshot,
)


@dataclass(frozen=True)
class H18PortfolioResult:
    trades: pd.DataFrame
    equity: pd.Series
    risk_events: pd.DataFrame
    metrics: dict[str, Any]


def _summary(trades: pd.DataFrame, equity: pd.Series, initial_cash: float) -> dict[str, Any]:
    pnl = trades["net_pnl"].to_numpy(float) if not trades.empty else np.array([])
    gains = float(pnl[pnl > 0].sum()) if len(pnl) else 0.0
    losses = float(-pnl[pnl < 0].sum()) if len(pnl) else 0.0
    drawdown = equity / equity.cummax() - 1.0
    daily = equity.resample("1D").last().ffill().pct_change().dropna()
    sharpe = (
        float(daily.mean() / daily.std(ddof=1) * np.sqrt(252.0))
        if len(daily) > 1 and daily.std(ddof=1) > 0
        else 0.0
    )
    return {
        "initial_cash": initial_cash,
        "final_equity": float(equity.iloc[-1]),
        "net_profit": float(equity.iloc[-1] - initial_cash),
        "return_pct": float((equity.iloc[-1] / initial_cash - 1.0) * 100.0),
        "closed_trades": int(len(trades)),
        "profit_factor": gains / losses if losses else float("inf") if gains else 0.0,
        "average_trade": float(pnl.mean()) if len(pnl) else 0.0,
        "max_drawdown_pct": float(drawdown.min() * 100.0),
        "daily_sharpe": sharpe,
        "risk_rejections": 0,
        "disaster_stop_exits": int((trades.get("exit_reason", pd.Series(dtype=str)) == "server_disaster_stop").sum()),
        "executive_stop_exits": int((trades.get("exit_reason", pd.Series(dtype=str)) == "executive_stop").sum()),
        "emergency_exits": int((trades.get("exit_reason", pd.Series(dtype=str)) == "drawdown_emergency").sum()),
    }


def run_h18_portfolio_backtest(
    signals_by_magic: dict[int, pd.DataFrame],
    *,
    policy: InstitutionalRiskPolicy  None = None,
    spec: InstrumentSpec  None = None,
    initial_cash: float = 100_000.0,
    spread_price: float = 2.5,
    slippage_price_per_side: float = 0.10,
    commission_per_lot_per_side: float = 3.0,
    maximum_volume: float = 10.0,
) -> H18PortfolioResult:
    """Run both sleeves on one equity curve with causal pre-trade risk checks.

    Signals at row t-1 execute at row t open.  The disaster SL is active from
    the entry bar and gap fills use the worse of bar open and stop price.
    """

    if set(signals_by_magic) != {6001, 6002}:
        raise ValueError("portfolio backtest requires exactly magics 6001 and 6002")
    first = signals_by_magic[6001]
    if len(first) == 0 or not first.index.equals(signals_by_magic[6002].index):
        raise ValueError("both signal frames must have the same non-empty index")
    if not first.index.is_monotonic_increasing or first.index.has_duplicates:
        raise ValueError("signal index must be increasing and unique")
    required = {
        "open", "high", "low", "close", "entry_signal", "exit_signal",
        "slow_decision", "slow_atr_h1", "slow_vol_h1",
    }
    for magic, frame in signals_by_magic.items():
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"magic {magic} missing columns: {sorted(missing)}")

    risk_policy = policy or InstitutionalRiskPolicy()
    instrument = spec or InstrumentSpec("NAS100.fs", 0.01, 0.20, 0.01, 10.0, 0.01, 1_000.0)
    governor = InstitutionalRiskGovernor(risk_policy)
    cash = float(initial_cash)
    high_water = float(initial_cash)
    day_start = float(initial_cash)
    current_day = first.index[0].date()
    positions: dict[int, dict[str, Any]] = {}
    trades: list[dict[str, Any]] = []
    risk_events: list[dict[str, Any]] = []
    equity_values = np.full(len(first), initial_cash, dtype=float)

    def spread_at(row: int) -> float:
        frame = signals_by_magic[6001]
        if "spread_price" in frame.columns and np.isfinite(frame["spread_price"].iloc[row]):
            return max(0.0, float(frame["spread_price"].iloc[row]))
        return max(0.0, float(spread_price))

    def mark(reference: float, spread: float) -> float:
        floating = sum(
            (reference - spread / 2.0 - p["entry_price"])
            * p["volume"] * instrument.tick_value / instrument.tick_size
            for p in positions.values()
        )
        return cash + floating

    def close(magic: int, row: int, reference: float, reason: str) -> None:
        nonlocal cash
        p = positions.pop(magic)
        spread = spread_at(row)
        fill = reference - spread / 2.0 - slippage_price_per_side
        price_pnl = (
            (fill - p["entry_price"]) * p["volume"]
            * instrument.tick_value / instrument.tick_size
        )
        exit_commission = p["volume"] * commission_per_lot_per_side
        net = price_pnl - p["entry_commission"] - exit_commission
        cash += price_pnl - exit_commission
        trades.append({
            "magic": magic,
            "entry_time": p["entry_time"],
            "exit_time": first.index[row],
            "volume": p["volume"],
            "entry_price": p["entry_price"],
            "exit_price": fill,
            "executive_stop": p["executive_stop"],
            "disaster_stop": p["disaster_stop"],
            "exit_reason": reason,
            "net_pnl": net,
            "cash_after": cash,
        })

    for row, timestamp in enumerate(first.index):
        reference_open = float(first["open"].iloc[row])
        spread = spread_at(row)
        open_equity = mark(reference_open, spread)
        if timestamp.date() != current_day:
            current_day = timestamp.date()
            day_start = open_equity
        high_water = max(high_water, open_equity)
        snapshot = RiskSnapshot(
            open_equity, cash, max(open_equity * 0.80, 1.0), 800.0,
            max(day_start, 1.0), max(high_water, 1.0),
        )

        if governor.emergency_flatten_required(snapshot):
            for magic in list(positions):
                close(magic, row, reference_open, "drawdown_emergency")

        if row > 0:
            for magic in sorted(list(positions)):
                frame = signals_by_magic[magic]
                p = positions.get(magic)
                if p is None:
                    continue
                executive = bool(
                    frame["slow_decision"].iloc[row - 1]
                    and float(frame["close"].iloc[row - 1]) <= p["executive_stop"]
                )
                model_exit = bool(frame["exit_signal"].iloc[row - 1])
                if executive or model_exit:
                    close(magic, row, reference_open, "executive_stop" if executive else "signal_exit")

            for magic in (6001, 6002):
                frame = signals_by_magic[magic]
                if magic in positions or int(frame["entry_signal"].iloc[row - 1]) != 1:
                    continue
                spread = spread_at(row)
                entry_fill = reference_open + spread / 2.0 + slippage_price_per_side
                open_equity = mark(reference_open, spread)
                high_water = max(high_water, open_equity)
                existing = [
                    PortfolioPosition(m, instrument.symbol, p["volume"], p["entry_price"], p["disaster_stop"])
                    for m, p in positions.items()
                ]
                decision = governor.authorize_long(
                    magic=magic,
                    entry_price=entry_fill,
                    atr_h1=float(frame["slow_atr_h1"].iloc[row - 1]),
                    vol_h1=float(frame["slow_vol_h1"].iloc[row - 1]),
                    snapshot=RiskSnapshot(
                        open_equity, cash, max(open_equity * 0.80, 1.0), 800.0,
                        max(day_start, 1.0), max(high_water, 1.0),
                    ),
                    spec=instrument,
                    positions=existing,
                    maximum_volume=maximum_volume,
                )
                risk_events.append({"time": timestamp, "magic": magic, **decision.__dict__})
                if not decision.approved:
                    continue
                entry_commission = decision.volume * commission_per_lot_per_side
                cash -= entry_commission
                positions[magic] = {
                    "entry_time": timestamp,
                    "entry_price": entry_fill,
                    "volume": decision.volume,
                    "executive_stop": decision.executive_stop,
                    "disaster_stop": decision.disaster_stop,
                    "entry_commission": entry_commission,
                }

        # Server stop is active during the entry bar.  It precedes close marking.
        low = float(first["low"].iloc[row])
        for magic in sorted(list(positions)):
            p = positions.get(magic)
            if p is not None and low <= p["disaster_stop"]:
                close(magic, row, min(reference_open, p["disaster_stop"]), "server_disaster_stop")

        if row == len(first) - 1:
            for magic in list(positions):
                close(magic, row, float(first["close"].iloc[row]), "end_of_test")
        equity_values[row] = mark(float(first["close"].iloc[row]), spread_at(row))
        high_water = max(high_water, equity_values[row])

    trades_frame = pd.DataFrame(trades)
    events_frame = pd.DataFrame(risk_events)
    equity = pd.Series(equity_values, index=first.index, name="equity")
    metrics = _summary(trades_frame, equity, initial_cash)
    metrics["risk_rejections"] = int((~events_frame["approved"]).sum()) if not events_frame.empty else 0
    return H18PortfolioResult(trades_frame, equity, events_frame, metrics)
