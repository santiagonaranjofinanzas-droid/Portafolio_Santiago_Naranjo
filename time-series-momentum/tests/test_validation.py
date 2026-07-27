import pytest
import numpy as np
from src.optimization import (
    calcular_dsr_empirical, 
    calcular_dsr_conservative, 
    simulate_threshold_validation,
    calcular_costo_transaccion,
    calcular_swap_pnl,
    signal_to_weight_fn
)
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
        return np.ones(len(features)) * 0.5

#1. Confirmar que no existe np.random.normal en threshold validation
def test_no_random_normal_in_validation():
    import inspect
    src_code = inspect.getsource(simulate_threshold_validation)
    assert "random" not in src_code
    assert "normal" not in src_code

#2. Confirmar timing T-1 peso / T retorno
def test_simulate_threshold_timing_and_returns():
    dates = pd.date_range("2021-01-01", periods=3)
    df = pd.DataFrame({
        "Close": [100.0, 110.0, 120.0],
        "feature": [1.0, 2.0, 3.0],
        "Spread": [0.0, 0.0, 0.0],
        "SwapLong": [0.0, 0.0, 0.0],
        "SwapShort": [0.0, 0.0, 0.0],
        "Vol_YZ_21": [0.15, 0.15, 0.15],
        "Z_252d": [1.0, 1.0, 1.0]
    }, index=dates)
    
    master_dates = list(dates)
    c4_val_returns = pd.Series([0.0]*len(master_dates), index=master_dates)
    
    res = simulate_threshold_validation(
        val_dfs=[df],
        model=MockModel(),
        threshold_candidates=[0.0],
        features_list=["feature"],
        tickers=["TICKER"],
        master_dates=master_dates,
        c4_val_returns_history=c4_val_returns,
        get_swap_multiplier_fn=lambda t, d: 1.0
    )
    
    val_rets = res["val_returns_by_threshold"][0.0]
    assert len(val_rets) == 2
    # El primer retorno (Día 2) debe ser positivo y aproximarse a 0.01998 ya que w_prev de T0 fue 0.20
    assert np.isclose(val_rets[0], 0.01998)
    # El segundo retorno (Día 3) también debe ser positivo ya que w_prev de T1 fue 0.20
    assert val_rets[1] > 0.0

#3. Confirmar que costos de validation and OOS usan la misma función
def test_shared_cost_functions_consistency():
    p_yesterday = 100.0
    spread_yesterday = 0.02
    w_prev = 0.5
    w_prev_prev = 0.1
    comm = 0.00005
    slip = 0.00005
    
    tc_rate_oos = (spread_yesterday / (2 * p_yesterday)) + comm + slip
    tc_oos = abs(w_prev - w_prev_prev) * tc_rate_oos
    
    tc_val = calcular_costo_transaccion(w_prev, w_prev_prev, p_yesterday, spread_yesterday, comm, slip)
    assert np.isclose(tc_oos, tc_val)

#4. Confirmar que el calendario maestro es compartido y respetado
def test_master_calendar_shared():
    dates = pd.date_range("2021-01-01", periods=3)
    df = pd.DataFrame({
        "Close": [100.0, 110.0, 120.0],
        "feature": [1.0, 2.0, 3.0],
        "Spread": [0.0, 0.0, 0.0],
        "SwapLong": [0.0, 0.0, 0.0],
        "SwapShort": [0.0, 0.0, 0.0],
        "Vol_YZ_21": [0.15, 0.15, 0.15],
        "Z_252d": [1.0, 1.0, 1.0]
    }, index=dates)
    
    master_dates = list(dates[:2])
    c4_val_returns = pd.Series([0.0]*len(master_dates), index=master_dates)
    res = simulate_threshold_validation(
        val_dfs=[df],
        model=MockModel(),
        threshold_candidates=[0.0],
        features_list=["feature"],
        tickers=["TICKER"],
        master_dates=master_dates,
        c4_val_returns_history=c4_val_returns
    )
    assert res["valid_obs_by_threshold"][0.0] == 1

#5. Confirmar que trial_sharpes viene de Sharpes reales de validation
def test_real_validation_sharpe():
    dates = pd.date_range("2021-01-01", periods=10)
    df = pd.DataFrame({
        "Close": [100.0 + i for i in range(10)],
        "feature": [1.0] * 10,
        "Spread": [0.0] * 10,
        "SwapLong": [0.0] * 10,
        "SwapShort": [0.0] * 10,
        "Vol_YZ_21": [0.15] * 10,
        "Z_252d": [1.0] * 10
    }, index=dates)
    
    c4_val_returns = pd.Series([0.0]*len(dates), index=dates)
    res = simulate_threshold_validation(
        val_dfs=[df],
        model=MockModel(),
        threshold_candidates=[0.0],
        features_list=["feature"],
        tickers=["TICKER"],
        master_dates=list(dates),
        c4_val_returns_history=c4_val_returns
    )
    sharpe = res["results_by_threshold"][0.0]
    assert sharpe != 0.0
    retornos = pd.Series(res["val_returns_by_threshold"][0.0])
    std = retornos.std()
    expected_sharpe = (retornos.mean() / std * np.sqrt(252)) if std > 0 else 0.0
    assert np.isclose(sharpe, expected_sharpe)

#6. Confirmar que valid_obs_by_threshold se reporta por threshold
def test_valid_obs_by_threshold():
    dates = pd.date_range("2021-01-01", periods=5)
    df = pd.DataFrame({
        "Close": [100, 102, 104, 106, 108],
        "feature": [1.0] * 5,
        "Spread": [0.0] * 5,
        "SwapLong": [0.0] * 5,
        "SwapShort": [0.0] * 5,
        "Vol_YZ_21": [0.15] * 5,
        "Z_252d": [1.0] * 5
    }, index=dates)
    
    c4_val_returns = pd.Series([0.0]*len(dates), index=dates)
    res = simulate_threshold_validation(
        val_dfs=[df],
        model=MockModel(),
        threshold_candidates=[0.0, 0.001],
        features_list=["feature"],
        tickers=["TICKER"],
        master_dates=list(dates),
        c4_val_returns_history=c4_val_returns
    )
    
    assert "valid_obs_by_threshold" in res
    assert 0.0 in res["valid_obs_by_threshold"]
    assert 0.001 in res["valid_obs_by_threshold"]
    assert res["valid_obs_by_threshold"][0.0] == 4

#7. Confirmar long/short swap sign
def test_swap_pnl_direction_and_sign():
    swap_long = -2.5
    swap_short = -1.5
    
    swap_pnl_long = calcular_swap_pnl(w_prev=0.5, swap_long=swap_long, swap_short=swap_short, multiplier=1.0)
    assert swap_pnl_long < 0
    expected_long = 0.5 * swap_long / 360.0
    assert np.isclose(swap_pnl_long, expected_long)
    
    swap_pnl_short = calcular_swap_pnl(w_prev=-0.5, swap_long=swap_long, swap_short=swap_short, multiplier=1.0)
    assert swap_pnl_short < 0
    expected_short = 0.5 * swap_short / 360.0
    assert np.isclose(swap_pnl_short, expected_short)
