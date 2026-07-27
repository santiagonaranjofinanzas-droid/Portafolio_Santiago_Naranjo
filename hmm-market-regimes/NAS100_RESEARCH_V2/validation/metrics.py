from __future__ import annotations

import math
from itertools import combinations

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew


def profit_factor(values: np.ndarray) -> float:
    array = np.asarray(values, dtype=float)
    wins = array[array > 0.0].sum()
    losses = abs(array[array <= 0.0].sum())
    return float(wins / losses) if losses > 0.0 else float("inf") if wins > 0.0 else 0.0


def deflated_sharpe_ratio(returns: np.ndarray, trials: int, benchmark_sharpe: float = 0.0) -> tuple[float, float]:
    clean = np.asarray(returns, dtype=float)
    clean = clean[np.isfinite(clean)]
    if len(clean) < 3 or np.std(clean, ddof=1) <= 0.0:
        return 0.0, 0.0
    sharpe = float(np.mean(clean) / np.std(clean, ddof=1))
    sr_std = math.sqrt(
        max(
            (1.0 - skew(clean) * sharpe + ((kurtosis(clean, fisher=False) - 1.0) / 4.0) * sharpe * sharpe)
            / (len(clean) - 1),
            1e-12,
        )
    )
    trials = max(1, int(trials))
    if trials == 1:
        sr_star = benchmark_sharpe
    else:
        gamma = 0.5772156649015329
        sr_star = benchmark_sharpe + sr_std * (
            (1.0 - gamma) * norm.ppf(1.0 - 1.0 / trials)
            + gamma * norm.ppf(1.0 - 1.0 / (trials * math.e))
        )
    z_stat = (sharpe - sr_star) / sr_std
    return float(norm.cdf(z_stat)), float(z_stat)


def _drawdown(equity: pd.Series) -> tuple[float, float]:
    peak = equity.cummax()
    money = equity - peak
    pct = money / peak.replace(0.0, np.nan) * 100.0
    return float(money.min()), float(pct.min())


def daily_pnl_from_trades(trades: pd.DataFrame, start=None, end=None) -> pd.Series:
    if trades.empty:
        return pd.Series(dtype=float, name="pnl")
    required = {"exit_time", "pnl"}
    if not required.issubset(trades.columns):
        raise ValueError(f"trades require columns {sorted(required)}")
    exits = pd.DatetimeIndex(pd.to_datetime(trades["exit_time"], errors="raise"))
    pnl = pd.Series(trades["pnl"].to_numpy(float), index=exits.floor("D")).groupby(level=0).sum()
    if start is not None and end is not None:
        calendar = pd.date_range(pd.Timestamp(start).floor("D"), pd.Timestamp(end).floor("D"), freq="D")
        pnl = pnl.reindex(calendar, fill_value=0.0)
    pnl.name = "pnl"
    return pnl.sort_index()


