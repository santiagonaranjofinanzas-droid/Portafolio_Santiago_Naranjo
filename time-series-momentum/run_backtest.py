import os
import pandas as pd
import numpy as np
import torch
import random
import json
from pathlib import Path
from datetime import datetime
from src.features import generar_features_tensor
from src.optimization import (
    calcular_catsmom_factor, 
    calcular_floor_causal, 
    calcular_dsr_empirical, 
    calcular_dsr_conservative, 
    calcular_probabilistic_sharpe, 
    get_purged_train_slice, 
    simulate_threshold_validation,
    calcular_costo_transaccion,
    calcular_swap_pnl,
    signal_to_weight_fn,
    compute_c6_target_weights
)
from src.models.markov import estimar_regimen_volatilidad, estimar_regimen_hmm, estimar_regimen_msssm
from src.models.classical import entrenar_xgboost
from src.models.dmn import train_dmn_model, DeepMomentumNetwork

#Categorías de activos para la aplicación de swaps triples
FX_TICKERS = ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"]
INDEX_TICKERS = ["SPX500", "NAS100", "DJI30", "GER30", "EU50", "UK100", "JPN225"]
COMMODITY_TICKERS = ["XAUUSD", "XAGUSD", "Cobre", "Brent", "WTI", "GasNatural", "Cafe", "Azucar", "Trigo", "Maiz", "Soja"]
BOND_TICKERS = ["US10Y", "BUND"]

def get_swap_multiplier(ticker, date):
    """
    Devuelve el multiplicador de swap overnight (triple swap) según la categoría del activo y el día de la semana.
    """
    day = date.dayofweek
    if ticker in FX_TICKERS:
        return 3.0 if day == 2 else 1.0
    elif ticker in INDEX_TICKERS:
        return 3.0 if day == 4 else 1.0
    else:
        return 1.0

def get_file_md5(filepath):
    import hashlib
    if not os.path.exists(filepath):
        return "NOT_FOUND"
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def fmt_val(v, fmt="{:.4f}", na_val="N/A"):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return na_val
    if isinstance(v, str):
        return v
    return fmt.format(v)

def calcular_metricas(retornos_portafolio, weights_history, trials_sr_list=None):
    """
    Calcula las métricas de rendimiento: Sharpe Ratio anualizado, CAGR, Max Drawdown y Turnover.
    """
    mean_ret = retornos_portafolio.mean()
    std_ret = retornos_portafolio.std()
    
    if std_ret > 0:
        sharpe = (mean_ret / std_ret) * np.sqrt(252)
    else:
        sharpe = 0.0
        
    cum_returns = (1 + retornos_portafolio).cumprod()
    total_ret = cum_returns.iloc[-1] if len(cum_returns) > 0 else 1.0
    n_days = len(retornos_portafolio)
    years = n_days / 252.0
    cagr = (total_ret ** (1 / years) - 1) if years > 0 and total_ret > 0 else 0.0
    
    running_max = cum_returns.cummax()
    drawdowns = (cum_returns - running_max) / running_max
    max_dd = drawdowns.min()
    
    turnover_diario = weights_history.diff().abs().sum(axis=1).mean()
    
    psr = calcular_probabilistic_sharpe(retornos_portafolio)
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
    }

