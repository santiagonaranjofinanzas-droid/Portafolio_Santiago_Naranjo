from dataclasses import dataclass
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pandas as pd

from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics
from Capa_4.sovereign_execution import CFinancialEngine


@dataclass(frozen=True)
class TickBacktestConfig:
    data_root: Path
    max_holding_bars: int = 500
    entry_delay_bars: int = 1
    max_trades: int  None = None


def _month_range(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[int, int]]:
    months = pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")
    return [(int(p.year), int(p.month)) for p in months]


def load_ticks_window(data_root: Path, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    frames = []
    for year, month in _month_range(start, end):
        month_dir = data_root / f"year={year}" / f"month={month}"
        if not month_dir.exists():
            continue
        for path in sorted(month_dir.glob("*.parquet")):
            df = pd.read_parquet(path, columns=["timestamp", "bid", "ask"])
            mask = (df["timestamp"] >= start) & (df["timestamp"] <= end)
            if mask.any():
                frames.append(df.loc[mask])
    if not frames:
        return pd.DataFrame(columns=["timestamp", "bid", "ask"])
    ticks = pd.concat(frames, ignore_index=True)
    ticks = ticks.dropna(subset=["timestamp", "bid", "ask"]).sort_values("timestamp")
    ticks = ticks.drop_duplicates(subset=["timestamp", "bid", "ask"], keep="first")
    return ticks.reset_index(drop=True)


class TickDataStore:
    def __init__(self, data_root: Path, max_cached_months: int = 2):
        self.data_root = Path(data_root)
        self.max_cached_months = max(1, int(max_cached_months))
        self._cache: OrderedDict[tuple[int, int], pd.DataFrame] = OrderedDict()

    def _load_month(self, year: int, month: int) -> pd.DataFrame:
        key = (year, month)
        if key in self._cache:
            ticks = self._cache.pop(key)
            self._cache[key] = ticks
            return ticks
        month_dir = self.data_root / f"year={year}" / f"month={month}"
        frames = []
        if month_dir.exists():
            for path in sorted(month_dir.glob("*.parquet")):
                frames.append(pd.read_parquet(path, columns=["timestamp", "bid", "ask"]))
        if frames:
            ticks = pd.concat(frames, ignore_index=True)
            ticks = ticks.dropna(subset=["timestamp", "bid", "ask"]).sort_values("timestamp")
            ticks = ticks.drop_duplicates(subset=["timestamp", "bid", "ask"], keep="first").reset_index(drop=True)
        else:
            ticks = pd.DataFrame(columns=["timestamp", "bid", "ask"])
        self._cache[key] = ticks
        while len(self._cache) > self.max_cached_months:
            self._cache.popitem(last=False)
        return ticks

    def window(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        frames = []
        for year, month in _month_range(start, end):
            ticks = self._load_month(year, month)
            if ticks.empty:
                continue
            mask = (ticks["timestamp"] >= start) & (ticks["timestamp"] <= end)
            if mask.any():
                frames.append(ticks.loc[mask])
        if not frames:
            return pd.DataFrame(columns=["timestamp", "bid", "ask"])
        return pd.concat(frames, ignore_index=True).sort_values("timestamp").reset_index(drop=True)


def _pnl_money(price_diff: float, lot: float, tick_value: float, tick_size: float) -> float:
    return price_diff * lot * (tick_value / tick_size)


def _append_equity(equity_values: list, ts, balance: float):
    if not equity_values or equity_values[-1][0] != ts:
        equity_values.append((ts, balance))


def _first_idx(mask: np.ndarray) -> int  None:
    idx = np.flatnonzero(mask)
    return int(idx[0]) if len(idx) else None


def run_tick_backtest(
    signals: pd.DataFrame,
    assumptions: BacktestAssumptions,
    config: TickBacktestConfig,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series]:
    required = {"Regime_Buffer_18", "ML_Master_Strength", "Vol_Projected_Sigma"}
    missing = required.difference(signals.columns)
    if missing:
        raise ValueError(f"Faltan columnas de senal: {sorted(missing)}")

    balance = assumptions.initial_balance
    trades = []
    cashflows = []
    equity_values = []
    bar_index = signals.index
    tick_store = TickDataStore(Path(config.data_root))
    i = 0

    while i < len(signals) - config.entry_delay_bars:
        if config.max_trades is not None and len(trades) >= config.max_trades:
            break
        ts = bar_index[i]
        _append_equity(equity_values, ts, balance)

        regime = int(signals["Regime_Buffer_18"].iloc[i])
        strength = float(signals["ML_Master_Strength"].iloc[i])
        if regime == 0 or strength < assumptions.min_strength:
            i += 1
            continue

        entry_bar_i = i + config.entry_delay_bars
        entry_time = pd.Timestamp(bar_index[entry_bar_i])
        max_exit_i = min(len(signals) - 1, entry_bar_i + config.max_holding_bars)
        end_time = pd.Timestamp(bar_index[max_exit_i]) + pd.Timedelta(minutes=15)
        ticks = tick_store.window(entry_time, end_time)
        if ticks.empty:
            i += 1
            continue

        entry_tick = ticks.iloc[0]
        side = "BUY" if regime == 1 else "SELL"
        entry_price = float(entry_tick["ask"] if side == "BUY" else entry_tick["bid"])
        entry_price += assumptions.slippage_price if side == "BUY" else -assumptions.slippage_price
        sl_dist = CFinancialEngine.calculate_volatility_stop(
            entry_price,
            float(signals["Vol_Projected_Sigma"].iloc[i]),
            assumptions.vol_multiplier,
            max(float(entry_tick["ask"] - entry_tick["bid"]), 0.0),
        )
        sl_pts = int(sl_dist / assumptions.point)
        lot = CFinancialEngine.calculate_adaptive_lot(
            balance,
            assumptions.risk_percent,
            sl_pts,
            assumptions.tick_value,
            assumptions.tick_size,
            assumptions.point,
            assumptions.max_lot,
            min_lot=assumptions.min_lot,
            lot_step=assumptions.lot_step,
        )
        if lot <= 0:
            i += 1
            continue

        if side == "BUY":
            stop_loss = entry_price - sl_dist
            take_profit = entry_price + sl_dist * assumptions.reward_risk
            partial_target = entry_price + sl_dist * (assumptions.reward_risk / 1.5)
        else:
            stop_loss = entry_price + sl_dist
            take_profit = entry_price - sl_dist * assumptions.reward_risk
            partial_target = entry_price - sl_dist * (assumptions.reward_risk / 1.5)

        current_lot = lot
        partial_done = False
        trade_cashflow_start = len(cashflows)
        closed = False
        exit_reason = "TIME"
        exit_price = float(ticks.iloc[-1]["bid"] if side == "BUY" else ticks.iloc[-1]["ask"])
        exit_time = ticks.iloc[-1]["timestamp"]

        bid_arr = ticks["bid"].to_numpy(dtype=float)
        ask_arr = ticks["ask"].to_numpy(dtype=float)
        ts_arr = ticks["timestamp"].to_numpy()

        if side == "BUY":
            sl_idx = _first_idx(bid_arr <= stop_loss)
            tp_idx = _first_idx(bid_arr >= take_profit)
            partial_idx = _first_idx(bid_arr >= partial_target) if assumptions.use_partials else None

            first_final_idx = None
            first_final_reason = None
            if sl_idx is not None and (tp_idx is None or sl_idx <= tp_idx):
                first_final_idx = sl_idx
                first_final_reason = "SL"
            elif tp_idx is not None:
                first_final_idx = tp_idx
                first_final_reason = "TP"

            if partial_idx is not None and (first_final_idx is None or partial_idx < first_final_idx):
                tick_time = pd.Timestamp(ts_arr[partial_idx])
                closed_lot = round((lot * 0.70) / assumptions.lot_step) * assumptions.lot_step
                closed_lot = round(closed_lot, 8)
                remaining_lot = round(lot - closed_lot, 8)
                if closed_lot < assumptions.min_lot or remaining_lot < assumptions.min_lot:
                    partial_idx = None
                else:
                    fill = partial_target - assumptions.slippage_price
                    result = _pnl_money(fill - entry_price, closed_lot, assumptions.tick_value, assumptions.tick_size)
                    result -= closed_lot * 2.0 * assumptions.commission_per_lot
            if partial_idx is not None and (first_final_idx is None or partial_idx < first_final_idx):
                balance += result
                cashflows.append({"time": tick_time, "type": "partial", "side": side, "pnl": result, "balance": balance})
                current_lot = remaining_lot
                partial_done = True
                post_bid = bid_arr[partial_idx:]
                post_sl = _first_idx(post_bid <= entry_price)
                post_tp = _first_idx(post_bid >= take_profit)
                if post_sl is not None and (post_tp is None or post_sl <= post_tp):
                    final_idx = partial_idx + post_sl
                    exit_price = min(entry_price, float(bid_arr[final_idx])) - assumptions.slippage_price
                    exit_reason = "SL"
                    result = _pnl_money(exit_price - entry_price, current_lot, assumptions.tick_value, assumptions.tick_size)
                elif post_tp is not None:
                    final_idx = partial_idx + post_tp
                    exit_price = take_profit - assumptions.slippage_price
                    exit_reason = "TP"
                    result = _pnl_money(exit_price - entry_price, current_lot, assumptions.tick_value, assumptions.tick_size)
                else:
                    final_idx = None
                if final_idx is not None:
                    result -= current_lot * 2.0 * assumptions.commission_per_lot
                    exit_time = pd.Timestamp(ts_arr[final_idx])
                    balance += result
                    cashflows.append({"time": exit_time, "type": "final", "side": side, "pnl": result, "balance": balance})
                    closed = True
            elif first_final_idx is not None:
                exit_time = pd.Timestamp(ts_arr[first_final_idx])
                exit_reason = first_final_reason
                exit_price = (min(stop_loss, float(bid_arr[first_final_idx])) - assumptions.slippage_price) if first_final_reason == "SL" else (take_profit - assumptions.slippage_price)
                result = _pnl_money(exit_price - entry_price, current_lot, assumptions.tick_value, assumptions.tick_size)
                result -= current_lot * 2.0 * assumptions.commission_per_lot
                balance += result
                cashflows.append({"time": exit_time, "type": "final", "side": side, "pnl": result, "balance": balance})
                closed = True
        else:
            sl_idx = _first_idx(ask_arr >= stop_loss)
            tp_idx = _first_idx(ask_arr <= take_profit)
            partial_idx = _first_idx(ask_arr <= partial_target) if assumptions.use_partials else None

            first_final_idx = None
            first_final_reason = None
            if sl_idx is not None and (tp_idx is None or sl_idx <= tp_idx):
                first_final_idx = sl_idx
                first_final_reason = "SL"
            elif tp_idx is not None:
                first_final_idx = tp_idx
                first_final_reason = "TP"

            if partial_idx is not None and (first_final_idx is None or partial_idx < first_final_idx):
                tick_time = pd.Timestamp(ts_arr[partial_idx])
                closed_lot = round((lot * 0.70) / assumptions.lot_step) * assumptions.lot_step
                closed_lot = round(closed_lot, 8)
                remaining_lot = round(lot - closed_lot, 8)
                if closed_lot < assumptions.min_lot or remaining_lot < assumptions.min_lot:
                    partial_idx = None
                else:
                    fill = partial_target + assumptions.slippage_price
                    result = _pnl_money(entry_price - fill, closed_lot, assumptions.tick_value, assumptions.tick_size)
                    result -= closed_lot * 2.0 * assumptions.commission_per_lot
            if partial_idx is not None and (first_final_idx is None or partial_idx < first_final_idx):
                balance += result
                cashflows.append({"time": tick_time, "type": "partial", "side": side, "pnl": result, "balance": balance})
                current_lot = remaining_lot
                partial_done = True
                post_ask = ask_arr[partial_idx:]
                post_sl = _first_idx(post_ask >= entry_price)
                post_tp = _first_idx(post_ask <= take_profit)
                if post_sl is not None and (post_tp is None or post_sl <= post_tp):
                    final_idx = partial_idx + post_sl
                    exit_price = max(entry_price, float(ask_arr[final_idx])) + assumptions.slippage_price
                    exit_reason = "SL"
                    result = _pnl_money(entry_price - exit_price, current_lot, assumptions.tick_value, assumptions.tick_size)
                elif post_tp is not None:
                    final_idx = partial_idx + post_tp
                    exit_price = take_profit + assumptions.slippage_price
                    exit_reason = "TP"
                    result = _pnl_money(entry_price - exit_price, current_lot, assumptions.tick_value, assumptions.tick_size)
                else:
                    final_idx = None
                if final_idx is not None:
                    result -= current_lot * 2.0 * assumptions.commission_per_lot
                    exit_time = pd.Timestamp(ts_arr[final_idx])
                    balance += result
                    cashflows.append({"time": exit_time, "type": "final", "side": side, "pnl": result, "balance": balance})
                    closed = True
            elif first_final_idx is not None:
                exit_time = pd.Timestamp(ts_arr[first_final_idx])
                exit_reason = first_final_reason
                exit_price = (max(stop_loss, float(ask_arr[first_final_idx])) + assumptions.slippage_price) if first_final_reason == "SL" else (take_profit + assumptions.slippage_price)
                result = _pnl_money(entry_price - exit_price, current_lot, assumptions.tick_value, assumptions.tick_size)
                result -= current_lot * 2.0 * assumptions.commission_per_lot
                balance += result
                cashflows.append({"time": exit_time, "type": "final", "side": side, "pnl": result, "balance": balance})
                closed = True

        if not closed:
            if side == "BUY":
                exit_price -= assumptions.slippage_price
                result = _pnl_money(exit_price - entry_price, current_lot, assumptions.tick_value, assumptions.tick_size)
            else:
                exit_price += assumptions.slippage_price
                result = _pnl_money(entry_price - exit_price, current_lot, assumptions.tick_value, assumptions.tick_size)
            result -= current_lot * 2.0 * assumptions.commission_per_lot
            balance += result
            cashflows.append({"time": exit_time, "type": "final", "side": side, "pnl": result, "balance": balance})

        trade_pnl = sum(cf["pnl"] for cf in cashflows[trade_cashflow_start:])
        exit_i = int(bar_index.searchsorted(pd.Timestamp(exit_time).floor("15min"), side="left"))
        trades.append({
            "entry_time": entry_time,
            "exit_time": exit_time,
            "entry_i": entry_bar_i,
            "exit_i": exit_i,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "exit_reason": exit_reason,
            "initial_lot": lot,
            "bars_held": max(0, exit_i - entry_bar_i),
            "partial_done": partial_done,
            "pnl": trade_pnl,
            "return_on_initial_balance": trade_pnl / assumptions.initial_balance,
            "balance": balance,
        })
        _append_equity(equity_values, exit_time, balance)
        i = max(i + 1, exit_i + 1)

    trades_df = pd.DataFrame(trades)
    cashflows_df = pd.DataFrame(cashflows)
    equity = pd.Series([v for _, v in equity_values], index=[t for t, _ in equity_values], name="equity")
    return trades_df, cashflows_df, equity


def run_tick_backtest_with_metrics(
    signals: pd.DataFrame,
    assumptions: BacktestAssumptions,
    config: TickBacktestConfig,
    dsr_trials: int = 1,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.Series]:
    trades, cashflows, equity = run_tick_backtest(signals, assumptions, config)
    metrics = compute_backtest_metrics(trades, cashflows, equity, assumptions, dsr_trials=dsr_trials)
    return metrics, trades, cashflows, equity
