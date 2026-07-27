import pytest
import pandas as pd
import numpy as np
from src.optimization import simulate_threshold_validation
from run_backtest import simular_capa4_retornos

class MockModel:
    def predict(self, X):
        return np.ones(len(X)) * 0.1

class FeatureEchoModel:
    def predict(self, X):
        return X[:, 0]

def test_simulate_threshold_validation_causality():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    tickers = ["Asset1", "Asset2"]
    
    val_dfs = []
    for ticker in tickers:
        df = pd.DataFrame({
            "Close": [10.0 + i * 0.1 for i in range(10)],
            "Spread": [0.01] * 10,
            "SwapLong": [-0.005] * 10,
            "SwapShort": [-0.006] * 10,
            "Vol_YZ_21": [0.15] * 10,
            "Z_252d": [1.0] * 10,
            "Z_63d": [1.0] * 10,
            "Z_21d": [1.0] * 10,
            "Z_126d": [1.0] * 10,
            "MACD_2": [1.0] * 10,
            "xi_3": [1.0] * 10,
            "target": [0.01] * 10
        }, index=dates)
        val_dfs.append(df)
        
    model = MockModel()
    threshold_candidates = [0.0, 0.0005]
    features_list = ["Z_21d", "Z_126d", "MACD_2", "xi_3"]
    
    c4_val_returns = pd.Series([0.001] * 10, index=dates)
    
    def get_swap_mult(ticker, date):
        return 1.0
        
    metrics = simulate_threshold_validation(
        val_dfs=val_dfs,
        model=model,
        threshold_candidates=threshold_candidates,
        features_list=features_list,
        tickers=tickers,
        master_dates=dates,
        c4_val_returns_history=c4_val_returns,
        get_swap_multiplier_fn=get_swap_mult,
        comm_rate=0.00005,
        slippage_rate=0.00005
    )
    
    assert "valid_obs_by_threshold" in metrics
    assert len(metrics["valid_obs_by_threshold"]) == len(threshold_candidates)
    assert metrics["valid_obs_by_threshold"][0.0] == 9
    assert metrics["best_th"] in threshold_candidates
    assert isinstance(metrics["results_by_threshold"][0.0], float)

def test_simular_capa4_retornos_dynamic_catsmom():
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    tickers = ["Asset1", "Asset2"]
    
    val_dfs = []
    for ticker in tickers:
        df = pd.DataFrame({
            "Close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "Spread": [0.0] * 5,
            "SwapLong": [0.0] * 5,
            "SwapShort": [0.0] * 5,
            "Vol_YZ_21": [0.15] * 5,
            "Z_252d": [1.0] * 5,
            "Z_63d": [1.0] * 5,
            "Z_21d": [1.0] * 5,
            "Z_126d": [1.0] * 5,
            "MACD_2": [1.0] * 5,
            "xi_3": [1.0] * 5,
            "target": [0.01] * 5
        }, index=dates)
        val_dfs.append(df)
        
    idx = pd.MultiIndex.from_product([dates, tickers], names=["Date", "Ticker"])
    rolling_corr = pd.DataFrame(1.0, index=idx, columns=tickers)
    
    rets = simular_capa4_retornos(
        val_dfs=val_dfs,
        master_dates=dates,
        tickers=tickers,
        rolling_corr=rolling_corr,
        get_swap_multiplier_fn=lambda t, d: 1.0,
        comm_rate=0.0,
        slippage_rate=0.0
    )
    
    assert isinstance(rets, pd.Series)
    assert len(rets) == 5

def test_simular_capa4_retornos_catsmom_changes_returns():
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    tickers = ["Asset1", "Asset2"]
    
    val_dfs = []
    for ticker in tickers:
        df = pd.DataFrame({
            "Close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "Spread": [0.0] * 5,
            "SwapLong": [0.0] * 5,
            "SwapShort": [0.0] * 5,
            "Vol_YZ_21": [0.15] * 5,
            "Z_252d": [1.0] * 5,
            "Z_63d": [1.0] * 5,
            "Z_21d": [1.0] * 5,
            "Z_126d": [1.0] * 5,
            "MACD_2": [1.0] * 5,
            "xi_3": [1.0] * 5,
            "target": [0.01] * 5
        }, index=dates)
        val_dfs.append(df)
        
    idx_high = pd.MultiIndex.from_product([dates, tickers], names=["Date", "Ticker"])
    rolling_corr_high = pd.DataFrame(1.0, index=idx_high, columns=tickers)
    
    rets_high = simular_capa4_retornos(
        val_dfs=val_dfs,
        master_dates=dates,
        tickers=tickers,
        rolling_corr=rolling_corr_high,
        get_swap_multiplier_fn=lambda t, d: 1.0,
        comm_rate=0.0,
        slippage_rate=0.0
    )
    
    rolling_corr_low = pd.DataFrame(-0.9, index=idx_high, columns=tickers)
    
    rets_low = simular_capa4_retornos(
        val_dfs=val_dfs,
        master_dates=dates,
        tickers=tickers,
        rolling_corr=rolling_corr_low,
        get_swap_multiplier_fn=lambda t, d: 1.0,
        comm_rate=0.0,
        slippage_rate=0.0
    )
    
    assert not rets_high.equals(rets_low)

def test_simulate_threshold_validation_causality_timing():
    dates = pd.date_range("2020-01-01", periods=4, freq="D")
    tickers = ["Asset1"]
    
    df = pd.DataFrame({
        "Close": [100.0, 101.0, 102.01, 103.03],
        "Spread": [0.0] * 4,
        "SwapLong": [0.0] * 4,
        "SwapShort": [0.0] * 4,
        "Vol_YZ_21": [0.1587] * 4, 
        "Z_252d": [1.0] * 4,
        "Z_63d": [1.0] * 4,
        "Z_21d": [1.0, -1.0, 0.0, 0.0],
        "Z_126d": [0.0] * 4,
        "MACD_2": [0.0] * 4,
        "xi_3": [0.0] * 4,
        "target": [0.0] * 4
    }, index=dates)
    
    c4_val_returns = pd.Series([0.0]*4, index=dates)
    
    res = simulate_threshold_validation(
        val_dfs=[df],
        model=FeatureEchoModel(),
        threshold_candidates=[0.0],
        features_list=["Z_21d", "Z_126d", "MACD_2", "xi_3"],
        tickers=tickers,
        master_dates=dates,
        c4_val_returns_history=c4_val_returns,
        get_swap_multiplier_fn=lambda t, d: 1.0,
        comm_rate=0.0,
        slippage_rate=0.0
    )
    
    val_rets = res["val_returns_by_threshold"][0.0]
    assert len(val_rets) == 3
    assert val_rets[0] == pytest.approx(0.002)
    assert val_rets[1] == pytest.approx(-0.002)
    assert val_rets[2] == pytest.approx(0.0)
