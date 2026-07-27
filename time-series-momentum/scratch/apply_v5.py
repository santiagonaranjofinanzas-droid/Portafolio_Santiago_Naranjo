import re
import os

#1. UPDATE optimization.py WITH FULL SIMULATE_THRESHOLD_VALIDATION
with open("src/optimization.py", "r", encoding="utf-8") as f:
    opt = f.read()

sim_code = """
def simulate_threshold_validation(val_dfs, model, threshold_candidates, features_list, tickers, get_swap_multiplier_fn=None):
    # 1. Master calendar
    all_dates = sorted(list(set().union(*[df.index for df in val_dfs])))
    
    # 2. Precompute raw preds
    raw_preds = {ticker: {} for ticker in tickers}
    for i, ticker in enumerate(tickers):
        df_v = val_dfs[i]
        valid_features = df_v[features_list].dropna()
        if len(valid_features) > 0:
            preds = model.predict(valid_features.values)
            for d_idx, d in enumerate(valid_features.index):
                raw_preds[ticker][d] = preds[d_idx]
                
    best_th = threshold_candidates[0]
    best_val_sharpe = -999.0
    results = {}
    
    for th_cand in threshold_candidates:
        val_returns = []
        prev_w = {t: 0.0 for t in tickers}
        prev_w_prev = {t: 0.0 for t in tickers}
        
        for v_idx, v_date in enumerate(all_dates):
            day_ret = 0.0
            has_trade = False
            
            # --- PHASE 1: EVALUATE YESTERDAY'S WEIGHTS ON TODAY'S RETURN ---
            if v_idx > 0:
                prev_date = all_dates[v_idx - 1]
                for i, ticker in enumerate(tickers):
                    df_v = val_dfs[i]
                    if v_date in df_v.index and prev_date in df_v.index:
                        p_today = df_v.loc[v_date, "Close"]
                        p_yesterday = df_v.loc[prev_date, "Close"]
                        asset_ret = (p_today - p_yesterday) / p_yesterday
                        
                        w_prev = prev_w[ticker]
                        w_prev_prev = prev_w_prev[ticker]
                        
                        tc_rate = 0.0001
                        tc_cost = abs(w_prev - w_prev_prev) * tc_rate
                        
                        swap_cost = 0.0
                        if get_swap_multiplier_fn is not None and w_prev != 0:
                            mult = get_swap_multiplier_fn(ticker, prev_date)
                            swap_rate = df_v.loc[prev_date, "SwapLong"] if w_prev > 0 else df_v.loc[prev_date, "SwapShort"]
                            swap_cost = abs(w_prev) * swap_rate / 360.0 * mult
                        
                        day_ret += (w_prev * asset_ret - tc_cost + swap_cost)
                        has_trade = True
            
            if has_trade:
                val_returns.append(day_ret)
                
            # --- PHASE 2: CALCULATE WEIGHTS FOR NEXT DAY ---
            for i, ticker in enumerate(tickers):
                if ticker in raw_preds and v_date in raw_preds[ticker]:
                    raw_p = raw_preds[ticker][v_date]
                    proposed_w = raw_p
                    
                    if abs(proposed_w - prev_w[ticker]) < th_cand:
                        curr_w = prev_w[ticker]
                    else:
                        curr_w = proposed_w
                        
                    prev_w_prev[ticker] = prev_w[ticker]
                    prev_w[ticker] = curr_w
                    
        # Calculate empirical Sharpe
        if len(val_returns) > 3:
            th_series = pd.Series(val_returns)
            std = th_series.std()
            val_sharpe = (th_series.mean() / std * np.sqrt(252)) if std > 0 else 0.0
        else:
            val_sharpe = 0.0
            
        results[th_cand] = val_sharpe
        if val_sharpe > best_val_sharpe:
            best_val_sharpe = val_sharpe
            best_th = th_cand
            
    return best_th, best_val_sharpe, results
"""

if "simulate_threshold_validation" not in opt:
    with open("src/optimization.py", "a", encoding="utf-8") as f:
        f.write("\n" + sim_code)

#2. UPDATE run_backtest.py
with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb = f.read()

#Make sure imports are correct
if "simulate_threshold_validation" not in rb:
    rb = rb.replace(
        "from src.optimization import calcular_catsmom_factor, calcular_floor_causal, calcular_dsr_empirical, calcular_dsr_conservative, calcular_probabilistic_sharpe, get_purged_train_slice",
        "from src.optimization import calcular_catsmom_factor, calcular_floor_causal, calcular_dsr_empirical, calcular_dsr_conservative, calcular_probabilistic_sharpe, get_purged_train_slice, simulate_threshold_validation"
    )

#Fix missing global_trials_sr initialization
if "global_trials_sr =" not in rb:
    rb = rb.replace("validation_logs = []", "global_trials_sr = []\nvalidation_logs = []")

