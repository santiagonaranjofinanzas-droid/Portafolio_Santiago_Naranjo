"""Script to execute the complete backtest simulation for HRP-RMT and all benchmarks.

Saves results and generates report data for reporte_fases.md.
"""

from __future__ import annotations
import os
import sys
from pathlib import Path
import numpy as np
import pandas as pd

#Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from backtest.simulator import BacktestConfig, run_backtest, load_returns_panel
from backtest.cost_model import CostScenario
from backtest.metrics import calculate_metrics, calculate_weight_metrics
from backtest.benchmarks import (
    equal_weight,
    inverse_volatility,
    equal_risk_contribution,
    min_variance_lw,
    hrp_empirical,
    hrp_lw,
    benchmark_60_40,
    benchmark_composite,
)
from risk.rmt_filter import calculate_rmt_covariance
from portfolio.hrp import calculate_hrp_weights
from data.point_in_time_universe import PITUniverseManager


#1. Initialize PIT Universe Manager
UNIVERSE_CSV = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
PRICE_DIR = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"

pit_manager = PITUniverseManager(
    universe_csv=UNIVERSE_CSV,
    price_dir=PRICE_DIR,
    min_history_days=252,  # 1 year min history
    min_adv_usd=5_000_000.0,  # 5M USD ADV
)


def get_eligible_data(returns_window, tickers):
    """Filter returns_window to only include PIT eligible tickers."""
    ref_date = returns_window.index[-1]
    state = pit_manager.get_universe_state(ref_date)
    eligible = state["eligible_tickers"]
    
    # Ensure BIL (cash sink) is present
    if "BIL" not in eligible and "BIL" in returns_window.columns:
        eligible.append("BIL")
        
    # Intersect with input tickers and returns_window columns
    active_tickers = [t for t in eligible if t in tickers and t in returns_window.columns]
    
    # Extract window and clean NaNs
    df = returns_window[active_tickers].dropna(how="all")
    df_clean = df.dropna()
    
    # Fallback if too many rows dropped
    if len(df_clean) < 22:
        df_clean = df.fillna(0.0)
        
    return df_clean, df_clean.columns.tolist()


#2. Define weight functions matching simulator signature:
#(returns_window, eligible_tickers, **kwargs) -> pd.Series

from risk.cov_estimators import calculate_oas_covariance

def weight_hrp_unconditional(returns_window, tickers, **kwargs):
    df_clean, active_tickers = get_eligible_data(returns_window, tickers)
    if len(active_tickers) < 3:
        return pd.Series(1.0 / len(tickers), index=tickers)
    
    # OAS filtered covariance (parameterless unconditional robustness)
    cov_oas = calculate_oas_covariance(df_clean)
    
    lm = kwargs.get("linkage_method", "single")
    cap = kwargs.get("cap", 0.15)
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    rm = kwargs.get("redistribution_method", "proportional")
    
    res = calculate_hrp_weights(
        cov_oas,
        linkage_method=lm,
        cap=cap,
        redistribution_method=rm,
        cash_ticker=cash_ticker,
    )
    return res["weights_restricted"]


def weight_equal_weight(returns_window, tickers, **kwargs):
    _, active_tickers = get_eligible_data(returns_window, tickers)
    cap = kwargs.get("cap", 0.15)
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    return equal_weight(active_tickers, cap=cap, cash_ticker=cash_ticker)


def weight_inverse_volatility(returns_window, tickers, **kwargs):
    df_clean, active_tickers = get_eligible_data(returns_window, tickers)
    if len(active_tickers) == 0:
        return pd.Series(dtype=float)
    cov = df_clean.cov()
    cap = kwargs.get("cap", 0.15)
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    return inverse_volatility(cov, cap=cap, cash_ticker=cash_ticker)


def weight_equal_risk_contribution(returns_window, tickers, **kwargs):
    df_clean, active_tickers = get_eligible_data(returns_window, tickers)
    if len(active_tickers) == 0:
        return pd.Series(dtype=float)
    cov = df_clean.cov()
    cap = kwargs.get("cap", 0.15)
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    return equal_risk_contribution(cov, cap=cap, cash_ticker=cash_ticker)


def weight_min_variance_lw(returns_window, tickers, **kwargs):
    df_clean, active_tickers = get_eligible_data(returns_window, tickers)
    if len(active_tickers) == 0:
        return pd.Series(dtype=float)
    cap = kwargs.get("cap", 0.15)
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    return min_variance_lw(df_clean, cap=cap, cash_ticker=cash_ticker)


def weight_60_40(returns_window, tickers, **kwargs):
    # Static 60/40 benchmark
    w = benchmark_60_40(equity_ticker="SPY", bond_ticker="AGG")
    return w.reindex(tickers, fill_value=0.0)


def weight_composite(returns_window, tickers, **kwargs):
    # Equal-weight of selectable universe, subject to cap
    _, active_tickers = get_eligible_data(returns_window, tickers)
    cap = kwargs.get("cap", 0.15)
    cash_ticker = kwargs.get("cash_ticker", "BIL")
    return benchmark_composite(active_tickers, cap=cap, cash_ticker=cash_ticker)


