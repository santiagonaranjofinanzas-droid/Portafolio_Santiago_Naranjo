import math

import numpy as np
import pandas as pd

from Capa_4.backtest_metrics import BacktestAssumptions


def _equity_metrics(equity: pd.Series, cfg: BacktestAssumptions) -> dict:
    returns = equity.pct_change().dropna().to_numpy(dtype=float)
    if len(returns) > 1 and np.std(returns, ddof=1) > 0:
        sharpe = float((np.mean(returns) / np.std(returns, ddof=1)) * math.sqrt(cfg.periods_per_year))
    else:
        sharpe = 0.0

    peak = equity.cummax()
    dd_pct = ((equity - peak) / peak.replace(0.0, np.nan)) * 100.0
    max_dd = float(dd_pct.min()) if not dd_pct.dropna().empty else 0.0

    return {
        "final_balance": float(equity.iloc[-1]),
        "net_profit": float(equity.iloc[-1] - cfg.initial_balance),
        "return_pct": float(((equity.iloc[-1] / cfg.initial_balance) - 1.0) * 100.0),
        "sharpe": sharpe,
        "max_dd_pct": max_dd,
    }


def _standardize_trades(trades: pd.DataFrame, strategy: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["entry_time", "exit_time", "pnl", "strategy"])

    out = trades.copy()
    out["entry_time"] = pd.to_datetime(out["entry_time"])
    out["exit_time"] = pd.to_datetime(out["exit_time"])
    out["strategy"] = strategy
    return out.sort_values(["entry_time", "exit_time"]).reset_index(drop=True)


def _recent_expectancy(candidates: pd.DataFrame, strategy: str, now: pd.Timestamp, lookback: pd.Timedelta) -> float:
    past = candidates[
        (candidates["strategy"] == strategy)
        & (candidates["exit_time"] < now)
        & (candidates["exit_time"] >= now - lookback)
    ]
    if len(past) < 3:
        return 0.0
    return float(past["pnl"].mean())


def _exclusive_from_trade_ledgers(
    trend_trades: pd.DataFrame,
    mr_trades: pd.DataFrame,
    index: pd.Index,
    cfg: BacktestAssumptions,
) -> tuple[pd.DataFrame, pd.Series]:
    candidates = pd.concat(
        [_standardize_trades(trend_trades, "TREND"), _standardize_trades(mr_trades, "MR")],
        ignore_index=True,
    )
    if candidates.empty:
        return candidates, pd.Series(cfg.initial_balance, index=index, name="Exclusive_Coex")

    candidates = candidates.sort_values(["entry_time", "exit_time"]).reset_index(drop=True)

    accepted = []
    last_exit = pd.Timestamp.min
    balance = cfg.initial_balance
    equity = pd.Series(cfg.initial_balance, index=index, dtype=float, name="Exclusive_Coex")
    lookback = pd.Timedelta(minutes=15 * 96)
    ptr = 0

    while ptr < len(candidates):
        available = candidates[candidates["entry_time"] >= last_exit]
        if available.empty:
            break

        first_entry = available["entry_time"].min()
        conflict_end = available.loc[available["entry_time"] == first_entry, "exit_time"].max()
        overlapping = available[(available["entry_time"] < conflict_end) & (available["entry_time"] >= first_entry)].copy()
        if overlapping.empty:
            break

        overlapping["recent_expectancy"] = overlapping["strategy"].map(
            lambda s: _recent_expectancy(candidates, s, first_entry, lookback)
        )
        overlapping["fallback_priority"] = overlapping["strategy"].map({"TREND": 1, "MR": 0}).fillna(2)
        overlapping = overlapping.sort_values(
            ["recent_expectancy", "fallback_priority", "entry_time"],
            ascending=[False, True, True],
        )
        trade = overlapping.iloc[0]

        balance += float(trade["pnl"])
        last_exit = trade["exit_time"]
        accepted_trade = trade.drop(labels=["recent_expectancy", "fallback_priority"]).to_dict()
        accepted_trade["balance"] = balance
        accepted.append(accepted_trade)

        mask = equity.index >= trade["exit_time"]
        equity.loc[mask] = balance
        ptr = int(candidates.index[candidates["entry_time"] >= last_exit].min()) if (candidates["entry_time"] >= last_exit).any() else len(candidates)

    return pd.DataFrame(accepted), equity


def run_coexistence_analysis(
    df: pd.DataFrame,
    assumptions: BacktestAssumptions,
    trend_trades: pd.DataFrame,
    trend_equity: pd.Series,
    mr_trades: pd.DataFrame,
    mr_equity: pd.Series,
    parallel_weight_trend: float = 0.50,
    parallel_weight_mr: float = 0.50,
) -> dict:
    """
    Construye coexistencia auditable desde ledgers ya ejecutados.

    Paralelo: dos sleeves fijos 50/50, usando PnL realizado/flotante de cada motor.
    Exclusivo: ledger combinado que acepta una sola posicion a la vez, con prioridad TREND.
    """
    cfg = assumptions
    trend_equity = trend_equity.reindex(df.index).ffill().fillna(cfg.initial_balance)
    mr_equity = mr_equity.reindex(df.index).ffill().fillna(cfg.initial_balance)

    parallel_equity = (
        cfg.initial_balance
        + parallel_weight_trend * (trend_equity - cfg.initial_balance)
        + parallel_weight_mr * (mr_equity - cfg.initial_balance)
    )
    parallel_equity.name = "Parallel_Coex_50_50"

    exclusive_trades, exclusive_equity = _exclusive_from_trade_ledgers(
        trend_trades,
        mr_trades,
        df.index,
        cfg,
    )

    trend_daily = trend_equity.pct_change().resample("D").sum() if isinstance(df.index, pd.DatetimeIndex) else trend_equity.pct_change()
    mr_daily = mr_equity.pct_change().resample("D").sum() if isinstance(df.index, pd.DatetimeIndex) else mr_equity.pct_change()
    correlation = float(trend_daily.corr(mr_daily))
    if not np.isfinite(correlation):
        correlation = 0.0

    par_metrics = _equity_metrics(parallel_equity, cfg)
    excl_metrics = _equity_metrics(exclusive_equity, cfg)

    return {
        "correlation": correlation,
        "par_final_balance": par_metrics["final_balance"],
        "par_net_profit": par_metrics["net_profit"],
        "par_return_pct": par_metrics["return_pct"],
        "par_sharpe": par_metrics["sharpe"],
        "par_max_dd_pct": par_metrics["max_dd_pct"],
        "excl_final_balance": excl_metrics["final_balance"],
        "excl_net_profit": excl_metrics["net_profit"],
        "excl_return_pct": excl_metrics["return_pct"],
        "excl_sharpe": excl_metrics["sharpe"],
        "excl_max_dd_pct": excl_metrics["max_dd_pct"],
        "excl_total_trades": int(len(exclusive_trades)),
        "portfolio_equity_series": parallel_equity,
        "exclusive_equity_series": exclusive_equity,
        "exclusive_trades": exclusive_trades,
    }
