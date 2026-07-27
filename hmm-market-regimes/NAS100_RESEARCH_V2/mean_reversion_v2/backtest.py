"""Cost-aware next-open backtest for the MR V2 signal contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import BacktestConfig


TRADE_COLUMNS = [
    "signal_time",
    "entry_time",
    "exit_time",
    "signal_i",
    "entry_i",
    "exit_i",
    "side",
    "entry_price",
    "exit_price",
    "target_price",
    "stop_price",
    "lots",
    "bars_held",
    "gross_price_pnl",
    "price_pnl_cash",
    "commission_cash",
    "net_pnl",
    "return_on_entry_balance",
    "exit_reason",
    "partial_exit",
    "balance",
]


@dataclass(frozen=True)
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    audit: pd.DataFrame
    metrics: dict[str, Any]


def _floor_lot(raw: float, minimum: float, maximum: float, step: float) -> float:
    if not np.isfinite(raw) or raw < minimum:
        return 0.0
    units = np.floor((min(raw, maximum) + 1e-12) / step)
    lot = float(units * step)
    return lot if lot >= minimum else 0.0


def _spread_at(frame: pd.DataFrame, i: int, default: float) -> float:
    for column in ("spread_price", "spread_median", "spread"):
        if column in frame.columns:
            value = float(frame[column].iloc[i])
            if not np.isfinite(value) or value < 0:
                raise ValueError(f"invalid {column} at row {i}")
            return value
    return default


def _stop_from_signal(target: float, scale: float, stop_z: float, transform: str, side: str) -> float:
    signed = -1.0 if side == "LONG" else 1.0
    if transform == "log":
        return float(target * np.exp(signed * stop_z * scale))
    if transform == "identity":
        return float(target + signed * stop_z * scale)
    raise ValueError(f"unknown model transform: {transform}")


def _entry_fill(reference: float, spread: float, slippage: float, basis: str, side: str) -> float:
    half = spread / 2.0
    if basis == "bid":
        return reference + spread + slippage if side == "LONG" else reference - slippage
    return reference + half + slippage if side == "LONG" else reference - half - slippage


def _exit_fill(reference: float, spread: float, slippage: float, basis: str, side: str) -> float:
    half = spread / 2.0
    if basis == "bid":
        return reference - slippage if side == "LONG" else reference + spread + slippage
    return reference - half - slippage if side == "LONG" else reference + half + slippage


def _metrics(trades: pd.DataFrame, equity: pd.Series, initial_balance: float) -> dict[str, Any]:
    if trades.empty:
        return {
            "trades": 0,
            "net_pnl": 0.0,
            "return_pct": 0.0,
            "profit_factor": 0.0,
            "win_rate": 0.0,
            "max_drawdown_pct": 0.0,
            "long_trades": 0,
            "short_trades": 0,
            "partial_exits": 0,
        }
    pnl = trades["net_pnl"].to_numpy(dtype=float)
    gross_profit = float(pnl[pnl > 0].sum())
    gross_loss = float(-pnl[pnl < 0].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else (float("inf") if gross_profit > 0 else 0.0)
    running_peak = equity.cummax()
    drawdown = equity / running_peak - 1.0
    return {
        "trades": int(len(trades)),
        "net_pnl": float(pnl.sum()),
        "return_pct": float(100.0 * pnl.sum() / initial_balance),
        "profit_factor": float(profit_factor),
        "win_rate": float(np.mean(pnl > 0)),
        "max_drawdown_pct": float(-100.0 * drawdown.min()),
        "long_trades": int((trades["side"] == "LONG").sum()),
        "short_trades": int((trades["side"] == "SHORT").sum()),
        "partial_exits": int(trades["partial_exit"].sum()),
    }


def run_mean_reversion_backtest(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    config: BacktestConfig  None = None,
) -> BacktestResult:
    """Run a conservative OHLC backtest with next-bar-open execution.

    By default OHLC is treated as MT5 bid bars (configurable as mid). Full
    bid/ask spread, per-side slippage, and commission are charged; a same-bar
    target/stop ambiguity resolves to the stop, and no partial exit exists.
    """

    cfg = config or BacktestConfig()
    required_bars = {"open", "high", "low", "close"}
    required_signals = {
        "mr_long_signal",
        "mr_short_signal",
        "mr_signal_target_price",
        "mr_signal_residual_scale",
    }
    missing_bars = required_bars.difference(bars.columns)
    missing_signals = required_signals.difference(signals.columns)
    if missing_bars:
        raise ValueError(f"bars missing columns: {sorted(missing_bars)}")
    if missing_signals:
        raise ValueError(f"signals missing columns: {sorted(missing_signals)}")
    if not bars.index.equals(signals.index):
        raise ValueError("bars and signals must have exactly equal indices")
    if bars.index.has_duplicates or not bars.index.is_monotonic_increasing:
        raise ValueError("bar index must be unique and monotonically increasing")
    if len(bars) < 2:
        raise ValueError("backtest requires at least two bars")

    frame = bars.copy()
    open_ = frame["open"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    close = frame["close"].to_numpy(dtype=float)
    if np.any(~np.isfinite(np.column_stack([open_, high, low, close]))):
        raise ValueError("OHLC values must be finite")
    if np.any(high < np.maximum(open_, close)) or np.any(low > np.minimum(open_, close)):
        raise ValueError("invalid OHLC geometry")

    costs = cfg.costs
    value_per_price = costs.value_per_price_unit_per_lot
    balance = cfg.initial_balance
    position: dict[str, Any]  None = None
    trades: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    equity_values: list[float] = [balance]

    for i in range(1, len(frame)):
        ts = frame.index[i]
        spread = _spread_at(frame, i, costs.spread_price)
        closed_this_bar = False

        if position is not None:
            side = position["side"]
            bars_held = i - position["entry_i"]
            prior_break = bool(signals.get("structural_break", pd.Series(False, index=signals.index)).iloc[i - 1])
            exit_reason: str  None = None
            exit_mid: float  None = None

            if prior_break:
                exit_reason, exit_mid = "STRUCTURAL_BREAK", open_[i]
            elif bars_held >= position["time_stop_bars"]:
                exit_reason, exit_mid = "TIME_STOP", open_[i]
            else:
                if side == "LONG":
                    hit_stop = low[i] <= position["stop_price"]
                    hit_target = high[i] >= position["target_price"]
                else:
                    hit_stop = high[i] >= position["stop_price"]
                    hit_target = low[i] <= position["target_price"]
                if hit_stop:
                    exit_reason, exit_mid = "STOP", position["stop_price"]
                elif hit_target:
                    exit_reason, exit_mid = "FROZEN_MEAN", position["target_price"]

            if exit_reason is not None and exit_mid is not None:
                exit_fill = _exit_fill(
                    exit_mid,
                    spread,
                    costs.slippage_price_per_side,
                    costs.bar_price_basis,
                    side,
                )
                gross_price_pnl = (
                    exit_fill - position["entry_price"]
                    if side == "LONG"
                    else position["entry_price"] - exit_fill
                )
                price_pnl_cash = gross_price_pnl * position["lots"] * value_per_price
                commission = 2.0 * costs.commission_per_lot_per_side * position["lots"]
                net_pnl = price_pnl_cash - commission
                entry_balance = position["entry_balance"]
                balance += net_pnl
                trades.append(
                    {
                        "signal_time": position["signal_time"],
                        "entry_time": position["entry_time"],
                        "exit_time": ts,
                        "signal_i": position["signal_i"],
                        "entry_i": position["entry_i"],
                        "exit_i": i,
                        "side": side,
                        "entry_price": position["entry_price"],
                        "exit_price": exit_fill,
                        "target_price": position["target_price"],
                        "stop_price": position["stop_price"],
                        "lots": position["lots"],
                        "bars_held": bars_held,
                        "gross_price_pnl": gross_price_pnl,
                        "price_pnl_cash": price_pnl_cash,
                        "commission_cash": commission,
                        "net_pnl": net_pnl,
                        "return_on_entry_balance": net_pnl / entry_balance,
                        "exit_reason": exit_reason,
                        "partial_exit": False,
                        "balance": balance,
                    }
                )
                audit.append(
                    {
                        "time": ts,
                        "event": "EXIT",
                        "side": side,
                        "reason": exit_reason,
                        "source_signal_time": position["signal_time"],
                    }
                )
                position = None
                closed_this_bar = True

        if position is None and not closed_this_bar:
            long_signal = bool(signals["mr_long_signal"].iloc[i - 1])
            short_signal = bool(signals["mr_short_signal"].iloc[i - 1])
            if long_signal and short_signal:
                audit.append(
                    {
                        "time": ts,
                        "event": "SIGNAL_SKIPPED",
                        "side": "BOTH",
                        "reason": "CONFLICTING_SIGNALS",
                        "source_signal_time": signals.index[i - 1],
                    }
                )
            elif long_signal or short_signal:
                side = "LONG" if long_signal else "SHORT"
                target = float(signals["mr_signal_target_price"].iloc[i - 1])
                scale = float(signals["mr_signal_residual_scale"].iloc[i - 1])
                transform = (
                    str(signals["mr_model_transform"].iloc[i - 1])
                    if "mr_model_transform" in signals.columns
                    else "log"
                )
                half_life = (
                    float(signals["mr_signal_half_life"].iloc[i - 1])
                    if "mr_signal_half_life" in signals.columns
                    else float("nan")
                )
                if not np.isfinite(half_life) or half_life <= 0:
                    audit.append(
                        {
                            "time": ts,
                            "event": "SIGNAL_SKIPPED",
                            "side": side,
                            "reason": "INVALID_HALF_LIFE",
                            "source_signal_time": signals.index[i - 1],
                        }
                    )
                else:
                    stop = _stop_from_signal(target, scale, cfg.stop_z, transform, side)
                    entry_fill = _entry_fill(
                        open_[i],
                        spread,
                        costs.slippage_price_per_side,
                        costs.bar_price_basis,
                        side,
                    )
                    target_exit_fill = _exit_fill(
                        target,
                        spread,
                        costs.slippage_price_per_side,
                        costs.bar_price_basis,
                        side,
                    )
                    favorable_target = target_exit_fill > entry_fill if side == "LONG" else target_exit_fill < entry_fill
                    gross_reference_edge = target - open_[i] if side == "LONG" else open_[i] - target
                    required_signal_edge = (
                        float(signals["mr_required_edge_price"].iloc[i - 1])
                        if "mr_required_edge_price" in signals.columns
                        else float("nan")
                    )
                    edge_survives_gap = (
                        not np.isfinite(required_signal_edge)
                        or gross_reference_edge >= required_signal_edge
                    )
                    valid_stop = stop < entry_fill if side == "LONG" else stop > entry_fill
                    if not favorable_target or not edge_survives_gap or not valid_stop:
                        if not favorable_target:
                            reason = "TARGET_NOT_NET_FAVORABLE"
                        elif not edge_survives_gap:
                            reason = "OPEN_GAP_ERASED_EDGE"
                        else:
                            reason = "STOP_NOT_ADVERSE"
                        audit.append(
                            {
                                "time": ts,
                                "event": "SIGNAL_SKIPPED",
                                "side": side,
                                "reason": reason,
                                "source_signal_time": signals.index[i - 1],
                            }
                        )
                    else:
                        risk_price = abs(entry_fill - stop)
                        risk_cash_per_lot = (
                            risk_price * value_per_price
                            + 2.0 * costs.commission_per_lot_per_side
                        )
                        raw_lot = balance * cfg.risk_fraction / risk_cash_per_lot
                        lots = _floor_lot(raw_lot, costs.min_lot, costs.max_lot, costs.lot_step)
                        if lots <= 0:
                            audit.append(
                                {
                                    "time": ts,
                                    "event": "SIGNAL_SKIPPED",
                                    "side": side,
                                    "reason": "LOT_BELOW_MINIMUM",
                                    "source_signal_time": signals.index[i - 1],
                                }
                            )
                        else:
                            time_stop = int(np.ceil(cfg.time_stop_half_lives * half_life))
                            time_stop = min(cfg.max_time_stop_bars, max(cfg.min_time_stop_bars, time_stop))
                            position = {
                                "signal_time": signals.index[i - 1],
                                "entry_time": ts,
                                "signal_i": i - 1,
                                "entry_i": i,
                                "side": side,
                                "entry_price": entry_fill,
                                "target_price": target,
                                "stop_price": stop,
                                "lots": lots,
                                "time_stop_bars": time_stop,
                                "entry_balance": balance,
                            }
                            audit.append(
                                {
                                    "time": ts,
                                    "event": "ENTRY",
                                    "side": side,
                                    "reason": "NEXT_OPEN",
                                    "source_signal_time": signals.index[i - 1],
                                }
                            )

        # A position entered at this bar's open is exposed to this same bar's
        # full range.  Stop wins any ambiguous stop/target collision.
        if position is not None and position["entry_i"] == i:
            side = position["side"]
            if side == "LONG":
                hit_stop = low[i] <= position["stop_price"]
                hit_target = high[i] >= position["target_price"]
            else:
                hit_stop = high[i] >= position["stop_price"]
                hit_target = low[i] <= position["target_price"]
            if hit_stop or hit_target:
                exit_reason = "STOP" if hit_stop else "FROZEN_MEAN"
                exit_mid = position["stop_price"] if hit_stop else position["target_price"]
                exit_fill = _exit_fill(
                    exit_mid,
                    spread,
                    costs.slippage_price_per_side,
                    costs.bar_price_basis,
                    side,
                )
                gross_price_pnl = (
                    exit_fill - position["entry_price"]
                    if side == "LONG"
                    else position["entry_price"] - exit_fill
                )
                price_pnl_cash = gross_price_pnl * position["lots"] * value_per_price
                commission = 2.0 * costs.commission_per_lot_per_side * position["lots"]
                net_pnl = price_pnl_cash - commission
                balance += net_pnl
                trades.append(
                    {
                        "signal_time": position["signal_time"],
                        "entry_time": position["entry_time"],
                        "exit_time": ts,
                        "signal_i": position["signal_i"],
                        "entry_i": position["entry_i"],
                        "exit_i": i,
                        "side": side,
                        "entry_price": position["entry_price"],
                        "exit_price": exit_fill,
                        "target_price": position["target_price"],
                        "stop_price": position["stop_price"],
                        "lots": position["lots"],
                        "bars_held": 0,
                        "gross_price_pnl": gross_price_pnl,
                        "price_pnl_cash": price_pnl_cash,
                        "commission_cash": commission,
                        "net_pnl": net_pnl,
                        "return_on_entry_balance": net_pnl / position["entry_balance"],
                        "exit_reason": exit_reason,
                        "partial_exit": False,
                        "balance": balance,
                    }
                )
                audit.append(
                    {
                        "time": ts,
                        "event": "EXIT",
                        "side": side,
                        "reason": exit_reason,
                        "source_signal_time": position["signal_time"],
                    }
                )
                position = None

        if position is None:
            equity_values.append(balance)
        else:
            spread_now = _spread_at(frame, i, costs.spread_price)
            liquidation = _exit_fill(
                close[i],
                spread_now,
                costs.slippage_price_per_side,
                costs.bar_price_basis,
                position["side"],
            )
            price_pnl = (
                liquidation - position["entry_price"]
                if position["side"] == "LONG"
                else position["entry_price"] - liquidation
            )
            mtm = price_pnl * position["lots"] * value_per_price
            mtm -= 2.0 * costs.commission_per_lot_per_side * position["lots"]
            equity_values.append(balance + mtm)

    if position is not None and cfg.force_close_end:
        i = len(frame) - 1
        ts = frame.index[i]
        spread = _spread_at(frame, i, costs.spread_price)
        exit_fill = _exit_fill(
            close[i],
            spread,
            costs.slippage_price_per_side,
            costs.bar_price_basis,
            position["side"],
        )
        gross_price_pnl = (
            exit_fill - position["entry_price"]
            if position["side"] == "LONG"
            else position["entry_price"] - exit_fill
        )
        price_pnl_cash = gross_price_pnl * position["lots"] * value_per_price
        commission = 2.0 * costs.commission_per_lot_per_side * position["lots"]
        net_pnl = price_pnl_cash - commission
        balance += net_pnl
        trades.append(
            {
                "signal_time": position["signal_time"],
                "entry_time": position["entry_time"],
                "exit_time": ts,
                "signal_i": position["signal_i"],
                "entry_i": position["entry_i"],
                "exit_i": i,
                "side": position["side"],
                "entry_price": position["entry_price"],
                "exit_price": exit_fill,
                "target_price": position["target_price"],
                "stop_price": position["stop_price"],
                "lots": position["lots"],
                "bars_held": i - position["entry_i"],
                "gross_price_pnl": gross_price_pnl,
                "price_pnl_cash": price_pnl_cash,
                "commission_cash": commission,
                "net_pnl": net_pnl,
                "return_on_entry_balance": net_pnl / position["entry_balance"],
                "exit_reason": "END_OF_DATA",
                "partial_exit": False,
                "balance": balance,
            }
        )
        equity_values[-1] = balance

    trades_frame = pd.DataFrame(trades).reindex(columns=TRADE_COLUMNS)
    equity = pd.Series(equity_values, index=frame.index, name="equity", dtype=float)
    audit_frame = pd.DataFrame(audit).reindex(
        columns=["time", "event", "side", "reason", "source_signal_time"]
    )
    return BacktestResult(
        trades=trades_frame,
        equity=equity,
        audit=audit_frame,
        metrics=_metrics(trades_frame, equity, cfg.initial_balance),
    )
