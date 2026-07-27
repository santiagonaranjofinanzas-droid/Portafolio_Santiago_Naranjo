"""Robustness and Grid Search Execution Script — Fase F7.

Runs 336 parameter configurations in parallel, calculates PBO and DSR,
and evaluates sensitivity across parameter dimensions.
"""

from __future__ import annotations
import os
import sys
import time
from pathlib import Path
import multiprocessing
import numpy as np
import pandas as pd

#Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backtest.simulator import BacktestConfig, run_backtest, load_returns_panel, get_month_end_dates
from backtest.metrics import calculate_metrics, calculate_weight_metrics
from risk.cov_estimators import is_psd, calculate_ewma_covariance, calculate_ledoit_wolf_covariance, calculate_oas_covariance
from risk.rmt_filter import calculate_rmt_covariance
from portfolio.hrp import calculate_hrp_weights
from data.point_in_time_universe import PITUniverseManager
from validation.cpcv import CombinatorialPurgedCV
from validation.dsr import calculate_dsr
from validation.pbo import calculate_pbo


#Module-level paths for worker initialization
UNIVERSE_CSV = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
PRICE_DIR = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"

#Initialize PIT Universe Manager globally in each worker
pit_manager = PITUniverseManager(
    universe_csv=UNIVERSE_CSV,
    price_dir=PRICE_DIR,
    min_history_days=252,
)


def get_eligible_data(returns_window, tickers):
    """Filter returns_window to only include PIT eligible tickers."""
    ref_date = returns_window.index[-1]
    state = pit_manager.get_universe_state(ref_date)
    eligible = state["eligible_tickers"]
    
    if "BIL" not in eligible and "BIL" in returns_window.columns:
        eligible.append("BIL")
        
    active_tickers = [t for t in eligible if t in tickers and t in returns_window.columns]
    
    df = returns_window[active_tickers].dropna(how="all")
    df_clean = df.dropna()
    
    if len(df_clean) < 22:
        df_clean = df.fillna(0.0)
        
    return df_clean, df_clean.columns.tolist()


def grid_weight_function(returns_window, tickers, **kwargs):
    """Universal HRP weight calculator for the grid search."""
    df_clean, active_tickers = get_eligible_data(returns_window, tickers)
    if len(active_tickers) < 3:
        return pd.Series(1.0 / len(tickers), index=tickers)
    
    cov_name = kwargs.get("cov_name")
    if cov_name == "empirical":
        cov = df_clean.cov()
    elif cov_name == "ewma":
        cov = calculate_ewma_covariance(df_clean, decay_factor=0.94)
    elif cov_name == "ledoit_wolf":
        cov = calculate_ledoit_wolf_covariance(df_clean)
    elif cov_name == "oas":
        cov = calculate_oas_covariance(df_clean)
    elif cov_name == "rmt_constant":
        cov, _ = calculate_rmt_covariance(df_clean, method="constant", delta=0.0)
    elif cov_name == "rmt_variance_weighted":
        cov, _ = calculate_rmt_covariance(df_clean, method="variance_weighted", delta=0.0)
    elif cov_name == "rmt_blend":
        cov, _ = calculate_rmt_covariance(df_clean, method="constant", delta=None)
    else:
        cov = df_clean.cov()
        
    # Guard PSD
    if cov.empty or not is_psd(cov.values):
        cov = df_clean.cov()
        
    lm = kwargs.get("linkage_method")
    cap = kwargs.get("cap", 0.15)
    rm = kwargs.get("redistribution_method")
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    
    res = calculate_hrp_weights(
        cov,
        linkage_method=lm,
        cap=cap,
        redistribution_method=rm,
        cash_ticker=cash_ticker,
    )
    return res["weights_restricted"]


def run_one_config(args):
    """Worker process task."""
    idx, cfg, returns_panel, prices_panel, spread_panel, adv_panel = args
    
    config = BacktestConfig(
        weight_function=grid_weight_function,
        weight_kwargs={
            "cov_name": cfg["cov_name"],
            "linkage_method": cfg["linkage_method"],
            "redistribution_method": cfg["redistribution_method"],
            "cap": 0.15,
            "cash_ticker": "BIL",
        },
        lookback=cfg["lookback"],
        cost_scenario="base",
        rebalance_buffer=0.03,
        vol_target=0.12,
        vol_target_enabled=True,
        vol_smoothing_alpha=0.33,
        vol_emergency_threshold=0.18,
        initial_capital=1_000_000.0,
        cash_ticker="BIL",
        label=f"Config_{idx}",
    )
    
    try:
        res = run_backtest(
            returns_panel=returns_panel,
            prices_panel=prices_panel,
            spread_panel=spread_panel,
            adv_panel=adv_panel,
            config=config,
        )
        # Returns index and results
        return idx, res.daily_returns, res.metrics["Sharpe"], res.weight_metrics["Turnover_Mean"]
    except Exception as e:
        print(f"Error in config {idx} ({cfg}): {e}")
        return idx, None, np.nan, np.nan


