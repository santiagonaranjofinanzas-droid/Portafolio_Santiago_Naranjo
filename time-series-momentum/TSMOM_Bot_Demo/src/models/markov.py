import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM

#Clasificación de activos por sector para el modelo jerárquico
SECTOR_MAP = {
    # Sector 1: Riesgo Sistémico (Equities + G10 FX)
    "SPX500": 1, "NAS100": 1, "DJI30": 1, "GER30": 1, "EU50": 1, "UK100": 1, "JPN225": 1,
    "EURUSD": 1, "GBPUSD": 1, "AUDUSD": 1,
    # Sector 2: Energía y Materias Primas Cíclicas
    "Brent": 2, "WTI": 2, "GasNatural": 2, "Cobre": 2,
    "Maiz": 2, "Trigo": 2, "Soja": 2, "Cafe": 2, "Azucar": 2,
    # Sector 3: Refugio y Deflación
    "XAUUSD": 3, "XAGUSD": 3, "US10Y": 3, "BUND": 3,
    "USDCHF": 3, "USDJPY": 3
}

def estimar_regimen_volatilidad(retornos_hist, window=63, threshold_pct=0.8):
    """
    Capa 5 (Regímenes por volatilidad simple):
    Devuelve 1.0 si la volatilidad reciente de 63 días está por encima de su percentil 80 histórico,
    lo que indica régimen de alta volatilidad (crisis). De lo contrario devuelve 0.0.
    """
    if len(retornos_hist) < window * 2:
        return 0.0
        
    # Calcular la volatilidad rodante de 63 días de los retornos históricos
    returns_series = pd.Series(retornos_hist)
    vol_rodante = returns_series.rolling(window=window).std()
    
    # Volatilidad actual (última observación disponible)
    vol_actual = vol_rodante.iloc[-1]
    
    if pd.isna(vol_actual):
        return 0.0
        
    # Percentil 80 de la volatilidad histórica
    percentil_80 = vol_rodante.quantile(threshold_pct)
    
    # Si la volatilidad actual supera el percentil 80, estamos en crisis
    return 1.0 if vol_actual > percentil_80 else 0.0

def estimar_regimen_hmm(retornos_proxy, window=500):
    """
    Capa 5 (Regímenes por HMM de 2 estados):
    Entrena un HMM gaussiano de 2 estados sobre una ventana retrospectiva de retornos del proxy (e.g. SPX500).
    Devuelve la probabilidad filtrada del estado de alta volatilidad (crisis).
    """
    if len(retornos_proxy) < 100:
        return 0.0
        
    # Tomar la ventana retrospectiva (dinámica durante el warm-up inicial)
    actual_window = min(len(retornos_proxy), window)
    data = np.array(retornos_proxy[-actual_window:]).reshape(-1, 1)
    
    try:
        # Entrenar HMM de 2 estados
        model = GaussianHMM(n_components=2, covariance_type="full", n_iter=100, random_state=42)
        model.fit(data)
        
        # Identificar cuál estado es el de alta volatilidad (crisis)
        # Comparamos las covarianzas (varianzas de cada estado)
        var_state_0 = model.covars_[0][0][0]
        var_state_1 = model.covars_[1][0][0]
        
        high_vol_state = 1 if var_state_1 > var_state_0 else 0
        
        # Obtener las probabilidades de estado actuales (posteriores/filtradas)
        state_probs = model.predict_proba(data)
        prob_crisis = state_probs[-1, high_vol_state]
        
        return prob_crisis
    except Exception:
        # Fallback si falla la convergencia de EM
        return 0.0

def estimar_regimen_msssm(raw_data, tickers, date, window=252):
    """
    Capa 5 (Regímenes por MS-SSSM de 3 factores sectoriales jerárquicos):
    Calcula una probabilidad agregada de crisis macro basada en la volatilidad de los 3 sectores.
    Representa una aproximación robusta del MS-SSSM que mide la dispersión del mercado.
    Incorpora robustez frente a feriados asincrónicos y NaNs mediante ffill/bfill.
    """
    try:
        vol_sectores = {1: [], 2: [], 3: []}
        
        for ticker in tickers:
            df = raw_data[ticker]
            vol = np.nan
            
            # 1. Intentar acceso directo a la fecha
            if date in df.index:
                vol = df.loc[date, "Vol_YZ_21"]
                
            # 2. Si no existe la fecha o el valor es NaN/0, aplicar ffill (buscar el último valor anterior disponible)
            if pd.isna(vol) or vol <= 0:
                past_df = df.loc[:date]
                if len(past_df) > 0:
                    vol = past_df.iloc[-1]["Vol_YZ_21"]
                    
            # 3. Si sigue siendo NaN (e.g. feriado largo al inicio), usar solo media histórica causal
            if pd.isna(vol) or vol <= 0:
                past_df = df.loc[:date]
                if len(past_df) > 0:
                    past_vols = past_df["Vol_YZ_21"].dropna()
                    past_vols = past_vols[past_vols > 0]
                    if len(past_vols) > 0:
                        vol = past_vols.mean()
                        
            # 4. Si todo lo anterior falla, usar un prior fijo sin mirar el futuro
            if pd.isna(vol) or vol <= 0:
                vol = 0.15  # Volatilidad anualizada por defecto razonable
                    
            sector = SECTOR_MAP.get(ticker, 1)
            vol_sectores[sector].append(vol)
            
        # Calcular volatilidad promedio de cada sector
        mean_vols = []
        for s in [1, 2, 3]:
            vols = vol_sectores[s]
            # Limpiar NaNs individuales
            vols_clean = [v for v in vols if not pd.isna(v) and v > 0]
            mean_vols.append(np.mean(vols_clean) if len(vols_clean) > 0 else 0.15)
            
        avg_vol = np.mean(mean_vols)
        if pd.isna(avg_vol):
            return 0.33
            
        # Sigmoide centrada en 0.20 (20% vol promedio) con pendiente 15
        prob_crisis = 1.0 / (1.0 + np.exp(-15.0 * (avg_vol - 0.20)))
        return prob_crisis
    except Exception:
        return 0.33  # Retorno seguro a la distribución a priori balanceada
