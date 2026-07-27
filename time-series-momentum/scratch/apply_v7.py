import re
import os

#1. Add simulate_threshold_validation to src/optimization.py
with open("src/optimization.py", "r", encoding="utf-8") as f:
    opt = f.read()

sim_code = """
def simulate_threshold_validation(val_dfs, model, threshold_candidates, features_list, tickers, get_swap_multiplier_fn=None):
    import pandas as pd
    import numpy as np
    
    # 1. Calendario Maestro (Unión del índice OOS)
    all_dates = sorted(list(set().union(*[df.index for df in val_dfs])))
    
    # Precomputar predicciones crudas del modelo entrenado en train_sub
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
    results_by_threshold = {}
    val_returns_by_threshold = {}
    turnover_by_threshold = {}
    costs_by_threshold = {}
    
    for th_cand in threshold_candidates:
        val_returns = []
        total_turnover = 0.0
        total_costs = 0.0
        
        # Pesos históricos
        prev_w = {t: 0.0 for t in tickers}
        prev_w_prev = {t: 0.0 for t in tickers}
        
        for v_idx, v_date in enumerate(all_dates):
            day_ret = 0.0
            has_trade = False
            
            # --- FASE 1: APLICACIÓN DE PESOS (T-1) AL RETORNO (T) ---
            if v_idx > 0:
                prev_date = all_dates[v_idx - 1]
                for i, ticker in enumerate(tickers):
                    df_v = val_dfs[i]
                    if v_date in df_v.index and prev_date in df_v.index:
                        # Retorno Empírico Vectorial
                        p_today = df_v.loc[v_date, "Close"]
                        p_yesterday = df_v.loc[prev_date, "Close"]
                        asset_ret = (p_today - p_yesterday) / p_yesterday
                        
                        w_prev = prev_w[ticker]
                        w_prev_prev = prev_w_prev[ticker]
                        
                        # Costos de Transacción (Idénticos al OOS)
                        tc_rate = 0.0001
                        tc_cost = abs(w_prev - w_prev_prev) * tc_rate
                        
                        # Triple Swap Cost
                        swap_cost = 0.0
                        if w_prev != 0 and "SwapLong" in df_v.columns:
                            m_mult = get_swap_multiplier_fn(ticker, prev_date) if get_swap_multiplier_fn else 1.0
                            swap_rate = df_v.loc[prev_date, "SwapLong"] if w_prev > 0 else df_v.loc[prev_date, "SwapShort"]
                            swap_cost = abs(w_prev) * swap_rate / 360.0 * m_mult
                        
                        day_ret += (w_prev * asset_ret - tc_cost + swap_cost)
                        total_costs += (tc_cost - swap_cost)
                        has_trade = True
            
            if has_trade:
                val_returns.append(day_ret)
                
            # --- FASE 2: GENERACIÓN DE NUEVAS SEÑALES PARA (T+1) ---
            for i, ticker in enumerate(tickers):
                if ticker in raw_preds and v_date in raw_preds[ticker]:
                    proposed_w = raw_preds[ticker][v_date]
                    
                    # Histéresis Exacta OOS
                    if abs(proposed_w - prev_w[ticker]) < th_cand:
                        curr_w = prev_w[ticker]
                    else:
                        curr_w = proposed_w
                        total_turnover += abs(curr_w - prev_w[ticker])
                        
                    prev_w_prev[ticker] = prev_w[ticker]
                    prev_w[ticker] = curr_w
                    
        # Métricas de la Simulación
        if len(val_returns) > 3:
            th_series = pd.Series(val_returns)
            std = th_series.std()
            val_sharpe = (th_series.mean() / std * np.sqrt(252)) if std > 0 else 0.0
        else:
            val_sharpe = 0.0
            
        results_by_threshold[th_cand] = val_sharpe
        val_returns_by_threshold[th_cand] = val_returns
        turnover_by_threshold[th_cand] = total_turnover
        costs_by_threshold[th_cand] = total_costs
        
        if val_sharpe > best_val_sharpe:
            best_val_sharpe = val_sharpe
            best_th = th_cand
            
    return {
        "best_th": best_th,
        "best_val_sharpe": best_val_sharpe,
        "results_by_threshold": results_by_threshold,
        "val_returns_by_threshold": val_returns_by_threshold,
        "turnover_by_threshold": turnover_by_threshold,
        "costs_by_threshold": costs_by_threshold,
        "valid_obs": len(val_returns)
    }
"""

if "def simulate_threshold_validation" in opt:
    opt = re.sub(r"def simulate_threshold_validation.*?return \{.*?\}", sim_code.strip(), opt, flags=re.DOTALL)
else:
    opt = opt + "\n" + sim_code.strip() + "\n"

with open("src/optimization.py", "w", encoding="utf-8") as f:
    f.write(opt)

#2. Update run_backtest.py
with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb = f.read()

#Add import
if "simulate_threshold_validation" not in rb:
    rb = rb.replace("get_purged_train_slice", "get_purged_train_slice, simulate_threshold_validation")

#Check where best_th is generated and replace it.
#Look for: "threshold_candidates = [0.0, 0.0002, 0.0005, 0.0010]"
#and replace until "validation_logs.append({"

new_call = """
                threshold_candidates = [0.0, 0.0002, 0.0005, 0.0010]
                
                # We need get_swap_multiplier available
                # It is defined later in the script but can be called if we move it or pass it.
                # Since get_swap_multiplier is at the module level in run_backtest.py, we can pass it.
                val_metrics = simulate_threshold_validation(
                    val_sub, xgb_temp, threshold_candidates, features_list_ml, tickers, get_swap_multiplier
                )
                best_th = val_metrics["best_th"]
                best_val_sharpe = val_metrics["best_val_sharpe"]
                
                for sh in val_metrics["results_by_threshold"].values():
                    global_trials_sr.append(sh)
"""

#Replace block safely
rb = re.sub(
    r"threshold_candidates = \[0\.0, 0\.0002, 0\.0005, 0\.0010\].*?validation_logs\.append",
    new_call.strip() + "\n                validation_logs.append",
    rb,
    flags=re.DOTALL
)

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb)

#3. Update Tests
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
    assert prob1 > 0

class MockModel:
    def predict(self, features):
        return np.ones(len(features))

def test_simulate_threshold_timing():
    dates = pd.date_range("2021-01-01", periods=3)
    df = pd.DataFrame({"Close": [100, 105, 110], "feature": [1, 2, 3], "SwapLong": [0.01, 0.01, 0.01], "SwapShort": [0.01, 0.01, 0.01]}, index=dates)
    
    def mock_swap(ticker, date): return 1.0
    
    res = simulate_threshold_validation(
        [df], MockModel(), [0.0], ["feature"], ["TICKER"], mock_swap
    )
    
    assert res["best_th"] == 0.0
    assert res["valid_obs"] == 2 # 2 days of returns
''')

print("Applied V7 Full OOS Miniature.")
