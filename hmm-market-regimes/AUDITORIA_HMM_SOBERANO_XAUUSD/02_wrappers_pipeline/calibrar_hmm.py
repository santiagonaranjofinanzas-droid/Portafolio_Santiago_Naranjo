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

from Capa_3.sovereign_calibration import CSystemCalibrator

def calibrar_hmm_activo(ruta_lago: str, asset_name: str, ruta_salida: str = None) -> str:
    """
    Capa 3: Ejecuta estimación de momentos y optimización MLE para determinar los parámetros
    estructurales del HMM 30001 en el activo seleccionado.
    """
    print("=========================================================================")
    print(f" CAPA 3: CALIBRACIÓN DE PARÁMETROS HMM - {asset_name.upper()}")
    print("=========================================================================")
    
    if not os.path.exists(ruta_lago):
        raise FileNotFoundError(f"Lago de datos no encontrado: {ruta_lago}")
        
    df = pd.read_parquet(ruta_lago)
    close_raw = df['close'].values
    rates_total = len(close_raw)
    
    if rates_total < 200:
        raise ValueError(f"Datos insuficientes para calibrar ({rates_total} velas). Se necesitan al menos 200.")
        
    # Reconstrucción de los vectores de retornos exactos de OnCalculate
    b_returns = np.zeros(rates_total)
    for i in range(2, rates_total):
        b_returns[i] = np.log(close_raw[i-1] / close_raw[i-2])
        
    # Estadísticas rodantes alineadas con MQL5
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

    print("• Estimando distribución por momentos para la componente de saltos...")
    nu_opt, lambda_opt, lr_sigma = CSystemCalibrator.estimate_moments_distribution(b_returns, jump_sigma_k=3.0)
    
    print("• Optimizando matriz de transición HMM mediante máxima verosimilitud...")
    p_bull_opt, p_bear_opt = CSystemCalibrator.optimize_hmm_matrix(
        b_returns, b_mu_rets, b_sig_rets, b_kurtosis, nu_opt, lambda_opt
    )
    
    # Parámetros por defecto para mitigación de Concept Drift
    WConf = 0.5; WVol = 0.5; WSlope = 0.5; WAccel = 0.0; WInter = 0.0
    MuConf = 0.4820; StdConf = 0.2215
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

    if not ruta_salida:
        dir_resultados = os.path.abspath(os.path.join(ruta_actual, "..", "resultados"))
        os.makedirs(dir_resultados, exist_ok=True)
        ruta_salida = os.path.join(dir_resultados, f"HMM_Params_15M_{asset_name.upper()}.csv")
        
    df_csv.to_csv(ruta_salida, index=False, sep=",")
    
    print(f" CAPA 3 COMPLETADA")
    print(f" • Destino CSV:      {ruta_salida}")
    print(f" • Parámetros HMM:   P(Bull) = {p_bull_opt:.4f}  P(Bear) = {p_bear_opt:.4f}")
    print(f" • Proceso de Salto: Grados Libertad ν = {nu_opt:.4f}  Tasa Saltos λ = {lambda_opt*100:.2f}%")
    print("=========================================================================\n")
    return ruta_salida

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        calibrar_hmm_activo(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python calibrar_hmm.py <ruta_lago> <nombre_activo>")
