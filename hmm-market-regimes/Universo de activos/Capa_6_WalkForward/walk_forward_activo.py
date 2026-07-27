import os
import sys
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#Resolver rutas para importar del proyecto principal
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, "..", ".."))

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from Capa_2.sovereign_signal import calculate_kurtosis, calculate_stdev, run_sovereign_signal_engine
from Capa_3.sovereign_calibration import CSystemCalibrator
from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics, run_backtest
from Capa_6.optimizer import iter_candidates, load_parameter_space, score_metrics

def make_hmm_params_csv_from_train(df: pd.DataFrame, out_path: Path) -> dict:
    """Calibra los parámetros HMM utilizando únicamente el subconjunto de entrenamiento de un fold."""
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
    """Divide cronológicamente el índice temporal en folds de Walk-Forward."""
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

def evaluate_fold_activo(
    df: pd.DataFrame, 
    fold: dict, 
    candidates: list[dict], 
    space: dict, 
    dsr_trials: int, 
    out_dir: Path,
    point: float,
    tick_size: float,
    tick_value: float,
    spread_price: float,
    slippage_price: float,
    commission_per_lot: float = 0.0,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    intrabar_mode: str = "pessimistic"
) -> pd.DataFrame:
    """Evalúa los candidatos sobre la sección de validación de un fold usando parámetros del activo."""
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
            # Inyectar 2000 barras de contexto previo (warm-up) para los filtros inerciales
            context_df = train_df.tail(2000)
            eval_input = pd.concat([context_df, val_df])
            
            cache[key] = run_sovereign_signal_engine(
                eval_input,
                params_csv=str(params_path),
                threshold=float(candidate["threshold"]),
                min_strength=float(candidate["min_strength"]),
                kalman_gate=bool(candidate["kalman_gate"]),
                point=point,
            ).loc[val_df.index]
            
        assumptions = BacktestAssumptions(
            min_strength=float(candidate["min_strength"]),
            vol_multiplier=float(candidate["vol_multiplier"]),
            reward_risk=float(candidate["reward_risk"]),
            point=point,
            tick_size=tick_size,
            tick_value=tick_value,
            spread_price=spread_price,
            slippage_price=slippage_price,
            periods_per_year=24 * 4 * 252,
            commission_per_lot=commission_per_lot,
            min_lot=min_lot,
            lot_step=lot_step,
            intrabar_mode=intrabar_mode
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

def ejecutar_walk_forward_activo(
    ruta_lago: str,
    asset_name: str,
    point: float = 0.01,
    tick_size: float = 0.01,
    tick_value: float = 1.0,
    spread_price: float = 0.0,
    slippage_price: float = 0.0,
    n_folds: int = 4,
    purge_bars: int = 120,
    dsr_trials: int = 81,
    max_candidates: int = None,
    commission_per_lot: float = 0.0,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    intrabar_mode: str = "pessimistic",
    dir_salida: str = None
) -> pd.DataFrame:
    """
    Capa 6: Ejecuta la validación Walk-Forward y el análisis de estabilidad
    para el activo especificado.
    """
    print("=========================================================================")
    print(f" CAPA 6: NESTED WALK-FORWARD Y ESTABILIDAD - {asset_name.upper()}")
    print("=========================================================================")
    
    if not os.path.exists(ruta_lago):
        raise FileNotFoundError(f"Lago de datos no encontrado: {ruta_lago}")
        
    df = pd.read_parquet(ruta_lago)
    
    # Cargar espacio de parámetros original
    ruta_space = os.path.join(ruta_raiz, "Capa_6", "parameter_space.json")
    if not os.path.exists(ruta_space):
        # Crear un espacio básico de contingencia si no se encuentra
        space = {
            "threshold": [0.60, 0.65, 0.70],
            "min_strength": [0.30, 0.35, 0.40],
            "vol_multiplier": [2.0, 2.5, 3.0],
            "reward_risk": [1.5, 2.0, 2.5],
            "kalman_gate": [True],
            "objective_weights": {
                "profit_factor": 1.00,
                "deflated_sharpe_probability": 1.00,
                "recovery_factor": 0.35,
                "total_return_pct": 0.02,
                "drawdown_penalty": 0.04,
                "low_trade_penalty": 0.05
            },
            "constraints": {
                "min_closed_trades": 30, # Reducido para permitir más folds
                "max_drawdown_pct_floor": -35.0,
                "min_profit_factor": 1.0
            }
        }
    else:
        space = load_parameter_space(Path(ruta_space))
        
    candidates = iter_candidates(space)
    if max_candidates is not None:
        candidates = candidates[:max(1, int(max_candidates))]
        
    folds = make_walk_forward_folds(df.index, n_folds=n_folds, purge_bars=purge_bars)
    
    if not dir_salida:
        dir_salida = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "resultados", f"{asset_name.upper()}_nested_walk_forward")
        
    out_path = Path(dir_salida)
    out_path.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(folds).to_csv(out_path / "folds.csv", index=False)
    
    print(f"• Cargadas {len(df)} velas.")
    print(f"• Analizando {len(candidates)} candidatos de optimización.")
    print(f"• Evaluando {len(folds)} folds cronológicos de Walk-Forward...")
    
    all_rankings = []
    for fold in folds:
        print(f"   Fold {fold['fold_id']}: train {fold['train_start_time'].date()} a {fold['train_end_time'].date()}  val {fold['val_start_time'].date()} a {fold['val_end_time'].date()}")
        ranking = evaluate_fold_activo(
            df, fold, candidates, space, dsr_trials, out_path, point, tick_size, tick_value, spread_price, slippage_price,
            commission_per_lot, min_lot, lot_step, intrabar_mode
        )
        all_rankings.append(ranking)
        best = ranking.iloc[0]
        print(f"     Mejor Score: {best['score']:.4f}  PF: {best['profit_factor']:.2f}  DD: {best['max_drawdown_pct']:.2f}%  Trades: {int(best['closed_trades'])}")
        
    combined = pd.concat(all_rankings, ignore_index=True) if all_rankings else pd.DataFrame()
    combined.to_csv(out_path / "nested_all_rankings.csv", index=False)
    
    if combined.empty:
        print(" ERROR: No se pudieron calcular combinaciones válidas.")
        return pd.DataFrame()
        
    # Calcular estabilidad
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
    stability.to_csv(out_path / "nested_stability_ranking.csv", index=False)
    
    print(f"\n CAPA 6 COMPLETADA")
    print(f" • Rankings guardados en: {dir_salida}")
    print("\n Top 3 configuraciones estables encontradas:")
    cols = ["robust_score", "threshold", "min_strength", "vol_multiplier", "reward_risk", "mean_pf", "worst_dd"]
    print(stability[cols].head(3).to_string(index=False))
    print("=========================================================================\n")
    return stability

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ejecutar_walk_forward_activo(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python walk_forward_activo.py <ruta_lago> <nombre_activo>")
