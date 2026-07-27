import pandas as pd
import numpy as np

import logging

def get_purged_train_slice(df, current_date, label_horizon=1, execution_lag=1):
    if not df.index.is_monotonic_increasing:
        raise ValueError("Index must be monotonically increasing.")
    if not df.index.is_unique:
        raise ValueError("Index must be unique.")
        
    past_dates = df.index[df.index < current_date]
    if len(past_dates) == 0:
        return pd.DataFrame(columns=df.columns)
        
    if current_date not in df.index:
        logging.warning(f"current_date {current_date} not in index. Falling back to closest past date: {past_dates[-1]}")
        
    current_pos = df.index.get_loc(past_dates[-1]) + 1
    train_end_pos = current_pos - label_horizon - execution_lag + 1
    
    if train_end_pos <= 0:
        return pd.DataFrame(columns=df.columns)
        
    return df.iloc[:train_end_pos]

def calcular_catsmom_factor(signals, corr_matrix, epsilon=0.1):
    active_tickers = list(signals.keys())
    N_t = len(active_tickers)
    if N_t <= 1:
        return 1.0
        
    signed_corr_sum = 0.0
    count = 0
    
    for i in range(N_t):
        ticker_i = active_tickers[i]
        sig_i = signals[ticker_i]
        for j in range(i + 1, N_t):
            ticker_j = active_tickers[j]
            sig_j = signals[ticker_j]
            
            if ticker_i in corr_matrix.index and ticker_j in corr_matrix.columns:
                rho = corr_matrix.loc[ticker_i, ticker_j]
                if not pd.isna(rho):
                    signed_corr_sum += sig_i * sig_j * rho
                    count += 1
                    
    if count == 0:
        return 1.0
        
    rho_bar = signed_corr_sum / count
    denominator = max(1.0 + (N_t - 1) * rho_bar, 0.1)
    cf_t = np.sqrt(N_t / denominator)
    cf_t = np.clip(cf_t, 0.5, 2.0)
    
    return cf_t

def calcular_floor_causal(vols_ratio_history, date, window=252):
    if len(vols_ratio_history) <= 1:
        return 0.1
        
    history = vols_ratio_history[:-1][-window:]
    mean_val = np.mean(history)
    return 0.1 * mean_val

import scipy.stats as stats

def calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=0.0):
    mean_ret = retornos_portafolio.mean()
    std_ret = retornos_portafolio.std()
    if std_ret == 0 or len(retornos_portafolio) < 3: 
        return 0.0
    sr = mean_ret / std_ret
    skew = retornos_portafolio.skew()
    kurt = retornos_portafolio.kurtosis() + 3
    n = len(retornos_portafolio)
    
    sr_var = (1 - skew * sr + (kurt - 1) / 4 * sr**2) / (n - 1)
    if sr_var <= 0: return 0.0
    
    psr = stats.norm.cdf((sr - benchmark_sharpe / np.sqrt(252)) / np.sqrt(sr_var))
    return psr

def calcular_dsr_empirical(retornos_portafolio, trials_sr_list):
    if trials_sr_list is None or len(trials_sr_list) < 2:
        return np.nan
        
    variance_trials = np.var(trials_sr_list, ddof=1)
    mean_trials = np.mean(trials_sr_list)
    n = len(trials_sr_list)
        
    emc = 0.5772156649
    exp_max_z = np.sqrt(2 * np.log(n)) + (emc / np.sqrt(2 * np.log(n)))
    benchmark_sr_annualized = mean_trials + exp_max_z * np.sqrt(variance_trials)
    
    return calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=benchmark_sr_annualized)

def calcular_dsr_conservative(retornos_portafolio, trials_sr_list, conservative_n=64):
    if trials_sr_list is None or len(trials_sr_list) < 2:
        return np.nan
        
    variance_trials = np.var(trials_sr_list, ddof=1)
    mean_trials = np.mean(trials_sr_list)
        
    emc = 0.5772156649
    exp_max_z = np.sqrt(2 * np.log(conservative_n)) + (emc / np.sqrt(2 * np.log(conservative_n)))
    benchmark_sr_annualized = mean_trials + exp_max_z * np.sqrt(variance_trials)
    
    return calcular_probabilistic_sharpe(retornos_portafolio, benchmark_sharpe=benchmark_sr_annualized)

def calcular_costo_transaccion(curr_w, prev_w, price_yesterday, spread_yesterday, comm_rate=0.00005, slippage_rate=0.00005):
    """
    Calcula el costo de transacción de manera idéntica al OOS.
    """
    tc_rate = (spread_yesterday / (2 * price_yesterday)) + comm_rate + slippage_rate
    return abs(curr_w - prev_w) * tc_rate

