import numpy as np
import pandas as pd

def calcular_catsmom_factor(signals, corr_matrix, epsilon=0.1):
    """
    Calcula el multiplicador CATSMOM de ajuste por correlación CF_t.
    signals: dict o Series con las señales de cada activo {ticker: signal}
    corr_matrix: DataFrame (correlation matrix) de los activos activos
    epsilon: regularizador numérico para evitar singularidad
    """
    active_tickers = list(signals.keys())
    N_t = len(active_tickers)
    if N_t <= 1:
        return 1.0
        
    # Calcular la correlación firmada promedio de la cartera
    # rho_bar = [2 / (N_t * (N_t - 1))] * sum_{i < j} X_i * X_j * rho_{i, j}
    signed_corr_sum = 0.0
    count = 0
    
    for i in range(N_t):
        ticker_i = active_tickers[i]
        sig_i = signals[ticker_i]
        for j in range(i + 1, N_t):
            ticker_j = active_tickers[j]
            sig_j = signals[ticker_j]
            
            # Obtener correlación entre i y j
            if ticker_i in corr_matrix.index and ticker_j in corr_matrix.columns:
                rho = corr_matrix.loc[ticker_i, ticker_j]
                if not pd.isna(rho):
                    signed_corr_sum += sig_i * sig_j * rho
                    count += 1
                    
    if count == 0:
        return 1.0
        
    rho_bar = signed_corr_sum / count
    
    # CF_t = clip( sqrt( N_t / max(1 + (N_t - 1)*rho_bar, 0.1) ), 0.5, 2.0 )
    denominator = max(1.0 + (N_t - 1) * rho_bar, 0.1)
    cf_t = np.sqrt(N_t / denominator)
    cf_t = np.clip(cf_t, 0.5, 2.0)
    
    return cf_t

def calcular_floor_causal(vols_ratio_history, date, window=252):
    """
    Calcula el floor causal delta_{min, t} basado en la historia retrospectiva.
    vols_ratio_history: lista o Serie con la suma histórica de X_j / sigma_j,diaria
    date: fecha actual (para asegurar causalidad)
    window: ventana retrospectiva
    """
    if len(vols_ratio_history) <= 1:
        return 0.1 # valor inicial por defecto
        
    # Tomar la ventana retrospectiva (hasta t-1)
    history = vols_ratio_history[:-1][-window:]
    mean_val = np.mean(history)
    
    # delta_min = 0.1 * mean(sum X_j / sigma_j,diaria)
    return 0.1 * mean_val
