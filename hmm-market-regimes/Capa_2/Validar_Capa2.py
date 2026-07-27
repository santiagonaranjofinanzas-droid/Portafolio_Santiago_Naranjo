import os
import sys

import pandas as pd

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from Capa_2.sovereign_signal import run_sovereign_signal_engine


def ejecutar_simulacion_capa2():
    ruta_lago = os.path.join(ruta_raiz, "XAUUSD_M15_Training.parquet")
    ruta_params = os.path.join(ruta_raiz, "HMM_Params_15M.csv")
    ruta_reporte = os.path.join(ruta_actual, "auditoria_capa2_signals.csv")

    print("=========================================================================")
    print("CAPA 2: MOTOR SECUENCIAL SOVEREIGN SIGNAL")
    print("=========================================================================")

    if not os.path.exists(ruta_lago):
        print(f"ERROR: Lago de Datos no encontrado en: {ruta_lago}")
        return

    df = pd.read_parquet(ruta_lago)
    signals = run_sovereign_signal_engine(df, params_csv=ruta_params, point=0.01)
    signals.to_csv(ruta_reporte, sep=",")

    print(f"Barras procesadas: {len(signals)}")
    print(f"P(Bull) final: {signals['HMM_Prob_Bull'].iloc[-1]:.4f}")
    print(f"Regime final buffer 18: {int(signals['Regime_Buffer_18'].iloc[-1])}")
    print(f"Volatilidad proyectada final: {signals['Vol_Projected_Sigma'].iloc[-1] * 100:.4f}%")
    print(f"ML Strength final: {signals['ML_Master_Strength'].iloc[-1] * 100:.2f}%")
    print(f"Reporte: {ruta_reporte}")
    print("=========================================================================")


if __name__ == "__main__":
    ejecutar_simulacion_capa2()
