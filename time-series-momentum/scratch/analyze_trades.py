import os
import sys
import pandas as pd
import numpy as np
import torch

#Add current workspace to path
sys.path.append(r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM")

from run_backtest import FX_TICKERS, INDEX_TICKERS, BOND_TICKERS, get_swap_multiplier
from src.features import generar_features_tensor
from src.optimization import calcular_catsmom_factor, calcular_floor_causal
from src.models.markov import estimar_regimen_volatilidad
from src.models.dmn import DeepMomentumNetwork

def main():
    data_dir = r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\data"
    raw_data = {}
    tickers = [f.replace(".csv", "") for f in os.listdir(data_dir) if f.endswith(".csv")]
    
    returns_dict = {}
    features_list = [
        "Z_21d", "Z_126d", "MACD_2", "xi_3"
    ]
    
    print("Loading data...")
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
    
    attn_path = r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\attn_model_dynamic.pt"
    print("Capa 8 (Attention) ha sido desmantelada estructuralmente.")
    attn_model = None
    
    all_dates = sorted(list(set().union(*[df.index for df in raw_data.values()])))
    test_dates = [d for d in all_dates if d > split_date]
    
    target_vol = 0.15
    phi = 0.25
    target_vol_efectivo = phi * target_vol  # 3.75%
    comm_rate = 0.00005
    slippage_rate = 0.00005
    L = 63
    max_swap_cost_annualized = 0.085
    
    c8_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c8_vols_ratio_history = []
    c4_returns_history = []  # needed for vol filter
    c4_returns = []
    
    # We also need to compute C1-C4 to get scale_5a (vol_crisis_factor) and c4_returns
    # Since c4_returns_history is used for volatility filter, we must run the full sizing pipeline
    c1_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c3_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    c4_weights = pd.DataFrame(index=test_dates, columns=tickers).fillna(0.0)
    vols_ratio_history = []
    
    c1_prev_w = {t: 0.0 for t in tickers}
    c3_prev_w = {t: 0.0 for t in tickers}
    c4_prev_w = {t: 0.0 for t in tickers}
    c8_prev_w = {t: 0.0 for t in tickers}
    
    # Compute rolling correlations for CATSMOM (Capa 4)
    print("Computing rolling correlations...")
    rolling_corr = returns_df.rolling(window=63, min_periods=30).corr()
    
    print("Running simulation loop...")
    for idx, date in enumerate(test_dates):
        active_assets = []
        for ticker in tickers:
            df = raw_data[ticker]
            if date in df.index and not pd.isna(df.loc[date, "Z_252d"]):
                date_idx = df.index.get_loc(date)
                if date_idx >= L - 1:
                    active_assets.append(ticker)
                    
        N_t = len(active_assets)
        if N_t == 0:
            c4_returns_history.append(0.0)
            continue
            
        signals_c1 = {}
        signals_c8 = {}
        vols_diarias = {}
        ratios_sum = 0.0
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
            if sig_c1 > 0 and swap_l < 0 and abs(swap_l) > max_swap_cost_annualized:
                sig_c1 = 0.0
            elif sig_c1 < 0 and swap_s < 0 and abs(swap_s) > max_swap_cost_annualized:
                sig_c1 = 0.0
            signals_c1[ticker] = sig_c1
            ratios_sum += abs(sig_c1) / vol_diaria
            
            # Capa 8 (Attention)
            sig_c8 = 0.0
            date_idx = df.index.get_loc(date)
            # Capa 8 (Attention)
            sig_c8 = 0.0
            if attn_model is not None:
                date_idx = df.index.get_loc(date)
                seq = df.iloc[date_idx - L + 1 : date_idx + 1][features_list_ml].values
                seq = np.nan_to_num(seq)
                t_seq = torch.tensor(seq, dtype=torch.float32).unsqueeze(0)
                with torch.no_grad():
                    pred_attn = attn_model(t_seq).item()
                if abs(pred_attn) < 0.25:
                    sig_c8 = 0.0
                else:
                    sig_c8 = pred_attn
                if sig_c8 > 0 and swap_l < 0 and abs(swap_l) > max_swap_cost_annualized:
                    sig_c8 = 0.0
                elif sig_c8 < 0 and swap_s < 0 and abs(swap_s) > max_swap_cost_annualized:
                    sig_c8 = 0.0
            signals_c8[ticker] = sig_c8
            c8_ratios_sum += abs(sig_c8) / vol_diaria
            
        vols_ratio_history.append(ratios_sum)
        delta_min = calcular_floor_causal(vols_ratio_history, date)
        
        c8_vols_ratio_history.append(c8_ratios_sum)
        c8_delta_min = calcular_floor_causal(c8_vols_ratio_history, date)
        
        corr_matrix_today = pd.DataFrame()
        if date in rolling_corr.index.levels[0]:
            corr_matrix_today = rolling_corr.loc[date]
            
        cf_t = calcular_catsmom_factor(signals_c1, corr_matrix_today)
        denom_sum = max(ratios_sum, delta_min)
        c8_denom_sum = max(c8_ratios_sum, c8_delta_min)
        
        vol_crisis_factor = estimar_regimen_volatilidad(c4_returns_history, window=63, threshold_pct=0.8)
        scale_5a = 1.0 - vol_crisis_factor
        
        c1_curr_w = {}
        c3_curr_w = {}
        c4_curr_w = {}
        c8_curr_w = {}
        
        for ticker in active_assets:
            sig = signals_c1[ticker]
            sig_c8 = signals_c8[ticker]
            vol_d = vols_diarias[ticker]
            vol_anual = vol_d * np.sqrt(252)
            
            c1_curr_w[ticker] = (target_vol / vol_anual) * sig * (1.0 / N_t) if N_t > 0 else 0.0
            w3 = (sig / vol_d) * (target_vol_efectivo / denom_sum) if denom_sum > 0 else 0.0
            c3_curr_w[ticker] = w3
            c4_curr_w[ticker] = cf_t * w3
            
            w8_base = (sig_c8 / vol_d) * (target_vol_efectivo / c8_denom_sum) if c8_denom_sum > 0 else 0.0
            c8_curr_w[ticker] = scale_5a * w8_base
            
        # Hysteresis for Capa 1-4 to calculate returns correctly
        rebalance_threshold = 0.0005
        for t in tickers:
            val_proposed = c3_curr_w.get(t, 0.0)
            val_prev = c3_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c3_curr_w[t] = val_prev
                
        for t in tickers:
            val_proposed = c4_curr_w.get(t, 0.0)
            val_prev = c4_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < rebalance_threshold:
                c4_curr_w[t] = val_prev
                
        for t in tickers:
            val_proposed = c8_curr_w.get(t, 0.0)
            val_prev = c8_prev_w.get(t, 0.0)
            if abs(val_proposed - val_prev) < 0.0001:  # optimal hysteresis for Capa 8
                c8_curr_w[t] = val_prev
                
        for t in tickers:
            c1_weights.loc[date, t] = c1_curr_w.get(t, 0.0)
            c3_weights.loc[date, t] = c3_curr_w.get(t, 0.0)
            c4_weights.loc[date, t] = c4_curr_w.get(t, 0.0)
            c8_weights.loc[date, t] = c8_curr_w.get(t, 0.0)
            
        # Daily return calculation for C4 (needed for vol filter)
        if idx > 0:
            prev_date = test_dates[idx - 1]
            ret_c4_day = 0.0
            for ticker in tickers:
                df = raw_data[ticker]
                if date in df.index and prev_date in df.index:
                    p_today = df.loc[date, "Close"]
                    p_yesterday = df.loc[prev_date, "Close"]
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    w4_prev = c4_prev_w.get(ticker, 0.0)
                    w4_prev_prev = c4_weights.iloc[idx - 2][ticker] if idx > 1 else 0.0
                    spread_yesterday = df.loc[prev_date, "Spread"]
                    tc_rate = (spread_yesterday / (2 * p_yesterday)) + comm_rate + slippage_rate
                    m_mult = get_swap_multiplier(ticker, prev_date)
                    tc_c4 = abs(w4_prev - w4_prev_prev) * tc_rate
                    swap_c4 = abs(w4_prev) * (df.loc[prev_date, "SwapLong"] if w4_prev > 0 else df.loc[prev_date, "SwapShort"]) / 360.0 * m_mult
                    ret_c4_day += (w4_prev * asset_ret - tc_c4 + swap_c4)
            c4_returns_history.append(ret_c4_day)
        else:
            c4_returns_history.append(0.0)
            
        c1_prev_w = c1_curr_w
        c3_prev_w = c3_curr_w
        c4_prev_w = c4_curr_w
        c8_prev_w = c8_curr_w
        
    print("Simulation finished. Analyzing trades...")
    
    # Let's reconstruct trades for Capa 8 (Attention)
    # A trade is defined per asset.
    # An active trade starts when weight goes from 0 to non-zero, or changes sign.
    # We accumulate daily returns:
    # daily_net_ret = w8_prev * asset_ret - tc_c8 + swap_c8
    # note: daily returns occur at date t, based on weights at t-1.
    
    trades = []
    
    for ticker in tickers:
        df = raw_data[ticker]
        w_series = c8_weights[ticker]
        
        active_trade = None
        
        for idx in range(1, len(test_dates)):
            date = test_dates[idx]
            prev_date = test_dates[idx - 1]
            
            w_prev = w_series.iloc[idx - 1]
            w_prev_prev = w_series.iloc[idx - 2] if idx > 1 else 0.0
            
            # Check if active trade exists
            if active_trade is not None:
                # Check if position is closed or reversed
                sign_prev = np.sign(w_prev)
                sign_curr = np.sign(w_series.iloc[idx]) # proposed new position
                
                # If weight goes to 0 or changes sign
                # Note: a trade is closed at the end of the day when we decide to close/reverse it.
                # So the daily return of the day is still part of the trade.
                # The trade close date is 'date'.
                
                p_today = df.loc[date, "Close"] if date in df.index else None
                p_yesterday = df.loc[prev_date, "Close"] if prev_date in df.index else None
                
                if p_today is not None and p_yesterday is not None:
                    asset_ret = (p_today - p_yesterday) / p_yesterday
                    spread_yesterday = df.loc[prev_date, "Spread"]
                    tc_rate = (spread_yesterday / (2 * p_yesterday)) + comm_rate + slippage_rate
                    m_mult = get_swap_multiplier(ticker, prev_date)
                    tc_c8 = abs(w_prev - w_prev_prev) * tc_rate
                    swap_c8 = abs(w_prev) * (df.loc[prev_date, "SwapLong"] if w_prev > 0 else df.loc[prev_date, "SwapShort"]) / 360.0 * m_mult
                    
                    net_ret = w_prev * asset_ret - tc_c8 + swap_c8
                    raw_ret = np.sign(w_prev) * asset_ret
                    
                    active_trade["net_returns"].append(net_ret)
                    active_trade["raw_returns"].append(raw_ret)
                    
                # Close condition: current weight is 0 or sign changed
                if w_series.iloc[idx] == 0 or np.sign(w_series.iloc[idx]) != active_trade["direction"]:
                    active_trade["end_date"] = date
                    active_trade["exit_price"] = df.loc[date, "Close"] if date in df.index else None
                    trades.append(active_trade)
                    active_trade = None
            
            # Check if we should open a new trade
            # This happens if w_prev is non-zero, and (active_trade is None)
            # which can happen if we just closed a trade or if we were at 0 before.
            if w_series.iloc[idx] != 0 and active_trade is None:
                # Open trade starting from 'date' (this means the trade is active for the return of next day, from date to next_date)
                active_trade = {
                    "ticker": ticker,
                    "direction": np.sign(w_series.iloc[idx]), # 1 for Long, -1 for Short
                    "start_date": date,
                    "entry_price": df.loc[date, "Close"] if date in df.index else None,
                    "net_returns": [],
                    "raw_returns": [],
                    "end_date": None,
                    "exit_price": None
                }
                
        # If a trade is still active at the end, close it on the last date
        if active_trade is not None:
            active_trade["end_date"] = test_dates[-1]
            active_trade["exit_price"] = df.loc[test_dates[-1], "Close"] if test_dates[-1] in df.index else None
            trades.append(active_trade)
            
    print(f"Total trades identified: {len(trades)}")
    
    # Process trades
    trade_records = []
    for t in trades:
        total_net_ret = sum(t["net_returns"])
        total_raw_ret = sum(t["raw_returns"])
        
        # Simple percentage asset return
        if t["entry_price"] is not None and t["exit_price"] is not None and t["entry_price"] > 0:
            simple_ret = t["direction"] * (t["exit_price"] - t["entry_price"]) / t["entry_price"]
        else:
            simple_ret = total_raw_ret
            
        trade_records.append({
            "ticker": t["ticker"],
            "direction": "Long" if t["direction"] > 0 else "Short",
            "start_date": t["start_date"],
            "end_date": t["end_date"],
            "net_ret": total_net_ret,
            "simple_ret": simple_ret,
            "is_win_net": total_net_ret > 0,
            "is_win_simple": simple_ret > 0
        })
        
    df_trades = pd.DataFrame(trade_records)
    
    total_ops = len(df_trades)
    win_ops_net = df_trades["is_win_net"].sum()
    win_rate_net = win_ops_net / total_ops if total_ops > 0 else 0.0
    
    win_ops_simple = df_trades["is_win_simple"].sum()
    win_rate_simple = win_ops_simple / total_ops if total_ops > 0 else 0.0
    
    print("\n--- RESULTS FOR CAPA 8 (ATTENTION) ---")
    print(f"Total Operations (Trades): {total_ops}")
    print(f"Net Win Rate (includes sizing, TC, swaps): {win_rate_net * 100:.2f}% ({win_ops_net} wins, {total_ops - win_ops_net} losses)")
    print(f"Simple Asset Win Rate: {win_rate_simple * 100:.2f}% ({win_ops_simple} wins, {total_ops - win_ops_simple} losses)")
    
    # Break down by Long / Short
    longs = df_trades[df_trades["direction"] == "Long"]
    shorts = df_trades[df_trades["direction"] == "Short"]
    
    print(f"\nLong Trades: {len(longs)}")
    if len(longs) > 0:
        print(f"  Long Net Win Rate: {longs['is_win_net'].mean() * 100:.2f}%")
        print(f"  Long Simple Win Rate: {longs['is_win_simple'].mean() * 100:.2f}%")
        
    print(f"\nShort Trades: {len(shorts)}")
    if len(shorts) > 0:
        print(f"  Short Net Win Rate: {shorts['is_win_net'].mean() * 100:.2f}%")
        print(f"  Short Simple Win Rate: {shorts['is_win_simple'].mean() * 100:.2f}%")
        
    # Break down by Asset
    print("\n--- WIN RATE BY ASSET ---")
    asset_stats = []
    for ticker, group in df_trades.groupby("ticker"):
        asset_ops = len(group)
        asset_win_net = group["is_win_net"].sum()
        asset_wr_net = asset_win_net / asset_ops
        asset_stats.append({
            "ticker": ticker,
            "trades": asset_ops,
            "win_rate_net": asset_wr_net,
            "avg_net_ret": group["net_ret"].mean()
        })
    df_asset = pd.DataFrame(asset_stats).sort_values("win_rate_net", ascending=False)
    print(df_asset.to_string(index=False))

    # Save trades to csv for inspection
    df_trades.to_csv(r"c:\Users\YOUR_USERNAME\Desktop\Trading\TSMOM\c8_trades_analysis.csv", index=False)
    print("\nDetailed trades analysis saved to c8_trades_analysis.csv")

if __name__ == "__main__":
    main()
