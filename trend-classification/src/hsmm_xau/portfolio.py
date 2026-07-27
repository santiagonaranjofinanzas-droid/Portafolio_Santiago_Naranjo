from __future__ import annotations

import numpy as np
import pandas as pd


def non_overlapping_mask(
    index: pd.DatetimeIndex, exit_times: pd.Series  np.ndarray, eligible: np.ndarray
) -> np.ndarray:
    """Select candidates chronologically with at most one open position."""
    exits = pd.to_datetime(exit_times).to_numpy(dtype="datetime64[ns]")
    selected = np.zeros(len(index), dtype=bool)
    last_exit = np.datetime64("NaT")
    for i in np.flatnonzero(eligible):
        entry = index[i].to_datetime64()
        exit_time = exits[i]
        if np.isnat(exit_time):
            continue
        if np.isnat(last_exit) or entry > last_exit:
            selected[i] = True
            last_exit = exit_time
    return selected


def daily_returns_from_trades(
    exit_times: pd.Series  np.ndarray,
    pnl: np.ndarray,
    entry_price: np.ndarray,
    selected: np.ndarray,
) -> pd.Series:
    valid = selected & np.isfinite(pnl) & np.isfinite(entry_price) & (entry_price > 0)
    if not valid.any():
        return pd.Series(dtype=float, name="daily_return")
    frame = pd.DataFrame(
        {
            "exit_time": pd.to_datetime(np.asarray(exit_times)[valid]),
            "return": np.asarray(pnl, float)[valid] / np.asarray(entry_price, float)[valid],
        }
    ).dropna()
    result = frame.groupby(frame.exit_time.dt.normalize())["return"].sum().sort_index()
    result.name = "daily_return"
    return result


def mark_to_market_daily_returns(
    bars: pd.DataFrame,
    entry_times: pd.Series  np.ndarray,
    exit_times: pd.Series  np.ndarray,
    pnl: np.ndarray,
    entry_price: np.ndarray,
    side: np.ndarray,
    selected: np.ndarray,
) -> pd.Series:
    """Realized plus unrealized daily returns along each selected trade's path."""
    totals: dict[pd.Timestamp, float] = {}
    entries = pd.to_datetime(np.asarray(entry_times))
    exits = pd.to_datetime(np.asarray(exit_times))
    for i in np.flatnonzero(selected):
        if not (np.isfinite(pnl[i]) and np.isfinite(entry_price[i]) and entry_price[i] > 0):
            continue
        entry, exit_time = entries[i], exits[i]
        if pd.isna(entry) or pd.isna(exit_time):
            continue
        path = bars.loc[(bars.index >= entry) & (bars.index <= exit_time)]
        if path.empty:
            continue
        closes = path.groupby(path.index.normalize()).tail(1)
        previous = 0.0
        exit_day = exit_time.normalize()
        for timestamp, row in closes.iterrows():
            day = timestamp.normalize()
            if day == exit_day:
                cumulative = float(pnl[i])
            elif int(side[i]) == 1:
                cumulative = float(row["bid_close"] - entry_price[i])
            else:
                cumulative = float(entry_price[i] - row["ask_close"])
            totals[day] = totals.get(day, 0.0) + (cumulative - previous) / entry_price[i]
            previous = cumulative
    result = pd.Series(totals, dtype=float).sort_index()
    result.name = "daily_return"
    return result


def portfolio_metrics(daily_returns: pd.Series, annualization_days: int = 252) -> dict:
    returns = daily_returns.astype(float).replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        return {"days": 0, "sharpe_daily": None, "max_drawdown_return": None}
    full_index = pd.date_range(returns.index.min(), returns.index.max(), freq="D")
    returns = returns.reindex(full_index, fill_value=0.0)
    equity = (1.0 + returns).cumprod()
    drawdown = equity / equity.cummax() - 1.0
    std = returns.std(ddof=1)
    downside = returns[returns < 0].std(ddof=1)
    return {
        "days": int(len(returns)),
        "active_days": int((returns != 0).sum()),
        "total_return": float(equity.iloc[-1] - 1.0),
        "annualized_return": float(equity.iloc[-1] ** (annualization_days / len(returns)) - 1.0),
        "sharpe_daily": float(returns.mean() / std * np.sqrt(annualization_days))
        if std > 0
        else None,
        "sortino_daily": float(returns.mean() / downside * np.sqrt(annualization_days))
        if downside > 0
        else None,
        "max_drawdown_return": float(drawdown.min()),
        "daily_returns": returns,
    }
