import itertools
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_2.sovereign_signal import run_sovereign_signal_engine
from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest


def load_parameter_space(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_candidates(space: dict) -> list[dict]:
    keys = ["threshold", "min_strength", "vol_multiplier", "reward_risk", "kalman_gate"]
    values = [space[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def split_train_validation(df: pd.DataFrame, validation_fraction: float = 0.25, purge_bars: int = 120) -> tuple[pd.DataFrame, pd.DataFrame]:
    split_i = int(len(df) * (1.0 - validation_fraction))
    train_end = max(0, split_i - purge_bars)
    val_start = min(len(df), split_i)
    return df.iloc[:train_end].copy(), df.iloc[val_start:].copy()


def score_metrics(metrics: dict, space: dict) -> float:
    weights = space["objective_weights"]
    constraints = space["constraints"]
    score = 0.0
    pf = metrics.get("profit_factor", 0.0)
    recovery = metrics.get("recovery_factor", 0.0)
    if not np.isfinite(recovery):
        recovery = 10.0
    score += weights["profit_factor"] * pf
    score += weights["deflated_sharpe_probability"] * metrics.get("deflated_sharpe_probability", 0.0)
    score += weights["recovery_factor"] * recovery
    score += weights["total_return_pct"] * metrics.get("total_return_pct", 0.0)
    score -= weights["drawdown_penalty"] * abs(min(0.0, metrics.get("max_drawdown_pct", 0.0)))

    if metrics.get("closed_trades", 0) < constraints["min_closed_trades"]:
        score -= weights["low_trade_penalty"] * (constraints["min_closed_trades"] - metrics.get("closed_trades", 0))
    if metrics.get("max_drawdown_pct", 0.0) < constraints["max_drawdown_pct_floor"]:
        score -= 5.0
    if pf < constraints["min_profit_factor"]:
        score -= 3.0
    if metrics.get("total_return_pct", 0.0) <= 0:
        score -= 3.0
    return float(score)


def evaluate_candidate(
    candidate: dict,
    dataset: pd.DataFrame,
    params_path: Path,
    dsr_trials: int,
    signal_cache: dict,
    asset_cfg: dict = None,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.Series]:
    cfg = asset_cfg or {}
    point = cfg.get("point", 0.01)
    tick_size = cfg.get("tick_size", 0.01)
    tick_value = cfg.get("tick_value", 1.0)
    spread_price = cfg.get("spread_price", 0.0)
    slippage_price = cfg.get("slippage_price", 0.0)
    
    signal_key = (
        float(candidate["threshold"]),
        float(candidate["min_strength"]),
        bool(candidate["kalman_gate"]),
    )
    if signal_key not in signal_cache:
        signal_cache[signal_key] = run_sovereign_signal_engine(
            dataset,
            params_csv=str(params_path),
            threshold=float(candidate["threshold"]),
            min_strength=float(candidate["min_strength"]),
            kalman_gate=bool(candidate["kalman_gate"]),
            point=point,
        )
    signals = signal_cache[signal_key]
    assumptions = BacktestAssumptions(
        min_strength=float(candidate["min_strength"]),
        vol_multiplier=float(candidate["vol_multiplier"]),
        reward_risk=float(candidate["reward_risk"]),
        point=point,
        tick_size=tick_size,
        tick_value=tick_value,
        spread_price=spread_price,
        slippage_price=slippage_price,
        commission_per_lot=float(cfg.get("commission_per_lot", 0.0)),
        min_lot=float(cfg.get("min_lot", 0.01)),
        lot_step=float(cfg.get("lot_step", 0.01)),
        intrabar_mode=str(cfg.get("intrabar_mode", "pessimistic")),
    )
    trades, cashflows, equity = run_backtest(signals, assumptions)
    metrics = compute_backtest_metrics(trades, cashflows, equity, assumptions, dsr_trials=dsr_trials)
    return metrics, trades, cashflows, equity


def alpha_decay_summary(trades: pd.DataFrame, freq: str = "QE") -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    local = trades.copy()
    local["exit_time"] = pd.to_datetime(local["exit_time"])
    local = local.set_index("exit_time").sort_index()
    grouped = local.groupby(pd.Grouper(freq=freq))
    rows = []
    for period, chunk in grouped:
        if chunk.empty:
            continue
        pnl = chunk["pnl"].to_numpy(dtype=float)
        wins = pnl[pnl > 0]
        losses = pnl[pnl <= 0]
        rows.append({
            "period": period,
            "closed_trades": len(chunk),
            "net_pnl": float(np.sum(pnl)),
            "win_rate_pct": float(len(wins) / len(pnl) * 100.0) if len(pnl) else 0.0,
            "profit_factor": float(np.sum(wins) / abs(np.sum(losses))) if len(losses) and abs(np.sum(losses)) > 0 else math.inf if len(wins) else 0.0,
            "avg_pnl": float(np.mean(pnl)) if len(pnl) else 0.0,
        })
    report = pd.DataFrame(rows)
    if not report.empty:
        report["pf_rolling_4p"] = report["profit_factor"].replace([np.inf, -np.inf], np.nan).rolling(4, min_periods=1).mean()
        report["avg_pnl_rolling_4p"] = report["avg_pnl"].rolling(4, min_periods=1).mean()
    return report


def write_best_candidate(best_row: pd.Series, out_path: Path):
    payload = {
        "threshold": float(best_row["threshold"]),
        "min_strength": float(best_row["min_strength"]),
        "vol_multiplier": float(best_row["vol_multiplier"]),
        "reward_risk": float(best_row["reward_risk"]),
        "kalman_gate": bool(best_row["kalman_gate"]),
        "score": float(best_row["score"]),
    }
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def run_optimization(
    is_path: Path,
    oos_path: Path,
    params_path: Path,
    space_path: Path,
    out_dir: Path,
    max_candidates: int  None = None,
    dsr_trials: int = 1,
    asset_cfg: dict = None,
) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    space = load_parameter_space(space_path)
    candidates = iter_candidates(space)
    if max_candidates is not None:
        candidates = candidates[:max(1, int(max_candidates))]

    # Ajustar severamente el DSR usando el número real de iteraciones probadas
    dsr_trials = len(candidates)
    if asset_cfg is None:
        asset_cfg = {}

    is_df = pd.read_parquet(is_path)
    _, validation_df = split_train_validation(is_df, validation_fraction=0.25, purge_bars=120)
    oos_df = pd.read_parquet(oos_path)

    val_cache: dict = {}
    rows = []
    for idx, candidate in enumerate(candidates, start=1):
        metrics, _, _, _ = evaluate_candidate(candidate, validation_df, params_path, dsr_trials, val_cache, asset_cfg)
        row = {**candidate, **metrics}
        row["score"] = score_metrics(metrics, space)
        row["rank_source"] = "IS_VALIDATION"
        rows.append(row)
        print(f"[{idx}/{len(candidates)}] score={row['score']:.4f} pf={row['profit_factor']:.3f} dd={row['max_drawdown_pct']:.2f}% {candidate}")

    ranking = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    ranking.to_csv(out_dir / "ranking_parametros.csv", index=False)
    if ranking.empty:
        return ranking

    best = ranking.iloc[0]
    write_best_candidate(best, out_dir / "best_params.json")

    best_candidate = {
        "threshold": float(best["threshold"]),
        "min_strength": float(best["min_strength"]),
        "vol_multiplier": float(best["vol_multiplier"]),
        "reward_risk": float(best["reward_risk"]),
        "kalman_gate": bool(best["kalman_gate"]),
    }
    oos_cache: dict = {}
    oos_metrics, oos_trades, oos_cashflows, oos_equity = evaluate_candidate(best_candidate, oos_df, params_path, dsr_trials, oos_cache, asset_cfg)
    pd.DataFrame([{**best_candidate, **oos_metrics, "rank_source": "OOS_HOLDOUT"}]).to_csv(out_dir / "best_oos_holdout_metrics.csv", index=False)
    oos_trades.to_csv(out_dir / "best_oos_trades.csv", index=False)
    oos_cashflows.to_csv(out_dir / "best_oos_cashflows.csv", index=False)
    oos_equity.to_frame().to_csv(out_dir / "best_oos_equity.csv")
    alpha_decay_summary(oos_trades).to_csv(out_dir / "alpha_decay_oos_quarterly.csv", index=False)
    return ranking
