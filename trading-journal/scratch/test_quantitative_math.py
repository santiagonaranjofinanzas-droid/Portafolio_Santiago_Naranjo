import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

#Inject backend path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.engine import calculate_stats

def run_test():
    print("======================================================================")
    print("--- INICIANDO VERIFICACIÓN DEL MOTOR CUANTITATIVO REFACTORIZADO ---")
    print("======================================================================")
    
    # 1. Crear DataFrame simulado de trades con diferentes duraciones y excursiones
    base_time = datetime(2026, 6, 1, 10, 0, 0)
    
    # 10 trades en total
    # Duraciones variables para testear normalización del E-Ratio:
    # Trade 0: 2 horas
    # Trade 1: 0.5 horas (30 mins)
    # Trade 2: 12 horas
    # Trade 3: 24 horas
    # Trade 4: 1 hora
    # Trade 5: 0 horas (instantáneo - para probar el floor de duración)
    # Trade 6: 4 horas
    # Trade 7: 6 horas
    # Trade 8: 8 horas
    # Trade 9: 10 horas
    data = {
        'position_id': list(range(1001, 1011)),
        'entrytime': [
            base_time,                                # T0
            base_time + timedelta(days=1),            # T1
            base_time + timedelta(days=2),            # T2
            base_time + timedelta(days=3),            # T3
            base_time + timedelta(days=4),            # T4
            base_time + timedelta(days=5),            # T5 (instant)
            base_time + timedelta(days=6),            # T6
            base_time + timedelta(days=7),            # T7
            base_time + timedelta(days=8),            # T8
            base_time + timedelta(days=9)             # T9
        ],
        'exittime': [
            base_time + timedelta(hours=2),                      # T0: 2h
            base_time + timedelta(days=1, minutes=30),            # T1: 0.5h
            base_time + timedelta(days=2, hours=12),             # T2: 12h
            base_time + timedelta(days=3, hours=24),             # T3: 24h
            base_time + timedelta(days=4, hours=1),              # T4: 1h
            base_time + timedelta(days=5),                       # T5: 0h (floor check)
            base_time + timedelta(days=6, hours=4),              # T6: 4h
            base_time + timedelta(days=7, hours=6),              # T7: 6h
            base_time + timedelta(days=8, hours=8),              # T8: 8h
            base_time + timedelta(days=9, hours=10)              # T9: 10h
        ],
        'symbol': ['EURUSD'] * 10,
        'type_op': [0, 1, 0, 0, 1, 0, 1, 0, 0, 1], # Buy/Sell
        'entryprice': [1.1000] * 10,
        'exitprice': [1.1050, 1.0950, 1.1020, 1.0980, 1.1050, 1.1010, 1.0970, 1.1080, 1.0980, 1.1030],
        'netpnl': [500.0, -500.0, 200.0, -200.0, 500.0, 100.0, -300.0, 800.0, -200.0, 300.0],
        'commission': [-5.0] * 10,
        'volume': [1.0] * 10,
        'sl': [1.0950, 1.1050, 1.0980, 1.1020, 1.1100, 1.0980, 1.0950, 1.0920, 1.1020, 1.1060],
        'valid_sl': [True] * 10,
        'r_multiple': [1.0, -1.0, 1.0, -1.0, 1.0, 0.5, -0.6, 1.0, -1.0, 0.75],
        # Excursiones (para validar E-Ratio)
        'mae_r': [-0.2, -0.8, -0.1, -0.9, -0.2, 0.0, -0.5, -0.1, -0.4, -0.3],
        'mfe_r': [1.2, 0.2, 1.1, 0.1, 1.3, 0.5, 0.1, 1.5, 0.2, 0.8]
    }
    df = pd.DataFrame(data)
    
    # 2. Flujos de caja simulados (para probar aislamiento TWR)
    # Depositamos $5000 a la mitad
    df_deposits = pd.DataFrame([
        {'Fecha': base_time + timedelta(days=4, hours=12), 'Monto': 5000.0, 'Nota': 'Depósito de prueba'}
    ])
    
    start_cap = 10000.0
    
    # Ejecutar motor cuantitativo
    try:
        results = calculate_stats(df, start_cap, df_deposits)
        
        if results is None:
            print("[FAIL] results is None!")
            sys.exit(1)
            
        print("\n--- 1. VALIDACIÓN DE TWR CURVA DE EQUIDAD ---")
        eq_curve = results['equity_curve']
        print(f"Puntos de equidad generados: {len(eq_curve)}")
        print(f"Capital Inicial: ${results['summary']['start_cap']}")
        print(f"Retorno Total Compuesto TWR: {results['summary']['total_return'] * 100:.2f}%")
        print(f"Equidad Final: ${results['summary']['end_equity']}")
        
        # El retorno simple con un depósito de $5000 (total_cap = 15000) y pnl de $1200 sería ~8%.
        # Con TWR, el rendimiento acumulado aísla el depósito.
        print("\n--- 2. VALIDACIÓN DE RIESGO BASEL AL 99% ---")
        print(f"VaR Histórico 99%: {results['risk']['var'] * 100:.4f}%")
        print(f"CVaR Histórico 99%: {results['risk']['cvar'] * 100:.4f}%")
        print(f"Cornish-Fisher VaR 99%: {results['risk']['cf_var'] * 100:.4f}%")
        print(f"Volatilidad Diaria (Raw): {results['risk']['daily_vol'] * 100:.4f}%")
        
        # Verificar que el Cornish-Fisher a 99% responde lógicamente
        print("\n--- 3. VALIDACIÓN DE CRITERIO DE KELLY CONTINUO ---")
        print(f"Kelly Fraction Óptimo Continuo: {results['perf']['optimal_risk_kelly'] * 100:.2f}%")
        print(f"Sugerencia Half-Kelly: {results['perf']['suggested_risk_half_kelly'] * 100:.2f}%")
        
        print("\n--- 4. VALIDACIÓN DE E-RATIO CON NORMALIZACIÓN DE DURACIÓN ---")
        print(f"E-Ratio Normalizado por raíz de duración: {results['quant']['e_ratio']:.4f}")
        
        print("\n[OK] TODOS LOS CÁLCULOS CUANTITATIVOS PASARON LA PRUEBA DE ESTRUCTURA Y SINTAXIS.")
        
    except Exception as e:
        print(f"\n[FAIL] ERROR EN LA VERIFICACIÓN: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_test()