def performance_summary(trades: pd.DataFrame, initial_balance: float = 100_000.0, trials: int = 1, start=None, end=None) -> dict:
    pnl = trades["pnl"].to_numpy(float) if not trades.empty else np.array([], dtype=float)
    daily = daily_pnl_from_trades(trades, start=start, end=end)
    equity = initial_balance + daily.cumsum()
    previous = equity.shift(1).fillna(initial_balance)
    returns = (daily / previous.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    daily_sharpe = float(returns.mean() / std * math.sqrt(252.0)) if std > 0.0 else 0.0
    dsr, dsr_z = deflated_sharpe_ratio(returns.to_numpy(float), trials=trials)
    dd_money, dd_pct = _drawdown(equity) if not equity.empty else (0.0, 0.0)
    quarterly_pf = []
    if not trades.empty:
        exits = pd.Series(pd.to_datetime(trades["exit_time"], errors="raise"), index=trades.index)
        quarter = exits.dt.tz_localize(None).dt.to_period("Q")
        for _, group in trades.assign(_exit=exits).groupby(quarter):
            quarterly_pf.append(profit_factor(group["pnl"].to_numpy(float)))
    winners = np.sort(pnl[pnl > 0.0])[::-1]
    gross_profit = winners.sum()
    top5_share = float(winners[:5].sum() / gross_profit * 100.0) if gross_profit > 0.0 else 100.0
    return {
        "closed_trades": int(len(trades)),
        "net_profit": float(pnl.sum()) if len(pnl) else 0.0,
        "return_pct": float(pnl.sum() / initial_balance * 100.0) if len(pnl) else 0.0,
        "profit_factor": profit_factor(pnl),
        "expectancy": float(pnl.mean()) if len(pnl) else 0.0,
        "win_rate_pct": float((pnl > 0.0).mean() * 100.0) if len(pnl) else 0.0,
        "daily_sharpe": daily_sharpe,
        "dsr_probability": dsr,
        "dsr_z": dsr_z,
        "max_drawdown_money": dd_money,
        "max_drawdown_pct": dd_pct,
        "worst_quarter_profit_factor": float(min(quarterly_pf)) if quarterly_pf else 0.0,
        "top5_winner_share_pct": top5_share,
    }


def _moving_block_sample(values: np.ndarray, block_size: int, rng: np.random.Generator) -> np.ndarray:
    n = len(values)
    blocks = int(math.ceil(n / block_size))
    starts = rng.integers(0, n, size=blocks)
    sampled = []
    for start in starts:
        sampled.extend(values[(start + np.arange(block_size)) % n])
    return np.asarray(sampled[:n], dtype=float)


def block_bootstrap(daily_pnl: np.ndarray, samples: int = 10_000, block_size: int = 5, seed: int = 50001) -> dict:
    values = np.asarray(daily_pnl, dtype=float)
    values = values[np.isfinite(values)]
    if len(values) < max(2, block_size):
        return {"samples": 0, "pf_p05": 0.0, "expectancy_p05": 0.0, "probability_positive": 0.0}
    rng = np.random.default_rng(seed)
    pfs = np.empty(samples, dtype=float)
    means = np.empty(samples, dtype=float)
    totals = np.empty(samples, dtype=float)
    for i in range(samples):
        draw = _moving_block_sample(values, block_size, rng)
        pfs[i] = profit_factor(draw)
        means[i] = draw.mean()
        totals[i] = draw.sum()
    finite_pf = pfs[np.isfinite(pfs)]
    return {
        "samples": int(samples),
        "pf_p05": float(np.quantile(finite_pf, 0.05)) if len(finite_pf) else float("inf"),
        "expectancy_p05": float(np.quantile(means, 0.05)),
        "probability_positive": float((totals > 0.0).mean()),
    }


def paired_block_bootstrap(candidate_daily: np.ndarray, baseline_daily: np.ndarray, samples: int = 10_000,
                           block_size: int = 5, seed: int = 50001) -> dict:
    candidate = np.asarray(candidate_daily, dtype=float)
    baseline = np.asarray(baseline_daily, dtype=float)
    if candidate.shape != baseline.shape:
        raise ValueError("candidate and baseline daily series must have identical shape")
    delta = candidate - baseline
    clean = delta[np.isfinite(delta)]
    if len(clean) < max(2, block_size):
        return {"samples": 0, "delta_expectancy_p05": 0.0, "probability_improvement": 0.0}
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=float)
    totals = np.empty(samples, dtype=float)
    for i in range(samples):
        draw = _moving_block_sample(clean, block_size, rng)
        means[i] = draw.mean()
        totals[i] = draw.sum()
    return {
        "samples": int(samples),
        "delta_expectancy_p05": float(np.quantile(means, 0.05)),
        "probability_improvement": float((totals > 0.0).mean()),
    }


def probability_backtest_overfitting(performance_by_block: np.ndarray) -> dict:
    """CSCV-style PBO using candidate performance across an even number of time blocks."""
    matrix = np.asarray(performance_by_block, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("performance_by_block must be candidates x blocks")
    candidates, blocks = matrix.shape
    if candidates < 2 or blocks < 4 or blocks % 2:
        raise ValueError("PBO requires >=2 candidates and an even number of >=4 blocks")
    logits = []
    half = blocks // 2
    all_blocks = set(range(blocks))
    for in_sample_tuple in combinations(range(blocks), half):
        in_sample = np.asarray(in_sample_tuple, dtype=int)
        out_sample = np.asarray(sorted(all_blocks.difference(in_sample_tuple)), dtype=int)
        is_score = np.nanmean(matrix[:, in_sample], axis=1)
        winner = int(np.nanargmax(is_score))
        oos_score = np.nanmean(matrix[:, out_sample], axis=1)
        order = np.argsort(np.argsort(oos_score))
        relative_rank = (order[winner] + 1.0) / (candidates + 1.0)
        logits.append(math.log(relative_rank / (1.0 - relative_rank)))
    values = np.asarray(logits, dtype=float)
    return {
        "pbo": float((values <= 0.0).mean()),
        "logit_median": float(np.median(values)),
        "partitions": int(len(values)),
    }
