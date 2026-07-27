import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Capa_4.backtest_metrics import BacktestAssumptions
from Capa_4.sovereign_execution import CFinancialEngine


def _pnl_money(price_diff: float, lot: float, tick_value: float, tick_size: float) -> float:
    return price_diff * lot * (tick_value / tick_size)


def _shifted_bool(df: pd.DataFrame, column: str, default: bool = False) -> np.ndarray:
    if column not in df.columns:
        return np.full(len(df), default, dtype=bool)
    return df[column].shift(1).fillna(int(default)).to_numpy(dtype=bool)


def _record_cashflow(cashflows: list[dict], ts, i: int, kind: str, side: str, pnl: float, balance: float) -> None:
    cashflows.append({
        "time": ts,
        "bar_i": i,
        "type": kind,
        "side": side,
        "pnl": pnl,
        "balance": balance,
    })


def run_mean_reversion_backtest(
    df: pd.DataFrame,
    assumptions: BacktestAssumptions,
    z_entry_long: float,
    z_entry_short: float,
    vol_multiplier_mr: float,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    """Backtest MR with ex-ante filters, partial TP, breakeven, costs, and MTM equity."""
    cfg = assumptions

    open_prices = df["open"].to_numpy(dtype=float)
    close_prices = df["close"].to_numpy(dtype=float)
    high_prices = df["high"].to_numpy(dtype=float)
    low_prices = df["low"].to_numpy(dtype=float)

    z_dev = df["Z_dev"].shift(1).fillna(0).to_numpy(dtype=float)
    regime = df["Regime_Buffer_18"].shift(1).fillna(0).to_numpy(dtype=int)
    atr = df["ATR_14"].shift(1).fillna(0).to_numpy(dtype=float)
    kalman_mean = df["Kalman_Precio_Medio"].shift(1).fillna(0).to_numpy(dtype=float)
    vol_blocked = _shifted_bool(df, "MR_Volatility_Blocked", default=False)
    accel_blocked = _shifted_bool(df, "MR_Accel_Blocked", default=False)
    up_blocked = _shifted_bool(df, "MR_Strong_Up_Blocked", default=False)
    down_blocked = _shifted_bool(df, "MR_Strong_Down_Blocked", default=False)

    timestamps = df.index.to_numpy() if isinstance(df.index, pd.DatetimeIndex) else np.arange(len(df))

    balance = cfg.initial_balance
    position = None
    entry_price = 0.0
    entry_time = None
    entry_i = 0
    initial_lot = 0.0
    current_lot = 0.0
    stop_loss = 0.0
    partial_done = False

    cashflows: list[dict] = []
    trades: list[dict] = []
    equity_values: list[tuple] = []

    for i in range(1, len(df)):
        ts = timestamps[i]
        close_t = close_prices[i]
        high_t = high_prices[i]
        low_t = low_prices[i]
        open_t = open_prices[i]

        if position is None:
            if regime[i] == 0 and not vol_blocked[i] and not accel_blocked[i]:
                is_long = (z_dev[i] < -z_entry_long) and not down_blocked[i]
                is_short = (z_dev[i] > z_entry_short) and not up_blocked[i]

                if is_long or is_short:
                    entry_time = ts
                    entry_i = i
                    atr_i = max(atr[i], 1e-6)
                    sl_dist = vol_multiplier_mr * atr_i
                    sl_pts = int(sl_dist / cfg.point)
                    initial_lot = CFinancialEngine.calculate_adaptive_lot(
                        balance,
                        cfg.risk_percent,
                        sl_pts,
                        cfg.tick_value,
                        cfg.tick_size,
                        cfg.point,
                        cfg.max_lot,
                        min_lot=cfg.min_lot,
                        lot_step=cfg.lot_step,
                    )
                    current_lot = initial_lot
                    partial_done = False

                    if is_long:
                        position = "BUY"
                        entry_price = open_t + (cfg.spread_price / 2.0)
                        stop_loss = entry_price - sl_dist
                    else:
                        position = "SELL"
                        entry_price = open_t - (cfg.spread_price / 2.0)
                        stop_loss = entry_price + sl_dist

            equity_values.append((ts, balance))
            continue

        closed = False
        exit_reason = None
        exit_price = None
        current_kalman = kalman_mean[i]

        if regime[i] != 0:
            closed = True
            exit_reason = "REGIME_CHANGE"
            if position == "BUY":
                exit_price = open_t - (cfg.spread_price / 2.0) - cfg.slippage_price
            else:
                exit_price = open_t + (cfg.spread_price / 2.0) + cfg.slippage_price

        if not closed and position == "BUY":
            hit_sl = low_t <= stop_loss
            hit_tp = current_kalman > entry_price and high_t >= current_kalman
            partial_target = entry_price + max((current_kalman - entry_price) * 0.50, cfg.point)
            hit_partial = (not partial_done) and current_kalman > entry_price and high_t >= partial_target

            if cfg.intrabar_mode == "pessimistic" and hit_sl and (hit_tp or hit_partial):
                closed = True
                exit_reason = "SL"
                exit_price = stop_loss - cfg.slippage_price
            elif hit_sl:
                closed = True
                exit_reason = "SL"
                exit_price = stop_loss - cfg.slippage_price
            elif hit_partial:
                closed_lot = round((current_lot * 0.50) / cfg.lot_step) * cfg.lot_step
                closed_lot = round(closed_lot, 4)
                remaining_lot = round(current_lot - closed_lot, 4)
                if closed_lot >= cfg.min_lot and remaining_lot >= cfg.min_lot:
                    fill = partial_target - cfg.slippage_price
                    result = _pnl_money(fill - entry_price, closed_lot, cfg.tick_value, cfg.tick_size)
                    result -= closed_lot * 2.0 * cfg.commission_per_lot
                    balance += result
                    _record_cashflow(cashflows, ts, i, "partial", position, result, balance)
                    current_lot = remaining_lot
                    stop_loss = entry_price
                    partial_done = True
                    if low_t <= stop_loss:
                        closed = True
                        exit_reason = "BE_AFTER_PARTIAL"
                        exit_price = stop_loss - cfg.slippage_price
            elif hit_tp:
                closed = True
                exit_reason = "TP"
                exit_price = max(current_kalman, open_t) - cfg.slippage_price

        elif not closed and position == "SELL":
            hit_sl = high_t >= stop_loss
            hit_tp = current_kalman < entry_price and low_t <= current_kalman
            partial_target = entry_price - max((entry_price - current_kalman) * 0.50, cfg.point)
            hit_partial = (not partial_done) and current_kalman < entry_price and low_t <= partial_target

            if cfg.intrabar_mode == "pessimistic" and hit_sl and (hit_tp or hit_partial):
                closed = True
                exit_reason = "SL"
                exit_price = stop_loss + cfg.slippage_price
            elif hit_sl:
                closed = True
                exit_reason = "SL"
                exit_price = stop_loss + cfg.slippage_price
            elif hit_partial:
                closed_lot = round((current_lot * 0.50) / cfg.lot_step) * cfg.lot_step
                closed_lot = round(closed_lot, 4)
                remaining_lot = round(current_lot - closed_lot, 4)
                if closed_lot >= cfg.min_lot and remaining_lot >= cfg.min_lot:
                    fill = partial_target + cfg.slippage_price
                    result = _pnl_money(entry_price - fill, closed_lot, cfg.tick_value, cfg.tick_size)
                    result -= closed_lot * 2.0 * cfg.commission_per_lot
                    balance += result
                    _record_cashflow(cashflows, ts, i, "partial", position, result, balance)
                    current_lot = remaining_lot
                    stop_loss = entry_price
                    partial_done = True
                    if high_t >= stop_loss:
                        closed = True
                        exit_reason = "BE_AFTER_PARTIAL"
                        exit_price = stop_loss + cfg.slippage_price
            elif hit_tp:
                closed = True
                exit_reason = "TP"
                exit_price = min(current_kalman, open_t) + cfg.slippage_price

        if not closed and i == len(df) - 1:
            closed = True
            exit_reason = "END_OF_DATA"
            if position == "BUY":
                exit_price = close_t - (cfg.spread_price / 2.0) - cfg.slippage_price
            else:
                exit_price = close_t + (cfg.spread_price / 2.0) + cfg.slippage_price

        if closed:
            price_diff = exit_price - entry_price if position == "BUY" else entry_price - exit_price
            result = _pnl_money(price_diff, current_lot, cfg.tick_value, cfg.tick_size)
            result -= current_lot * 2.0 * cfg.commission_per_lot
            balance += result
            _record_cashflow(cashflows, ts, i, "final", position, result, balance)

            interval_pnl = sum(cf["pnl"] for cf in cashflows if entry_i <= cf["bar_i"] <= i)
            trades.append({
                "entry_time": entry_time,
                "exit_time": ts,
                "entry_i": entry_i,
                "exit_i": i,
                "side": position,
                "entry_price": entry_price,
                "exit_price": exit_price,
                "initial_lot": initial_lot,
                "final_lot": current_lot,
                "pnl": interval_pnl,
                "reason": exit_reason,
                "bars_held": i - entry_i,
                "partial_done": partial_done,
                "balance": balance,
            })
            position = None
            equity_values.append((ts, balance))
        else:
            if position == "BUY":
                floating_pnl = _pnl_money((close_t - (cfg.spread_price / 2.0)) - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
            else:
                floating_pnl = _pnl_money(entry_price - (close_t + (cfg.spread_price / 2.0)), current_lot, cfg.tick_value, cfg.tick_size)
            equity_values.append((ts, balance + floating_pnl))

    cashflows_df = pd.DataFrame(cashflows)
    trades_df = pd.DataFrame(trades)
    if equity_values:
        times, balances = zip(*equity_values)
        equity_series = pd.Series(balances, index=times, name="equity")
    else:
        equity_series = pd.Series([cfg.initial_balance], index=[df.index[0]], name="equity")
    return cashflows_df, trades_df, equity_series
