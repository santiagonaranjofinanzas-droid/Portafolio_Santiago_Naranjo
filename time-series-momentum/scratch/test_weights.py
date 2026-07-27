import sys
import os
import time
import pandas as pd
import numpy as np
import torch

#Set up dynamic path relative to the script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)
BOT_DIR = os.path.join(PARENT_DIR, "TSMOM_Bot")

if BOT_DIR not in sys.path:
    sys.path.append(BOT_DIR)

os.chdir(BOT_DIR)

from src.features import generar_features_tensor
from src.optimization import calcular_catsmom_factor, calcular_floor_causal
from src.models.markov import estimar_regimen_volatilidad
from src.models.dmn import DeepMomentumNetwork
from execution_server import ALL_TICKERS, PROFITABLE_ASSETS, get_swap_multiplier

#Highly optimized Markov regime function using pre-built dict
def estimar_regimen_msssm_fast(raw_data_dict, tickers, date):
    try:
        vol_sectores = {1: [], 2: [], 3: []}
        SECTOR_MAP = {
            "SPX500": 1, "NAS100": 1, "DJI30": 1, "GER30": 1, "EU50": 1, "UK100": 1, "JPN225": 1,
            "EURUSD": 1, "GBPUSD": 1, "AUDUSD": 1,
            "Brent": 2, "WTI": 2, "GasNatural": 2, "Cobre": 2,
            "Maiz": 2, "Trigo": 2, "Soja": 2, "Cafe": 2, "Azucar": 2,
            "XAUUSD": 3, "XAGUSD": 3, "US10Y": 3, "BUND": 3,
            "USDCHF": 3, "USDJPY": 3
        }
        
        for ticker in tickers:
            ticker_data = raw_data_dict[ticker]
            vol = np.nan
            
            # Direct lookup
            if date in ticker_data:
                vol = ticker_data[date]["Vol_YZ_21"]
                
            # If NaN/0, fallback
            if pd.isna(vol) or vol <= 0:
                vol = ticker_data.get("_mean_vol", 0.15)
                
            sector = SECTOR_MAP.get(ticker, 1)
            vol_sectores[sector].append(vol)
            
        mean_vols = []
        for s in [1, 2, 3]:
            vols = vol_sectores[s]
            vols_clean = [v for v in vols if not pd.isna(v) and v > 0]
            mean_vols.append(np.mean(vols_clean) if len(vols_clean) > 0 else 0.15)
            
        avg_vol = np.mean(mean_vols)
        if pd.isna(avg_vol):
            return 0.33
            
        prob_crisis = 1.0 / (1.0 + np.exp(-15.0 * (avg_vol - 0.20)))
        return prob_crisis
    except Exception:
        return 0.33


