"""Exact signal/trade parity checks required before an MT5 release."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def compare_python_mt5(
    python_signals: pd.DataFrame,
    mt5_signals: pd.DataFrame,
    python_trades: pd.DataFrame,
    mt5_trades: pd.DataFrame,
    *,
    tick_size: float = 0.01,
) -> dict[str, Any]:
    signal_keys = ["time", "signal"]
    trade_keys = ["entry_time", "exit_time", "side", "entry_price", "exit_price", "pnl"]
    for label, frame, required in (
        ("python_signals", python_signals, signal_keys),
        ("mt5_signals", mt5_signals, signal_keys),
        ("python_trades", python_trades, trade_keys),
        ("mt5_trades", mt5_trades, trade_keys),
    ):
        missing = set(required).difference(frame.columns)
        if missing:
            raise ValueError(f"{label} missing columns: {sorted(missing)}")
    left_s = python_signals[signal_keys].copy().reset_index(drop=True)
    right_s = mt5_signals[signal_keys].copy().reset_index(drop=True)
    for frame in (left_s, right_s):
        frame["time"] = pd.to_datetime(frame["time"], utc=True)
    signal_count_equal = len(left_s) == len(right_s)
    signal_parity = bool(signal_count_equal and left_s.equals(right_s))

    left_t = python_trades[trade_keys].copy().reset_index(drop=True)
    right_t = mt5_trades[trade_keys].copy().reset_index(drop=True)
    for frame in (left_t, right_t):
        frame["entry_time"] = pd.to_datetime(frame["entry_time"], utc=True)
        frame["exit_time"] = pd.to_datetime(frame["exit_time"], utc=True)
    trade_count_equal = len(left_t) == len(right_t)
    structural = False
    max_price_difference = float("inf")
    pnl_difference_pct = float("inf")
    if trade_count_equal:
        structural = bool(
            left_t[["entry_time", "exit_time", "side"]].equals(
                right_t[["entry_time", "exit_time", "side"]]
            )
        )
        if len(left_t):
            price_delta = np.abs(
                left_t[["entry_price", "exit_price"]].to_numpy(float)
                - right_t[["entry_price", "exit_price"]].to_numpy(float)
            )
            max_price_difference = float(np.max(price_delta))
            python_pnl = float(left_t["pnl"].sum())
            mt5_pnl = float(right_t["pnl"].sum())
            pnl_difference_pct = abs(mt5_pnl - python_pnl) / max(abs(python_pnl), 1e-12) * 100.0
        else:
            max_price_difference = 0.0
            pnl_difference_pct = 0.0
    result = {
        "signal_parity_100pct": signal_parity,
        "trade_count_equal": trade_count_equal,
        "trade_structure_equal": structural,
        "maximum_price_difference": max_price_difference,
        "maximum_allowed_price_difference": tick_size,
        "cumulative_pnl_difference_pct": pnl_difference_pct,
        "maximum_allowed_pnl_difference_pct": 0.5,
    }
    result["approved"] = bool(
        signal_parity
        and trade_count_equal
        and structural
        and max_price_difference <= tick_size + 1e-12
        and pnl_difference_pct <= 0.5
    )
    return result


def write_parity(result: dict[str, Any], path: str  Path) -> None:
    Path(path).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
