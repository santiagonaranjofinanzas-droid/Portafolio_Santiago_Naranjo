"""Diagnostic script to calculate risk and portfolio metrics on real ETF data and generate reporte_fases.md."""

from __future__ import annotations
from datetime import datetime
from pathlib import Path
import numpy as np
import pandas as pd

from data.point_in_time_universe import PITUniverseManager
from data.returns import calculate_returns
from risk.cov_estimators import (
    calculate_empirical_covariance,
    calculate_ewma_covariance,
    calculate_ledoit_wolf_covariance,
    calculate_oas_covariance,
)
from risk.rmt_filter import calculate_rmt_covariance, calculate_tie_rate
from portfolio.hrp import calculate_hrp_weights


PROJECT_ROOT = Path(__file__).resolve().parents[1]
UNIVERSE_CSV = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
PRICE_DIR = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"
REPORT_MD = PROJECT_ROOT / "reporte_fases.md"


def get_condition_number(matrix: pd.DataFrame) -> float:
    """Calculate the condition number of a covariance matrix."""
    if matrix.empty:
        return 0.0
    eigenvals = np.linalg.eigvalsh(matrix.values)
    min_val = np.min(eigenvals)
    max_val = np.max(eigenvals)
    if min_val <= 0.0:
        return float("inf")
    return float(max_val / min_val)


