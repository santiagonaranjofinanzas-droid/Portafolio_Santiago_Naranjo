"""Pessimistic next-open backtest for MR V3 shock rejection."""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v2.config import CostConfig

from .config import MRV3Config


@dataclass(frozen=True)
class MRV3BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series


def _round_lot(raw: float, cfg: MRV3Config) -> float:
    clipped = min(cfg.max_lot, max(cfg.min_lot, float(raw)))
    steps = np.floor((clipped + 1e-12) / cfg.lot_step)
    return float(max(cfg.min_lot, steps * cfg.lot_step))


def with_costs(config: MRV3Config, costs: CostConfig) -> MRV3Config:
    return replace(config, costs=costs)


def run_mr_v3_backtest(
    signals: pd.DataFrame, config: MRV3Config  None = None
) -> MRV3BacktestResult:
    cfg = config or MRV3Config()
    required = {
        "open", "high", "low", "close", "entry_signal",
        "mr_target_reference", "mr_stop_reference",
    }
    missing = required.difference(signals.columns)
    if missing:
        raise ValueError(f"MR V3 backtest missing columns: {sorted(missing)}")
    if not signals.index.is_monotonic_increasing or signals.index.has_duplicates:
        raise ValueError("MR V3 signal index must be unique and increasing")

    n = len(signals)
    if n == 0:
        return MRV3BacktestResult(pd.DataFrame(), pd.Series(dtype=float, name="equity"))
    opens = signals["open"].to_numpy(float)
    highs = signals["high"].to_numpy(float)
    lows = signals["low"].to_numpy(float)
    closes = signals["close"].to_numpy(float)
    entries = signals["entry_signal"].fillna(0).to_numpy(int)
    targets = signals["mr_target_reference"].to_numpy(float)
    stops = signals["mr_stop_reference"].to_numpy(float)
    if "spread_price" in signals.columns:
        spreads = pd.to_numeric(signals["spread_price"], errors="coerce").fillna(
            cfg.costs.spread_price
        ).to_numpy(float)
    elif "spread_median" in signals.columns:
        spreads = pd.to_numeric(signals["spread_median"], errors="coerce").fillna(
            cfg.costs.spread_price
        ).to_numpy(float)
    else:
        spreads = np.full(n, cfg.costs.spread_price, dtype=float)
    spreads = np.maximum(spreads, 0.0)

    cash = float(cfg.initial_balance)
    equity_values = np.full(n, cash, dtype=float)
    side = 0
    lot = 0.0
    entry_i = -1
    entry_time = None
    entry_reference = np.nan
    entry_price = np.nan
    target_reference = np.nan
    stop_reference = np.nan
    entry_commission = 0.0
    cash_before_trade = np.nan
    trades: list[dict] = []
    value_per_price = cfg.costs.value_per_price_unit_per_lot

    def close(row: int, reference: float, reason: str) -> None:
        nonlocal cash, side, lot, entry_i, entry_time, entry_reference, entry_price
        nonlocal target_reference, stop_reference, entry_commission, cash_before_trade
        half_spread = spreads[row] / 2.0
        exit_price = reference - side * (half_spread + cfg.costs.slippage_price_per_side)
        price_pnl = side * (exit_price - entry_price) * lot * value_per_price
        exit_commission = lot * cfg.costs.commission_per_lot_per_side
        net = price_pnl - entry_commission - exit_commission
        cash += price_pnl - exit_commission
        trades.append(
            {
                "entry_time": entry_time,
                "exit_time": signals.index[row],
                "entry_i": int(entry_i),
                "exit_i": int(row),
                "side": int(side),
                "units": float(lot),
                "entry_reference": float(entry_reference),
                "entry_price": float(entry_price),
                "exit_reference": float(reference),
                "exit_price": float(exit_price),
                "target_reference": float(target_reference),
                "stop_reference": float(stop_reference),
                "bars_held": int(row - entry_i),
                "exit_reason": reason,
                "commission_cost": float(entry_commission + exit_commission),
                "net_pnl": float(net),
                "return_pct": float(net / cash_before_trade * 100.0),
                "cash_after": float(cash),
            }
        )
        side = 0
        lot = 0.0
        entry_i = -1
        entry_time = None
        entry_reference = np.nan
        entry_price = np.nan
        target_reference = np.nan
        stop_reference = np.nan
        entry_commission = 0.0
        cash_before_trade = np.nan

    for row in range(n):
        if side == 0 and row > 0 and entries[row - 1] != 0:
            proposed_side = int(np.sign(entries[row - 1]))
            proposed_target = targets[row - 1]
            proposed_stop = stops[row - 1]
            risk_distance = proposed_side * (opens[row] - proposed_stop)
            reward_distance = proposed_side * (proposed_target - opens[row])
            if (
                np.isfinite(proposed_target)
                and np.isfinite(proposed_stop)
                and risk_distance > 0.0
                and reward_distance > 0.0
                and reward_distance / risk_distance >= cfg.minimum_reward_risk
            ):
                raw_lot = cash * cfg.risk_fraction / (risk_distance * value_per_price)
                lot = _round_lot(raw_lot, cfg)
                side = proposed_side
                entry_i = row
                entry_time = signals.index[row]
                entry_reference = opens[row]
                entry_price = opens[row] + side * (
                    spreads[row] / 2.0 + cfg.costs.slippage_price_per_side
                )
                target_reference = proposed_target
                stop_reference = proposed_stop
                entry_commission = lot * cfg.costs.commission_per_lot_per_side
                cash_before_trade = cash
                cash -= entry_commission

        if side != 0:
            stop_touched = bool(
                (side == 1 and lows[row] <= stop_reference)
                or (side == -1 and highs[row] >= stop_reference)
            )
            target_touched = bool(
                (side == 1 and highs[row] >= target_reference)
                or (side == -1 and lows[row] <= target_reference)
            )
            if stop_touched:
                close(row, stop_reference, "shock_stop")
            elif target_touched:
                close(row, target_reference, "pre_shock_target")
            elif row - entry_i >= cfg.maximum_holding_bars:
                close(row, opens[row], "time_stop")
            elif row == n - 1:
                close(row, closes[row], "end_of_fold")

        if side == 0:
            equity_values[row] = cash
        else:
            liquidation = closes[row] - side * spreads[row] / 2.0
            equity_values[row] = cash + side * (liquidation - entry_price) * lot * value_per_price

    return MRV3BacktestResult(
        pd.DataFrame(trades),
        pd.Series(equity_values, index=signals.index, name="equity"),
    )
