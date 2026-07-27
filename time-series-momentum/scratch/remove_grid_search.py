import re
import os

with open("run_backtest.py", "r", encoding="utf-8") as f:
    content = f.read()

#1. Remove grid search variables
content = re.sub(
    r"    # Variables para Grid Search de Histéresis en Capa 8 \(Attention\).*?c8_grid_prev_w = \{th: \{t: 0\.0 for t in tickers\} for th in threshold_candidates\}",
    r"    # Histéresis fija para Capa 8\n    best_th = 0.0005",
    content,
    flags=re.DOTALL
)

#2. Update Grid search returns initialization
content = re.sub(
    r"            ret_c8_day_th_dict = \{th: 0\.0 for th in threshold_candidates\}",
    r"",
    content
)
content = re.sub(
    r"            for th in threshold_candidates:\n                c8_grid_returns\[th\].append\(0\.0\)",
    r"",
    content
)

#3. Remove Grid Search update in weights calculation
content = re.sub(
    r"        # Para Capa 8 Grid Search.*?c8_grid_weights\[th\]\.loc\[date, ticker\] = c8_curr_w_th\.get\(ticker, 0\.0\)",
    r"",
    content,
    flags=re.DOTALL
)

#4. Remove Grid Search day return logic
content = re.sub(
    r"                    # Capa 8 Grid Search.*?ret_c8_day_th_dict\[th\] \+= \(w8_prev_th \* asset_ret - tc_c8_th \+ swap_c8_th\)",
    r"",
    content,
    flags=re.DOTALL
)

#5. Remove Grid search returns append
content = re.sub(
    r"            for th in threshold_candidates:\n                c8_grid_returns\[th\]\.append\(ret_c8_day_th_dict\[th\]\)",
    r"",
    content
)

#6. Remove Grid search prev_w update
content = re.sub(
    r"        # Grid Search updates\n        for th in threshold_candidates:\n            c8_grid_prev_w\[th\] = \{t: c8_grid_weights\[th\]\.loc\[date, t\] for t in tickers\}",
    r"",
    content
)

#7. Modify the best_th fixed threshold usage
content = content.replace(
    "if abs(val_proposed - val_prev) < 0.0001:",
    "if abs(val_proposed - val_prev) < best_th:"
)

#8. Remove printing grid search
content = re.sub(
    r"    # Grid Search Metrics Calculation.*?Mejor umbral de histéresis encontrado: \{best_th:\.4f\} con Sharpe Neto = \{best_sharpe_th:\.4f\}\"\)",
    r"",
    content,
    flags=re.DOTALL
)

#9. Remove report writing grid search
content = re.sub(
    r"        f\.write\(\"## Grid Search de Histéresis: Capa 8 \(Attention\)\\n\\n\"\).*?Mejor umbral de histéresis encontrado: \*\*\{best_th:\.4f\}\*\* con Sharpe Neto = \*\*\{best_sharpe_th:\.4f\}\*\*\\n\\n\"\)",
    r"",
    content,
    flags=re.DOTALL
)

with open("run_backtest.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Grid search removed.")
