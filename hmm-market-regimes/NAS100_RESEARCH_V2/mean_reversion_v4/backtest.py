"""Pessimistic next-open execution adapter for MR V4."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v3.backtest import run_mr_v3_backtest

from .config import MRV4Config


@dataclass(frozen=True)
class MRV4BacktestResult:
    trades: pd.DataFrame
    equity: pd.Series


def run_mr_v4_backtest(signals: pd.DataFrame, config: MRV4Config  None = None) -> MRV4BacktestResult:
    cfg = config or MRV4Config()
    translated = signals.rename(
        columns={"v4_target_reference": "mr_target_reference", "v4_stop_reference": "mr_stop_reference"}
    )
    result = run_mr_v3_backtest(translated, cfg)
    trades = result.trades.copy()
    if not trades.empty:
        trades["exit_reason"] = trades["exit_reason"].replace(
            {"shock_stop": "pullback_stop", "pre_shock_target": "pre_shock_recovery"}
        )
    return MRV4BacktestResult(trades=trades, equity=result.equity)
