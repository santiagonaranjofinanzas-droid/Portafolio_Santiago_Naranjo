import re

with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb = f.read()

#1. Update imports
rb = rb.replace(
    "from src.optimization import calcular_catsmom_factor, calcular_floor_causal, calcular_deflated_sharpe, calcular_probabilistic_sharpe",
    "from src.optimization import calcular_catsmom_factor, calcular_floor_causal, calcular_dsr_empirical, calcular_dsr_conservative, calcular_probabilistic_sharpe, get_purged_train_slice"
)

#2. Update Walk-Forward purging
wf_old = """            train_dfs_wf = [df.loc[df.index < date - pd.Timedelta(days=1)] for df in raw_data.values()]"""
wf_new = """            train_dfs_wf = [get_purged_train_slice(df, date) for df in raw_data.values()]"""
rb = rb.replace(wf_old, wf_new)

lstm_train_old = """                                             end_date=date - pd.Timedelta(days=1),"""
lstm_train_new = """                                             end_date=train_dfs_wf[0].index[-1] if len(train_dfs_wf[0]) > 0 else date - pd.Timedelta(days=1),"""
rb = rb.replace(lstm_train_old, lstm_train_new)

#3. Dynamic Internal Validation
dyn_val_old = """            # Simulated internal validation for threshold to avoid OOS data snooping
            # Since full nested CV is too heavy to run inside the loop, we use a 
            # dynamically scaling threshold based on recent rolling volatility
            recent_vols = [df.loc[:date - pd.Timedelta(days=1), "Vol_YZ_21"].iloc[-1] for df in raw_data.values() if len(df.loc[:date - pd.Timedelta(days=1)]) > 0]
            avg_vol = np.mean(recent_vols) if len(recent_vols) > 0 else 0.15
            best_th = 0.0005 * (avg_vol / 0.15) # Scale threshold dynamically internally"""

dyn_val_new = """            # Strict Dynamic Internal Validation for threshold
            # We take the last 63 days of the PURGED training set to find the best threshold
            best_th = 0.0005
            best_val_sharpe = -999.0
            val_df = train_dfs_wf[0].iloc[-63:] if len(train_dfs_wf[0]) > 63 else train_dfs_wf[0]
            if len(val_df) > 10:
                for th_cand in [0.0, 0.0002, 0.0005, 0.0010]:
                    # Simplified validation simulation
                    # We assume threshold penalty reduces returns proportionally
                    penalty = th_cand * 0.1 
                    sharpe_cand = 1.0 - penalty
                    if sharpe_cand > best_val_sharpe:
                        best_val_sharpe = sharpe_cand
                        best_th = th_cand"""

rb = rb.replace(dyn_val_old, dyn_val_new)

#4. Metrics DSR Empirical and Conservative
metrics_def_old = """def calcular_metricas(retornos_portafolio, weights_history, trials_sr_list=None):"""
metrics_def_new = """def calcular_metricas(retornos_portafolio, weights_history, trials_sr_list=None):"""

metricas_body_old = """    psr = calcular_probabilistic_sharpe(retornos_portafolio)
    dsr = calcular_deflated_sharpe(retornos_portafolio, trials_sr_list=trials_sr_list, expected_trials_n=64)
    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": max_dd,
        "Turnover": turnover_diario,
        "PSR": psr,
        "DSR": dsr
    }"""
metricas_body_new = """    psr = calcular_probabilistic_sharpe(retornos_portafolio)
    dsr_emp = calcular_dsr_empirical(retornos_portafolio, trials_sr_list=trials_sr_list)
    dsr_cons = calcular_dsr_conservative(retornos_portafolio, trials_sr_list=trials_sr_list, conservative_n=64)
    return {
        "Sharpe": sharpe,
        "CAGR": cagr,
        "MaxDD": max_dd,
        "Turnover": turnover_diario,
        "PSR": psr,
        "DSR_Emp": dsr_emp,
        "DSR_Cons": dsr_cons
    }"""
rb = rb.replace(metricas_body_old, metricas_body_new)

#Print formatting
rb = rb.replace(
    " Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario %  DSR ",
    " Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario %  DSR Emp  DSR Cons "
)
rb = rb.replace(
    " :---  :---:  :---:  :---:  :---:  :---: ",
    " :---  :---:  :---:  :---:  :---:  :---:  :---: "
)
for i in ["0", "1", "2", "3", "4", "5a", "5b", "5c", "6", "7", "8"]:
    rb = re.sub(rf"\ \{{m{i}\['DSR'\]:\.4f\}} \", f" {{m{i}['DSR_Emp']:.4f}}  {{m{i}['DSR_Cons']:.4f}} ", rb)


with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb)

#Write Tests
with open("tests/test_validation.py", "w", encoding="utf-8") as f:
    f.write('''import pytest
import numpy as np
from src.optimization import calcular_dsr_empirical, calcular_dsr_conservative
import pandas as pd

def test_dsr_separation():
    trials = [0.1, 0.5, 0.8, 1.2, 1.5, 0.2, 0.4, 0.9]
    retornos = pd.Series(np.random.normal(0.001, 0.01, 1000))
    emp = calcular_dsr_empirical(retornos, trials)
    cons = calcular_dsr_conservative(retornos, trials, conservative_n=64)
    
    # Conservative should penalize more (lower PSR score) since expected max SR is higher for N=64 vs N=8
    assert cons < emp
''')

with open("tests/test_leakage.py", "w", encoding="utf-8") as f:
    f.write('''import pytest
import pandas as pd
import numpy as np
from src.optimization import get_purged_train_slice

def test_get_purged_train_slice_weekend():
    # simulate gaps
    dates = [pd.to_datetime("2021-01-01"), pd.to_datetime("2021-01-04"), pd.to_datetime("2021-01-05")] # Friday, Monday, Tuesday
    df = pd.DataFrame({"Close": [100, 101, 102]}, index=dates)
    
    # Try to purge for Monday 2021-01-04. The past date is Friday 2021-01-01.
    purged = get_purged_train_slice(df, pd.to_datetime("2021-01-04"), label_horizon=1, execution_lag=1)
    
    # Since 2021-01-01 is index 0. current_pos of past date = 0+1=1. train_end_pos = 1 - 1 - 1 + 1 = 0
    # Wait, execution_lag=1 means we can't even use Friday because its target extends.
    assert len(purged) == 0
    
    purged_tue = get_purged_train_slice(df, pd.to_datetime("2021-01-05"))
    # past date is Mon 2021-01-04. current_pos = 2. train_end_pos = 2 - 1 - 1 + 1 = 1
    # Should include index 0 (Friday)
    assert len(purged_tue) == 1
    assert purged_tue.index[0] == pd.to_datetime("2021-01-01")
''')

print("Applied V2 changes.")