def compute_weights_fast(lstm_model, raw_data, test_dates, rolling_corr, returns_df):
    target_vol = 0.40
    phi = 1.0
    target_vol_efectivo = phi * target_vol
    comm_rate = 0.00005
    slippage_rate = 0.00005
    rebalance_threshold = 0.0150
    max_swap_cost_annualized = 0.085
    features_list_ml = ["Z_21d", "Z_126d", "MACD_2", "xi_3"]
    
    # Pre-convert raw_data DataFrames to dict of dicts for O(1) lookups
    raw_data_dict = {}
    for ticker in ALL_TICKERS:
        df = raw_data[ticker]
        cols = ["Vol_YZ_21", "Z_252d", "Z_63d", "Z_21d", "Z_126d", "MACD_2", "xi_3", "SwapLong", "SwapShort", "Close", "Open", "Spread"]
        df_subset = df[cols].copy()
        raw_data_dict[ticker] = df_subset.to_dict(orient='index')
        raw_data_dict[ticker]["_mean_vol"] = df["Vol_YZ_21"].mean()
        raw_data_dict[ticker]["_date_set"] = set(df.index)
        raw_data_dict[ticker]["_values"] = df_subset[features_list_ml].values
        raw_data_dict[ticker]["_dates_list"] = list(df.index)
        raw_data_dict[ticker]["_date_to_idx"] = {d: i for i, d in enumerate(df.index)}
        
    c7_weights = pd.DataFrame(index=test_dates, columns=ALL_TICKERS).fillna(0.0)
    c7_vols_ratio_history = []
    c4_returns_history = []
    c7_returns_history = []
    
    leveraged_equity = 1.0
    running_max_equity = 1.0
    in_drawdown_lock = False
    leverage_factor_prev = 8.0
    
    c1_weights = pd.DataFrame(index=test_dates, columns=ALL_TICKERS).fillna(0.0)
    c3_weights = pd.DataFrame(index=test_dates, columns=ALL_TICKERS).fillna(0.0)
    c4_weights = pd.DataFrame(index=test_dates, columns=ALL_TICKERS).fillna(0.0)
    vols_ratio_history = []
    
    c1_prev_w = {t: 0.0 for t in ALL_TICKERS}
    c3_prev_w = {t: 0.0 for t in ALL_TICKERS}
    c4_prev_w = {t: 0.0 for t in ALL_TICKERS}
    c7_prev_w = {t: 0.0 for t in ALL_TICKERS}
    
    rolling_corr_dict = {}
    for date in test_dates:
        if date in rolling_corr.index.levels[0]:
            rolling_corr_dict[date] = rolling_corr.loc[date]
            
    close_prices = {t: df["Close"].to_dict() for t, df in raw_data.items()}
    open_prices = {t: df["Open"].to_dict() for t, df in raw_data.items()}
    spread_vals = {t: df["Spread"].to_dict() for t, df in raw_data.items()}
    swap_long_vals = {t: df["SwapLong"].to_dict() for t, df in raw_data.items()}
    swap_short_vals = {t: df["SwapShort"].to_dict() for t, df in raw_data.items()}
    
    for idx, date in enumerate(test_dates):
        prob_crisis_msssm = estimar_regimen_msssm_fast(raw_data_dict, ALL_TICKERS, date)
        L_t = 126
        
        active_assets = []
        for ticker in ALL_TICKERS:
            ticker_dict = raw_data_dict[ticker]
            if date in ticker_dict["_date_set"]:
                row = ticker_dict[date]
                if not pd.isna(row["Z_252d"]):
                    date_idx = ticker_dict["_date_to_idx"][date]
                    if date_idx >= L_t - 1:
                        active_assets.append(ticker)
                        
        N_t = len(active_assets)
        if N_t == 0:
            c4_returns_history.append(0.0)
            continue
            
        # 1. Pre-collect and batch PyTorch inputs
        seq_list = []
        for ticker in active_assets:
            ticker_dict = raw_data_dict[ticker]
            date_idx = ticker_dict["_date_to_idx"][date]
            seq = ticker_dict["_values"][date_idx - L_t + 1 : date_idx + 1]
            seq = np.nan_to_num(seq)
            
            L_seq = seq.shape[0]
            decay_len = L_seq - 21
            w_decay = np.ones((L_seq, 1))
            w_decay[:decay_len, 0] = (1.0 - prob_crisis_msssm) + prob_crisis_msssm * np.arange(decay_len) / decay_len
            seq = seq * w_decay
            seq_list.append(seq)
            
        if seq_list:
            t_seq_batch = torch.tensor(np.array(seq_list), dtype=torch.float32)
            with torch.no_grad():
                preds_lstm = lstm_model(t_seq_batch).numpy()
        else:
            preds_lstm = []
            
        signals_c1 = {}
        signals_c7 = {}
        vols_diarias = {}
        ratios_sum = 0.0
        c7_ratios_sum = 0.0
        
        for asset_idx, ticker in enumerate(active_assets):
            ticker_dict = raw_data_dict[ticker]
            row = ticker_dict[date]
            
            vol_anual = row["Vol_YZ_21"]
            if vol_anual <= 0 or pd.isna(vol_anual):
                vol_anual = 0.15
            vol_diaria = vol_anual / np.sqrt(252)
            vols_diarias[ticker] = vol_diaria
            
            swap_l = row["SwapLong"]
            swap_s = row["SwapShort"]
            swap_l = swap_l if not pd.isna(swap_l) else 0.0
            swap_s = swap_s if not pd.isna(swap_s) else 0.0
            
            # Capa 1
            z21 = row["Z_21d"]
            z63 = row["Z_63d"]
            z126 = row["Z_126d"]
            z252_val = row["Z_252d"]
            z21 = z21 if not pd.isna(z21) else 0.0
            z63 = z63 if not pd.isna(z63) else 0.0
            z126 = z126 if not pd.isna(z126) else 0.0
            z252_val = z252_val if not pd.isna(z252_val) else 0.0
            
            s_i = 0.1 * z21 + 0.2 * z63 + 0.3 * z126 + 0.4 * z252_val
            sig_c1 = np.tanh(s_i)
            if sig_c1 > 0 and swap_l < 0 and abs(swap_l) > max_swap_cost_annualized:
                sig_c1 = 0.0
            elif sig_c1 < 0 and swap_s < 0 and abs(swap_s) > max_swap_cost_annualized:
                sig_c1 = 0.0
            signals_c1[ticker] = sig_c1
            ratios_sum += abs(sig_c1) / vol_diaria
            
            # Capa 7 (LSTM) - Batched lookup
            pred_lstm = float(preds_lstm[asset_idx])
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
            
        vols_ratio_history.append(ratios_sum)
        delta_min = calcular_floor_causal(vols_ratio_history, date)
        
        c7_vols_ratio_history.append(c7_ratios_sum)
        c7_delta_min = calcular_floor_causal(c7_vols_ratio_history, date)
        
        corr_matrix_today = rolling_corr_dict.get(date, pd.DataFrame())
            
        cf_t = calcular_catsmom_factor(signals_c1, corr_matrix_today)
        denom_sum = max(ratios_sum, delta_min)
        c7_denom_sum = max(c7_ratios_sum, c7_delta_min)
        
        vol_crisis_factor = estimar_regimen_volatilidad(c4_returns_history, window=63, threshold_pct=0.8)
        scale_5a = 1.0 - vol_crisis_factor
        
        c1_curr_w = {}
        c3_curr_w = {}
        c4_curr_w = {}
        c7_curr_w = {}
        
        for ticker in active_assets:
            sig = signals_c1[ticker]
            sig_c7 = signals_c7[ticker]
            vol_d = vols_diarias[ticker]
            vol_anual = vol_d * np.sqrt(252)
            
            c1_curr_w[ticker] = (target_vol / vol_anual) * sig * (1.0 / N_t) if N_t > 0 else 0.0
            w3 = (sig / vol_d) * (target_vol_efectivo / denom_sum) if denom_sum > 0 else 0.0
            c3_curr_w[ticker] = w3
            c4_curr_w[ticker] = cf_t * w3
            
            w7_base = (sig_c7 / vol_d) * (target_vol_efectivo / c7_denom_sum) if c7_denom_sum > 0 else 0.0
            c7_curr_w[ticker] = scale_5a * w7_base
            
        for t in ALL_TICKERS:
            val_proposed = c3_curr_w.get(t, 0.0)
            val_prev = c3_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c3_curr_w[t] = val_prev
                
        for t in ALL_TICKERS:
            val_proposed = c4_curr_w.get(t, 0.0)
            val_prev = c4_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c4_curr_w[t] = val_prev
                
        for t in ALL_TICKERS:
            val_proposed = c7_curr_w.get(t, 0.0)
            val_prev = c7_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c7_curr_w[t] = val_prev
                
        for t in ALL_TICKERS:
            c1_weights.loc[date, t] = c1_curr_w.get(t, 0.0)
            c3_weights.loc[date, t] = c3_curr_w.get(t, 0.0)
            c4_weights.loc[date, t] = c4_curr_w.get(t, 0.0)
            c7_weights.loc[date, t] = c7_curr_w.get(t, 0.0)
            
        if idx > 0:
            prev_date = test_dates[idx - 1]
            ret_c4_day = 0.0
            ret_c7_day = 0.0
            for ticker in ALL_TICKERS:
                ticker_close = close_prices[ticker]
                if date in ticker_close and prev_date in ticker_close:
                    p_today = ticker_close[date]
                    p_yesterday = ticker_close[prev_date]
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    spread_yesterday = spread_vals[ticker][prev_date]
                    tc_rate = (spread_yesterday / (2 * p_yesterday)) + comm_rate + slippage_rate
                    m_mult = get_swap_multiplier(ticker, prev_date)
                    
                    w4_prev = c4_prev_w.get(ticker, 0.0)
                    w4_prev_prev = c4_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c4 = abs(w4_prev - w4_prev_prev) * tc_rate
                    swap_c4 = abs(w4_prev) * (swap_long_vals[ticker][prev_date] if w4_prev > 0 else swap_short_vals[ticker][prev_date]) / 360.0 * m_mult
                    ret_c4_day += (w4_prev * asset_ret - tc_c4 + swap_c4)
                    
                    w7_prev = c7_prev_w.get(ticker, 0.0)
                    w7_prev_prev = c7_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    tc_c7 = abs(w7_prev - w7_prev_prev) * tc_rate
                    swap_c7 = abs(w7_prev) * (swap_long_vals[ticker][prev_date] if w7_prev > 0 else swap_short_vals[ticker][prev_date]) / 360.0 * m_mult
                    ret_c7_day += (w7_prev * asset_ret - tc_c7 + swap_c7)
                    
            c4_returns_history.append(ret_c4_day)
            c7_returns_history.append(ret_c7_day)
            
            ret_c7_day_leveraged = leverage_factor_prev * ret_c7_day
            leveraged_equity = leveraged_equity * (1.0 + ret_c7_day_leveraged)
            running_max_equity = max(running_max_equity, leveraged_equity)
            drawdown = (leveraged_equity - running_max_equity) / running_max_equity
            
            if drawdown <= -0.10:
                leverage_factor_raw = max(1.0, 8.0 * (1.0 - (abs(drawdown) - 0.10) / 0.15))
            else:
                leverage_factor_raw = 8.0
                
            if drawdown <= -0.12:
                in_drawdown_lock = True
            if in_drawdown_lock and drawdown >= -0.06:
                in_drawdown_lock = False
                
            if in_drawdown_lock:
                leverage_factor = min(4.0, leverage_factor_raw)
            else:
                leverage_factor = leverage_factor_raw
                
            leverage_factor_prev = leverage_factor
        else:
            c4_returns_history.append(0.0)
            c7_returns_history.append(0.0)
            drawdown = 0.0
            
        c1_prev_w = c1_curr_w
        c3_prev_w = c3_curr_w
        c4_prev_w = c4_curr_w
        c7_prev_w = c7_curr_w
        
    last_date = test_dates[-1]
    last_weights = c7_weights.loc[last_date]
    final_weights = {}
    for ticker in ALL_TICKERS:
        if ticker in PROFITABLE_ASSETS:
            final_weights[ticker] = float(last_weights[ticker]) * leverage_factor_prev
        else:
            final_weights[ticker] = 0.0
    return final_weights, leverage_factor_prev, drawdown, in_drawdown_lock


