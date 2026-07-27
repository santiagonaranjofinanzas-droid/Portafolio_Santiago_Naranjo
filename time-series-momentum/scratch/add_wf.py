import re

with open("run_backtest.py", "r", encoding="utf-8") as f:
    content = f.read()

wf_code = """
    # Bucle diario Out-of-Sample
    for idx, date in enumerate(test_dates):
        # --- WALK FORWARD VALIDATION (Retrain every year = ~252 days) ---
        if idx > 0 and idx % 252 == 0:
            print(f"\\n--- Retraining Models (Walk-Forward) at {date.strftime('%Y-%m-%d')} ---")
            train_dfs_wf = [df.loc[df.index < date] for df in raw_data.values()]
            
            # Use global to modify the outer scope variables if necessary, but since they are in the same function scope it's fine.
            xgb_model = entrenar_xgboost(train_dfs_wf, features_list_ml, max_depth=2)
            
            if lstm_model is not None:
                print("Retraining LSTM (5 epochs)...")
                lstm_model = train_dmn_model(raw_data, tickers, features_list_ml, 
                                             start_date=raw_data["SPX500"].index[0], 
                                             end_date=date, 
                                             use_attention=False, 
                                             epochs=5)
                if lstm_model is not None:
                    lstm_model.eval()
        # ----------------------------------------------------------------
"""

content = content.replace("    # Bucle diario Out-of-Sample\n    for idx, date in enumerate(test_dates):", wf_code.strip('\n'))

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Walk-forward added.")
