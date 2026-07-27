import os
import sys
import pandas as pd
import numpy as np
import torch
import math

#Add current workspace to path
sys.path.append(r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM")

from run_backtest import FX_TICKERS, INDEX_TICKERS, get_swap_multiplier
from src.features import generar_features_tensor
from src.optimization import calcular_catsmom_factor, calcular_floor_causal
from src.models.markov import estimar_regimen_volatilidad, estimar_regimen_msssm
from src.models.dmn import DeepMomentumNetwork

def cdf_normal(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))

def calculate_metrics_for_layer(series_returns, weights_df, raw_data, tickers, test_dates, comm_rate, slippage_rate, layer_name):
    # 1. General performance
    cum_returns = (1 + series_returns).cumprod()
    running_max = cum_returns.cummax()
    drawdowns = (cum_returns - running_max) / running_max
    max_dd = drawdowns.min()
    
    mean_ret = series_returns.mean()
    std_ret = series_returns.std()
    sharpe = (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
    
    years = len(series_returns) / 252.0
    cagr = (cum_returns.iloc[-1] ** (1 / years) - 1) if years > 0 and cum_returns.iloc[-1] > 0 else 0.0
    calmar = cagr / abs(max_dd) if max_dd != 0 else 0.0
    
    print(f"\n--- METRICAS GENERALES {layer_name} ---")
    print(f"Sharpe Ratio Anualizado: {sharpe:.4f}")
    print(f"CAGR: {cagr*100:.4f}%")
    print(f"Maximum Drawdown (MDD): {max_dd*100:.4f}%")
    print(f"Calmar Ratio: {calmar:.4f}")
    
    # 2. Deflated Sharpe Ratio (DSR)
    T = len(series_returns)
    diffs = series_returns - mean_ret
    skew = (sum(diffs ** 3) / T) / (std_ret ** 3) if std_ret > 0 else 0.0
    kurt = (sum(diffs ** 4) / T) / (std_ret ** 4) if std_ret > 0 else 0.0
    
    print(f"\n--- DEFLATED SHARPE RATIO (DSR) {layer_name} ---")
    gamma = 0.5772156649
    sigma_sr = 0.15 
    
    for N in [10, 20, 50, 100]:
        def inv_norm_cdf(p):
            a1 = -3.969683028665376e+01
            a2 =  2.209460984044760e+02
            a3 = -2.759285104469687e+02
            a4 =  1.383577518672690e+02
            a5 = -3.066479571180290e+01
            a6 =  2.506628277459239e+00
            
            b1 = -5.447609879822406e+01
            b2 =  1.615858368580409e+02
            b3 = -1.556989798598866e+02
            b4 =  6.680131188771972e+01
            b5 = -1.328068155288572e+01
            
            if p <= 0 or p >= 1:
                return 0.0
            
            if p < 0.5:
                q = math.sqrt(-2.0 * math.log(p))
                return -(((((a1*q+a2)*q+a3)*q+a4)*q+a5)*q+a6) / (((((b1*q+b2)*q+b3)*q+b4)*q+b5)*q+1.0)
            else:
                q = math.sqrt(-2.0 * math.log(1.0 - p))
                return (((((a1*q+a2)*q+a3)*q+a4)*q+a5)*q+a6) / (((((b1*q+b2)*q+b3)*q+b4)*q+b5)*q+1.0)
        
        z_n = inv_norm_cdf(1.0 - 1.0/N)
        z_ne = inv_norm_cdf(1.0 - 1.0/(N * math.e))
        sr_0 = sigma_sr * ((1.0 - gamma) * z_n + gamma * z_ne)
        
        sr_daily = mean_ret / std_ret if std_ret > 0 else 0.0
        sr_0_daily = sr_0 / math.sqrt(252)
        
        numerator = (sr_daily - sr_0_daily) * math.sqrt(T - 1)
        denominator = math.sqrt(1.0 - skew * sr_daily + ((kurt - 1.0) / 4.0) * (sr_daily ** 2)) if std_ret > 0 else 1.0
        
        dsr_val = cdf_normal(numerator / denominator) if denominator > 0 else 0.0
        print(f"DSR (N = {N} trials): {dsr_val*100:.2f}% (Expected Max SR = {sr_0:.4f})")
        
    # 3. Individual Trades Analysis
    trades = []
    for ticker in tickers:
        df = raw_data[ticker]
        w_series = weights_df[ticker]
        active_trade = None
        
        for idx in range(1, len(test_dates)):
            date = test_dates[idx]
            prev_date = test_dates[idx - 1]
            
            w_prev = w_series.iloc[idx - 1]
            w_prev_prev = w_series.iloc[idx - 2] if idx > 1 else 0.0
            
            if active_trade is not None:
                p_today = df.loc[date, "Close"] if date in df.index else None
                p_yesterday = df.loc[prev_date, "Close"] if prev_date in df.index else None
                
                if p_today is not None and p_yesterday is not None:
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    spread_yesterday = df.loc[prev_date, "Spread"]
                    tc_rate = (spread_yesterday / (2 * p_yesterday)) + comm_rate + slippage_rate
                    m_mult = get_swap_multiplier(ticker, prev_date)
                    tc_cost = abs(w_prev - w_prev_prev) * tc_rate
                    swap_cost = abs(w_prev) * (df.loc[prev_date, "SwapLong"] if w_prev > 0 else df.loc[prev_date, "SwapShort"]) / 360.0 * m_mult
                    
                    net_ret = w_prev * asset_ret - tc_cost + swap_cost
                    active_trade["net_returns"].append(net_ret)
                    
                if w_series.iloc[idx] == 0 or np.sign(w_series.iloc[idx]) != active_trade["direction"]:
                    active_trade["end_date"] = date
                    trades.append(active_trade)
                    active_trade = None
                    
            if w_series.iloc[idx] != 0 and active_trade is None:
                active_trade = {
                    "ticker": ticker,
                    "direction": np.sign(w_series.iloc[idx]),
                    "start_date": date,
                    "net_returns": [],
                    "end_date": None
                }
                
        if active_trade is not None:
            active_trade["end_date"] = test_dates[-1]
            trades.append(active_trade)
            
    trade_records = []
    for t in trades:
        total_net_ret = sum(t["net_returns"])
        trade_records.append({
            "ticker": t["ticker"],
            "net_ret": total_net_ret,
            "is_win": total_net_ret > 0
        })
        
    df_trades = pd.DataFrame(trade_records)
    total_trades = len(df_trades)
    winning_trades = df_trades["is_win"].sum() if total_trades > 0 else 0
    hit_rate = winning_trades / total_trades if total_trades > 0 else 0.0
    
    sum_gains = df_trades[df_trades["net_ret"] > 0]["net_ret"].sum() if total_trades > 0 else 0.0
    sum_losses = abs(df_trades[df_trades["net_ret"] < 0]["net_ret"].sum()) if total_trades > 0 else 0.0
    profit_factor = sum_gains / sum_losses if sum_losses > 0 else float('inf')
    
    print(f"\n--- ESTADISTICAS DE OPERACIONES INDIVIDUALES {layer_name} ---")
    print(f"Total Operaciones: {total_trades}")
    print(f"Hit Rate (Win Rate): {hit_rate*100:.2f}% ({winning_trades} ganadas, {total_trades - winning_trades} perdidas)")
    print(f"Profit Factor (Bruto): {profit_factor:.4f} (Gains = {sum_gains:.6f}, Losses = {sum_losses:.6f})")
    print("=" * 60)

def main():
    data_dir = r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\data"
    raw_data = {}
    tickers = [f.replace(".csv", "") for f in os.listdir(data_dir) if f.endswith(".csv")]
    
    returns_dict = {}
    features_list = [
        "Z_21d", "Z_126d", "MACD_2", "xi_3"
    ]
    
    print("Cargando datos y generando features...")
    for ticker in tickers:
        csv_path = os.path.join(data_dir, f"{ticker}.csv")
        df = pd.read_csv(csv_path)
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.sort_values("Date").reset_index(drop=True)
        
        df, _ = generar_features_tensor(df)
        df["target"] = np.log(df["Close"] / df["Close"].shift(1)).shift(-1) / (df["Vol_YZ_21"] / np.sqrt(252))
        
        cols_needed = ["Date", "Close", "Open", "Spread", "SwapLong", "SwapShort", 
                       "Vol_YZ_21", "Z_252d", "Z_63d", "target"] + features_list
        df = df[cols_needed].copy()
        
        df_ret = df["Close"].pct_change()
        returns_dict[ticker] = pd.Series(df_ret.values, index=df["Date"])
        df = df.set_index("Date")
        raw_data[ticker] = df
        
    returns_df = pd.DataFrame(returns_dict).sort_index()
    split_date = pd.to_datetime("2021-06-03")
    
    features_list_ml = [
        "Z_21d", "Z_126d", "MACD_2", "xi_3"
    ]
    
    lstm_path = r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\lstm_model_dynamic.pt"
    attn_path = r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\attn_model_dynamic.pt"
    
    print("Cargando modelo LSTM...")
    lstm_model = DeepMomentumNetwork(input_dim=1, num_features=len(features_list_ml), hidden_dim=64, use_attention=False)
    lstm_model.load_state_dict(torch.load(lstm_path))
    lstm_model.eval()
    
    print("Capa 8 (Attention) ha sido desmantelada estructuralmente.")
    attn_model = None
    
    all_dates = sorted(list(set().union(*[df.index for df in raw_data.values()])))
    test_dates = [d for d in all_dates if d > split_date]
    
    target_vol = 0.40
    phi = 1.0
    target_vol_efectivo = phi * target_vol  # 40.0%
    comm_rate = 0.00005
    slippage_rate = 0.00005
    rebalance_threshold_lstm = 0.0150  # 150 bps
    rebalance_threshold_attn = 0.0010  # 10 bps (optimal hysteresis from search)
    
    c7_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c8_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    
    c4_returns_history = []
    c7_returns = []
    c8_returns = []
    
    c1_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c3_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c4_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    
    vols_ratio_history = []
    c7_vols_ratio_history = []
    c8_vols_ratio_history = []
    
    c1_prev_w = {t: 0.0 for t in tickers}
    c3_prev_w = {t: 0.0 for t in tickers}
    c4_prev_w = {t: 0.0 for t in tickers}
    c7_prev_w = {t: 0.0 for t in tickers}
    c8_prev_w = {t: 0.0 for t in tickers}
    
    print("Calculando correlaciones rodantes...")
    rolling_corr = returns_df.rolling(window=63, min_periods=30).corr()
    
    print("Ejecutando simulacion diaria de OOS...")
    for idx, date in enumerate(test_dates):
        prob_crisis_msssm = estimar_regimen_msssm(raw_data, tickers, date)
        L_t = 126
        
        active_assets = []
        for ticker in tickers:
            df = raw_data[ticker]
            if date in df.index and not pd.isna(df.loc[date, "Z_252d"]):
                date_idx = df.index.get_loc(date)
                if date_idx >= L_t - 1:
                    active_assets.append(ticker)
                    
        N_t = len(active_assets)
        if N_t == 0:
            c4_returns_history.append(0.0)
            c7_returns.append(0.0)
            c8_returns.append(0.0)
            continue
            
        signals_c1 = {}
        signals_c7 = {}
        signals_c8 = {}
        vols_diarias = {}
        ratios_sum = 0.0
        c7_ratios_sum = 0.0
        c8_ratios_sum = 0.0
        
        for ticker in active_assets:
            df = raw_data[ticker]
            vol_anual = df.loc[date, "Vol_YZ_21"]
            if vol_anual <= 0 or pd.isna(vol_anual):
                vol_anual = 0.15
            vol_diaria = vol_anual / np.sqrt(252)
            vols_diarias[ticker] = vol_diaria
            
            swap_l = df.loc[date, "SwapLong"]
            swap_s = df.loc[date, "SwapShort"]
            swap_l = swap_l if not pd.isna(swap_l) else 0.0
            swap_s = swap_s if not pd.isna(swap_s) else 0.0
            
            # Capa 1
            z21 = df.loc[date, "Z_21d"]
            z63 = df.loc[date, "Z_63d"]
            z126 = df.loc[date, "Z_126d"]
            z252 = df.loc[date, "Z_252d"]
            z21 = z21 if not pd.isna(z21) else 0.0
            z63 = z63 if not pd.isna(z63) else 0.0
            z126 = z126 if not pd.isna(z126) else 0.0
            z252_val = z252 if not pd.isna(z252) else 0.0
            
            s_i = 0.1 * z21 + 0.2 * z63 + 0.3 * z126 + 0.4 * z252_val
            sig_c1 = np.tanh(s_i)
            if sig_c1 > 0 and swap_l < 0 and abs(swap_l) > 0.085:
                sig_c1 = 0.0
            elif sig_c1 < 0 and swap_s < 0 and abs(swap_s) > 0.085:
                sig_c1 = 0.0
            signals_c1[ticker] = sig_c1
            ratios_sum += abs(sig_c1) / vol_diaria
            
            # Feature extraction for models
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
            
            # Capa 7 (LSTM)
            with torch.no_grad():
                pred_lstm = lstm_model(t_seq).item()
            if abs(pred_lstm) < 0.25:
                sig_c7 = 0.0
            else:
                sig_c7 = pred_lstm
            if sig_c7 > 0 and swap_l < 0 and abs(swap_l) > 0.085:
                sig_c7 = 0.0
            elif sig_c7 < 0 and swap_s < 0 and abs(swap_s) > 0.085:
                sig_c7 = 0.0
            signals_c7[ticker] = sig_c7
            c7_ratios_sum += abs(sig_c7) / vol_diaria
            
            # Capa 8 (Attention)
            sig_c8 = 0.0
            if attn_model is not None:
                with torch.no_grad():
                    pred_attn = attn_model(t_seq).item()
                if abs(pred_attn) < 0.25:
                    sig_c8 = 0.0
                else:
                    sig_c8 = pred_attn
                if sig_c8 > 0 and swap_l < 0 and abs(swap_l) > 0.085:
                    sig_c8 = 0.0
                elif sig_c8 < 0 and swap_s < 0 and abs(swap_s) > 0.085:
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
        
        vol_crisis_factor = estimar_regimen_volatilidad(c4_returns_history, window=63, threshold_pct=0.8)
        scale_5a = 1.0 - vol_crisis_factor
        
        c1_curr_w = {}
        c3_curr_w = {}
        c4_curr_w = {}
        c7_curr_w = {}
        c8_curr_w = {}
        
        for ticker in active_assets:
            sig = signals_c1[ticker]
            sig_c7 = signals_c7[ticker]
            sig_c8 = signals_c8[ticker]
            vol_d = vols_diarias[ticker]
            vol_anual = vol_d * np.sqrt(252)
            
            c1_curr_w[ticker] = (target_vol / vol_anual) * sig * (1.0 / N_t) if N_t > 0 else 0.0
            w3 = (sig / vol_d) * (target_vol_efectivo / denom_sum) if denom_sum > 0 else 0.0
            c3_curr_w[ticker] = w3
            c4_curr_w[ticker] = cf_t * w3
            
            w7_base = (sig_c7 / vol_d) * (target_vol_efectivo / c7_denom_sum) if c7_denom_sum > 0 else 0.0
            c7_curr_w[ticker] = scale_5a * w7_base
            
            w8_base = (sig_c8 / vol_d) * (target_vol_efectivo / c8_denom_sum) if c8_denom_sum > 0 else 0.0
            c8_curr_w[ticker] = scale_5a * w8_base
            
        # Hysteresis for Capa 3 & 4
        for t in tickers:
            val_proposed = c3_curr_w.get(t, 0.0)
            val_prev = c3_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < 0.0150:  # rebalance_threshold = 1.5%
                c3_curr_w[t] = val_prev
                
        for t in tickers:
            val_proposed = c4_curr_w.get(t, 0.0)
            val_prev = c4_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < 0.0150:
                c4_curr_w[t] = val_prev
                
        # Hysteresis for Capa 7 (LSTM)
        for t in tickers:
            val_proposed = c7_curr_w.get(t, 0.0)
            val_prev = c7_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold_lstm:
                c7_curr_w[t] = val_prev
                
        # Hysteresis for Capa 8 (Attention) - Optimal from search (10 bps)
        for t in tickers:
            val_proposed = c8_curr_w.get(t, 0.0)
            val_prev = c8_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold_attn:
                c8_curr_w[t] = val_prev
                
        for t in tickers:
            c1_weights.loc[date, t] = c1_curr_w.get(t, 0.0)
            c3_weights.loc[date, t] = c3_curr_w.get(t, 0.0)
            c4_weights.loc[date, t] = c4_curr_w.get(t, 0.0)
            c7_weights.loc[date, t] = c7_curr_w.get(t, 0.0)
            c8_weights.loc[date, t] = c8_curr_w.get(t, 0.0)
            
        if idx > 0:
            prev_date = test_dates[idx - 1]
            ret_c4_day = 0.0
            ret_c7_day = 0.0
            ret_c8_day = 0.0
            for ticker in tickers:
                df = raw_data[ticker]
                if date in df.index and prev_date in df.index:
                    p_today = df.loc[date, "Close"]
                    p_yesterday = df.loc[prev_date, "Close"]
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    
                    w4_prev = c4_prev_w.get(ticker, 0.0)
                    w4_prev_prev = c4_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    w7_prev = c7_prev_w.get(ticker, 0.0)
                    w7_prev_prev = c7_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    w8_prev = c8_prev_w.get(ticker, 0.0)
                    w8_prev_prev = c8_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    
                    spread_yesterday = df.loc[prev_date, "Spread"]
                    tc_rate = (spread_yesterday / (2 * p_yesterday)) + comm_rate + slippage_rate
                    m_mult = get_swap_multiplier(ticker, prev_date)
                    
                    tc_c4 = abs(w4_prev - w4_prev_prev) * tc_rate
                    swap_c4 = abs(w4_prev) * (df.loc[prev_date, "SwapLong"] if w4_prev > 0 else df.loc[prev_date, "SwapShort"]) / 360.0 * m_mult
                    ret_c4_day += (w4_prev * asset_ret - tc_c4 + swap_c4)
                    
                    tc_c7 = abs(w7_prev - w7_prev_prev) * tc_rate
                    swap_c7 = abs(w7_prev) * (df.loc[prev_date, "SwapLong"] if w7_prev > 0 else df.loc[prev_date, "SwapShort"]) / 360.0 * m_mult
                    ret_c7_day += (w7_prev * asset_ret - tc_c7 + swap_c7)
                    
                    tc_c8 = abs(w8_prev - w8_prev_prev) * tc_rate
                    swap_c8 = abs(w8_prev) * (df.loc[prev_date, "SwapLong"] if w8_prev > 0 else df.loc[prev_date, "SwapShort"]) / 360.0 * m_mult
                    ret_c8_day += (w8_prev * asset_ret - tc_c8 + swap_c8)
                    
            c4_returns_history.append(ret_c4_day)
            c7_returns.append(ret_c7_day)
            c8_returns.append(ret_c8_day)
        else:
            c4_returns_history.append(0.0)
            c7_returns.append(0.0)
            c8_returns.append(0.0)
            
        c1_prev_w = c1_curr_w
        c3_prev_w = c3_curr_w
        c4_prev_w = c4_curr_w
        c7_prev_w = c7_curr_w
        c8_prev_w = c8_curr_w
        
    c7_series = pd.Series(c7_returns, index=test_dates)
    c8_series = pd.Series(c8_returns, index=test_dates)
    
    calculate_metrics_for_layer(c7_series, c7_weights, raw_data, tickers, test_dates, comm_rate, slippage_rate, "CAPA 7 (LSTM)")
    calculate_metrics_for_layer(c8_series, c8_weights, raw_data, tickers, test_dates, comm_rate, slippage_rate, "CAPA 8 (ATTENTION - BEST HYSTERESIS = 10 BPS)")

if __name__ == "__main__":
    main()
