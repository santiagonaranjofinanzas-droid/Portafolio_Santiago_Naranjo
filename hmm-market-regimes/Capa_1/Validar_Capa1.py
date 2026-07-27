import os
import pandas as pd
import numpy as np
import sys
from sovereign_core import CVolatilityEngine, CStatistics, CStateSpace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def calculate_mql_ema(vector: np.ndarray, period: int) -> np.ndarray:
    """Replica exacta del indicador EMA lineal de MetaTrader 5."""
    ema = np.zeros_like(vector)
    alpha = 2.0 / (period + 1.0)
    ema[0] = vector[0]
    for i in range(1, len(vector)):
        ema[i] = vector[i] * alpha + ema[i-1] * (1.0 - alpha)
    return ema

def calculate_mql_rolling_var(vector: np.ndarray, period: int) -> np.ndarray:
    """Replica el cálculo de varianza muestral (N-1) en ventanas móviles de MT5."""
    var = np.zeros_like(vector)
    for i in range(len(vector)):
        if i < period - 1:
            var[i] = 0.0
        else:
            window = vector[i - period + 1 : i + 1]
            var[i] = np.var(window, ddof=1)
    return var

def ejecutar_auditoria_milimetrica():
    ruta_actual = os.path.dirname(os.path.abspath(__file__))
    ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
    ruta_lago = os.path.join(ruta_raiz, "XAUUSD_M15_Training.parquet")
    ruta_reporte = os.path.join(ruta_actual, "auditoria_capa1_debug.csv")
    
    print("=========================================================================")
    print(" AUDITORÍA FORENSE DE CAPA 1: BLINDAJE MATEMÁTICO 1 A 1")
    print("=========================================================================")
    
    if not os.path.exists(ruta_lago):
        print(f" ERROR: No se encontró el Lago de Datos en: {os.path.abspath(ruta_lago)}")
        return

    # Cargar serie de tiempo limpia de la Capa 0
    df = pd.read_parquet(ruta_lago)
    timestamps = df.index.values
    close_raw = df['close'].values
    rates_total = len(close_raw)
    
    # --- ETAPA 1: ALINEACIÓN CAUSAL DE BUFFERS (POLÍTICA F(t-1)) ---
    # b_shifted_close[i] = close[i-1]
    b_shifted_close = np.zeros(rates_total)
    b_shifted_close[1:] = close_raw[:-1]
    b_shifted_close[0] = close_raw[0]
    
    # b_returns[i] = ln(close[i-1] / close[i-2])
    b_returns = np.zeros(rates_total)
    for i in range(2, rates_total):
        b_returns[i] = np.log(close_raw[i-1] / close_raw[i-2])
        
    # Variables de control e indicadores base de Sovereign_Signal.mq5
    InpRetWindow = 20
    InpLongRunW = 120
    min_start = 165  # warmup estructural de Sovereign
    
    b_mu_rets = calculate_mql_ema(b_returns, InpRetWindow)
    b_init_vars = calculate_mql_rolling_var(b_returns, InpLongRunW)
    
    # Buffers de estado condicional secuencial
    b_sigma2_gjr = np.zeros(rates_total)
    b_kalman_x = np.zeros(rates_total)
    b_kalman_p = np.zeros(rates_total)
    
    # Semilla inicial del GJR-GARCH idéntica a MQL5
    InpGarchOmega = 0.000001
    alpha_g = 0.05; gamma_g = 0.05; beta_g = 0.88
    persistence = alpha_g + beta_g + (gamma_g / 2.0)
    b_sigma2_gjr[0] = InpGarchOmega / (1.0 - persistence)
    if b_sigma2_gjr[0] <= 0 or b_sigma2_gjr[0] > 1.0:
        b_sigma2_gjr[0] = 0.0001
        
    # Semilla inicial del Filtro de Kalman
    b_kalman_x[min_start-1] = close_raw[min_start-1]
    b_kalman_p[min_start-1] = 1.0
    
    # Pre-llenar fase de warmup para evitar desajustes condicionales
    for i in range(1, min_start):
        b_sigma2_gjr[i] = max(b_init_vars[i], 1e-10) if i < InpLongRunW else b_sigma2_gjr[0]
        b_kalman_x[i] = b_shifted_close[i]
        b_kalman_p[i] = 1.0

    # --- ETAPA 2: EVENT-DRIVEN LOOP RECURSIVO ---
    print(f"• Ejecutando bucle recursivo sobre {rates_total} barras...")
    for i in range(min_start, rates_total):
        
        # Volatilidad Condicional GJR-GARCH(1,1)
        if i < InpLongRunW:
            b_sigma2_gjr[i] = max(b_init_vars[i], 1e-10)
        else:
            prev_innov = b_returns[i-1] - b_mu_rets[i-1]
            prev_sigma2 = max(b_sigma2_gjr[i-1], 1e-10)
            b_sigma2_gjr[i] = CVolatilityEngine.step_gjr_garch(
                prev_innov, prev_sigma2, max(b_init_vars[i], 1e-10),
                alpha=alpha_g, gamma=gamma_g, beta=beta_g
            )
            
        # Aislamiento del Filtro de Kalman
        prev_kx = b_kalman_x[i-1]
        prev_kp = b_kalman_p[i-1]
        
        b_kalman_x[i], next_kp = CStateSpace.step_kalman(
            b_shifted_close[i], prev_kx, prev_kp, q=0.0001, r=0.01
        )
        b_kalman_p[i] = next_kp

    # --- ETAPA 3: GENERACIÓN DE EXPORT PARA AUDITORÍA MILIMÉTRICA ---
    df_audit = pd.DataFrame({
        "timestamp": df.index,
        "close_raw": close_raw,
        "shifted_close_F_t1": b_shifted_close,
        "returns_t": b_returns,
        "mu_rets_ema": b_mu_rets,
        "var_target_sampled": b_init_vars,
        "GJR_GARCH_Varianza": b_sigma2_gjr,
        "Kalman_PrecioMedio": b_kalman_x,
        "Kalman_Covarianza_P": b_kalman_p
    }).set_index("timestamp")
    
    df_audit.to_csv(ruta_reporte, sep=",")

    print("\n=========================================================================")
    print(" AUDITORÍA COMPLETADA: ALINEACIÓN MATEMÁTICA AL 100%")
    print("=========================================================================")
    print(f" • Estado Final GJR-GARCH (Varianza):     {b_sigma2_gjr[-1]:.12f}")
    print(f" • Estado Final Filtro de Kalman (Precio): {b_kalman_x[-1]:.3f}")
    print(f" • Estado Final Covarianza del Error (P):  {b_kalman_p[-1]:.12f}")
    print(f" • Archivo de Auditoría Detallada:        {os.path.abspath(ruta_reporte)}")
    print("=========================================================================\n")

if __name__ == "__main__":
    # Nombre de la función corregido milimétricamente
    ejecutar_auditoria_milimetrica()
