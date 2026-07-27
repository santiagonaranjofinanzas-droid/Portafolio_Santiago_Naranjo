import re

with open("run_backtest.py", "r", encoding="utf-8") as f:
    rb = f.read()

#Replace the mocked evaluation with actual evaluation logic using xgb_temp
#Since predicting feature by feature inside the threshold candidate loop is extremely slow,
#we will first predict all raw signals for val_sub with xgb_temp, then evaluate thresholds.

mock_block_old = """                for th_cand in threshold_candidates:
                    # In a full simulation we would predict on val_sub using xgb_temp. 
                    # Here we proxy the sharpe penalty logic securely over val_sub
                    # Mock evaluation appending to global_trials_sr (simulated extraction)
                    val_sharpe = np.random.normal(0.5, 0.1) - th_cand * 10
                    global_trials_sr.append(val_sharpe)
                    if val_sharpe > best_val_sharpe:
                        best_val_sharpe = val_sharpe
                        best_th = th_cand"""

mock_block_new = """                # Pre-calculate raw predictions on val_sub to speed up threshold evaluation
                val_dates = val_sub[0].index
                raw_preds = {ticker: {} for ticker in tickers}
                for i, ticker in enumerate(tickers):
                    df_v = val_sub[i]
                    if len(df_v) > 0:
                        # Extract features block
                        valid_features = df_v[features_list_ml].dropna()
                        if len(valid_features) > 0:
                            preds = xgb_temp.predict(valid_features.values)
                            for d_idx, d in enumerate(valid_features.index):
                                raw_preds[ticker][d] = preds[d_idx]
                
                for th_cand in threshold_candidates:
                    val_returns = []
                    prev_w = {t: 0.0 for t in tickers}
                    
                    for v_date in val_dates:
                        day_ret = 0.0
                        has_trade = False
                        for i, ticker in enumerate(tickers):
                            if v_date in raw_preds[ticker]:
                                raw_p = raw_preds[ticker][v_date]
                                
                                # Hysteresis logic
                                if abs(raw_p - prev_w[ticker]) < th_cand:
                                    curr_w = prev_w[ticker]
                                else:
                                    curr_w = raw_p
                                
                                df_v = val_sub[i]
                                # We need target proxy. We use log_ret_1d if available
                                if "log_ret_1d" in df_v.columns:
                                    ret_t = df_v.loc[v_date, "log_ret_1d"]
                                else:
                                    ret_t = 0.0
                                    
                                cost = abs(curr_w - prev_w[ticker]) * 0.0001
                                day_ret += curr_w * ret_t - cost
                                prev_w[ticker] = curr_w
                                has_trade = True
                                
                        if has_trade:
                            val_returns.append(day_ret)
                            
                    if len(val_returns) > 3:
                        th_series = pd.Series(val_returns)
                        std = th_series.std()
                        val_sharpe = (th_series.mean() / std * np.sqrt(252)) if std > 0 else 0.0
                    else:
                        val_sharpe = 0.0
                        
                    global_trials_sr.append(val_sharpe)
                    if val_sharpe > best_val_sharpe:
                        best_val_sharpe = val_sharpe
                        best_th = th_cand"""

rb = rb.replace(mock_block_old, mock_block_new)

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(rb)

print("Mock evaluation fixed with real simulation.")
