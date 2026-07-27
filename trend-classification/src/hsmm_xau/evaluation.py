from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm, skew, kurtosis
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    log_loss,
    matthews_corrcoef,
    roc_auc_score,
)


def expected_calibration_error(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = len(y)
    error = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        mask = (p >= lo) & (p < hi if hi < 1 else p <= hi)
        if mask.any():
            error += mask.mean() * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(error) if total else float("nan")


def probability_metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    mask = np.isfinite(y) & np.isfinite(p)
    y = y[mask].astype(int)
    p = np.clip(p[mask], 1e-9, 1 - 1e-9)
    if not len(y):
        return {"n": 0}
    predicted = p >= threshold
    both = len(np.unique(y)) == 2
    return {
        "n": int(len(y)),
        "prevalence": float(y.mean()),
        "brier": float(brier_score_loss(y, p)),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "ece": expected_calibration_error(y, p),
        "roc_auc": float(roc_auc_score(y, p)) if both else None,
        "pr_auc": float(average_precision_score(y, p)) if both else None,
        "mcc": float(matthews_corrcoef(y, predicted)) if both else None,
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)) if both else None,
    }


def economic_metrics(pnl: np.ndarray) -> dict:
    pnl = np.asarray(pnl, float)
    pnl = pnl[np.isfinite(pnl)]
    if not len(pnl):
        return {"trades": 0}
    equity = np.cumsum(pnl)
    drawdown = equity - np.maximum.accumulate(np.r_[0.0, equity])[-len(equity) :]
    gains = pnl[pnl > 0].sum()
    losses = -pnl[pnl < 0].sum()
    std = pnl.std(ddof=1) if len(pnl) > 1 else np.nan
    return {
        "trades": int(len(pnl)),
        "expectancy": float(pnl.mean()),
        "hit_rate": float((pnl > 0).mean()),
        "profit_factor": float(gains / losses) if losses > 0 else None,
        "trade_sharpe": float(pnl.mean() / std * np.sqrt(len(pnl))) if std > 0 else None,
        "max_drawdown_price": float(drawdown.min()),
        "total_pnl_price": float(pnl.sum()),
    }


def deflated_sharpe_probability(returns: np.ndarray, trials: int) -> float:
    """Approximate DSR probability using non-normal Sharpe variance and trial penalty."""
    returns = np.asarray(returns, float)
    returns = returns[np.isfinite(returns)]
    if len(returns) < 3 or returns.std(ddof=1) == 0:
        return float("nan")
    sr = returns.mean() / returns.std(ddof=1)
    n = len(returns)
    sr_std = math.sqrt(
        (1 - skew(returns) * sr + (kurtosis(returns, fisher=False) - 1) * sr**2 / 4) / (n - 1)
    )
    expected_max = norm.ppf((max(trials, 1) - 0.375) / (max(trials, 1) + 0.25)) / math.sqrt(n)
    return float(norm.cdf((sr - expected_max) / max(sr_std, 1e-12)))


def cscv_pbo(candidate_returns: np.ndarray) -> float:
    """CSCV-style rank degradation estimate; rows are time blocks, columns candidates."""
    matrix = np.asarray(candidate_returns, float)
    if matrix.ndim != 2 or matrix.shape[0] < 4 or matrix.shape[1] < 2:
        return float("nan")
    from itertools import combinations

    n_blocks = matrix.shape[0]
    half = n_blocks // 2
    logits = []
    for train_blocks in combinations(range(n_blocks), half):
        test_blocks = sorted(set(range(n_blocks)) - set(train_blocks))
        train_score = np.nanmean(matrix[list(train_blocks)], axis=0)
        test_score = np.nanmean(matrix[test_blocks], axis=0)
        winner = int(np.nanargmax(train_score))
        rank = (np.argsort(np.argsort(test_score))[winner] + 1) / (len(test_score) + 1)
        logits.append(np.log(rank / (1 - rank)))
    return float(np.mean(np.asarray(logits) < 0))