def main() -> int:
    evaluation_date = "2026-06-22"
    print(f"Running HRP-RMT quantitative diagnosis for date: {evaluation_date}...")
    
    # 1. Initialize PIT Universe Manager
    # Lookback history = 252 days minimum
    manager = PITUniverseManager(
        universe_csv=UNIVERSE_CSV,
        price_dir=PRICE_DIR,
        min_history_days=252,
    )
    
    # Get active/eligible universe
    state = manager.get_universe_state(evaluation_date)
    eligible_tickers = state["eligible_tickers"]
    metrics = state["metrics"]
    
    print(f"Active ETFs: {metrics['N_active']}, Eligible ETFs (ADV and History): {metrics['N_elegible']}")
    
    # 2. Extract price history and compute returns for eligible assets
    returns_list = []
    for ticker in eligible_tickers:
        file_path = PRICE_DIR / f"{ticker}.csv"
        df_price = pd.read_csv(file_path)
        df_price["date"] = pd.to_datetime(df_price["date"]).dt.tz_localize(None).dt.normalize()
        df_price = df_price.sort_values("date")
        df_price.set_index("date", inplace=True)
        
        # Get past 252 EOD prices prior to or on evaluation_date
        past_prices = df_price[df_price.index <= pd.to_datetime(evaluation_date)].iloc[-252:]
        if len(past_prices) < 252:
            continue
            
        ret_df = calculate_returns(past_prices)
        returns_list.append(ret_df["simple_return"].rename(ticker))
        
    returns_df = pd.concat(returns_list, axis=1).dropna()
    print(f"Returns panel shape: {returns_df.shape} (T={returns_df.shape[0]}, N={returns_df.shape[1]})")
    
    # 3. Calculate Covariance Matrices and Condition Numbers
    cov_empirical = calculate_empirical_covariance(returns_df)
    cov_ewma = calculate_ewma_covariance(returns_df)
    cov_lw = calculate_ledoit_wolf_covariance(returns_df)
    cov_oas = calculate_oas_covariance(returns_df)
    
    # RMT Filter (with automatic delta selection)
    cov_rmt, selected_delta = calculate_rmt_covariance(returns_df, method="constant", delta=None)
    
    cond_emp = get_condition_number(cov_empirical)
    cond_ewma = get_condition_number(cov_ewma)
    cond_lw = get_condition_number(cov_lw)
    cond_oas = get_condition_number(cov_oas)
    cond_rmt = get_condition_number(cov_rmt)
    
    # Tie Rates (on correlation matrices)
    def to_corr(cov_mat):
        std = np.sqrt(np.diag(cov_mat.values))
        std[std == 0.0] = 1e-8
        return cov_mat.values / np.outer(std, std)
        
    tie_emp_10 = calculate_tie_rate(to_corr(cov_empirical), 1e-10)
    tie_rmt_10 = calculate_tie_rate(to_corr(cov_rmt), 1e-10)
    
    print("Condition Numbers:")
    print(f"- Empirical: {cond_emp:,.2f}")
    print(f"- EWMA: {cond_ewma:,.2f}")
    print(f"- Ledoit-Wolf: {cond_lw:,.2f}")
    print(f"- OAS: {cond_oas:,.2f}")
    print(f"- RMT Filter (delta={selected_delta}): {cond_rmt:,.2f}")
    
    # 4. Calculate HRP weights for each estimator (using Ward linkage and hierarchical redistribution)
    weights_dict = {}
    drag_dict = {}
    max_w_dict = {}
    capped_count_dict = {}
    
    estimators = {
        "Empirical": cov_empirical,
        "EWMA": cov_ewma,
        "Ledoit-Wolf": cov_lw,
        "OAS": cov_oas,
        "RMT": cov_rmt,
    }
    
    for name, cov_mat in estimators.items():
        res = calculate_hrp_weights(
            cov_mat,
            linkage_method="ward",
            cap=0.15,
            redistribution_method="hierarchical",
            cash_ticker="BIL",
        )
        weights_dict[name] = res["weights_restricted"]
        max_w_dict[name] = res["weights_restricted"].max()
        capped_count_dict[name] = np.sum(res["weights_restricted"] == 0.15)
        
        # Calculate Constraint Drag
        drag = np.sum(np.abs(res["weights_pure"] - res["weights_restricted"]))
        drag_dict[name] = drag

    # Create comparison table
    df_weights = pd.DataFrame(weights_dict)
    
    # Write reporte_fases.md
    with REPORT_MD.open("w", encoding="utf-8") as f:
        f.write(f"# Reporte de Investigación Cuantitativa: Fase F3 y F4\n\n")
        f.write(f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Fecha histórica evaluada:** {evaluation_date}\n")
        f.write(f"**Parámetros:** Lookback = 252 días  Activos Elegibles N = {returns_df.shape[1]}\n\n")
        
        f.write(f"## 1. Análisis de Matrices de Riesgo (Fase F3)\n\n")
        f.write(f"Evaluación del condicionamiento matemático y tasa de empates topológicos en la matriz de correlación:\n\n")
        
        f.write(f" Estimador  Condition Number  Tie Rate (1e-10)  Delta Blend Seleccionado \n")
        f.write(f"------:---:---:\n")
        f.write(f" Empirical  {cond_emp:,.2f}  {tie_emp_10*100:.4f}%  N/A \n")
        f.write(f" EWMA  {cond_ewma:,.2f}  -  N/A \n")
        f.write(f" Ledoit-Wolf  {cond_lw:,.2f}  -  N/A \n")
        f.write(f" OAS  {cond_oas:,.2f}  -  N/A \n")
        f.write(f" RMT Constant Bulk  {cond_rmt:,.2f}  {tie_rmt_10*100:.4f}%  {selected_delta} \n\n")
        
        f.write(f"> [!NOTE]\n")
        f.write(f"> **Random Matrix Theory (RMT)** comprime drásticamente el condition number (de {cond_emp:,.2f} a {cond_rmt:,.2f}), ")
        f.write(f"lo que reduce la sensibilidad numérica a matrices invertidas. El valor de delta = {selected_delta} ")
        f.write(f"fue seleccionado automáticamente para romper empates y prevenir degeneración topológica.\n\n")
        
        f.write(f"## 2. Resultados de Asignación de Portafolios HRP (Fase F4)\n\n")
        f.write(f"Métricas de los pesos HRP resultantes tras aplicar caps (máximo 15% por ETF) y redistribución jerárquica:\n\n")
        
        f.write(f" Estimador  Max Peso Restricted  Cantidad de Activos Capped (15%)  Constraint Drag (L1-norm)  Peso a BIL (Cash) \n")
        f.write(f"------:---:---:---:\n")
        for name in estimators:
            cash_w = df_weights.loc["BIL", name] if "BIL" in df_weights.index else 0.0
            f.write(f" {name}  {max_w_dict[name]:.4%}  {capped_count_dict[name]}  {drag_dict[name]:.6f}  {cash_w:.4%} \n")
        f.write("\n")
        
        f.write(f"## 3. Pesos Detallados por Estimador\n\n")
        f.write(f"A continuación se muestran los pesos restricted de los activos en el portafolio (ordenados por el estimador RMT):\n\n")
        
        df_sorted = df_weights.sort_values(by="RMT", ascending=False)
        f.write(" Ticker  Empirical  EWMA  Ledoit-Wolf  OAS  RMT \n")
        f.write("------:---:---:---:---:\n")
        for ticker, row in df_sorted.iterrows():
            f.write(f" **{ticker}**  {row['Empirical']:.4%}  {row['EWMA']:.4%}  {row['Ledoit-Wolf']:.4%}  {row['OAS']:.4%}  {row['RMT']:.4%} \n")
            
        f.write("\n---\n*Fin del reporte de fases F3 y F4.*\n")
        
    print(f"Report phase generated at: {REPORT_MD}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