def calcular_swap_pnl(w_prev, swap_long, swap_short, multiplier=1.0):
    """
    Calcula el PnL de swap (costo o crédito) de forma idéntica al OOS.
    """
    rate = swap_long if w_prev > 0 else swap_short
    swap_pnl = abs(w_prev) * rate / 360.0 * multiplier
    return swap_pnl

def signal_to_weight_fn(raw_pred, vol_diaria, swap_l, swap_s, denom_sum, scale_5a, target_vol_efectivo=0.40, max_swap_cost_annualized=0.085):
    """
    Replicación de la ruta completa de señal a peso del OOS (Capa 6).
    """
    sig = np.tanh(raw_pred)
    # Filtro dinámico de swap
    if sig > 0 and swap_l < 0 and abs(swap_l) > max_swap_cost_annualized:
        sig = 0.0
    elif sig < 0 and swap_s < 0 and abs(swap_s) > max_swap_cost_annualized:
        sig = 0.0
    
    # Sizing
    w_base = (sig / vol_diaria) * (target_vol_efectivo / denom_sum) if denom_sum > 0 else 0.0
    
    # Filtro de Volatilidad
    return scale_5a * w_base

def compute_c6_target_weights(
    dfs,
    model,
    date,
    tickers,
    features_list,
    target_vol_efectivo=0.40,
    max_swap_cost_annualized=0.085,
    scale_5a=1.0,
    vols_ratio_history=None
):
    import pandas as pd
    import numpy as np
    
    if vols_ratio_history is None:
        vols_ratio_history = []
        
    if isinstance(dfs, list):
        dfs_dict = {tickers[i]: dfs[i] for i in range(len(tickers))}
    else:
        dfs_dict = dfs
        
    # 1. Identificar activos activos hoy
    active_assets = []
    vols_diarias = {}
    swaps_l = {}
    swaps_s = {}
    raw_preds = {}
    
    for ticker in tickers:
        df = dfs_dict[ticker]
        if date in df.index and not pd.isna(df.loc[date, "Z_252d"]):
            active_assets.append(ticker)
            vol_anual = df.loc[date, "Vol_YZ_21"]
            if vol_anual <= 0 or pd.isna(vol_anual):
                vol_anual = 0.15
            vols_diarias[ticker] = vol_anual / np.sqrt(252)
            
            sw_l = df.loc[date, "SwapLong"]
            sw_s = df.loc[date, "SwapShort"]
            swaps_l[ticker] = sw_l if not pd.isna(sw_l) else 0.0
            swaps_s[ticker] = sw_s if not pd.isna(sw_s) else 0.0
            
            # Obtener predicciones crudas
            valid_features = df.loc[[date], features_list].dropna()
            if len(valid_features) > 0:
                pred = model.predict(valid_features.values)[0]
                raw_preds[ticker] = pred
            else:
                raw_preds[ticker] = 0.0
                
    # 2. Calcular señales y ratios_sum
    ratios_sum = 0.0
    signals = {}
    for ticker in active_assets:
        pred = raw_preds.get(ticker, 0.0)
        sig = np.tanh(pred)
        # Filtro de Swap
        if sig > 0 and swaps_l[ticker] < 0 and abs(swaps_l[ticker]) > max_swap_cost_annualized:
            sig = 0.0
        elif sig < 0 and swaps_s[ticker] < 0 and abs(swaps_s[ticker]) > max_swap_cost_annualized:
            sig = 0.0
        signals[ticker] = sig
        ratios_sum += abs(sig) / vols_diarias[ticker]
        
    # 3. Actualizar vols_ratio_history y obtener denom_sum
    vols_ratio_history.append(ratios_sum)
    delta_min = calcular_floor_causal(vols_ratio_history, date)
    denom_sum = max(ratios_sum, delta_min)
    
    # 4. Calcular pesos objetivo
    target_weights = {}
    for ticker in tickers:
        if ticker in active_assets:
            pred = raw_preds.get(ticker, 0.0)
            target_weights[ticker] = signal_to_weight_fn(
                raw_pred=pred,
                vol_diaria=vols_diarias[ticker],
                swap_l=swaps_l[ticker],
                swap_s=swaps_s[ticker],
                denom_sum=denom_sum,
                scale_5a=scale_5a,
                target_vol_efectivo=target_vol_efectivo,
                max_swap_cost_annualized=max_swap_cost_annualized
            )
        else:
            target_weights[ticker] = 0.0
            
    return target_weights, signals, ratios_sum, denom_sum, active_assets

