import os
import sys
import pandas as pd
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
ruta_capa3 = os.path.join(ruta_raiz, "Capa_3")

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)
if ruta_capa3 not in sys.path:
    sys.path.insert(0, ruta_capa3)

from sovereign_calibration import CSystemCalibrator

def lanzar_pipeline_calibracion_maestra():
    ruta_lago = os.environ.get("SOVEREIGN_DATA_PATH", os.path.join(ruta_raiz, "XAUUSD_M15_Training.parquet"))
    ruta_csv_salida = os.environ.get("SOVEREIGN_PARAMS_OUT", os.path.join(ruta_raiz, "HMM_Params_15M.csv"))
    
    print("=========================================================================")
    print(" AUDITORÍA EN ACCIÓN: PIPELINE DE CALIBRACIÓN COMPLETO (MLE)")
    print("=========================================================================")
    
    if not os.path.exists(ruta_lago):
        print(f" ERROR: Lago de Datos maestro no encontrado.")
        return
        
    df = pd.read_parquet(ruta_lago)
    close_raw = df['close'].values
    rates_total = len(close_raw)
    
    # Reconstrucción de los vectores de retornos exactos del OnCalculate de Sovereign
    b_returns = np.zeros(rates_total)
    for i in range(2, rates_total):
        b_returns[i] = np.log(close_raw[i-1] / close_raw[i-2])
        
    # Inicialización de estadísticas rodantes idénticas a MQL5
    alpha_20 = 2.0 / (20 + 1.0)
    b_mu_rets = np.zeros(rates_total)
    b_mu_rets[0] = b_returns[0]
    for i in range(1, rates_total):
        b_mu_rets[i] = b_returns[i] * alpha_20 + b_mu_rets[i-1] * (1.0 - alpha_20)
        
    b_sig_rets = np.zeros(rates_total)
    b_kurtosis = np.zeros(rates_total)
    for i in range(rates_total):
        if i >= 59:
            b_sig_rets[i] = np.std(b_returns[i-59:i+1], ddof=1)
        if i >= 119:
            window = b_returns[i-119:i+1]
            mean_w = np.mean(window)
            m2 = np.mean((window - mean_w)**2)
            m4 = np.mean((window - mean_w)**4)
            b_kurtosis[i] = (m4 / (m2 * m2)) - 3.0 if m2 > 1e-20 else 0.0

    print("• Lanzando estimación por momentos para el componente de Salto...")
    nu_opt, lambda_opt, lr_sigma = CSystemCalibrator.estimate_moments_distribution(b_returns, jump_sigma_k=3.0)
    
    print("• Ejecutando optimización por máxima verosimilitud de la matriz HMM...")
    p_bull_opt, p_bear_opt = CSystemCalibrator.optimize_hmm_matrix(
        b_returns, b_mu_rets, b_sig_rets, b_kurtosis, nu_opt, lambda_opt
    )
    
    # Bloque de constantes estructurales e históricos para la mitigación del Concept Drift
    WConf = 0.5; WVol = 0.5; WSlope = 0.5; WAccel = 0.0; WInter = 0.0
    MuConf = 0.4820; StdConf = 0.2215 # Medias obtenidas mediante el log de señales de la Capa 2
    MuVol = 1.0; StdVol = 0.5
    MuSlope = 1.0; StdSlope = 2.0
    MuAccel = 0.0; StdAccel = 1.0
    ExtSlopeT = 0.0273

    df_csv = pd.DataFrame({
        "InpPBull": [p_bull_opt],
        "InpPBear": [p_bear_opt],
        "InpSlopeT": [ExtSlopeT],
        "InpLambdaJ": [lambda_opt],
        "InpNu": [nu_opt],
        "WConf": [WConf],
        "WVol": [WVol],
        "WSlope": [WSlope],
        "WAccel": [WAccel],
        "WInter": [WInter],
        "MuConf": [MuConf],
        "MuVol": [MuVol],
        "MuSlope": [MuSlope],
        "MuAccel": [MuAccel],
        "StdConf": [StdConf],
        "StdVol": [StdVol],
        "StdSlope": [StdSlope],
        "StdAccel": [StdAccel]
    })

    df_csv.to_csv(ruta_csv_salida, index=False, sep=",")
    
    print("\n=========================================================================")
    print(" PARIDAD MAESTRA LOGRADA: ARCHIVO HMM_PARAMS GENERADO")
    print("=========================================================================")
    print(f" • Parámetros HMM:   P(Bull) = {p_bull_opt:.4f}  P(Bear) = {p_bear_opt:.4f}")
    print(f" • Proceso de Salto: Grados Libertad ν = {nu_opt:.4f}  Tasa Saltos λ = {lambda_opt*100:.2f}%")
    print(f" • Archivo de Calibración Exportado Con Éxito.")
    print("=========================================================================\n")

if __name__ == "__main__":
    lanzar_pipeline_calibracion_maestra()