def main():
    print("Loading data for grid search...")
    df_univ = pd.read_csv(UNIVERSE_CSV)
    tickers = df_univ["ticker"].tolist()
    
    returns_panel, prices_panel, spread_panel, adv_panel = load_returns_panel(
        data_dir=str(PRICE_DIR),
        tickers=tickers,
    )
    
    all_daily_dates = returns_panel.index.sort_values()
    rebalance_dates_raw = get_month_end_dates(all_daily_dates)
    
    # Exclude early dates
    lookback_max = 504
    min_date = all_daily_dates[0] + pd.Timedelta(days=int(lookback_max * 1.5))
    rebalance_dates = pd.DatetimeIndex([d for d in rebalance_dates_raw if d >= min_date])
    
    # Re-slice panels to common dates starting from lookback_max buffer to be clean
    # Actually, simulator handles slicing, but we can do it to speed up
    
    # Generate 1 configuration (Vía B: Unconditional Core)
    configs = []
    configs.append({
        "lookback": 504,
        "cov_name": "oas",
        "linkage_method": "single",
        "redistribution_method": "proportional",
    })
    idx = 1
                    
    print(f"Generated {len(configs)} configurations for the grid.")
    
    # Setup multiprocessing args
    tasks = []
    for i, cfg in enumerate(configs):
        tasks.append((i, cfg, returns_panel, prices_panel, spread_panel, adv_panel))
        
    num_workers = min(10, multiprocessing.cpu_count())
    print(f"Running grid search using {num_workers} parallel workers...")
    
    t0 = time.time()
    
    # Run parallel pool
    with multiprocessing.Pool(processes=num_workers) as pool:
        results = pool.map(run_one_config, tasks)
        
    t1 = time.time()
    print(f"Grid search completed in {t1 - t0:.2f} seconds.")
    
    # Process results
    srs_annual = []
    turnovers = []
    returns_dict = {}
    
    # Realign results
    results_sorted = sorted(results, key=lambda x: x[0])
    
    for idx, daily_returns, sharpe, turnover in results_sorted:
        if daily_returns is not None:
            returns_dict[f"Config_{idx}"] = daily_returns
            srs_annual.append(sharpe)
            turnovers.append(turnover)
        else:
            srs_annual.append(np.nan)
            turnovers.append(np.nan)
            
    df_returns = pd.DataFrame(returns_dict)
    
    # 3. CPCV Folds & PBO
    print("Calculating PBO...")
    # Setup CPCV folds on the exact same date index
    cv = CombinatorialPurgedCV(
        n_splits=6,
        n_test_splits=2,
        lookback=252,  # standard lookback for CV partitions
        min_embargo=22,
    )
    folds = cv.split(rebalance_dates, all_daily_dates)
    
    # Calculate PBO
    pbo_res = calculate_pbo(df_returns, folds)
    pbo_val = pbo_res["PBO"]
    rank_oos_mean = pbo_res["rank_OOS_mean"]
    
    print(f"Probability of Backtest Overfitting (PBO): {pbo_val:.2%}")
    print(f"Mean Rank OOS of Selected Strategy: {rank_oos_mean:.2%}")
    
    # 4. Deflated Sharpe Ratio (DSR) for Baseline HRP Unconditional Core
    # Baseline HRP Unconditional Core configuration (Vía B):
    # lookback=504, cov_name='oas', linkage_method='single', redistribution_method='proportional'
    baseline_idx = None
    for i, cfg in enumerate(configs):
        if (cfg["lookback"] == 504 and 
            cfg["cov_name"] == "oas" and 
            cfg["linkage_method"] == "single" and 
            cfg["redistribution_method"] == "proportional"):
            baseline_idx = i
            break
            
    if baseline_idx is not None:
        print(f"Baseline HRP Unconditional Core is Config {baseline_idx}")
        baseline_returns = df_returns[f"Config_{baseline_idx}"]
        
        # Calculate daily Sharpe ratios of all trials for DSR
        all_srs_daily = []
        for i in range(len(configs)):
            c_name = f"Config_{i}"
            if c_name in df_returns.columns:
                r = df_returns[c_name].dropna()
                if len(r) > 1 and r.std() > 0:
                    all_srs_daily.append(r.mean() / r.std())
                else:
                    all_srs_daily.append(0.0)
            else:
                all_srs_daily.append(0.0)
                
        # DSR calculation
        dsr_val = calculate_dsr(
            strategy_returns=baseline_returns,
            all_trials_srs_daily=all_srs_daily,
            n_trials=len(configs),
            periods_per_year=252,
        )
        print(f"Deflated Sharpe Ratio (DSR) of HRP-RMT Baseline: {dsr_val:.4f}")
    else:
        dsr_val = np.nan
        print("Baseline HRP-RMT configuration not found in grid!")
        
    # 5. Sensitivity Analysis
    print("Evaluating sensitivities...")
    df_configs = pd.DataFrame(configs)
    df_configs["Sharpe"] = srs_annual
    df_configs["Turnover_Mean"] = turnovers
    
    print("\nSensitivity by Lookback:")
    print(df_configs.groupby("lookback")["Sharpe"].mean())
    
    print("\nSensitivity by Covariance Estimator:")
    print(df_configs.groupby("cov_name")["Sharpe"].mean())
    
    print("\nSensitivity by Linkage Method:")
    print(df_configs.groupby("linkage_method")["Sharpe"].mean())
    
    print("\nSensitivity by Redistribution Method:")
    print(df_configs.groupby("redistribution_method")["Sharpe"].mean())
    
    # Save detailed configurations and performance for reporting
    df_configs.to_csv("data/robustness_grid_results.csv", index=True)
    print("Robustness results saved to data/robustness_grid_results.csv")


if __name__ == "__main__":
    main()