def simulate_threshold_validation(val_dfs, model, threshold_candidates, features_list, tickers, master_dates, c4_val_returns_history, get_swap_multiplier_fn=None, comm_rate=0.00005, slippage_rate=0.00005):
    """
    Simulación fiel de Out-of-Sample (OOS) a escala reducida sobre el set de validación
    para seleccionar el umbral de histéresis (threshold_candidates).
    
    Nota: La validación se realiza para la capa XGBoost (Capa 6), ya que el stack
    completo hasta la Capa 8 de Attention está desmantelado o requiere el universo completo.
    """
    import pandas as pd
    import numpy as np
    from src.models.markov import estimar_regimen_volatilidad
    
    all_dates = master_dates
    best_th = threshold_candidates[0]
    best_val_sharpe = -999.0
    results_by_threshold = {}
    val_returns_by_threshold = {}
    turnover_by_threshold = {}
    costs_by_threshold = {}
    valid_obs_by_threshold = {}
    
    # Asegurarse de que c4_val_returns_history sea una serie pandas
    if not isinstance(c4_val_returns_history, pd.Series):
        c4_val_returns_history = pd.Series(c4_val_returns_history, index=all_dates)
        
    for th_cand in threshold_candidates:
        val_returns = []
        total_turnover = 0.0
        total_costs = 0.0
        
        # Pesos históricos de simulación
        prev_w = {t: 0.0 for t in tickers}
        prev_w_prev = {t: 0.0 for t in tickers}
        
        # Causal tracking tables
        val_vols_ratio_history = []
        
        for v_idx, v_date in enumerate(all_dates):
            day_ret = 0.0
            has_trade = False
            
            # --- FASE 1: APLICACIÓN DE PESOS (T-1) AL RETORNO (T) ---
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
                        
                        # Costos de Transacción Exactos del OOS
                        tc_cost = calcular_costo_transaccion(
                            curr_w=w_prev,
                            prev_w=w_prev_prev,
                            price_yesterday=p_yesterday,
                            spread_yesterday=df_v.loc[prev_date, "Spread"],
                            comm_rate=comm_rate,
                            slippage_rate=slippage_rate
                        )
                        
                        # Swap PnL Exacto del OOS (MT5 convention)
                        swap_pnl = 0.0
                        if w_prev != 0 and "SwapLong" in df_v.columns:
                            m_mult = get_swap_multiplier_fn(ticker, prev_date) if get_swap_multiplier_fn else 1.0
                            swap_pnl = calcular_swap_pnl(
                                w_prev=w_prev,
                                swap_long=df_v.loc[prev_date, "SwapLong"],
                                swap_short=df_v.loc[prev_date, "SwapShort"],
                                multiplier=m_mult
                            )
                        
                        day_ret += (w_prev * asset_ret - tc_cost + swap_pnl)
                        total_costs += (tc_cost - swap_pnl)
                        has_trade = True
            
            if has_trade:
                val_returns.append(day_ret)
                
            # --- FASE 2: GENERACIÓN DE NUEVAS SEÑALES PARA (T+1) ---
            # Get Capa 4 returns history up to prev_date (causally)
            if v_idx == 0:
                c4_hist_up_to_today = []
            else:
                prev_date = all_dates[v_idx - 1]
                c4_hist_up_to_today = c4_val_returns_history.loc[:prev_date].tolist()
                
            vol_crisis_factor = estimar_regimen_volatilidad(c4_hist_up_to_today, window=63, threshold_pct=0.8)
            scale_5a = 1.0 - vol_crisis_factor
            
            target_weights, _, _, _, active_today = compute_c6_target_weights(
                dfs=val_dfs,
                model=model,
                date=v_date,
                tickers=tickers,
                features_list=features_list,
                target_vol_efectivo=0.40,
                max_swap_cost_annualized=0.085,
                scale_5a=scale_5a,
                vols_ratio_history=val_vols_ratio_history
            )
            
            # Asignación de pesos y aplicación de histéresis
            for ticker in tickers:
                if ticker in active_today:
                    proposed_w = target_weights[ticker]
                    
                    # Histéresis
                    if abs(proposed_w - prev_w[ticker]) < th_cand:
                        curr_w = prev_w[ticker]
                    else:
                        curr_w = proposed_w
                        total_turnover += abs(curr_w - prev_w[ticker])
                        
                    prev_w_prev[ticker] = prev_w[ticker]
                    prev_w[ticker] = curr_w
                else:
                    prev_w_prev[ticker] = prev_w[ticker]
                    prev_w[ticker] = 0.0
                    
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
        valid_obs_by_threshold[th_cand] = len(val_returns)
        
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
        "valid_obs_by_threshold": valid_obs_by_threshold
    }
