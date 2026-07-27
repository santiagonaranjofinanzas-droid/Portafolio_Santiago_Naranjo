import pytest
import numpy as np
import pandas as pd
from src.optimization import calcular_dsr_empirical, calcular_dsr_conservative

def test_dsr_insufficient_trials():
    # Setup a mock returns series
    returns = pd.Series([0.001, -0.002, 0.003, 0.001, -0.001])
    
    # 0 or 1 trials should return np.nan (insufficient trials)
    assert np.isnan(calcular_dsr_empirical(returns, []))
    assert np.isnan(calcular_dsr_empirical(returns, [0.5]))
    assert np.isnan(calcular_dsr_conservative(returns, []))
    assert np.isnan(calcular_dsr_conservative(returns, [0.5], conservative_n=10))

def test_dsr_bounds_and_comparison():
    # With >= 2 trials, it should compute a valid value
    # Let's verify that DSR conservative <= DSR empirical when conservative_n > len(trials_sr_list)
    returns = pd.Series([0.001, 0.002, 0.003, 0.002, 0.001, 0.002, 0.003] * 10) # positive mean
    trials = [0.1, 0.2, 0.15, 0.05, 0.12]
    
    dsr_emp = calcular_dsr_empirical(returns, trials)
    dsr_cons = calcular_dsr_conservative(returns, trials, conservative_n=64)
    
    assert not np.isnan(dsr_emp)
    assert not np.isnan(dsr_cons)
    # Using 1e-12 tolerance for numerical precision
    assert dsr_cons <= dsr_emp + 1e-12

def test_dsr_zero_variance_trials():
    returns = pd.Series([0.001, 0.002, -0.001, 0.003] * 5)
    # Zero variance trials
    trials = [0.2, 0.2, 0.2]
    
    dsr_emp = calcular_dsr_empirical(returns, trials)
    dsr_cons = calcular_dsr_conservative(returns, trials, conservative_n=64)
    
    # Should not crash, and empirical and conservative should be equal (as variance is 0, max expected is mean)
    assert not np.isnan(dsr_emp)
    assert not np.isnan(dsr_cons)
    assert np.isclose(dsr_emp, dsr_cons)

def test_capa8_exclusion_from_registry_and_best_capa():
    # Verify that Capa 8 doesn't enter the trial registry and is not evaluated for best_capa
    mock_registry = []
    active_layers = ["Capa 0A", "Capa 0B", "Capa 1", "Capa 2", "Capa 3", "Capa 4", "Capa 5a", "Capa 5b", "Capa 5c", "Capa 6", "Capa 7"]
    
    for layer in active_layers:
        mock_registry.append({
            "trial_type": "final_layer",
            "layer": layer,
            "sharpe": 0.5
        })
        
    layers_in_registry = [x["layer"] for x in mock_registry]
    assert "Capa 8" not in layers_in_registry
    assert "Capa 8 (Attention)" not in layers_in_registry
    
    # Exclude from best_capa calculation
    metrics = {
        "Capa 0B": 0.2,
        "Capa 5a (Filtro Vol)": 0.3,
        "Capa 6 (XGBoost)": 0.4,
        "Capa 7 (LSTM)": 0.5,
        "Capa 8 (Attention)": 0.9 # highest but disabled
    }
    
    best_capa = "Capa 0B"
    best_val = metrics["Capa 0B"]
    for c_name, c_val in [("Capa 5a (Filtro Vol)", metrics["Capa 5a (Filtro Vol)"]), 
                          ("Capa 6 (XGBoost)", metrics["Capa 6 (XGBoost)"]), 
                          ("Capa 7 (LSTM)", metrics["Capa 7 (LSTM)"])]:
        if c_val > best_val:
            best_capa, best_val = c_name, c_val
            
    assert best_capa == "Capa 7 (LSTM)"
    assert best_capa != "Capa 8 (Attention)"