def simular_capa4_retornos(val_dfs, master_dates, tickers, rolling_corr, get_swap_multiplier_fn, comm_rate=0.00005, slippage_rate=0.00005):
    """
    Simula de forma causal el rendimiento de la Capa 4 (CATSMOM) sobre las fechas dadas.
    Retorna una Serie de pandas con los retornos diarios de Capa 4 indexados por master_dates.
    """
    import pandas as pd
    import numpy as np
    
    if isinstance(val_dfs, list):
        dfs_dict = {tickers[i]: val_dfs[i] for i in range(len(tickers))}
    else:
        dfs_dict = val_dfs
        
    val_returns = []
    # Pesos históricos
    prev_w = {t: 0.0 for t in tickers}
    prev_w_prev = {t: 0.0 for t in tickers}
    
    # Rastrear vols ratio history para delta_min
    vols_ratio_history = []
    
    for v_idx, v_date in enumerate(master_dates):
        day_ret = 0.0
        has_trade = False
        
        # --- FASE 1: RETORNO DIARIO DE T-1 A T ---
        if v_idx > 0:
            prev_date = master_dates[v_idx - 1]
            for ticker in tickers:
                df = dfs_dict[ticker]
                if v_date in df.index and prev_date in df.index:
                    p_today = df.loc[v_date, "Close"]
                    p_yesterday = df.loc[prev_date, "Close"]
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    
                    w_prev = prev_w[ticker]
                    w_prev_prev = prev_w_prev[ticker]
                    
                    tc_cost = calcular_costo_transaccion(w_prev, w_prev_prev, p_yesterday, df.loc[prev_date, "Spread"], comm_rate, slippage_rate)
                    
                    swap_pnl = 0.0
                    if w_prev != 0 and "SwapLong" in df.columns:
                        m_mult = get_swap_multiplier_fn(ticker, prev_date) if get_swap_multiplier_fn else 1.0
                        swap_pnl = calcular_swap_pnl(w_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                        
                    day_ret += (w_prev * asset_ret - tc_cost + swap_pnl)
                    has_trade = True
                    
        val_returns.append(day_ret if has_trade else 0.0)
        
        # --- FASE 2: SEÑALES Y PESOS PARA T+1 ---
        active_today = []
        vols_diarias = {}
        swaps_l = {}
        swaps_s = {}
        for ticker in tickers:
            df = dfs_dict[ticker]
            if v_date in df.index and not pd.isna(df.loc[v_date, "Z_252d"]):
                active_today.append(ticker)
                vol_anual = df.loc[v_date, "Vol_YZ_21"]
                if vol_anual <= 0 or pd.isna(vol_anual):
                    vol_anual = 0.15
                vols_diarias[ticker] = vol_anual / np.sqrt(252)
                swaps_l[ticker] = df.loc[v_date, "SwapLong"] if not pd.isna(df.loc[v_date, "SwapLong"]) else 0.0
                swaps_s[ticker] = df.loc[v_date, "SwapShort"] if not pd.isna(df.loc[v_date, "SwapShort"]) else 0.0
                
        signals_c1 = {}
        ratios_sum = 0.0
        for ticker in active_today:
            df = dfs_dict[ticker]
            z21 = df.loc[v_date, "Z_21d"] if not pd.isna(df.loc[v_date, "Z_21d"]) else 0.0
            z63 = df.loc[v_date, "Z_63d"] if not pd.isna(df.loc[v_date, "Z_63d"]) else 0.0
            z126 = df.loc[v_date, "Z_126d"] if not pd.isna(df.loc[v_date, "Z_126d"]) else 0.0
            z252 = df.loc[v_date, "Z_252d"] if not pd.isna(df.loc[v_date, "Z_252d"]) else 0.0
            
            s_i = 0.1 * z21 + 0.2 * z63 + 0.3 * z126 + 0.4 * z252
            sig_c1 = np.tanh(s_i)
            # Filtro de Swap
            if sig_c1 > 0 and swaps_l[ticker] < 0 and abs(swaps_l[ticker]) > 0.085:
                sig_c1 = 0.0
            elif sig_c1 < 0 and swaps_s[ticker] < 0 and abs(swaps_s[ticker]) > 0.085:
                sig_c1 = 0.0
                
            signals_c1[ticker] = sig_c1
            ratios_sum += abs(sig_c1) / vols_diarias[ticker]
            
        vols_ratio_history.append(ratios_sum)
        delta_min = calcular_floor_causal(vols_ratio_history, v_date)
        denom_sum = max(ratios_sum, delta_min)
        
        corr_matrix_today = pd.DataFrame()
        if v_date in rolling_corr.index.levels[0]:
            corr_matrix_today = rolling_corr.loc[v_date]
            
        cf_t = calcular_catsmom_factor(signals_c1, corr_matrix_today)
        
        for ticker in tickers:
            if ticker in active_today:
                sig = signals_c1[ticker]
                vol_d = vols_diarias[ticker]
                w3 = (sig / vol_d) * (0.40 / denom_sum) if denom_sum > 0 else 0.0
                w4 = cf_t * w3
                
                proposed_w = w4
                if abs(proposed_w - prev_w[ticker]) < 0.0150:
                    curr_w = prev_w[ticker]
                else:
                    curr_w = proposed_w
                prev_w_prev[ticker] = prev_w[ticker]
                prev_w[ticker] = curr_w
            else:
                prev_w_prev[ticker] = prev_w[ticker]
                prev_w[ticker] = 0.0
                
    return pd.Series(val_returns, index=master_dates)

def run_backtest(data_dir="data", force_retrain=True):
    SEED = 42
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
        
    trial_registry = []
    validation_logs = []
    
    # Parámetros del backtest
    target_vol = 0.40
    phi = 1.0
    target_vol_efectivo = phi * target_vol  # 40.0%
    comm_rate = 0.00005
    slippage_rate = 0.00005
    L = 63  # sequence length
    max_swap_cost_annualized = 0.085  # 8.5% coste anual de swap overnight límite
    rebalance_threshold = 0.0150  # 150 bps
    
    print("Cargando datos y generando características para todos los activos...")
    raw_data = {}
    tickers = [f.replace(".csv", "") for f in os.listdir(data_dir) if f.endswith(".csv")]
    
    returns_dict = {}
    features_list_ml = [
        "Z_21d", "Z_126d", "MACD_2", "xi_3"
    ]
    
    for ticker in tickers:
        csv_path = os.path.join(data_dir, f"{ticker}.csv")
        df = pd.read_csv(csv_path)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        
        df, _ = generar_features_tensor(df)
        
        # Calcular target variable para Capa 6 y 7
        close_pos = df["Close"].where(df["Close"] > 0)
        log_ret_1d = np.log(close_pos / close_pos.shift(1))
        df["target"] = log_ret_1d.shift(-1) / (df["Vol_YZ_21"] / np.sqrt(252))
        
        cols_needed = ["Date", "Close", "Open", "Spread", "SwapLong", "SwapShort", 
                       "Vol_YZ_21", "Z_252d", "Z_63d", "target"] + features_list_ml
        df = df[cols_needed].copy()
        
        df_ret = df["Close"].pct_change(fill_method=None)
        returns_dict[ticker] = pd.Series(df_ret.values, index=df["Date"])
        
        df = df.set_index("Date")
        raw_data[ticker] = df
        
    print("Calculando matrices de correlación condicional rodante (63 días)...")
    returns_df = pd.DataFrame(returns_dict).sort_index()
    rolling_corr = returns_df.rolling(window=63, min_periods=30).corr()
    
    # Extraer retornos del proxy (SPX500) para el HMM
    spx_returns = returns_df["SPX500"].fillna(0.0)
    
    split_date = pd.to_datetime("2021-06-03")
    
    print("\n" + "="*60)
    print("   ENTRENAMIENTO CAUSAL DE MODELOS DE ML Y DEEP LEARNING")
    print("="*60)
    
    # 1. Entrenar XGBoost en el set de entrenamiento inicial
    print("Entrenando modelo XGBoost inicial...")
    train_dfs = [get_purged_train_slice(df, split_date) for df in raw_data.values()]
    xgb_model = entrenar_xgboost(train_dfs, features_list_ml, max_depth=2, random_state=SEED)
    
    # --- VALIDACIÓN INTERNA INICIAL DE THRESHOLD ANTES DE INICIAR OOS ---
    print("\n--- Ejecutando Validación Interna Inicial de Threshold (XGBoost) ---")
    master_train_dates = sorted(list(set().union(*[df.index for df in train_dfs])))
    val_split_idx = int(len(master_train_dates) * 0.8)
    train_sub_dates = master_train_dates[:val_split_idx]
    val_sub_dates = master_train_dates[val_split_idx:]
    
    first_val_date = val_sub_dates[0]
    train_sub = [get_purged_train_slice(df, first_val_date) for df in train_dfs]
    val_sub = [df.loc[df.index >= first_val_date] for df in train_dfs]
    
    xgb_temp = entrenar_xgboost(train_sub, features_list_ml, max_depth=2, random_state=SEED)
    
    # Precomputar retornos de Capa 4 en todo master_train_dates usando catsmom factor dinámico
    c4_train_returns_full = simular_capa4_retornos(
        val_dfs=train_dfs,
        master_dates=master_train_dates,
        tickers=tickers,
        rolling_corr=rolling_corr,
        get_swap_multiplier_fn=get_swap_multiplier,
        comm_rate=comm_rate,
        slippage_rate=slippage_rate
    )
    
    threshold_candidates = [0.0, 0.0002, 0.0005, 0.0010]
    val_metrics = simulate_threshold_validation(
        val_dfs=val_sub,
        model=xgb_temp,
        threshold_candidates=threshold_candidates,
        features_list=features_list_ml,
        tickers=tickers,
        master_dates=val_sub_dates,
        c4_val_returns_history=c4_train_returns_full,
        get_swap_multiplier_fn=get_swap_multiplier,
        comm_rate=comm_rate,
        slippage_rate=slippage_rate
    )
    
    best_th = val_metrics["best_th"]
    best_val_sharpe = val_metrics["best_val_sharpe"]
    
    # Registrar en trial_registry y validation_logs
    for th_cand, val_sharpe in val_metrics["results_by_threshold"].items():
        trial_registry.append({
            "trial_type": "threshold_validation",
            "date": split_date.strftime('%Y-%m-%d'),
            "layer": "Capa 6",
            "threshold": th_cand,
            "sharpe": val_sharpe,
            "window_start": val_sub_dates[0].strftime('%Y-%m-%d'),
            "window_end": val_sub_dates[-1].strftime('%Y-%m-%d'),
            "n_obs": val_metrics["valid_obs_by_threshold"][th_cand]
        })
        
    validation_logs.append({
        "date": split_date.strftime('%Y-%m-%d'),
        "train_sub_len": len(train_sub_dates),
        "val_sub_len": len(val_sub_dates),
        "best_th": best_th,
        "val_sharpe": best_val_sharpe,
        "valid_obs_by_threshold": val_metrics["valid_obs_by_threshold"]
    })
    
    print(f"Seleccionado best_th inicial: {best_th} con Sharpe de validación de {best_val_sharpe:.4f}")
    
    # Paths para guardar modelos y evitar reentrenamiento
    lstm_path = "lstm_model_dynamic.pt"
    
    # 2. Cargar o entrenar LSTM (Capa 7)
    safe_end_date_initial = min(df.index[-1] for df in train_dfs if len(df) > 0)
    if os.path.exists(lstm_path) and not force_retrain:
        print("Cargando modelo LSTM preentrenado...")
        lstm_model = DeepMomentumNetwork(input_dim=1, num_features=len(features_list_ml), hidden_dim=64, use_attention=False)
        lstm_model.load_state_dict(torch.load(lstm_path))
        lstm_model.eval()
    else:
        print("\nEntrenando modelo LSTM (Capa 7) en PyTorch...")
        lstm_model = train_dmn_model(raw_data, tickers, features_list_ml, 
                                     start_date=raw_data["SPX500"].index[0], 
                                     end_date=safe_end_date_initial, 
                                     use_attention=False, 
                                     epochs=30)
        if lstm_model is not None:
            torch.save(lstm_model.state_dict(), lstm_path)
            
    # 3. Cargar o entrenar Attention (Capa 8) - DESMANTELADO EN v0.9.6
    print("Capa 8 (Attention) ha sido desmantelada estructuralmente.")
    attn_model = None
    
    # Filtrar fechas para la simulación OOS (deben ser posteriores al split de entrenamiento)
    all_dates = sorted(list(set().union(*[df.index for df in raw_data.values()])))
    test_dates = [d for d in all_dates if d > split_date]
    
    print("\n" + "="*60)
    print(f"   SIMULACIÓN OUT-OF-SAMPLE (OOS): {test_dates[0].strftime('%Y-%m-%d')} A {test_dates[-1].strftime('%Y-%m-%d')}")
    print("="*60)
    
    # DataFrames de pesos
    c0a_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c0b_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c1_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c2_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c3_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c4_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c5a_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c5b_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c5c_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c6_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c7_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c8_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c8_raw_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    
    # Retornos diarios
    c0a_returns, c0b_returns = [], []
    c1_returns, c2_returns, c3_returns = [], [], []
    c4_returns, c5a_returns = [], []
    c5b_returns, c5c_returns, c6_returns = [], [], []
    c7_returns, c8_returns = [], []
    
    # Históricos para volatilidad realizada y floor causal
    vols_ratio_history = []
    c4_returns_history = []
    
    c6_vols_ratio_history = []
    c7_vols_ratio_history = []
    c8_vols_ratio_history = []
    
    # Pesos previos
    c0a_prev_w = {t: 0.0 for t in tickers}
    c0b_prev_w = {t: 0.0 for t in tickers}
    c1_prev_w = {t: 0.0 for t in tickers}
    c2_prev_w = {t: 0.0 for t in tickers}
    c3_prev_w = {t: 0.0 for t in tickers}
    c4_prev_w = {t: 0.0 for t in tickers}
    c5a_prev_w = {t: 0.0 for t in tickers}
    c5b_prev_w = {t: 0.0 for t in tickers}
    c5c_prev_w = {t: 0.0 for t in tickers}
    c6_prev_w = {t: 0.0 for t in tickers}
    c7_prev_w = {t: 0.0 for t in tickers}
    c8_prev_w = {t: 0.0 for t in tickers}
    
    # Bucle diario Out-of-Sample
    for idx, date in enumerate(test_dates):
        # --- WALK FORWARD VALIDATION (Retrain every year = ~252 days) ---
        if idx > 0 and idx % 252 == 0:
            print(f"\n--- Retraining Models (Walk-Forward) at {date.strftime('%Y-%m-%d')} ---")
            train_dfs_wf = [get_purged_train_slice(df, date) for df in raw_data.values()]
            
            if len(train_dfs_wf[0]) > 252:
                # 1. Split master calendar 80/20 to avoid single-asset calendar bias
                master_train_dates = sorted(list(set().union(*[df.index for df in train_dfs_wf])))
                val_split_idx = int(len(master_train_dates) * 0.8)
                train_sub_dates = master_train_dates[:val_split_idx]
                val_sub_dates = master_train_dates[val_split_idx:]
                
                # Purgar la frontera train_sub -> val_sub
                first_val_date = val_sub_dates[0]
                train_sub = [get_purged_train_slice(df, first_val_date) for df in train_dfs_wf]
                val_sub = [df.loc[df.index >= first_val_date] for df in train_dfs_wf]
                
                # 2. Train temporary models on train_sub
                xgb_temp = entrenar_xgboost(train_sub, features_list_ml, max_depth=2, random_state=SEED)
                
                # Precomputar retornos de Capa 4 en todo master_train_dates con catsmom dinámico
                c4_train_returns_wf = simular_capa4_retornos(
                    val_dfs=train_dfs_wf,
                    master_dates=master_train_dates,
                    tickers=tickers,
                    rolling_corr=rolling_corr,
                    get_swap_multiplier_fn=get_swap_multiplier,
                    comm_rate=comm_rate,
                    slippage_rate=slippage_rate
                )
                
                # 3. Validation simulation for threshold
                val_metrics = simulate_threshold_validation(
                    val_dfs=val_sub,
                    model=xgb_temp,
                    threshold_candidates=threshold_candidates,
                    features_list=features_list_ml,
                    tickers=tickers,
                    master_dates=val_sub_dates,
                    c4_val_returns_history=c4_train_returns_wf,
                    get_swap_multiplier_fn=get_swap_multiplier,
                    comm_rate=comm_rate,
                    slippage_rate=slippage_rate
                )
                best_th = val_metrics["best_th"]
                best_val_sharpe = val_metrics["best_val_sharpe"]
                
                for th_cand, val_sharpe in val_metrics["results_by_threshold"].items():
                    trial_registry.append({
                        "trial_type": "threshold_validation",
                        "date": date.strftime('%Y-%m-%d'),
                        "layer": "Capa 6",
                        "threshold": th_cand,
                        "sharpe": val_sharpe,
                        "window_start": val_sub_dates[0].strftime('%Y-%m-%d'),
                        "window_end": val_sub_dates[-1].strftime('%Y-%m-%d'),
                        "n_obs": val_metrics["valid_obs_by_threshold"][th_cand]
                    })
                
                validation_logs.append({
                    "date": date.strftime('%Y-%m-%d'),
                    "train_sub_len": len(train_sub_dates),
                    "val_sub_len": len(val_sub_dates),
                    "best_th": best_th,
                    "val_sharpe": best_val_sharpe,
                    "valid_obs_by_threshold": val_metrics["valid_obs_by_threshold"]
                })
                
                # 4. Retrain final models on full train_purged
                xgb_model = entrenar_xgboost(train_dfs_wf, features_list_ml, max_depth=2, random_state=SEED)
                safe_end_date_wf = min(df.index[-1] for df in train_dfs_wf if len(df) > 0)
                if lstm_model is not None:
                    print("Retraining LSTM (5 epochs)...")
                    lstm_model = train_dmn_model(raw_data, tickers, features_list_ml, 
                                                 start_date=raw_data["SPX500"].index[0], 
                                                 end_date=safe_end_date_wf, 
                                                 use_attention=False, 
                                                 epochs=5)
                    lstm_model.eval()
            else:
                xgb_model = entrenar_xgboost(train_dfs_wf, features_list_ml, max_depth=2, random_state=SEED)
                
        # ----------------------------------------------------------------
        # Calcular prob_crisis_msssm al inicio para Fuzzy Gating
        prob_crisis_msssm = estimar_regimen_msssm(raw_data, tickers, date)
        L_t = 126
        
        # 1. Identificar activos activos hoy con historia suficiente para secuencia LSTM (L_t)
        active_assets = []
        for ticker in tickers:
            df = raw_data[ticker]
            if date in df.index and not pd.isna(df.loc[date, "Z_252d"]):
                date_idx = df.index.get_loc(date)
                if date_idx >= L_t - 1:
                    active_assets.append(ticker)
                    
        N_t = len(active_assets)
        if N_t == 0:
            for r_list in [c0a_returns, c0b_returns, c1_returns, c2_returns, c3_returns, c4_returns, 
                           c5a_returns, c5b_returns, c5c_returns, c6_returns, c7_returns, c8_returns]:
                r_list.append(0.0)
            c4_returns_history.append(0.0)
            continue
            
        # 2. Calcular señales y pesos
        c0a_curr_w = {}
        c0b_curr_w = {}
        c1_curr_w = {}
        c2_curr_w = {}
        c3_curr_w = {}
        c4_curr_w = {}
        c5a_curr_w = {}
        c5b_curr_w = {}
        c5c_curr_w = {}
        c6_curr_w = {}
        c7_curr_w = {}
        c8_curr_w = {}
        
        signals_c1 = {}
        signals_c7 = {}
        signals_c8 = {}
        vols_diarias = {}
        swaps_l_dict = {}
        swaps_s_dict = {}
        
        ratios_sum = 0.0
        c7_ratios_sum = 0.0
        c8_ratios_sum = 0.0
        
        # Filtro de Volatilidad Causal (Capa 5a)
        vol_crisis_factor = estimar_regimen_volatilidad(c4_returns_history, window=63, threshold_pct=0.8)
        scale_5a = 1.0 - vol_crisis_factor
        
        # Sizing común de Capa 6 (XGBoost)
        c6_target_w_dict, signals_c6, _, _, _ = compute_c6_target_weights(
            dfs=raw_data,
            model=xgb_model,
            date=date,
            tickers=tickers,
            features_list=features_list_ml,
            target_vol_efectivo=target_vol_efectivo,
            max_swap_cost_annualized=max_swap_cost_annualized,
            scale_5a=scale_5a,
            vols_ratio_history=c6_vols_ratio_history
        )
        
        for ticker in active_assets:
            df = raw_data[ticker]
            vol_anual = df.loc[date, "Vol_YZ_21"]
            if vol_anual <= 0 or pd.isna(vol_anual):
                vol_anual = 0.15
            vol_diaria = vol_anual / np.sqrt(252)
            vols_diarias[ticker] = vol_diaria
            
            # Obtener swaps diarios para filtrar dinámicamente posiciones caras
            swap_l = df.loc[date, "SwapLong"]
            swap_s = df.loc[date, "SwapShort"]
            swap_l = swap_l if not pd.isna(swap_l) else 0.0
            swap_s = swap_s if not pd.isna(swap_s) else 0.0
            swaps_l_dict[ticker] = swap_l
            swaps_s_dict[ticker] = swap_s

            # Capas 0A y 0B
            z252 = df.loc[date, "Z_252d"]
            sig_c0 = np.sign(z252) if not pd.isna(z252) else 0.0
            c0_w = (target_vol / vol_anual) * sig_c0 * (1.0 / N_t) if N_t > 0 else 0.0
            c0a_curr_w[ticker] = c0_w
            c0b_curr_w[ticker] = c0_w
            
            # Capa 1
            z21 = df.loc[date, "Z_21d"]
            z63 = df.loc[date, "Z_63d"]
            z126 = df.loc[date, "Z_126d"]
            
            z21 = z21 if not pd.isna(z21) else 0.0
            z63 = z63 if not pd.isna(z63) else 0.0
            z126 = z126 if not pd.isna(z126) else 0.0
            z252_val = z252 if not pd.isna(z252) else 0.0
            
            s_i = 0.1 * z21 + 0.2 * z63 + 0.3 * z126 + 0.4 * z252_val
            sig_c1 = np.tanh(s_i)
            if sig_c1 > 0 and swap_l < 0 and abs(swap_l) > max_swap_cost_annualized:
                sig_c1 = 0.0
            elif sig_c1 < 0 and swap_s < 0 and abs(swap_s) > max_swap_cost_annualized:
                sig_c1 = 0.0
            signals_c1[ticker] = sig_c1
            
            c1_curr_w[ticker] = (target_vol / vol_anual) * sig_c1 * (1.0 / N_t) if N_t > 0 else 0.0
            ratios_sum += abs(sig_c1) / vol_diaria
            
            # Capa 7 (LSTM)
            sig_c7 = 0.0
            if lstm_model is not None:
                date_idx = df.index.get_loc(date)
                seq = df.iloc[date_idx - L_t + 1 : date_idx + 1][features_list_ml].values
                seq = np.nan_to_num(seq)
                # Fuzzy Gating
                L_seq = seq.shape[0]
                decay_len = L_seq - 21
                w_decay = np.ones((L_seq, 1))
                w_decay[:decay_len, 0] = (1.0 - prob_crisis_msssm) + prob_crisis_msssm * np.arange(decay_len) / decay_len
                seq = seq * w_decay
                t_seq = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    pred_lstm = lstm_model(t_seq).item()
                if abs(pred_lstm) < 0.25:
                    sig_c7 = 0.0
                else:
                    sig_c7 = pred_lstm
                if sig_c7 > 0 and swap_l < 0 and abs(swap_l) > max_swap_cost_annualized:
                    sig_c7 = 0.0
                elif sig_c7 < 0 and swap_s < 0 and abs(swap_s) > max_swap_cost_annualized:
                    sig_c7 = 0.0
            signals_c7[ticker] = sig_c7
            c7_ratios_sum += abs(sig_c7) / vol_diaria
            
            # Capa 8 (Attention) - DESACTIVADA
            sig_c8 = 0.0
            signals_c8[ticker] = sig_c8
            c8_ratios_sum += abs(sig_c8) / vol_diaria
            
        vols_ratio_history.append(ratios_sum)
        delta_min = calcular_floor_causal(vols_ratio_history, date)
        
        c7_vols_ratio_history.append(c7_ratios_sum)
        c7_delta_min = calcular_floor_causal(c7_vols_ratio_history, date)
        
        c8_vols_ratio_history.append(c8_ratios_sum)
        c8_delta_min = calcular_floor_causal(c8_vols_ratio_history, date)
        
        corr_matrix_today = pd.DataFrame()
        if date in rolling_corr.index.levels[0]:
            corr_matrix_today = rolling_corr.loc[date]
            
        cf_t = calcular_catsmom_factor(signals_c1, corr_matrix_today)
        
        denom_sum = max(ratios_sum, delta_min)
        c7_denom_sum = max(c7_ratios_sum, c7_delta_min)
        c8_denom_sum = max(c8_ratios_sum, c8_delta_min)
        
        # HMM
        spx_returns_hist = spx_returns.loc[:date].values
        prob_crisis_hmm = estimar_regimen_hmm(spx_returns_hist, window=500)
        scale_5b = 1.0 - prob_crisis_hmm
        
        # MS-SSSM
        prob_crisis_msssm = estimar_regimen_msssm(raw_data, tickers, date)
        scale_5c = 1.0 - prob_crisis_msssm
        
        # Sizing final
        for ticker in active_assets:
            sig = signals_c1[ticker]
            sig_c7 = signals_c7[ticker]
            sig_c8 = signals_c8[ticker]
            vol_d = vols_diarias[ticker]
            
            # Capa 3
            w3 = (sig / vol_d) * (target_vol_efectivo / denom_sum) if denom_sum > 0 else 0.0
            c3_curr_w[ticker] = w3
            
            # Capa 4
            w4 = cf_t * w3
            c4_curr_w[ticker] = w4
            
            # Capas 5
            c5a_curr_w[ticker] = scale_5a * w4
            c5b_curr_w[ticker] = scale_5b * w4
            c5c_curr_w[ticker] = scale_5c * w4
            
            # Capa 6 (XGBoost Neto con Filtro de Vol)
            c6_curr_w[ticker] = c6_target_w_dict.get(ticker, 0.0)
            
            # Capa 7 (LSTM Neto con Filtro de Vol)
            w7_base = (sig_c7 / vol_d) * (target_vol_efectivo / c7_denom_sum) if c7_denom_sum > 0 else 0.0
            c7_curr_w[ticker] = scale_5a * w7_base
            
            # Capa 8 (Attention Neto con Filtro de Vol)
            w8_base = (sig_c8 / vol_d) * (target_vol_efectivo / c8_denom_sum) if c8_denom_sum > 0 else 0.0
            c8_curr_w[ticker] = scale_5a * w8_base
            
        # Aplicar histéresis de rebalanceo
        # Para Capa 2
        for t in tickers:
            val_proposed = c1_curr_w.get(t, 0.0)
            val_prev = c2_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c2_curr_w[t] = val_prev
            else:
                c2_curr_w[t] = val_proposed
 
        # Para Capa 3
        for t in tickers:
            val_proposed = c3_curr_w.get(t, 0.0)
            val_prev = c3_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c3_curr_w[t] = val_prev
 
        # Para Capa 4
        for t in tickers:
            val_proposed = c4_curr_w.get(t, 0.0)
            val_prev = c4_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c4_curr_w[t] = val_prev
 
        # Para Capas 5a, 5b, 5c
        for t in tickers:
            val_proposed = c5a_curr_w.get(t, 0.0)
            val_prev = c5a_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c5a_curr_w[t] = val_prev
                
        for t in tickers:
            val_proposed = c5b_curr_w.get(t, 0.0)
            val_prev = c5b_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c5b_curr_w[t] = val_prev
                
        for t in tickers:
            val_proposed = c5c_curr_w.get(t, 0.0)
            val_prev = c5c_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c5c_curr_w[t] = val_prev
 
        # Para Capa 6 (usando best_th validado causalmente)
        for t in tickers:
            val_proposed = c6_curr_w.get(t, 0.0)
            val_prev = c6_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < best_th:
                c6_curr_w[t] = val_prev
 
        # Para Capa 7
        for t in tickers:
            val_proposed = c7_curr_w.get(t, 0.0)
            val_prev = c7_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c7_curr_w[t] = val_prev
 
        # Guardar pesos crudos propuestos
        for t in tickers:
            c8_raw_weights.loc[date, t] = c8_curr_w.get(t, 0.0)
 
        # Para Capa 8
        for t in tickers:
            val_proposed = c8_curr_w.get(t, 0.0)
            val_prev = c8_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c8_curr_w[t] = val_prev
 
        for ticker in tickers:
            c0a_weights.loc[date, ticker] = c0a_curr_w.get(ticker, 0.0)
            c0b_weights.loc[date, ticker] = c0b_curr_w.get(ticker, 0.0)
            c1_weights.loc[date, ticker] = c1_curr_w.get(ticker, 0.0)
            c2_weights.loc[date, ticker] = c2_curr_w.get(ticker, 0.0)
            c3_weights.loc[date, ticker] = c3_curr_w.get(ticker, 0.0)
            c4_weights.loc[date, ticker] = c4_curr_w.get(ticker, 0.0)
            c5a_weights.loc[date, ticker] = c5a_curr_w.get(ticker, 0.0)
            c5b_weights.loc[date, ticker] = c5b_curr_w.get(ticker, 0.0)
            c5c_weights.loc[date, ticker] = c5c_curr_w.get(ticker, 0.0)
            c6_weights.loc[date, ticker] = c6_curr_w.get(ticker, 0.0)
            c7_weights.loc[date, ticker] = c7_curr_w.get(ticker, 0.0)
            c8_weights.loc[date, ticker] = c8_curr_w.get(ticker, 0.0)
            
        # 3. Calcular retornos de la cartera del día de HOY (de t-1 a t)
        if idx > 0:
            prev_date = test_dates[idx - 1]
            
            ret_c0a_day = 0.0
            ret_c0b_day = 0.0
            ret_c1_day = 0.0
            ret_c2_day = 0.0
            ret_c3_day = 0.0
            ret_c4_day = 0.0
            ret_c5a_day = 0.0
            ret_c5b_day = 0.0
            ret_c5c_day = 0.0
            ret_c6_day = 0.0
            ret_c7_day = 0.0
            ret_c8_day = 0.0
            
            for ticker in tickers:
                df = raw_data[ticker]
                if date in df.index and prev_date in df.index:
                    p_today = df.loc[date, "Close"]
                    p_yesterday = df.loc[prev_date, "Close"]
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    
                    w0a_prev = c0a_prev_w.get(ticker, 0.0)
                    w0b_prev = c0b_prev_w.get(ticker, 0.0)
                    w1_prev = c1_prev_w.get(ticker, 0.0)
                    w2_prev = c2_prev_w.get(ticker, 0.0)
                    w3_prev = c3_prev_w.get(ticker, 0.0)
                    w4_prev = c4_prev_w.get(ticker, 0.0)
                    w5a_prev = c5a_prev_w.get(ticker, 0.0)
                    w5b_prev = c5b_prev_w.get(ticker, 0.0)
                    w5c_prev = c5c_prev_w.get(ticker, 0.0)
                    w6_prev = c6_prev_w.get(ticker, 0.0)
                    w7_prev = c7_prev_w.get(ticker, 0.0)
                    w8_prev = c8_prev_w.get(ticker, 0.0)
                    
                    ret_c0a_day += w0a_prev * asset_ret
                    ret_c1_day += w1_prev * asset_ret
                    
                    spread_yesterday = df.loc[prev_date, "Spread"]
                    m_mult = get_swap_multiplier(ticker, prev_date)
                    
                    # Capa 0B (Neto)
                    w0b_prev_prev = c0b_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c0b = calcular_costo_transaccion(w0b_prev, w0b_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c0b = calcular_swap_pnl(w0b_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c0b_day += (w0b_prev * asset_ret - tc_c0b + swap_c0b)
                    
                    # Capa 2
                    w2_prev_prev = c2_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c2 = calcular_costo_transaccion(w2_prev, w2_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c2 = calcular_swap_pnl(w2_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c2_day += (w2_prev * asset_ret - tc_c2 + swap_c2)
                    
                    # Capa 3
                    w3_prev_prev = c3_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c3 = calcular_costo_transaccion(w3_prev, w3_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c3 = calcular_swap_pnl(w3_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c3_day += (w3_prev * asset_ret - tc_c3 + swap_c3)
                    
                    # Capa 4
                    w4_prev_prev = c4_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c4 = calcular_costo_transaccion(w4_prev, w4_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c4 = calcular_swap_pnl(w4_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c4_day += (w4_prev * asset_ret - tc_c4 + swap_c4)
                    
                    # Capa 5a
                    w5a_prev_prev = c5a_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c5a = calcular_costo_transaccion(w5a_prev, w5a_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c5a = calcular_swap_pnl(w5a_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c5a_day += (w5a_prev * asset_ret - tc_c5a + swap_c5a)
                    
                    # Capa 5b
                    w5b_prev_prev = c5b_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c5b = calcular_costo_transaccion(w5b_prev, w5b_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c5b = calcular_swap_pnl(w5b_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c5b_day += (w5b_prev * asset_ret - tc_c5b + swap_c5b)
                    
                    # Capa 5c
                    w5c_prev_prev = c5c_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c5c = calcular_costo_transaccion(w5c_prev, w5c_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c5c = calcular_swap_pnl(w5c_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c5c_day += (w5c_prev * asset_ret - tc_c5c + swap_c5c)
                    
                    # Capa 6 (XGBoost)
                    w6_prev_prev = c6_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c6 = calcular_costo_transaccion(w6_prev, w6_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c6 = calcular_swap_pnl(w6_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c6_day += (w6_prev * asset_ret - tc_c6 + swap_c6)
                    
                    # Capa 7 (LSTM)
                    w7_prev_prev = c7_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c7 = calcular_costo_transaccion(w7_prev, w7_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c7 = calcular_swap_pnl(w7_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c7_day += (w7_prev * asset_ret - tc_c7 + swap_c7)
                    
                    # Capa 8 (Attention)
                    w8_prev_prev = c8_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c8 = calcular_costo_transaccion(w8_prev, w8_prev_prev, p_yesterday, spread_yesterday, comm_rate, slippage_rate)
                    swap_c8 = calcular_swap_pnl(w8_prev, df.loc[prev_date, "SwapLong"], df.loc[prev_date, "SwapShort"], m_mult)
                    ret_c8_day += (w8_prev * asset_ret - tc_c8 + swap_c8)
                    
            c0a_returns.append(ret_c0a_day)
            c0b_returns.append(ret_c0b_day)
            c1_returns.append(ret_c1_day)
            c2_returns.append(ret_c2_day)
            c3_returns.append(ret_c3_day)
            c4_returns.append(ret_c4_day)
            c5a_returns.append(ret_c5a_day)
            c5b_returns.append(ret_c5b_day)
            c5c_returns.append(ret_c5c_day)
            c6_returns.append(ret_c6_day)
            c7_returns.append(ret_c7_day)
            c8_returns.append(ret_c8_day)
            c4_returns_history.append(ret_c4_day)
        else:
            c0a_returns.append(0.0)
            c0b_returns.append(0.0)
            c1_returns.append(0.0)
            c2_returns.append(0.0)
            c3_returns.append(0.0)
            c4_returns.append(0.0)
            c5a_returns.append(0.0)
            c5b_returns.append(0.0)
            c5c_returns.append(0.0)
            c6_returns.append(0.0)
            c7_returns.append(0.0)
            c8_returns.append(0.0)
            c4_returns_history.append(0.0)
            
        c0a_prev_w = c0a_curr_w
        c0b_prev_w = c0b_curr_w
        c1_prev_w = c1_curr_w
        c2_prev_w = c2_curr_w
        c3_prev_w = c3_curr_w
        c4_prev_w = c4_curr_w
        c5a_prev_w = c5a_curr_w
        c5b_prev_w = c5b_curr_w
        c5c_prev_w = c5c_curr_w
        c6_prev_w = c6_curr_w
        c7_prev_w = c7_curr_w
        c8_prev_w = c8_curr_w
        
    c0a_ret_series = pd.Series(c0a_returns, index=test_dates)
    c0b_ret_series = pd.Series(c0b_returns, index=test_dates)
    c1_ret_series = pd.Series(c1_returns, index=test_dates)
    c2_ret_series = pd.Series(c2_returns, index=test_dates)
    c3_ret_series = pd.Series(c3_returns, index=test_dates)
    c4_ret_series = pd.Series(c4_returns, index=test_dates)
    c5a_ret_series = pd.Series(c5a_returns, index=test_dates)
    c5b_ret_series = pd.Series(c5b_returns, index=test_dates)
    c5c_ret_series = pd.Series(c5c_returns, index=test_dates)
    c6_ret_series = pd.Series(c6_returns, index=test_dates)
    c7_ret_series = pd.Series(c7_returns, index=test_dates)
    c8_ret_series = pd.Series(c8_returns, index=test_dates)
    
    def get_sr(ret_s):
        r = ret_s.mean() / ret_s.std() if ret_s.std() > 0 else 0
        return r * np.sqrt(252)
        
    # Registrar trials finales (excluyendo Capa 8 por estar desactivada)
    for name, s in [
        ("Capa 0A", c0a_ret_series),
        ("Capa 0B", c0b_ret_series),
        ("Capa 1", c1_ret_series),
        ("Capa 2", c2_ret_series),
        ("Capa 3", c3_ret_series),
        ("Capa 4", c4_ret_series),
        ("Capa 5a", c5a_ret_series),
        ("Capa 5b", c5b_ret_series),
        ("Capa 5c", c5c_ret_series),
        ("Capa 6", c6_ret_series),
        ("Capa 7", c7_ret_series)
    ]:
        sr_val = get_sr(s)
        trial_registry.append({
            "trial_type": "final_layer",
            "date": test_dates[-1].strftime('%Y-%m-%d'),
            "layer": name,
            "threshold": np.nan,
            "sharpe": sr_val,
            "window_start": test_dates[0].strftime('%Y-%m-%d'),
            "window_end": test_dates[-1].strftime('%Y-%m-%d'),
            "n_obs": len(s)
        })
        
    trial_sharpes = [x["sharpe"] for x in trial_registry if not np.isnan(x["sharpe"])]
    
    m0a = calcular_metricas(c0a_ret_series, c0a_weights, trial_sharpes)
    m0b = calcular_metricas(c0b_ret_series, c0b_weights, trial_sharpes)
    m1 = calcular_metricas(c1_ret_series, c1_weights, trial_sharpes)
    m2 = calcular_metricas(c2_ret_series, c2_weights, trial_sharpes)
    m3 = calcular_metricas(c3_ret_series, c3_weights, trial_sharpes)
    m4 = calcular_metricas(c4_ret_series, c4_weights, trial_sharpes)
    m5a = calcular_metricas(c5a_ret_series, c5a_weights, trial_sharpes)
    m5b = calcular_metricas(c5b_ret_series, c5b_weights, trial_sharpes)
    m5c = calcular_metricas(c5c_ret_series, c5c_weights, trial_sharpes)
    m6 = calcular_metricas(c6_ret_series, c6_weights, trial_sharpes)
    m7 = calcular_metricas(c7_ret_series, c7_weights, trial_sharpes)
    m8 = {
        "Sharpe": 0.0,
        "CAGR": 0.0,
        "MaxDD": 0.0,
        "Turnover": 0.0,
        "PSR": 0.0,
        "DSR_Emp": np.nan,
        "DSR_Cons": np.nan
    }
    
    # Imprimir en consola
    print("\n" + "="*95)
    print("   RESULTADOS OUT-OF-SAMPLE (OOS): CAPAS 0 A 8")
    print("="*95)
    print(" Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario %  DSR Emp  DSR Cons ")
    print(" :---  :---:  :---:  :---:  :---:  :---:  :---: ")
    print(f" **Capa 0A: Benchmark Bruto**  {m0a['Sharpe']:.4f}  {m0a['CAGR']*100:.2f}%  {m0a['MaxDD']*100:.2f}%  {m0a['Turnover']*100:.2f}%  {fmt_val(m0a['DSR_Emp'])}  {fmt_val(m0a['DSR_Cons'])} ")
    print(f" **Capa 0B: Benchmark Neto**   {m0b['Sharpe']:.4f}  {m0b['CAGR']*100:.2f}%  {m0b['MaxDD']*100:.2f}%  {m0b['Turnover']*100:.2f}%  {fmt_val(m0b['DSR_Emp'])}  {fmt_val(m0b['DSR_Cons'])} ")
    print(f" **Capa 1: TSMOM Bruto**  {m1['Sharpe']:.4f}  {m1['CAGR']*100:.2f}%  {m1['MaxDD']*100:.2f}%  {m1['Turnover']*100:.2f}%  {fmt_val(m1['DSR_Emp'])}  {fmt_val(m1['DSR_Cons'])} ")
    print(f" **Capa 2: Fricciones Netas**  {m2['Sharpe']:.4f}  {m2['CAGR']*100:.2f}%  {m2['MaxDD']*100:.2f}%  {m2['Turnover']*100:.2f}%  {fmt_val(m2['DSR_Emp'])}  {fmt_val(m2['DSR_Cons'])} ")
    print(f" **Capa 3: Cartera Inv Vol (Neto)** {m3['Sharpe']:.4f}  {m3['CAGR']*100:.2f}%  {m3['MaxDD']*100:.2f}%  {m3['Turnover']*100:.2f}%  {fmt_val(m3['DSR_Emp'])}  {fmt_val(m3['DSR_Cons'])} ")
    print(f" **Capa 4: CATSMOM (Neto)**  {m4['Sharpe']:.4f}  {m4['CAGR']*100:.2f}%  {m4['MaxDD']*100:.2f}%  {m4['Turnover']*100:.2f}%  {fmt_val(m4['DSR_Emp'])}  {fmt_val(m4['DSR_Cons'])} ")
    print(f" **Capa 5a: Filtro Vol (Neto)**  {m5a['Sharpe']:.4f}  {m5a['CAGR']*100:.2f}%  {m5a['MaxDD']*100:.2f}%  {m5a['Turnover']*100:.2f}%  {fmt_val(m5a['DSR_Emp'])}  {fmt_val(m5a['DSR_Cons'])} ")
    print(f" **Capa 5b: Filtro HMM (Neto)**  {m5b['Sharpe']:.4f}  {m5b['CAGR']*100:.2f}%  {m5b['MaxDD']*100:.2f}%  {m5b['Turnover']*100:.2f}%  {fmt_val(m5b['DSR_Emp'])}  {fmt_val(m5b['DSR_Cons'])} ")
    print(f" **Capa 5c: Filtro MSSSM (Neto)**  {m5c['Sharpe']:.4f}  {m5c['CAGR']*100:.2f}%  {m5c['MaxDD']*100:.2f}%  {m5c['Turnover']*100:.2f}%  {fmt_val(m5c['DSR_Emp'])}  {fmt_val(m5c['DSR_Cons'])} ")
    print(f" **Capa 6: XGBoost (Neto)**  {m6['Sharpe']:.4f}  {m6['CAGR']*100:.2f}%  {m6['MaxDD']*100:.2f}%  {m6['Turnover']*100:.2f}%  {fmt_val(m6['DSR_Emp'])}  {fmt_val(m6['DSR_Cons'])} ")
    print(f" **Capa 7: LSTM (Neto)**  {m7['Sharpe']:.4f}  {m7['CAGR']*100:.2f}%  {m7['MaxDD']*100:.2f}%  {m7['Turnover']*100:.2f}%  {fmt_val(m7['DSR_Emp'])}  {fmt_val(m7['DSR_Cons'])} ")
    print(f" **Capa 8: Attention (Neto)**  DESACTIVADA / NO EVALUABLE ")
    print("="*95)
    
    # Escribir reporte consolidado
    report_path = "backtest_results_oos_consolidado.md"
    with open(report_path, "w") as f:
        f.write("# Reporte de Resultados del Backtest Out-of-Sample (OOS): Capas 0 a 8\n\n")
        f.write("Este reporte consolida el rendimiento de todos los modelos bajo la misma ventana de evaluación Out-of-Sample.\n\n")
        f.write("## Tabla Comparativa OOS\n\n")
        f.write(" Capa  Sharpe Anualizado  CAGR %  Max Drawdown %  Turnover Diario %  DSR Emp  DSR Cons  ¿Supera Benchmark Neto? \n")
        f.write(" :---  :---:  :---:  :---:  :---:  :---:  :---:  :---: \n")
        f.write(f" **Capa 0A: Benchmark Bruto**  {m0a['Sharpe']:.4f}  {m0a['CAGR']*100:.2f}%  {m0a['MaxDD']*100:.2f}%  {m0a['Turnover']*100:.2f}%  {fmt_val(m0a['DSR_Emp'])}  {fmt_val(m0a['DSR_Cons'])}  - \n")
        f.write(f" **Capa 0B: Benchmark Neto**   {m0b['Sharpe']:.4f}  {m0b['CAGR']*100:.2f}%  {m0b['MaxDD']*100:.2f}%  {m0b['Turnover']*100:.2f}%  {fmt_val(m0b['DSR_Emp'])}  {fmt_val(m0b['DSR_Cons'])}  - \n")
        f.write(f" **Capa 1: TSMOM Bruto**  {m1['Sharpe']:.4f}  {m1['CAGR']*100:.2f}%  {m1['MaxDD']*100:.2f}%  {m1['Turnover']*100:.2f}%  {fmt_val(m1['DSR_Emp'])}  {fmt_val(m1['DSR_Cons'])}  {'Sí' if m1['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 2: Fricciones Netas**  {m2['Sharpe']:.4f}  {m2['CAGR']*100:.2f}%  {m2['MaxDD']*100:.2f}%  {m2['Turnover']*100:.2f}%  {fmt_val(m2['DSR_Emp'])}  {fmt_val(m2['DSR_Cons'])}  {'Sí' if m2['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 3: Cartera Inv Vol (Neto)** {m3['Sharpe']:.4f}  {m3['CAGR']*100:.2f}%  {m3['MaxDD']*100:.2f}%  {m3['Turnover']*100:.2f}%  {fmt_val(m3['DSR_Emp'])}  {fmt_val(m3['DSR_Cons'])}  {'Sí' if m3['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 4: CATSMOM (Neto)**  {m4['Sharpe']:.4f}  {m4['CAGR']*100:.2f}%  {m4['MaxDD']*100:.2f}%  {m4['Turnover']*100:.2f}%  {fmt_val(m4['DSR_Emp'])}  {fmt_val(m4['DSR_Cons'])}  {'Sí' if m4['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 5a: Filtro Vol (Neto)**  {m5a['Sharpe']:.4f}  {m5a['CAGR']*100:.2f}%  {m5a['MaxDD']*100:.2f}%  {m5a['Turnover']*100:.2f}%  {fmt_val(m5a['DSR_Emp'])}  {fmt_val(m5a['DSR_Cons'])}  {'Sí' if m5a['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 5b: Filtro HMM (Neto)**  {m5b['Sharpe']:.4f}  {m5b['CAGR']*100:.2f}%  {m5b['MaxDD']*100:.2f}%  {m5b['Turnover']*100:.2f}%  {fmt_val(m5b['DSR_Emp'])}  {fmt_val(m5b['DSR_Cons'])}  {'Sí' if m5b['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 5c: Filtro MSSSM (Neto)**  {m5c['Sharpe']:.4f}  {m5c['CAGR']*100:.2f}%  {m5c['MaxDD']*100:.2f}%  {m5c['Turnover']*100:.2f}%  {fmt_val(m5c['DSR_Emp'])}  {fmt_val(m5c['DSR_Cons'])}  {'Sí' if m5c['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 6: XGBoost (Neto)**  {m6['Sharpe']:.4f}  {m6['CAGR']*100:.2f}%  {m6['MaxDD']*100:.2f}%  {m6['Turnover']*100:.2f}%  {fmt_val(m6['DSR_Emp'])}  {fmt_val(m6['DSR_Cons'])}  {'Sí' if m6['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 7: LSTM (Neto)**  {m7['Sharpe']:.4f}  {m7['CAGR']*100:.2f}%  {m7['MaxDD']*100:.2f}%  {m7['Turnover']*100:.2f}%  {fmt_val(m7['DSR_Emp'])}  {fmt_val(m7['DSR_Cons'])}  {'Sí' if m7['Sharpe'] > m0b['Sharpe'] else 'No'} \n")
        f.write(f" **Capa 8: Attention (Neto)**  DESACTIVADA / NO EVALUABLE  -  -  -  -  -  - \n\n")
        
        f.write("## Auditoría Final de Complejidad\n\n")
        f.write(f"1. **Rendimiento LSTM (Capa 7)**: Sharpe Neto OOS = **{m7['Sharpe']:.4f}**.\n")
        f.write(f"2. **Rendimiento Attention (Capa 8)**: DESACTIVADA / NO EVALUABLE.\n\n")
        
        best_capa = "Capa 0B"
        best_val = m0b['Sharpe']
        for c_name, c_val in [("Capa 5a (Filtro Vol)", m5a['Sharpe']), ("Capa 6 (XGBoost)", m6['Sharpe']), 
                              ("Capa 7 (LSTM)", m7['Sharpe'])]:
            if c_val > best_val:
                best_capa, best_val = c_name, c_val
                
        f.write(f"### Conclusión Operativa\nEl modelo con mejor rendimiento neto bajo condiciones reales de CFDs en el conjunto Out-of-Sample es **{best_capa}** con un Sharpe de **{best_val:.4f}** (comparado contra el Benchmark Neto Capa 0B).\n")
        
    if attn_model is not None:
        c8_raw_weights.to_csv("c8_raw_weights.csv")
        print("Pesos propuestos crudos de Capa 8 guardados en c8_raw_weights.csv")
    
    # Guardar registros de validación y de trials
    pd.DataFrame(trial_registry).to_csv("trial_registry.csv", index=False)
    pd.DataFrame(validation_logs).to_csv("validation_logs.csv", index=False)
    print("Registros de trials y logs de validación guardados en CSV.")
    
    # Escribir experiment_metadata.json
    base_dir = Path(__file__).resolve().parent
    metadata = {
        "run_date": datetime.now().isoformat(),
        "universe": tickers,
        "features_used": features_list_ml,
        "threshold_candidates": threshold_candidates,
        "split_date": "2021-06-03",
        "comm_rate": comm_rate,
        "slippage_rate": slippage_rate,
        "max_swap_cost_annualized": max_swap_cost_annualized,
        "target_vol": target_vol,
        "target_vol_efectivo": target_vol_efectivo,
        "rebalance_threshold": rebalance_threshold,
        "code_hashes": {
            "run_backtest.py": get_file_md5(str(base_dir / "run_backtest.py")),
            "src/optimization.py": get_file_md5(str(base_dir / "src" / "optimization.py"))
        },
        "data_version": {
            ticker: get_file_md5(str(base_dir / data_dir / f"{ticker}.csv"))
            for ticker in tickers
        }
    }
    with open(str(base_dir / "experiment_metadata.json"), "w") as f_meta:
        json.dump(metadata, f_meta, indent=4)
    print("Metadata del experimento guardada en experiment_metadata.json")
    
    print(f"Reporte consolidado OOS guardado en: {report_path}")
    return m0a, m0b, m1, m2, m3, m4, m5a, m5b, m5c, m6, m7, m8

if __name__ == "__main__":
    run_backtest()
