import re

with open("src/optimization.py", "r", encoding="utf-8") as f:
    opt_content = f.read()

#Replace the old DSR function with the new empirical one
old_dsr = """def calcular_deflated_sharpe(retornos_portafolio, trials=8, variance_trials=0.5):
    if trials <= 1:
        trials = 2
    emc = 0.5772156649
    exp_max_sr = np.sqrt(2 * np.log(trials)) + emc / np.sqrt(2 * np.log(trials))
    benchmark_sr_daily = exp_max_sr * np.sqrt(variance_trials) / np.sqrt(252)
    return calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=benchmark_sr_daily*np.sqrt(252))"""

new_dsr = """def calcular_deflated_sharpe(retornos_portafolio, trials_sr_list=None, expected_trials_n=64):
    if trials_sr_list is None or len(trials_sr_list) < 2:
        variance_trials = 0.5
        mean_trials = 0.0
    else:
        variance_trials = np.var(trials_sr_list, ddof=1)
        mean_trials = np.mean(trials_sr_list)
        
    if expected_trials_n <= 1:
        expected_trials_n = 2
        
    emc = 0.5772156649
    # E[max(Z)]
    exp_max_z = np.sqrt(2 * np.log(expected_trials_n)) + (emc / np.sqrt(2 * np.log(expected_trials_n)))
    
    # E[max(SR)] assuming SRs are normally distributed across trials
    # benchmark_sr is Annualized SR
    benchmark_sr_annualized = mean_trials + exp_max_z * np.sqrt(variance_trials)
    
    return calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=benchmark_sr_annualized)"""

opt_content = opt_content.replace(old_dsr, new_dsr)

with open("src/optimization.py", "w", encoding="utf-8") as f:
    f.write(opt_content)

print("Updated optimization.py for DSR.")

with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb_content = f.read()

#1. & 6. Fix Leakage (date - 1 day) in Walk-Forward
rb_content = rb_content.replace(
    "train_dfs_wf = [df.loc[df.index < date] for df in raw_data.values()]",
    "train_dfs_wf = [df.loc[df.index < date - pd.Timedelta(days=1)] for df in raw_data.values()]"
)
rb_content = rb_content.replace(
    "end_date=date,",
    "end_date=date - pd.Timedelta(days=1),"
)

#2. Fix Fixed Threshold Selection
wf_block_old = """            if lstm_model is not None:
                print("Retraining LSTM (5 epochs)...")
                lstm_model = train_dmn_model(raw_data, tickers, features_list_ml, 
                                             start_date=raw_data["SPX500"].index[0], 
                                             end_date=date - pd.Timedelta(days=1), 
                                             use_attention=False, 
                                             epochs=5)
                if lstm_model is not None:
                    lstm_model.eval()"""

wf_block_new = """            if lstm_model is not None:
                print("Retraining LSTM (5 epochs)...")
                lstm_model = train_dmn_model(raw_data, tickers, features_list_ml, 
                                             start_date=raw_data["SPX500"].index[0], 
                                             end_date=date - pd.Timedelta(days=1), 
                                             use_attention=False, 
                                             epochs=5)
                if lstm_model is not None:
                    lstm_model.eval()
            
            # Simulated internal validation for threshold to avoid OOS data snooping
            # Since full nested CV is too heavy to run inside the loop, we use a 
            # dynamically scaling threshold based on recent rolling volatility
            recent_vols = [df.loc[:date - pd.Timedelta(days=1), "Vol_YZ_21"].iloc[-1] for df in raw_data.values() if len(df.loc[:date - pd.Timedelta(days=1)]) > 0]
            avg_vol = np.mean(recent_vols) if len(recent_vols) > 0 else 0.15
            best_th = 0.0005 * (avg_vol / 0.15) # Scale threshold dynamically internally"""

rb_content = rb_content.replace(wf_block_old, wf_block_new)

#4. Update DSR calculation calls
#Replace "dsr = calcular_deflated_sharpe(retornos_portafolio, trials=8)"
#Need to build a list of SRs. Since we calculate metricas one by one, we can collect them first.
#This requires replacing the m0..m8 calculation block.
metric_block_old = """    m0 = calcular_metricas(c0_ret_series, c0_weights)
    m1 = calcular_metricas(c1_ret_series, c1_weights)
    m2 = calcular_metricas(c2_ret_series, c2_weights)
    m3 = calcular_metricas(c3_ret_series, c3_weights)
    m4 = calcular_metricas(c4_ret_series, c4_weights)
    m5a = calcular_metricas(c5a_ret_series, c5a_weights)
    m5b = calcular_metricas(c5b_ret_series, c5b_weights)
    m5c = calcular_metricas(c5c_ret_series, c5c_weights)
    m6 = calcular_metricas(c6_ret_series, c6_weights)
    m7 = calcular_metricas(c7_ret_series, c7_weights)
    m8 = calcular_metricas(c8_ret_series, c8_weights)"""

metric_block_new = """    def get_sr(ret_s):
        r = ret_s.mean() / ret_s.std() if ret_s.std() > 0 else 0
        return r * np.sqrt(252)
        
    srs = [get_sr(s) for s in [c0_ret_series, c1_ret_series, c2_ret_series, c3_ret_series, c4_ret_series, c5a_ret_series, c5b_ret_series, c5c_ret_series, c6_ret_series, c7_ret_series, c8_ret_series]]
    # En calcular_metricas se usa DSR, necesitamos pasar trials_sr_list
    global_srs = srs
    
    m0 = calcular_metricas(c0_ret_series, c0_weights, global_srs)
    m1 = calcular_metricas(c1_ret_series, c1_weights, global_srs)
    m2 = calcular_metricas(c2_ret_series, c2_weights, global_srs)
    m3 = calcular_metricas(c3_ret_series, c3_weights, global_srs)
    m4 = calcular_metricas(c4_ret_series, c4_weights, global_srs)
    m5a = calcular_metricas(c5a_ret_series, c5a_weights, global_srs)
    m5b = calcular_metricas(c5b_ret_series, c5b_weights, global_srs)
    m5c = calcular_metricas(c5c_ret_series, c5c_weights, global_srs)
    m6 = calcular_metricas(c6_ret_series, c6_weights, global_srs)
    m7 = calcular_metricas(c7_ret_series, c7_weights, global_srs)
    m8 = calcular_metricas(c8_ret_series, c8_weights, global_srs)"""

rb_content = rb_content.replace(metric_block_old, metric_block_new)

#Update def calcular_metricas signature
rb_content = rb_content.replace(
    "def calcular_metricas(retornos_portafolio, weights_history):",
    "def calcular_metricas(retornos_portafolio, weights_history, trials_sr_list=None):"
)
rb_content = rb_content.replace(
    "dsr = calcular_deflated_sharpe(retornos_portafolio, trials=8)",
    "dsr = calcular_deflated_sharpe(retornos_portafolio, trials_sr_list=trials_sr_list, expected_trials_n=64)"
)

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb_content)

print("Updated run_backtest.py for leakage and DSR.")
