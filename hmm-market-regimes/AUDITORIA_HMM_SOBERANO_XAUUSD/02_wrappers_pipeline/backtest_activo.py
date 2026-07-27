import os
import sys
import pandas as pd
import numpy as np

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#Resolver rutas para importar del proyecto principal
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, "..", ".."))

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

from Capa_4.backtest_metrics import BacktestAssumptions, run_backtest, compute_backtest_metrics

def ejecutar_backtest_activo(
    ruta_signals: str,
    asset_name: str,
    point: float = 0.01,
    tick_size: float = 0.01,
    tick_value: float = 1.0,
    spread_price: float = 0.0,
    slippage_price: float = 0.0,
    initial_balance: float = 10000.0,
    min_strength: float = 0.35,
    vol_multiplier: float = 2.5,
    reward_risk: float = 2.0,
    use_partials: bool = True,
    commission_per_lot: float = 0.0,
    min_lot: float = 0.01,
    lot_step: float = 0.01,
    intrabar_mode: str = "pessimistic",
    dsr_trials: int = 1,
    ruta_salida_reporte: str = None
) -> dict:
    """
    Capa 4: Simula el backtest del EA Sovereign para el activo especificado.
    Genera un reporte final en Markdown con métricas de robustez.
    """
    print("=========================================================================")
    print(f" CAPA 4: SIMULACIÓN DE BACKTEST Y MÉTRICAS - {asset_name.upper()}")
    print("=========================================================================")
    
    if not os.path.exists(ruta_signals):
        raise FileNotFoundError(f"Archivo de señales no encontrado: {ruta_signals}")
        
    df_signals = pd.read_csv(ruta_signals, index_col=0, parse_dates=True)
    
    assumptions = BacktestAssumptions(
        initial_balance=initial_balance,
        risk_percent=1.0,
        min_strength=min_strength,
        vol_multiplier=vol_multiplier,
        reward_risk=reward_risk,
        use_partials=use_partials,
        max_lot=10.0,
        point=point,
        tick_size=tick_size,
        tick_value=tick_value,
        spread_price=spread_price,
        slippage_price=slippage_price,
        periods_per_year=24 * 4 * 252, # M15 candles per year
        commission_per_lot=commission_per_lot,
        min_lot=min_lot,
        lot_step=lot_step,
        intrabar_mode=intrabar_mode,
    )
    
    print(f"• Cargadas {len(df_signals)} barras con señales de inferencia HMM.")
    print("• Ejecutando motor de backtest comercial...")
    
    trades, cashflows, equity = run_backtest(df_signals, assumptions)
    metrics = compute_backtest_metrics(trades, cashflows, equity, assumptions, dsr_trials=dsr_trials)
    
    print(f"• Total operaciones cerradas: {metrics['closed_trades']}")
    print(f"• Retorno Neto: ${metrics['net_profit']:.2f} ({metrics['total_return_pct']:.2f}%)")
    print(f"• Profit Factor: {metrics['profit_factor']:.2f}")
    print(f"• Sharpe Ratio Anualizado: {metrics['sharpe_ratio']:.2f}")
    print(f"• Drawdown Máximo: ${abs(metrics['max_drawdown_money']):.2f} ({metrics['max_drawdown_pct']:.2f}%)")
    print(f"• Ratio de Recuperación (Recovery Factor): {metrics['recovery_factor']:.2f}")
    
    # Generar reporte Markdown
    if not ruta_salida_reporte:
        dir_resultados = os.path.abspath(os.path.join(ruta_actual, "..", "resultados"))
        os.makedirs(dir_resultados, exist_ok=True)
        ruta_salida_reporte = os.path.join(dir_resultados, f"REPORTE_ROBUSTEZ_{asset_name.upper()}.md")
        
    with open(ruta_salida_reporte, "w", encoding="utf-8") as f:
        f.write(f"# Reporte de Robustez y Backtest HMM - {asset_name.upper()}\n\n")
        f.write(f"### Supuestos de Mercado y Configuración\n")
        f.write(f"- **Balance Inicial**: ${initial_balance:,.2f}\n")
        f.write(f"- **Medida del Punto (Point)**: {point}\n")
        f.write(f"- **Tamaño de Tick**: {tick_size}\n")
        f.write(f"- **Valor de Tick**: ${tick_value}\n")
        f.write(f"- **Spread Simulado**: {spread_price} pips/points\n")
        f.write(f"- **Multiplicador de Stop (Vol)**: {vol_multiplier}x\n")
        f.write(f"- **Ratio de Riesgo/Beneficio**: 1:{reward_risk}\n")
        f.write(f"- **Uso de Cierres Parciales**: {'Sí (70% parcial + breakeven)' if use_partials else 'No'}\n\n")
        
        f.write("### Métricas Clave de Desempeño\n")
        f.write(" Métrica  Valor \n")
        f.write(" ---  --- \n")
        f.write(f" **Balance Final**  ${metrics['final_balance']:,.2f} \n")
        f.write(f" **Retorno Neto**  ${metrics['net_profit']:,.2f} ({metrics['total_return_pct']:.2f}%) \n")
        f.write(f" **Operaciones Totales**  {metrics['closed_trades']} \n")
        f.write(f" **Win Rate**  {metrics['win_rate_pct']:.2f}% \n")
        f.write(f" **Loss Rate**  {metrics['loss_rate_pct']:.2f}% \n")
        f.write(f" **Profit Factor**  {metrics['profit_factor']:.2f} \n")
        f.write(f" **Payoff Ratio**  {metrics['payoff_ratio']:.2f} \n")
        f.write(f" **Esperanza Matemática**  ${metrics['expectancy']:.2f} \n")
        f.write(f" **Drawdown Máximo (Dinero)**  -${abs(metrics['max_drawdown_money']):,.2f} \n")
        f.write(f" **Drawdown Máximo (%)**  {metrics['max_drawdown_pct']:.2f}% \n")
        f.write(f" **Sharpe Ratio Anualizado**  {metrics['sharpe_ratio']:.2f} \n")
        f.write(f" **Sortino Ratio Anualizado**  {metrics['sortino_ratio']:.2f} \n")
        f.write(f" **Ratio de Recuperación**  {metrics['recovery_factor']:.2f} \n")
        f.write(f" **Rachas Máximas (Ganadoras/Perdedoras)**  {metrics['max_consecutive_wins']} / {metrics['max_consecutive_losses']} \n")
        
    out_dir = os.path.dirname(ruta_salida_reporte)
    trades.to_csv(os.path.join(out_dir, f"trades_{asset_name[-3:]}.csv"), index=False)
    cashflows.to_csv(os.path.join(out_dir, f"cashflows_{asset_name[-3:]}.csv"), index=False)
    equity.to_csv(os.path.join(out_dir, f"equity_{asset_name[-3:]}.csv"), index=True)
    pd.DataFrame([metrics]).to_csv(os.path.join(out_dir, f"metrics_{asset_name[-3:]}.csv"), index=False)
        
    print(" CAPA 4 COMPLETADA")
    print(f" • Reporte escrito en: {ruta_salida_reporte}")
    print("=========================================================================\n")
    return metrics

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ejecutar_backtest_activo(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python backtest_activo.py <ruta_signals> <nombre_activo>")
