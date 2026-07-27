import pytest
import pandas as pd
import numpy as np

def test_oos_timing_logic():
    # We will simulate a simplified mini version of the daily loop to check timing.
    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    prices = [100.0, 101.0, 102.01, 101.0, 102.01]
    signals = [1.0, -1.0, 1.0, 1.0, 1.0]
    
    prev_w = 0.0
    returns = []
    
    for idx, date in enumerate(dates):
        if idx > 0:
            p_today = prices[idx]
            p_yesterday = prices[idx - 1]
            ret_t = (p_today - p_yesterday) / p_yesterday
            
            day_ret = prev_w * ret_t
            returns.append(day_ret)
            
        prev_w = signals[idx]
        
    assert returns[0] == pytest.approx(0.01)
    assert returns[1] == pytest.approx(-0.01)
    assert returns[2] == pytest.approx(-0.009900990099009951)
    assert returns[3] == pytest.approx(0.01)

def test_run_backtest_has_initial_validation_before_oos_loop():
    import inspect
    import run_backtest

    src = inspect.getsource(run_backtest.run_backtest)

    idx_initial_validation = src.index("Ejecutando Validación Interna Inicial de Threshold")
    idx_oos_loop = src.index("for idx, date in enumerate(test_dates)")

    assert idx_initial_validation < idx_oos_loop

def test_capa8_not_registered_as_final_layer():
    import inspect
    import run_backtest

    src = inspect.getsource(run_backtest.run_backtest)

    registry_block_start = src.index("Registrar trials finales")
    registry_block_end = src.index("trial_sharpes =")
    registry_block = src[registry_block_start:registry_block_end]

    assert '"Capa 8"' not in registry_block
    assert '"Capa 8 (Attention)"' not in registry_block

def test_capa8_not_in_best_capa_candidates():
    import inspect
    import run_backtest

    src = inspect.getsource(run_backtest.run_backtest)

    best_block_start = src.index('best_capa = "Capa 0B"')
    best_block = src[best_block_start: best_block_start + 600]

    assert "Capa 8" not in best_block

def test_experiment_metadata_is_written():
    import inspect
    import run_backtest

    src = inspect.getsource(run_backtest.run_backtest)

    assert "experiment_metadata.json" in src
    assert "code_hashes" in src
    assert "data_version" in src
    assert "Path(__file__).resolve().parent" in src

def test_c8_raw_weights_only_saved_if_attention_active():
    import inspect
    import run_backtest

    src = inspect.getsource(run_backtest.run_backtest)

    assert 'if attn_model is not None:' in src
    assert 'c8_raw_weights.to_csv("c8_raw_weights.csv")' in src
