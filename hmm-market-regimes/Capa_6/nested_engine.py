from pathlib import Path

import numpy as np
import pandas as pd

from Capa_2.sovereign_signal import calculate_kurtosis, calculate_stdev, run_sovereign_signal_engine
from Capa_3.sovereign_calibration import CSystemCalibrator
from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest
from Capa_6.optimizer import iter_candidates, load_parameter_space, score_metrics


def make_hmm_params_csv_from_train(df: pd.DataFrame, out_path: Path) -> dict:
    close = df["close"].to_numpy(dtype=float)
    returns = np.zeros(len(close))
    for i in range(2, len(close)):
        returns[i] = np.log(close[i - 1] / close[i - 2])

    b_mu_rets = np.zeros(len(close))
    alpha_20 = 2.0 / 21.0
    for i in range(1, len(close)):
        b_mu_rets[i] = returns[i] * alpha_20 + b_mu_rets[i - 1] * (1.0 - alpha_20)
    b_sig_rets = calculate_stdev(returns, 60)
    b_kurtosis = calculate_kurtosis(returns, 120)

    nu_opt, lambda_opt, _ = CSystemCalibrator.estimate_moments_distribution(returns, jump_sigma_k=3.0)
    p_bull, p_bear = CSystemCalibrator.optimize_hmm_matrix(returns, b_mu_rets, b_sig_rets, b_kurtosis, nu_opt, lambda_opt)

    params = {
        "InpPBull": p_bull,
        "InpPBear": p_bear,
        "InpSlopeT": 0.0273,
        "InpLambdaJ": lambda_opt,
        "InpNu": nu_opt,
        "WConf": 0.5,
        "WVol": 0.5,
        "WSlope": 0.5,
        "WAccel": 0.0,
        "WInter": 0.0,
        "MuConf": 0.482,
        "MuVol": 1.0,
        "MuSlope": 1.0,
        "MuAccel": 0.0,
        "StdConf": 0.2215,
        "StdVol": 0.5,
        "StdSlope": 2.0,
        "StdAccel": 1.0,
    }
    pd.DataFrame([params]).to_csv(out_path, index=False)
    return params


def make_walk_forward_folds(index: pd.Index, n_folds: int = 4, purge_bars: int = 120, min_train_fraction: float = 0.35) -> list[dict]:
    n = len(index)
    start_val = int(n * min_train_fraction)
    fold_edges = np.linspace(start_val, n, n_folds + 1, dtype=int)
    folds = []
    for fold_id in range(n_folds):
        val_start = int(fold_edges[fold_id])
        val_end = int(fold_edges[fold_id + 1] - 1)
        train_end = max(0, val_start - purge_bars - 1)
        if train_end < 1000 or val_end <= val_start:
            continue
        folds.append({
            "fold_id": fold_id,
            "train_start": 0,
            "train_end": train_end,
            "val_start": val_start,
            "val_end": val_end,
            "train_start_time": index[0],
            "train_end_time": index[train_end],
            "val_start_time": index[val_start],
            "val_end_time": index[val_end],
        })
    return folds


def evaluate_fold(df: pd.DataFrame, fold: dict, candidates: list[dict], space: dict, dsr_trials: int, out_dir: Path) -> pd.DataFrame:
    train_df = df.iloc[fold["train_start"]:fold["train_end"] + 1].copy()
    val_df = df.iloc[fold["val_start"]:fold["val_end"] + 1].copy()
    fold_dir = out_dir / f"fold_{fold['fold_id']}"
    fold_dir.mkdir(parents=True, exist_ok=True)
    params_path = fold_dir / "HMM_Params_fold.csv"
    hmm_params = make_hmm_params_csv_from_train(train_df, params_path)

    cache = {}
    rows = []
    for candidate in candidates:
        key = (candidate["threshold"], candidate["min_strength"], candidate["kalman_gate"])
        if key not in cache:
            cache[key] = run_sovereign_signal_engine(
                val_df,
                params_csv=str(params_path),
                threshold=float(candidate["threshold"]),
                min_strength=float(candidate["min_strength"]),
                kalman_gate=bool(candidate["kalman_gate"]),
                point=0.01,
            )
        assumptions = BacktestAssumptions(
            min_strength=float(candidate["min_strength"]),
            vol_multiplier=float(candidate["vol_multiplier"]),
            reward_risk=float(candidate["reward_risk"]),
        )
        trades, cashflows, equity = run_backtest(cache[key], assumptions)
        metrics = compute_backtest_metrics(trades, cashflows, equity, assumptions, dsr_trials=dsr_trials)
        rows.append({
            **fold,
            **candidate,
            **metrics,
            "score": score_metrics(metrics, space),
            "hmm_p_bull": hmm_params["InpPBull"],
            "hmm_p_bear": hmm_params["InpPBear"],
            "hmm_lambda": hmm_params["InpLambdaJ"],
            "hmm_nu": hmm_params["InpNu"],
        })

    ranking = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    ranking.to_csv(fold_dir / "ranking_fold.csv", index=False)
    return ranking


def run_nested_walk_forward(
    data_path: Path,
    space_path: Path,
    out_dir: Path,
    n_folds: int = 4,
    purge_bars: int = 120,
    dsr_trials: int = 81,
    max_candidates: int  None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_parquet(data_path)
    space = load_parameter_space(space_path)
    candidates = iter_candidates(space)
    if max_candidates is not None:
        candidates = candidates[:max(1, int(max_candidates))]
    folds = make_walk_forward_folds(df.index, n_folds=n_folds, purge_bars=purge_bars)
    pd.DataFrame(folds).to_csv(out_dir / "folds.csv", index=False)

    all_rankings = []
    for fold in folds:
        print(f"Fold {fold['fold_id']}: train {fold['train_start_time']} -> {fold['train_end_time']}  val {fold['val_start_time']} -> {fold['val_end_time']}")
        ranking = evaluate_fold(df, fold, candidates, space, dsr_trials, out_dir)
        all_rankings.append(ranking)
        best = ranking.iloc[0]
        print(f"  best score={best['score']:.4f} pf={best['profit_factor']:.3f} dd={best['max_drawdown_pct']:.2f}% trades={int(best['closed_trades'])}")

    combined = pd.concat(all_rankings, ignore_index=True) if all_rankings else pd.DataFrame()
    combined.to_csv(out_dir / "nested_all_rankings.csv", index=False)
    if combined.empty:
        return combined, pd.DataFrame()

    group_cols = ["threshold", "min_strength", "vol_multiplier", "reward_risk", "kalman_gate"]
    stability = combined.groupby(group_cols).agg(
        folds=("fold_id", "nunique"),
        mean_score=("score", "mean"),
        median_score=("score", "median"),
        mean_pf=("profit_factor", "mean"),
        min_pf=("profit_factor", "min"),
        mean_return=("total_return_pct", "mean"),
        min_return=("total_return_pct", "min"),
        worst_dd=("max_drawdown_pct", "min"),
        mean_dsr=("deflated_sharpe_probability", "mean"),
        total_trades=("closed_trades", "sum"),
    ).reset_index()
    stability["robust_score"] = (
        stability["median_score"]
        + stability["mean_pf"]
        + stability["mean_dsr"]
        - 0.05 * abs(stability["worst_dd"])
        + 0.01 * stability["min_return"]
    )
    stability = stability.sort_values("robust_score", ascending=False).reset_index(drop=True)
    stability.to_csv(out_dir / "nested_stability_ranking.csv", index=False)
    return combined, stability
