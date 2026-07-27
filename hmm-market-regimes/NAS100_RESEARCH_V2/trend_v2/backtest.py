"""Causal next-open bar backtester with explicit NAS100 trading costs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .config import BacktestConfig


@dataclass(frozen=True)
class BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series
    metrics: dict[str, Any]


def _round_units(value: float, cfg: BacktestConfig) -> float:
    value = float(np.clip(value, cfg.min_units, cfg.max_units))
    steps = np.floor((value + 1e-12) / cfg.unit_step)
    return float(max(cfg.min_units, steps * cfg.unit_step))


def _metrics(
    trades: pd.DataFrame,
    equity: pd.Series,
    initial_cash: float,
    periods_per_year: int,
) -> dict[str, Any]:
    pnl = trades["net_pnl"].to_numpy(dtype=float) if not trades.empty else np.array([])
    wins = pnl[pnl > 0.0]
    losses = pnl[pnl < 0.0]
    gross_profit = float(wins.sum()) if len(wins) else 0.0
    gross_loss = float(abs(losses.sum())) if len(losses) else 0.0
    peak = equity.cummax() if len(equity) else pd.Series(dtype=float)
    drawdown = equity / peak - 1.0 if len(equity) else pd.Series(dtype=float)
    returns = equity.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    sharpe = (
        float(returns.mean() / returns.std(ddof=1) * np.sqrt(periods_per_year))
        if len(returns) > 1 and returns.std(ddof=1) > 0.0
        else 0.0
    )
    final_equity = float(equity.iloc[-1]) if len(equity) else float(initial_cash)
    return {
        "initial_cash": float(initial_cash),
        "final_equity": final_equity,
        "net_profit": float(final_equity - initial_cash),
        "return_pct": float((final_equity / initial_cash - 1.0) * 100.0),
        "closed_trades": int(len(trades)),
        "long_trades": int((trades["side"] == 1).sum()) if not trades.empty else 0,
        "short_trades": int((trades["side"] == -1).sum()) if not trades.empty else 0,
        "win_rate": float((pnl > 0.0).mean()) if len(pnl) else 0.0,
        "profit_factor": float(gross_profit / gross_loss)
        if gross_loss > 0.0
        else float("inf")
        if gross_profit > 0.0
        else 0.0,
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "total_transaction_cost": float(trades["costs"].sum()) if not trades.empty else 0.0,
        "spread_slippage_cost": float(trades["spread_slippage_cost"].sum())
        if not trades.empty
        else 0.0,
        "commission_cost": float(trades["commission_cost"].sum()) if not trades.empty else 0.0,
        "average_trade": float(pnl.mean()) if len(pnl) else 0.0,
        "max_drawdown_pct": float(drawdown.min() * 100.0) if len(drawdown) else 0.0,
        "bar_sharpe_annualized": sharpe,
    }


def run_bar_backtest(
    signals: pd.DataFrame,
    config: BacktestConfig  None = None,
) -> BacktestResult:
    """Execute close-derived signals at the following bar open.

    OHLC values are treated as reference (mid) prices. Buys pay half the spread
    and sells receive half less; adverse slippage is charged on both sides. A
    fixed ATR stop and maximum holding period are known when the trade opens.
    """

    cfg = config or BacktestConfig()
    required = {"open", "high", "low", "close", "atr", "entry_signal", "exit_signal"}
    missing = required.difference(signals.columns)
    if missing:
        raise ValueError(f"Missing backtest columns: {sorted(missing)}")
    if cfg.tick_size <= 0.0 or cfg.tick_value <= 0.0:
        raise ValueError("tick_size and tick_value must be positive")
    if cfg.unit_step <= 0.0 or cfg.maximum_holding_bars < 1 or cfg.periods_per_year < 1:
        raise ValueError("unit_step, maximum_holding_bars and periods_per_year must be positive")
    if cfg.target_annual_volatility is not None and cfg.volatility_column not in signals.columns:
        raise ValueError(f"volatility target requires column: {cfg.volatility_column}")
    if cfg.stop_mode == "decision_close_next_open" and cfg.stop_check_column not in signals.columns:
        raise ValueError(f"decision-close stop requires column: {cfg.stop_check_column}")
    if not signals.index.is_monotonic_increasing or signals.index.has_duplicates:
        raise ValueError("Signal index must be increasing and unique")
    if len(signals) == 0:
        empty_trades = pd.DataFrame()
        empty_equity = pd.Series(dtype=float, name="equity")
        return BacktestResult(
            empty_trades,
            empty_equity,
            _metrics(empty_trades, empty_equity, cfg.initial_cash, cfg.periods_per_year),
        )

    opens = signals["open"].to_numpy(dtype=float)
    highs = signals["high"].to_numpy(dtype=float)
    lows = signals["low"].to_numpy(dtype=float)
    closes = signals["close"].to_numpy(dtype=float)
    atr = signals["atr"].to_numpy(dtype=float)
    entry_signal = signals["entry_signal"].fillna(0).to_numpy(dtype=int)
    exit_signal = signals["exit_signal"].fillna(False).to_numpy(dtype=bool)
    if cfg.spread_column and cfg.spread_column in signals.columns:
        spreads = signals[cfg.spread_column].fillna(cfg.spread_price).to_numpy(dtype=float)
    else:
        spreads = np.full(len(signals), cfg.spread_price, dtype=float)
    spreads = np.maximum(spreads, 0.0)

    cash = float(cfg.initial_cash)
    side = 0
    units = 0.0
    entry_price = 0.0
    entry_reference = 0.0
    entry_commission = 0.0
    entry_index = -1
    entry_time: object  None = None
    stop_reference = np.nan
    trades: list[dict[str, Any]] = []
    equity_values = np.full(len(signals), cfg.initial_cash, dtype=float)

    def close_position(row: int, reference_price: float, reason: str) -> None:
        nonlocal cash, side, units, entry_price, entry_reference
        nonlocal entry_commission, entry_index, entry_time, stop_reference
        half_spread = spreads[row] / 2.0
        exit_price = reference_price - side * (half_spread + cfg.slippage_price)
        price_pnl = side * (exit_price - entry_price) * units * cfg.tick_value / cfg.tick_size
        reference_pnl = (
            side
            * (reference_price - entry_reference)
            * units
            * cfg.tick_value
            / cfg.tick_size
        )
        execution_drag = reference_pnl - price_pnl
        exit_commission = units * cfg.commission_per_unit_per_side
        cash += price_pnl - exit_commission
        net_pnl = price_pnl - entry_commission - exit_commission
        commission_cost = entry_commission + exit_commission
        total_cost = execution_drag + commission_cost
        trades.append(
            {
                "entry_time": entry_time,
                "exit_time": signals.index[row],
                "entry_i": int(entry_index),
                "exit_i": int(row),
                "side": int(side),
                "units": float(units),
                "entry_reference": float(entry_reference),
                "entry_price": float(entry_price),
                "exit_reference": float(reference_price),
                "exit_price": float(exit_price),
                "stop_reference": float(stop_reference),
                "bars_held": int(row - entry_index),
                "exit_reason": reason,
                "reference_pnl": float(reference_pnl),
                "price_pnl": float(price_pnl),
                "spread_slippage_cost": float(execution_drag),
                "commission_cost": float(commission_cost),
                "costs": float(total_cost),
                "net_pnl": float(net_pnl),
                "cash_after": float(cash),
            }
        )
        side = 0
        units = 0.0
        entry_price = 0.0
        entry_reference = 0.0
        entry_commission = 0.0
        entry_index = -1
        entry_time = None
        stop_reference = np.nan

    for row in range(len(signals)):
        # Signals observed at row-1 can only affect the open of this row.
        pending_entry = int(np.sign(entry_signal[row - 1])) if row > 0 else 0
        pending_exit = bool(exit_signal[row - 1]) if row > 0 else False

        if side != 0 and cfg.stop_mode == "decision_close_next_open" and row > 0:
            check = bool(signals[cfg.stop_check_column].iloc[row - 1])
            prior_close = closes[row - 1]
            catastrophe_exit = bool(
                check
                and (
                    (side == 1 and prior_close <= stop_reference)
                    or (side == -1 and prior_close >= stop_reference)
                )
            )
            if catastrophe_exit:
                close_position(row, opens[row], "catastrophe_stop")

        if side != 0:
            timed_out = (row - entry_index) >= cfg.maximum_holding_bars
            reversing = pending_entry != 0 and pending_entry != side
            if pending_exit or reversing or timed_out:
                reason = "time_stop" if timed_out and not (pending_exit or reversing) else "signal_exit"
                close_position(row, opens[row], reason)

        if side == 0 and pending_entry != 0:
            signal_atr = atr[row - 1]
            if np.isfinite(signal_atr) and signal_atr > 0.0:
                stop_distance = cfg.stop_atr_multiple * signal_atr
                if cfg.target_annual_volatility is not None:
                    bar_vol = float(signals[cfg.volatility_column].iloc[row - 1])
                    value_per_price_unit = cfg.tick_value / cfg.tick_size
                    annual_cash_vol_per_unit = (
                        opens[row]
                        * bar_vol
                        * value_per_price_unit
                        * np.sqrt(cfg.periods_per_year)
                    )
                    raw_units = (
                        max(cash, 0.0) * cfg.target_annual_volatility
                        / max(annual_cash_vol_per_unit, 1e-12)
                    )
                elif cfg.fixed_units is None:
                    cash_risk = max(cash, 0.0) * cfg.risk_fraction
                    risk_per_unit = stop_distance * cfg.tick_value / cfg.tick_size
                    raw_units = cash_risk / max(risk_per_unit, 1e-12)
                else:
                    raw_units = cfg.fixed_units
                units = _round_units(float(raw_units), cfg)
                side = pending_entry
                entry_reference = opens[row]
                entry_price = opens[row] + side * (spreads[row] / 2.0 + cfg.slippage_price)
                stop_reference = opens[row] - side * stop_distance
                entry_commission = units * cfg.commission_per_unit_per_side
                cash -= entry_commission
                entry_index = row
                entry_time = signals.index[row]

        # The fixed stop is active during the entry bar as well. With only OHLC,
        # a touched stop receives the configured adverse fill.
        if cfg.stop_mode == "intrabar" and side == 1 and lows[row] <= stop_reference:
            close_position(row, stop_reference, "atr_stop")
        elif cfg.stop_mode == "intrabar" and side == -1 and highs[row] >= stop_reference:
            close_position(row, stop_reference, "atr_stop")

        if side != 0 and row == len(signals) - 1 and cfg.force_close:
            close_position(row, closes[row], "end_of_test")

        if side == 0:
            equity_values[row] = cash
        else:
            liquidation_price = closes[row] - side * spreads[row] / 2.0
            floating = side * (liquidation_price - entry_price) * units * cfg.tick_value / cfg.tick_size
            equity_values[row] = cash + floating

    trades_frame = pd.DataFrame(trades)
    equity = pd.Series(equity_values, index=signals.index, name="equity")
    return BacktestResult(
        trades=trades_frame,
        equity=equity,
        metrics=_metrics(trades_frame, equity, cfg.initial_cash, cfg.periods_per_year),
    )