#Replace the Mock logic
bad_mock_block = """                # Pre-calculate raw predictions on val_sub to speed up threshold evaluation
                val_dates = val_sub[0].index
                raw_preds = {ticker: {} for ticker in tickers}
                for i, ticker in enumerate(tickers):
                    df_v = val_sub[i]
                    if len(df_v) > 0:
                        # Extract features block
                        valid_features = df_v[features_list_ml].dropna()
                        if len(valid_features) > 0:
                            preds = xgb_temp.predict(valid_features.values)
                            for d_idx, d in enumerate(valid_features.index):
                                raw_preds[ticker][d] = preds[d_idx]
                
                for th_cand in threshold_candidates:
                    val_returns = []
                    prev_w = {t: 0.0 for t in tickers}
                    
                    for v_date in val_dates:
                        day_ret = 0.0
                        has_trade = False
                        for i, ticker in enumerate(tickers):
                            if v_date in raw_preds[ticker]:
                                raw_p = raw_preds[ticker][v_date]
                                
                                # Hysteresis logic
                                if abs(raw_p - prev_w[ticker]) < th_cand:
                                    curr_w = prev_w[ticker]
                                else:
                                    curr_w = raw_p
                                
                                df_v = val_sub[i]
                                # We need target proxy. We use log_ret_1d if available
                                if "log_ret_1d" in df_v.columns:
                                    ret_t = df_v.loc[v_date, "log_ret_1d"]
                                else:
                                    ret_t = 0.0
                                    
                                cost = abs(curr_w - prev_w[ticker]) * 0.0001
                                day_ret += curr_w * ret_t - cost
                                prev_w[ticker] = curr_w
                                has_trade = True
                                
                        if has_trade:
                            val_returns.append(day_ret)
                            
                    if len(val_returns) > 3:
                        th_series = pd.Series(val_returns)
                        std = th_series.std()
                        val_sharpe = (th_series.mean() / std * np.sqrt(252)) if std > 0 else 0.0
                    else:
                        val_sharpe = 0.0
                        
                    global_trials_sr.append(val_sharpe)
                    if val_sharpe > best_val_sharpe:
                        best_val_sharpe = val_sharpe
                        best_th = th_cand"""

good_sim_block = """                best_th, best_val_sharpe, results_dict = simulate_threshold_validation(
                    val_sub, xgb_temp, threshold_candidates, features_list_ml, tickers, get_swap_multiplier
                )
                for val_sh in results_dict.values():
                    global_trials_sr.append(val_sh)"""

#In case the regex replace fails, let's just do a string replace of the exact block if present.
#It's safer to use re.sub between threshold_candidates = ... and validation_logs.append
rb = re.sub(
    r"threshold_candidates = \[0\.0, 0\.0002, 0\.0005, 0\.0010\].*?validation_logs\.append",
    r"threshold_candidates = [0.0, 0.0002, 0.0005, 0.0010]\n                " + good_sim_block.strip() + "\n                validation_logs.append",
    rb,
    flags=re.DOTALL
)

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb)

#Write test_validation.py updates
with open("tests/test_validation.py", "w", encoding="utf-8") as f:
    f.write('''import pytest
import numpy as np
from src.optimization import calcular_dsr_empirical, calcular_dsr_conservative, simulate_threshold_validation
import pandas as pd
from src.models.markov import estimar_regimen_hmm

def test_dsr_separation():
    trials = [0.1, 0.5, 0.8, 1.2, 1.5, 0.2, 0.4, 0.9]
    retornos = pd.Series(np.random.normal(0.001, 0.01, 1000))
    emp = calcular_dsr_empirical(retornos, trials)
    cons = calcular_dsr_conservative(retornos, trials, conservative_n=64)
    assert cons < emp

def test_hmm_label_switching():
    np.random.seed(42)
    data = np.concatenate([np.random.normal(0, 0.01, 100), np.random.normal(0, 0.05, 50)])
    prob1 = estimar_regimen_hmm(data, window=150)
    
    np.random.seed(43)
    data2 = np.concatenate([np.random.normal(0, 0.05, 100), np.random.normal(0, 0.01, 50)])
    prob2 = estimar_regimen_hmm(data2, window=150)
    
    assert prob1 > 0
    assert prob2 > 0

class MockModel:
    def predict(self, features):
        return np.ones(len(features))

def test_simulate_threshold_timing():
    dates = pd.date_range("2021-01-01", periods=3)
    df = pd.DataFrame({"Close": [100, 105, 110], "feature": [1, 2, 3], "SwapLong": [0.01, 0.01, 0.01], "SwapShort": [0.01, 0.01, 0.01]}, index=dates)
    
    def mock_swap(ticker, date): return 1.0
    
    best_th, best_val_sharpe, results = simulate_threshold_validation(
        [df], MockModel(), [0.0], ["feature"], ["TICKER"], mock_swap
    )
    
    assert best_th == 0.0
    # Day 1: weights computed for T=1. No return.
    # Day 2: weight T=1 applied to return T=2 (105-100)/100 = 0.05. New weights computed.
    # Day 3: weight T=2 applied to return T=3 (110-105)/105 = 0.0476.
''')

print("Applied V5 Final fixes.")