def main():
    print("Loading price panels...")
    # Load universe tickers
    df_univ = pd.read_csv(UNIVERSE_CSV)
    tickers = df_univ["ticker"].tolist()
    
    # Load EOD panels
    returns_panel, prices_panel, spread_panel, adv_panel = load_returns_panel(
        data_dir=str(PRICE_DIR),
        tickers=tickers,
    )
    print(f"Loaded returns panel with shape: {returns_panel.shape}")
    
    # Define strategy configurations
    strategies = {
        "HRP Unconditional Core": {
            "weight_function": weight_hrp_unconditional,
            "weight_kwargs": {"linkage_method": "single", "cap": 0.15, "cash_ticker": "BIL", "redistribution_method": "proportional"},
            "vol_target_enabled": True,
            "rebalance_buffer": 0.03,
            "lookback": 504,
        },
        "1/N Equal Weight": {
            "weight_function": weight_equal_weight,
            "weight_kwargs": {"cap": 0.15, "cash_ticker": "BIL"},
            "vol_target_enabled": True,
            "rebalance_buffer": 0.03,
            "lookback": 504,
        },
        "Inverse Volatility (IVP)": {
            "weight_function": weight_inverse_volatility,
            "weight_kwargs": {"cap": 0.15, "cash_ticker": "BIL"},
            "vol_target_enabled": True,
            "rebalance_buffer": 0.03,
            "lookback": 504,
        },
        "Equal Risk Contribution (ERC)": {
            "weight_function": weight_equal_risk_contribution,
            "weight_kwargs": {"cap": 0.15, "cash_ticker": "BIL"},
            "vol_target_enabled": True,
            "rebalance_buffer": 0.03,
            "lookback": 504,
        },
        "Minimum Variance (MinVar-LW)": {
            "weight_function": weight_min_variance_lw,
            "weight_kwargs": {"cap": 0.15, "cash_ticker": "BIL"},
            "vol_target_enabled": True,
            "rebalance_buffer": 0.03,
            "lookback": 504,
        },
        "Composite Benchmark": {
            "weight_function": weight_composite,
            "weight_kwargs": {"cap": 0.15, "cash_ticker": "BIL"},
            "vol_target_enabled": True,
            "rebalance_buffer": 0.03,
            "lookback": 504,
        },
        "60/40 Benchmark": {
            "weight_function": weight_60_40,
            "weight_kwargs": {},
            "vol_target_enabled": False,  # Passive benchmark, no vol target
            "rebalance_buffer": 0.0,       # Passive benchmark, rebalance monthly
            "lookback": 252,
        },
    }
    
    results = {}
    
    for name, s_cfg in strategies.items():
        print(f"Running backtest for: {name}...")
        config = BacktestConfig(
            weight_function=s_cfg["weight_function"],
            weight_kwargs=s_cfg["weight_kwargs"],
            lookback=s_cfg["lookback"],
            cost_scenario="base",
            rebalance_buffer=s_cfg["rebalance_buffer"],
            vol_target=0.12,
            vol_target_enabled=s_cfg["vol_target_enabled"],
            vol_smoothing_alpha=0.33,
            vol_emergency_threshold=0.18,
            initial_capital=1_000_000.0,
            cash_ticker="BIL",
            label=name,
        )
        
        try:
            res = run_backtest(
                returns_panel=returns_panel,
                prices_panel=prices_panel,
                spread_panel=spread_panel,
                adv_panel=adv_panel,
                config=config,
            )
            results[name] = res
            print(f"  Completed. Final NAV: {res.daily_nav.iloc[-1]:,.2f}  CAGR: {res.metrics['CAGR']:.2%}")
        except Exception as e:
            print(f"  Error running {name}: {e}")
            import traceback
            traceback.print_exc()

    # Generate results table
    print("\nBacktest Summary Table:")
    metrics_to_show = [
        ("CAGR", "{:.2%}"),
        ("Volatility_Ann", "{:.2%}"),
        ("Sharpe", "{:.3f}"),
        ("Sortino", "{:.3f}"),
        ("Calmar", "{:.3f}"),
        ("MDD", "{:.2%}"),
        ("Max_DD_Duration_Days", "{:,.0f}"),
        ("Turnover_Mean", "{:.2%}"),
        ("N_Effective_Mean", "{:.1f}"),
        ("N_Rebalances", "{:d}"),
    ]
    
    headers = ["Strategy"] + [m[0] for m in metrics_to_show]
    rows = []
    
    for name, res in results.items():
        row = [name]
        for m_key, fmt in metrics_to_show:
            val = np.nan
            if m_key in res.metrics:
                val = res.metrics[m_key]
            elif m_key in res.weight_metrics:
                val = res.weight_metrics[m_key]
            
            if pd.isna(val):
                row.append("N/A")
            else:
                row.append(fmt.format(val))
        rows.append(row)
        
    df_summary = pd.DataFrame(rows, columns=headers)
    print(df_summary.to_string(index=False))
    
    # Save the summary DataFrame to a CSV for later use if needed
    df_summary.to_csv("data/backtest_summary.csv", index=False)
    
    # Write to a temporary file the details of skipped rebalances for the report
    for name, res in results.items():
        if name in ["HRP Unconditional Core"]:
            total_rebs = len(res.rebalance_dates) + len(res.skipped_rebalances)
            skipped_buffer = sum(1 for x in res.skipped_rebalances if "buffer_skip" in str(x[1]))
            print(f"{name}: total schedules={total_rebs}, executed={len(res.rebalance_dates)}, skipped by buffer={skipped_buffer}")


if __name__ == "__main__":
    main()
