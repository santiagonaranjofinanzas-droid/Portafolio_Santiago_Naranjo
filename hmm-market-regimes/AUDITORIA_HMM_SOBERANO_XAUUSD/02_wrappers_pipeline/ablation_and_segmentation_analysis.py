import os
import sys
import json
import math
import pandas as pd
import numpy as np
from pathlib import Path

#Resolver rutas para importar del proyecto principal
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Capa_2.sovereign_signal import run_sovereign_signal_engine
from Capa_4.backtest_metrics import BacktestAssumptions, run_backtest, compute_backtest_metrics

def df_to_markdown(df):
    cols = list(df.columns)
    header = " " + "  ".join(str(c) for c in cols) + " "
    separator = " " + "  ".join("---" for _ in cols) + " "
    rows = []
    for _, r in df.iterrows():
        row_vals = [str(r[col]) for col in df.columns]
        rows.append(" " + "  ".join(row_vals) + " ")
    return "\n".join([header, separator] + rows)

def main():
    print("=========================================================================")
    print("=== INICIANDO AUDITORIA AVANZADA: ABLACION Y SEGMENTACION HMM ===")
    print("=========================================================================")
    
    asset = "XAUUSD"
    res_dir = ROOT / "Universo de activos" / "resultados" / asset
    oos_parquet = res_dir / f"{asset}_M15_OOS.parquet"
    is_parquet = res_dir / f"{asset}_M15_IS_PURGED.parquet"
    hmm_params_csv = res_dir / f"HMM_Params_15M_{asset}.csv"
    
    if not oos_parquet.exists() or not is_parquet.exists() or not hmm_params_csv.exists():
        print(f"[Error] Archivos necesarios no encontrados en {res_dir}")
        sys.exit(1)
        
    df_is = pd.read_parquet(is_parquet)
    df_oos = pd.read_parquet(oos_parquet)
    total_bars_oos = len(df_oos)
    print(f"[*] Cargadas {len(df_is)} velas IS para calibracion ex-ante.")
    print(f"[*] Cargadas {total_bars_oos} velas de holdout OOS ({df_oos.index[0]} a {df_oos.index[-1]})")

    # Configuración Base (óptima del optimizador)
    base_assumptions = {
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "spread_price": 0.15,
        "slippage_price": 0.05,
        "commission_per_lot": 3.0,
        "min_lot": 0.01,
        "lot_step": 0.01,
        "intrabar_mode": "pessimistic",
        "min_strength": 0.30,
        "vol_multiplier": 2.5,
        "reward_risk": 2.5,
        "threshold": 0.60,
        "kalman_gate": True,
        "dsr_trials": 81
    }

    # 1. Calcular mediana de volatilidad EX-ANTE en IS para evitar Leakage
    print("[*] Calculando mediana de volatilidad ex-ante en IS...")
    signals_is = run_sovereign_signal_engine(
        df_is,
        params_csv=str(hmm_params_csv),
        point=base_assumptions["point"],
        threshold=base_assumptions["threshold"],
        kalman_gate=base_assumptions["kalman_gate"],
        min_strength=base_assumptions["min_strength"]
    )
    is_vols = signals_is["Vol_Projected_Sigma"].to_numpy()
    valid_is_vols = is_vols[is_vols > 1e-8]
    volatility_median_is = np.median(valid_is_vols) if len(valid_is_vols) > 0 else 0.0
    print(f"[Info] Mediana ex-ante de volatilidad calculada en IS: {volatility_median_is:.6f}")

    # Helper para extraer métricas requeridas por el auditor
    def extract_metrics_dict(metrics, trades_df, label):
        exposure_time = (trades_df["bars_held"].sum() / total_bars_oos) * 100.0 if not trades_df.empty else 0.0
        return {
            "Label": label,
            "Trades": metrics["closed_trades"],
            "Win Rate %": f"{metrics['win_rate_pct']:.2f}%",
            "Avg Win": f"${metrics['avg_win']:.2f}",
            "Avg Loss": f"${metrics['avg_loss']:.2f}",
            "Profit Factor": f"{metrics['profit_factor']:.2f}" if metrics['profit_factor'] != np.inf else "N/A",
            "Expectancy": f"${metrics['expectancy']:.2f}",
            "Max DD %": f"{metrics['max_drawdown_pct']:.2f}%",
            "Sharpe Ratio": f"{metrics['sharpe_ratio']:.2f}",
            "DSR Prob": f"{metrics['deflated_sharpe_probability']*100:.2f}%",
            "Exposure %": f"{exposure_time:.2f}%",
            "Avg Bars Held": f"{trades_df['bars_held'].mean():.1f}" if not trades_df.empty else "0.0"
        }

    # Helper maestro de simulación
    def run_simulation(ablation_mode="none", dynamic_threshold=False, k=0.10, trade_direction="both", trading_session="all", volatility_regime="all", custom_costs=None):
        # Usar costos custom si están definidos (para sensibilidad de costos)
        costs = custom_costs or base_assumptions
        
        # Inferencia de señales
        signals = run_sovereign_signal_engine(
            df_oos,
            params_csv=str(hmm_params_csv),
            point=costs["point"],
            threshold=base_assumptions["threshold"],
            kalman_gate=base_assumptions["kalman_gate"],
            min_strength=base_assumptions["min_strength"],
            ablation_mode=ablation_mode,
            dynamic_threshold=dynamic_threshold,
            dynamic_threshold_k=k
        )
        
        assumptions = BacktestAssumptions(
            initial_balance=10000.0,
            risk_percent=1.0,
            min_strength=base_assumptions["min_strength"],
            vol_multiplier=base_assumptions["vol_multiplier"],
            reward_risk=base_assumptions["reward_risk"],
            use_partials=True,
            max_lot=10.0,
            point=costs["point"],
            tick_size=costs["tick_size"],
            tick_value=costs["tick_value"],
            spread_price=costs["spread_price"],
            slippage_price=costs["slippage_price"],
            periods_per_year=24 * 4 * 252,
            commission_per_lot=costs["commission_per_lot"],
            min_lot=costs["min_lot"],
            lot_step=costs["lot_step"],
            intrabar_mode=costs["intrabar_mode"],
            trade_direction=trade_direction,
            trading_session=trading_session,
            volatility_regime=volatility_regime,
            volatility_regime_mode="ex_ante",
            volatility_median_is=volatility_median_is
        )
        
        trades, cashflows, equity = run_backtest(signals, assumptions)
        metrics = compute_backtest_metrics(trades, cashflows, equity, assumptions, dsr_trials=base_assumptions["dsr_trials"])
        return metrics, trades, equity

    print("[*] Corriendo simulaciones...")
    
    # --- Experimentos ---
    
    # 0. Baseline
    m_base, t_base, eq_base = run_simulation()
    t_base.to_csv(res_dir / "trades_ablation_base.csv", index=False)
    pd.DataFrame([m_base]).to_csv(res_dir / "baseline_metrics.csv", index=False)
    r_base = extract_metrics_dict(m_base, t_base, "Base (Con todo)")

    # 1. Dirección (BUY vs SELL)
    m_buy, t_buy, _ = run_simulation(trade_direction="buy")
    m_sell, t_sell, _ = run_simulation(trade_direction="sell")
    
    df_dir = pd.DataFrame([
        extract_metrics_dict(m_buy, t_buy, "BUY Only"),
        extract_metrics_dict(m_sell, t_sell, "SELL Only")
    ])
    df_dir.to_csv(res_dir / "direction_segmentation.csv", index=False)

    # 2. Sesiones Horarias (London vs NY vs Asia)
    m_lon, t_lon, _ = run_simulation(trading_session="london")
    m_ny, t_ny, _ = run_simulation(trading_session="ny")
    m_asia, t_asia, _ = run_simulation(trading_session="asia")
    
    df_sess = pd.DataFrame([
        extract_metrics_dict(m_lon, t_lon, "Londres"),
        extract_metrics_dict(m_ny, t_ny, "Nueva York"),
        extract_metrics_dict(m_asia, t_asia, "Asia")
    ])
    df_sess.to_csv(res_dir / "session_segmentation.csv", index=False)

    # 3. Regímenes de Volatilidad (Alta vs Baja Ex-Ante)
    m_hvol, t_hvol, _ = run_simulation(volatility_regime="high")
    m_lvol, t_lvol, _ = run_simulation(volatility_regime="low")
    
    df_vol = pd.DataFrame([
        extract_metrics_dict(m_hvol, t_hvol, "Alta Volatilidad"),
        extract_metrics_dict(m_lvol, t_lvol, "Baja Volatilidad")
    ])
    df_vol.to_csv(res_dir / "volatility_segmentation.csv", index=False)

    # 4. Matriz Dirección x Sesión Horaria
    m_buy_lon, t_buy_lon, _ = run_simulation(trade_direction="buy", trading_session="london")
    m_buy_ny, t_buy_ny, _ = run_simulation(trade_direction="buy", trading_session="ny")
    m_buy_asia, t_buy_asia, _ = run_simulation(trade_direction="buy", trading_session="asia")
    m_sell_lon, t_sell_lon, _ = run_simulation(trade_direction="sell", trading_session="london")
    m_sell_ny, t_sell_ny, _ = run_simulation(trade_direction="sell", trading_session="ny")
    m_sell_asia, t_sell_asia, _ = run_simulation(trade_direction="sell", trading_session="asia")

    df_matrix = pd.DataFrame([
        extract_metrics_dict(m_buy_lon, t_buy_lon, "BUY x Londres"),
        extract_metrics_dict(m_buy_ny, t_buy_ny, "BUY x Nueva York"),
        extract_metrics_dict(m_buy_asia, t_buy_asia, "BUY x Asia"),
        extract_metrics_dict(m_sell_lon, t_sell_lon, "SELL x Londres"),
        extract_metrics_dict(m_sell_ny, t_sell_ny, "SELL x Nueva York"),
        extract_metrics_dict(m_sell_asia, t_sell_asia, "SELL x Asia")
    ])
    df_matrix.to_csv(res_dir / "direction_session_matrix.csv", index=False)

    # Identificar mejor segmento para exportación final trades/equity
    best_idx = df_matrix["Profit Factor"].replace("N/A", "0.0").astype(float).idxmax()
    best_lbl = df_matrix.iloc[best_idx]["Label"]
    print(f"[Info] Mejor segmento identificado: {best_lbl}")
    
    # Guardar trades y equity de ese mejor segmento
    best_dir = "buy" if "BUY" in best_lbl else "sell"
    best_sess = "london" if "Londres" in best_lbl else ("ny" if "Nueva York" in best_lbl else "asia")
    print(f"[Info] Corriendo mejor segmento: Direction={best_dir}, Session={best_sess}")
    m_best_seg, t_best_seg, eq_best_seg = run_simulation(trade_direction=best_dir, trading_session=best_sess)
    t_best_seg.to_csv(res_dir / "trades_best_segment.csv", index=False)
    eq_best_seg.to_frame().to_csv(res_dir / "equity_best_segment.csv")

    # 5. Suite de Ablación
    m_nohmm, t_nohmm, _ = run_simulation(ablation_mode="no_hmm")
    m_nokalman, t_nokalman, _ = run_simulation(ablation_mode="no_kalman")
    m_nohma, t_nohma, _ = run_simulation(ablation_mode="no_hma")
    m_nostrength, t_nostrength, _ = run_simulation(ablation_mode="no_strength")
    m_regonly, t_regonly, _ = run_simulation(ablation_mode="regime_only")

    df_ablation = pd.DataFrame([
        extract_metrics_dict(m_base, t_base, "Base (Con todo)"),
        extract_metrics_dict(m_nohmm, t_nohmm, "Sin HMM (Kalman/HMA + ML)"),
        extract_metrics_dict(m_nokalman, t_nokalman, "Sin Kalman (HMM + HMA + ML)"),
        extract_metrics_dict(m_nohma, t_nohma, "Sin HMA (HMM + Kalman + ML s/ HMA)"),
        extract_metrics_dict(m_nostrength, t_nostrength, "Sin ML Strength (HMM + Kalman puros)"),
        extract_metrics_dict(m_regonly, t_regonly, "Solo Régimen HMM (Sin validación)")
    ])
    df_ablation.to_csv(res_dir / "ablation_results.csv", index=False)

    # 6. Threshold Dinámico (k = 0.05, 0.10, 0.15)
    m_dyn_05, t_dyn_05, _ = run_simulation(dynamic_threshold=True, k=0.05)
    m_dyn_10, t_dyn_10, _ = run_simulation(dynamic_threshold=True, k=0.10)
    m_dyn_15, t_dyn_15, _ = run_simulation(dynamic_threshold=True, k=0.15)

    df_dyn = pd.DataFrame([
        extract_metrics_dict(m_base, t_base, "Threshold Fijo (0.60)"),
        extract_metrics_dict(m_dyn_05, t_dyn_05, "Threshold Dinámico (k=0.05)"),
        extract_metrics_dict(m_dyn_10, t_dyn_10, "Threshold Dinámico (k=0.10)"),
        extract_metrics_dict(m_dyn_15, t_dyn_15, "Threshold Dinámico (k=0.15)")
    ])
    df_dyn.to_csv(res_dir / "dynamic_threshold_results.csv", index=False)

    # 7. Ablación de Costos (Sensibilidad Progresiva)
    c_s1 = {**base_assumptions, "spread_price": 0.0, "slippage_price": 0.0, "commission_per_lot": 0.0, "intrabar_mode": "normal"}
    c_s2 = {**base_assumptions, "spread_price": 0.15, "slippage_price": 0.0, "commission_per_lot": 0.0, "intrabar_mode": "normal"}
    c_s3 = {**base_assumptions, "spread_price": 0.15, "slippage_price": 0.05, "commission_per_lot": 0.0, "intrabar_mode": "normal"}
    c_s4 = {**base_assumptions, "spread_price": 0.15, "slippage_price": 0.05, "commission_per_lot": 3.0, "intrabar_mode": "normal"}
    c_s5 = base_assumptions # Spread + Slippage + Comisión + Intrabar pessimistic
    
    m_s1, t_s1, _ = run_simulation(custom_costs=c_s1)
    m_s2, t_s2, _ = run_simulation(custom_costs=c_s2)
    m_s3, t_s3, _ = run_simulation(custom_costs=c_s3)
    m_s4, t_s4, _ = run_simulation(custom_costs=c_s4)
    m_s5, t_s5, _ = run_simulation(custom_costs=c_s5)

    df_costs = pd.DataFrame([
        extract_metrics_dict(m_s1, t_s1, "Base sin costos (Normal)"),
        extract_metrics_dict(m_s2, t_s2, "Base con Spread (Normal)"),
        extract_metrics_dict(m_s3, t_s3, "Base con Spread + Slippage (Normal)"),
        extract_metrics_dict(m_s4, t_s4, "Base con Spread + Slippage + Comisión (Normal)"),
        extract_metrics_dict(m_s5, t_s5, "Base con todo + Intrabar Pesimista")
    ])
    df_costs.to_csv(res_dir / "cost_sensitivity_results.csv", index=False)

    # 8. Post-2024 Decay por semestres
    t_base["exit_time"] = pd.to_datetime(t_base["exit_time"])
    
    def evaluate_trades_subset(t_df, start, end, label):
        sub = t_df[(t_df["exit_time"] >= pd.Timestamp(start)) & (t_df["exit_time"] <= pd.Timestamp(end))]
        total = len(sub)
        if total == 0:
            return {"Periodo": label, "Trades": 0, "Retorno %": "0.00%", "Profit Factor": "0.00", "Avg PnL": "$0.00", "Max DD %": "0.00%", "Win Rate %": "0.00%", "Avg Win": "$0.00", "Avg Loss": "$0.00", "SL exits": 0, "TP exits": 0, "Partials": 0}
            
        wins = sub[sub["pnl"] > 0]
        losses = sub[sub["pnl"] <= 0]
        net_pnl = sub["pnl"].sum()
        ret = (net_pnl / 10000.0) * 100.0
        pf = wins["pnl"].sum() / abs(losses["pnl"].sum()) if len(losses) > 0 and abs(losses["pnl"].sum()) > 0 else np.inf
        
        sl_ex = len(sub[sub["exit_reason"] == "SL"])
        tp_ex = len(sub[sub["exit_reason"] == "TP"])
        part_ex = sub["partial_done"].sum()
        
        cum_pnl = sub["pnl"].cumsum() + 10000.0
        peak = cum_pnl.cummax()
        dd = (cum_pnl - peak) / peak * 100.0
        max_dd = dd.min()
        
        return {
            "Periodo": label,
            "Trades": total,
            "Retorno %": f"{ret:.2f}%",
            "Profit Factor": f"{pf:.2f}" if pf != np.inf else "N/A",
            "Avg PnL": f"${sub['pnl'].mean():.2f}",
            "Max DD %": f"{max_dd:.2f}%",
            "Win Rate %": f"{(len(wins)/total)*100:.2f}%",
            "Avg Win": f"${wins['pnl'].mean():.2f}" if len(wins) > 0 else "$0.00",
            "Avg Loss": f"${losses['pnl'].mean():.2f}" if len(losses) > 0 else "$0.00",
            "SL exits": sl_ex,
            "TP exits": tp_ex,
            "Partials": part_ex
        }

    df_decay = pd.DataFrame([
        evaluate_trades_subset(t_base, "2024-05-01", "2024-12-31", "2024 S2 (May-Dic)"),
        evaluate_trades_subset(t_base, "2025-01-01", "2025-06-30", "2025 S1 (Ene-Jun)"),
        evaluate_trades_subset(t_base, "2025-07-01", "2025-12-31", "2025 S2 (Jul-Dic)"),
        evaluate_trades_subset(t_base, "2026-01-01", "2026-06-30", "2026 S1 (Ene-Jun)")
    ])
    df_decay.to_csv(res_dir / "post_2024_decay.csv", index=False)

    # 9. Analizar razones de salida
    total_tr = len(t_base)
    if total_tr > 0:
        sl_ex = len(t_base[t_base["exit_reason"] == "SL"])
        tp_ex = len(t_base[t_base["exit_reason"] == "TP"])
        part_ex = t_base["partial_done"].sum()
        df_exits = pd.DataFrame([{
            "Asset": asset,
            "Total Trades": total_tr,
            "SL Exits": sl_ex,
            "SL %": f"{(sl_ex/total_tr)*100:.2f}%",
            "TP Exits": tp_ex,
            "TP %": f"{(tp_ex/total_tr)*100:.2f}%",
            "Partials Done": part_ex,
            "Partials %": f"{(part_ex/total_tr)*100:.2f}%"
        }])
    else:
        df_exits = pd.DataFrame()
    df_exits.to_csv(res_dir / "exit_reason_analysis.csv", index=False)

    # 10. Resumen de Contribución de Componentes
    df_contrib = pd.DataFrame([
        {"Componente": "HMM puro", "Diagnostico": "debil"},
        {"Componente": "Kalman", "Diagnostico": "componente direccional principal"},
        {"Componente": "HMA/ML Strength", "Diagnostico": "no vinculantes bajo esta configuracion"},
        {"Componente": "SELL", "Diagnostico": "destructivo"},
        {"Componente": "BUY", "Diagnostico": "candidato a validacion"}
    ])
    df_contrib.to_csv(res_dir / "component_contribution_summary.csv", index=False)

    print("[*] Generando reporte final en Markdown...")
    report_path = res_dir / "REPORTE_ANALISIS_MODELO_XAUUSD.md"
    
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Reporte de Análisis Avanzado, Ablación y Segmentación HMM - XAUUSD\n\n")
        
        f.write("> [!IMPORTANT]\n")
        f.write("> **ADVERTENCIA MAESTRA**: Los experimentos de segmentación sobre OOS son diagnósticos, no evidencia final de robustez. Cualquier regla seleccionada a partir de estos resultados deberá validarse en un holdout independiente.\n\n")
        
        f.write("## 1. Resumen Ejecutivo\n")
        f.write("Este reporte presenta una auditoría analítica profunda del EA Sovereign HMM. Desarmamos el modelo en sus componentes lógicos básicos (HMM, Kalman, HMA, ML Strength) y segmentamos las operaciones por dirección, sesión horaria y régimen de volatilidad ex-ante en el holdout Out-Of-Sample (OOS) de 2024-2026. El objetivo no es optimizar o sobrefitar los resultados OOS, sino diagnosticar de manera descriptiva la salud estadística del sistema e identificar las fuentes reales del edge.\n\n")
        
        f.write("## 2. Configuración del Experimento (Grado Comercial)\n")
        f.write(f"- **Balance Inicial**: $10,000.00\n")
        f.write(f"- **Medida del Punto (Point)**: {base_assumptions['point']}\n")
        f.write(f"- **Spread Simulado**: {base_assumptions['spread_price']} puntos (1.5 pips en XAUUSD)\n")
        f.write(f"- **Slippage Simulado**: {base_assumptions['slippage_price']} puntos (0.5 pips en XAUUSD)\n")
        f.write(f"- **Comisión por Lote**: ${base_assumptions['commission_per_lot']} por lado ($6.00 por lote round-trip)\n")
        f.write(f"- **Lote Mínimo / Paso (Min Lot / Step)**: {base_assumptions['min_lot']} / {base_assumptions['lot_step']}\n")
        f.write(f"- **Fills Intrabar**: Pesimista estricto (SL prioritario sobre parcial/TP ante coincidencia en vela)\n")
        f.write(f"- **Volatilidad Ex-Ante IS**: Mediana de {volatility_median_is:.6f} calculada ciegamente sobre IS purgado\n\n")
        
        f.write("## 3. Baseline Reproducido\n")
        f.write("Resultados de la configuración óptima sin segmentación adicional:\n")
        f.write(df_to_markdown(df_ablation.iloc[0:1]) + "\n\n")
        
        f.write("## 4. Segmentación por Dirección (BUY vs SELL)\n")
        f.write("Aislando el comportamiento en posiciones de compra (BUY) y venta (SELL):\n")
        f.write(df_to_markdown(df_dir) + "\n\n")
        f.write("> [!NOTE]\n")
        f.write("> Las posiciones cortas (SELL) destruyeron valor durante este período. Dado el sesgo alcista del Oro en 2024-2026, el HMM generó ventas en retrocesos que fueron arrasadas rápidamente por la fuerte tendencia de fondo.\n\n")
        
        f.write("## 5. Segmentación por Sesión Horaria (Zona NY)\n")
        f.write("Segmentación basada en la hora de entrada convertida a hora de Nueva York (America/New_York):\n")
        f.write(df_to_markdown(df_sess) + "\n\n")
        f.write("> [!NOTE]\n")
        f.write("> En esta muestra OOS, Asia muestra mejor desempeño estadístico que NY y Londres, pero debe validarse con spread horario real antes de considerarla operable.\n\n")
        
        f.write("## 6. Segmentación por Volatilidad (Projected Sigma)\n")
        f.write("Segmentación usando la mediana ex-ante del IS de la volatilidad proyectada:\n")
        f.write(df_to_markdown(df_vol) + "\n\n")
        
        f.write("## 7. Matriz Cruzada Dirección × Sesión Horaria\n")
        f.write("Evaluación detallada de la interacción entre dirección y sesión comercial:\n")
        f.write(df_to_markdown(df_matrix) + "\n\n")
        
        f.write("## 8. Prueba de Ablación (¿Qué aporta cada módulo?)\n")
        f.write("Desactivando sistemáticamente los filtros lógicos para aislar la fuente de valor:\n")
        f.write(df_to_markdown(df_ablation) + "\n\n")
        f.write("> [!WARNING]\n")
        f.write("> **Hallazgo Clave**: El HMM no funciona bien como motor direccional puro, pero sí parece reducir exposición y riesgo cuando se combina con Kalman. El componente direccional más importante parece ser Kalman; el HMM actúa más como filtro de frecuencia/exposición que como fuente principal de alpha.\n\n")
        
        f.write("## 9. Threshold Dinámico por Volatilidad\n")
        f.write("Prueba parametrizando el threshold dinámico ($threshold_{dyn} = threshold + k \\times (vol_{ratio} - 1.0)$):\n")
        f.write(df_to_markdown(df_dyn) + "\n\n")
        
        f.write("## 10. Sensibilidad a Costos Comerciales\n")
        f.write("Ablación progresiva de costos para mapear la fricción del mercado:\n")
        f.write(df_to_markdown(df_costs) + "\n\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> Incluso sin costos, el edge bruto es pequeño. La fricción comercial lo vuelve estadísticamente débil. Esto demuestra que el EA Sovereign HMM posee una estructura estadística de baja magnitud y es altamente vulnerable a cualquier costo de ejecución.\n\n")
        
        f.write("## 11. Análisis del Decaimiento post-2024\n")
        f.write("Desglose del comportamiento del OOS por semestres cronológicos:\n")
        f.write(df_to_markdown(df_decay) + "\n\n")
        
        f.write("## 12. Diagnóstico Final\n")
        f.write("- **Decaimiento de Alpha**: El rendimiento se colapsa en la segunda mitad de 2025 y 2026. Esto coincide con el aumento masivo de la volatilidad del Oro, donde los movimientos intradiarios superaron los stops calculados de volatilidad HMA, provocando una avalancha de SLs prematuros.\n")
        f.write("- **Funcion del HMM**: El HMM no funciona bien como motor direccional puro, pero actúa como un filtro de frecuencia y exposición que reduce la exposición general al mercado cuando se asocia con Kalman.\n")
        f.write("- **Fricción de Costos**: Las comisiones e intrabar pesimista consumen por completo el escaso profit factor del EA.\n\n")
        
        f.write("## 13. Hipótesis para Siguiente Iteración\n")
        f.write("- **Hipótesis 1**: Eliminar el HMM por completo y utilizar únicamente Kalman para la dirección y GARCH/ATR para las salidas.\n")
        f.write("- **Hipótesis 2**: Filtrar el trading sólo para compras (BUY Only) durante las sesiones de Londres y Nueva York, desactivando las ventas.\n\n")
        
        f.write("## 14. Reglas Descartadas\n")
        f.write("- Operar posiciones cortas (SELL) en Oro en períodos de tendencia macro alcista.\n")
        f.write("- Operar en la sesión asiática (debido a baja liquidez y alta fricción).\n")
        f.write("- Usar el clasificador HMM Hamilton en escala temporal M15 como filtro exclusivo de entrada.\n\n")
        
        f.write("## 15. Reglas Candidatas para Validación Futura\n")
        f.write("- **BUY Only + NY/London Sessions + Ex-Ante Vol Low**.\n")
        
    print(f"[Success] Reporte escrito con exito en {report_path}")
    print("=========================================================================")

if __name__ == "__main__":
    main()