if __name__ == "__main__":
    # Load data
    data_dir = os.path.join(BOT_DIR, "data")
    raw_data = {}
    returns_dict = {}
    features_list_ml = ["Z_21d", "Z_126d", "MACD_2", "xi_3"]
    
    print("Loading data...")
    for ticker in ALL_TICKERS:
        csv_path = os.path.join(data_dir, f"{ticker}.csv")
        df = pd.read_csv(csv_path)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        df, _ = generar_features_tensor(df)
        df["target"] = np.log(df["Close"] / df["Close"].shift(1)).shift(-1) / (df["Vol_YZ_21"] / np.sqrt(252))
        cols_needed = ["Date", "Close", "Open", "Spread", "SwapLong", "SwapShort", 
                       "Vol_YZ_21", "Z_252d", "Z_63d", "target"] + features_list_ml
        df = df[cols_needed].copy()
        returns_dict[ticker] = pd.Series(df["Close"].pct_change().values, index=df["Date"])
        df = df.set_index("Date")
        raw_data[ticker] = df
        
    returns_df = pd.DataFrame(returns_dict).sort_index()
    split_date = pd.to_datetime("2021-06-03")
    all_dates = sorted(list(set().union(*[df.index for df in raw_data.values()])))
    test_dates = [d for d in all_dates if d > split_date]
    
    rolling_corr = returns_df.rolling(window=63, min_periods=30).corr()
    
    # Load model
    lstm_path = os.path.join(BOT_DIR, "lstm_model_dynamic.pt")
    lstm_model = DeepMomentumNetwork(input_dim=1, num_features=len(features_list_ml), hidden_dim=64, use_attention=False)
    lstm_model.load_state_dict(torch.load(lstm_path, map_location=torch.device('cpu')))
    lstm_model.eval()
    
    print("\nRunning Fast implementation on full history (approx 1300 dates)...")
    t0 = time.time()
    w_bat, l_bat, d_bat, lo_bat = compute_weights_fast(lstm_model, raw_data, test_dates, rolling_corr, returns_df)
    t1 = time.time()
    print(f"Fast implementation completed in {t1 - t0:.2f} seconds.")
    print("Leverage factor:", l_bat)
    # Print non-zero weights
    non_zero = {k: v for k, v in w_bat.items() if abs(v) > 1e-6}
    print("Non-zero weights:", non_zero)
