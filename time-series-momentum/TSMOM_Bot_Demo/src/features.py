import numpy as np
import pandas as pd

def calcular_volatilidad_yang_zhang(df, N, col_prefix="Vol_YZ"):
    """
    Calcula la varianza y desviacion estandar (volatilidad) anualizada de Yang-Zhang (2000).
    """
    df = df.copy()
    ohlc_cols = ["Open", "High", "Low", "Close"]
    invalid_ohlc = (df[ohlc_cols] <= 0).any(axis=1)
    if invalid_ohlc.any():
        df.loc[invalid_ohlc, ohlc_cols] = np.nan

    close = df["Close"].values
    open_val = df["Open"].values
    high = df["High"].values
    low = df["Low"].values
    
    # Gaps y rangos logaritmicos
    # close_prev es C_{s-1}
    close_prev = df["Close"].shift(1).values
    
    # log(O_s / C_{s-1})
    log_oc = np.log(open_val / close_prev)
    # log(C_s / O_s)
    log_co = np.log(close / open_val)
    # log(H_s / C_s) y log(H_s / O_s)
    log_hc = np.log(high / close)
    log_ho = np.log(high / open_val)
    # log(L_s / C_s) y log(L_s / O_s)
    log_lc = np.log(low / close)
    log_lo = np.log(low / open_val)
    
    # Creamos pandas series para aplicar rolling mean y rolling var facilmente
    s_log_oc = pd.Series(log_oc, index=df.index)
    s_log_co = pd.Series(log_co, index=df.index)
    
    # 1. Varianza Close-to-Open (gaps de apertura):
    # E_hist[log_oc]
    o_bar = s_log_oc.rolling(window=N).mean()
    # Var[log_oc] * 252 * (N / (N-1))
    sigma_o_sq = (252 / (N - 1)) * ((s_log_oc - o_bar)**2).rolling(window=N).sum()
    
    # 2. Varianza Open-to-Close (rango intradia):
    c_bar = s_log_co.rolling(window=N).mean()
    sigma_c_sq = (252 / (N - 1)) * ((s_log_co - c_bar)**2).rolling(window=N).sum()
    
    # 3. Estimador de Rogers-Satchell:
    rs_elements = log_hc * log_ho + log_lc * log_lo
    s_rs = pd.Series(rs_elements, index=df.index)
    sigma_rs_sq = (252 / N) * s_rs.rolling(window=N).sum()
    
    # 4. Peso optimo k:
    k = 0.34 / (1.34 + (N + 1) / (N - 1))
    
    # 5. Varianza General Yang-Zhang:
    var_yz = sigma_o_sq + k * sigma_c_sq + (1.0 - k) * sigma_rs_sq
    
    # Evitar indeterminaciones por ceros o valores negativos
    var_yz = np.clip(var_yz, 1e-8, None)
    
    df[f"{col_prefix}_{N}"] = np.sqrt(var_yz)
    return df

def calcular_retornos_normalizados(df, s, N_s, col_name, swap_long=None, swap_short=None):
    """
    Calcula los retornos normalizados por volatilidad Z_{i, t}^{(s)} de forma causal.
    Usa la volatilidad Yang-Zhang de ventana N_s rezagada en 1 periodo.
    Si swap_long y swap_short están presentes, calcula el retorno ajustado por swaps acumulados (neto).
    """
    close = df["Close"].where(df["Close"] > 0)
    # Retorno logaritmico bruto de s dias: ln(C_t / C_{t-s})
    log_return_s = np.log(close / close.shift(s))
    
    if swap_long is not None and swap_short is not None:
        # Calcular el swap acumulado diario dividido por 360 (y rezagado en 1 periodo para causalidad)
        # Rezagamos el swap en 1 periodo (shift(1)) porque la decisión en t usa la información ex-ante
        swap_long_daily = (df[swap_long] / 360).shift(1)
        swap_short_daily = (df[swap_short] / 360).shift(1)
        
        swap_long_s = swap_long_daily.rolling(window=s).sum()
        swap_short_s = swap_short_daily.rolling(window=s).sum()
        
        # El ajuste de carry: si el retorno es alcista, sumamos el swap de compra (usualmente negativo)
        # Si el retorno es bajista, restamos el swap de venta (coste de ir short reduce el retorno bajista)
        swap_adjust = np.where(log_return_s >= 0, swap_long_s, -swap_short_s)
        log_return_s = log_return_s + swap_adjust
        
    # Desviacion estandar (volatilidad) Yang-Zhang ex-ante de N_s dias (shift(1))
    vol_ex_ante = df[f"Vol_YZ_{N_s}"].shift(1)
    
    # Normalizacion temporal: vol_diaria = vol_anualizada / sqrt(252)
    df[col_name] = log_return_s / ( (vol_ex_ante / np.sqrt(252)) * np.sqrt(s) )
    return df

def calcular_macd_normalizado(df, S_k, L_k, N_norm, col_name):
    """
    Calcula el MACD sobre log-precios normalizado por volatilidad de log-retornos de N_norm dias.
    S_k: vida media de EMA rapida
    L_k: vida media de EMA lenta
    N_norm: ventana de normalizacion de log-retornos
    """
    close = df["Close"].where(df["Close"] > 0)
    log_price = np.log(close)
    
    # EMAs sobre log-precios
    ema_s = log_price.ewm(span=S_k, adjust=False).mean()
    ema_l = log_price.ewm(span=L_k, adjust=False).mean()
    
    macd_signal = ema_s - ema_l
    
    # Log-retornos diarios para normalizacion
    log_ret_1d = np.log(close / close.shift(1))
    
    # Volatilidad (std) ex-ante de log-retornos diarios sobre N_norm dias (shift(1) para causalidad)
    std_ret = log_ret_1d.rolling(window=N_norm).std().shift(1)
    
    df[col_name] = macd_signal / std_ret
    return df

def generar_features_tensor(df):
    """
    Genera el feature tensor completo de 12 dimensiones para el activo.
    """
    # 1. Calculamos las volatilidades de Yang-Zhang necesarias de forma anticipada
    # N_s correpondientes a s: {5 (para gap), 10 (s=5), 15 (s=10), 21 (s=21), 63 (s=63), 126 (s=126), 252 (s=252)}
    for N in [5, 10, 15, 21, 63, 126, 252]:
        df = calcular_volatilidad_yang_zhang(df, N)
        
    # 2. Variable 1: Overnight Gap Normalizado Rezagado Z_{i, t-1}^{(gap)}
    # ln(O_{t-1} / C_{t-2}) / (vol_YZ_{t-1}(5) / sqrt(252))
    open_pos = df["Open"].where(df["Open"] > 0)
    close_pos = df["Close"].where(df["Close"] > 0)
    df["Gap_Raw"] = np.log(open_pos / close_pos.shift(1))
    df["Gap_Raw_Rezagado"] = df["Gap_Raw"].shift(1)
    df["Z_gap"] = df["Gap_Raw_Rezagado"] / (df["Vol_YZ_5"].shift(1) / np.sqrt(252))
    
    # 3. Variables 2 a 6: Retornos normalizados Z_{i, t}^{(s)} para s en {5, 10, 21, 63, 126}
    # con N_s en {10, 15, 21, 63, 126} respectivamente.
    ret_horizontes = [5, 10, 21, 63, 126]
    vol_ventanas = [10, 15, 21, 63, 126]
    
    for s, N_s in zip(ret_horizontes, vol_ventanas):
        df = calcular_retornos_normalizados(df, s, N_s, f"Z_{s}d", swap_long="SwapLong", swap_short="SwapShort")
        
    # También calculamos Z_252d para el benchmark TSMOM clásico (Fase I)
    df = calcular_retornos_normalizados(df, 252, 252, "Z_252d", swap_long="SwapLong", swap_short="SwapShort")
        
    # 4. Variables 7 a 9: MACD Multiescala Normalizado (MACD_{i, t}^{(k)})
    # para pares (S_k, L_k) en {(8, 24), (16, 48), (32, 96)}
    # y ventanas de normalizacion N_norm en {63, 72, 144}
    df = calcular_macd_normalizado(df, 8, 24, 63, "MACD_1")
    df = calcular_macd_normalizado(df, 16, 48, 72, "MACD_2")
    df = calcular_macd_normalizado(df, 32, 96, 144, "MACD_3")
    
    # 5. Variables 10 y 11: Swaps normalizados S_{i, t}^{long}, S_{i, t}^{short}
    # Swap diario / (vol_YZ_{t-1}(21) / sqrt(252))
    # Nota: la tasa de swap en el dataset se espera anualizada.
    vol_21_diaria = df["Vol_YZ_21"].shift(1) / np.sqrt(252)
    df["S_long"] = (df["SwapLong"].shift(1) / 360) / vol_21_diaria
    df["S_short"] = (df["SwapShort"].shift(1) / 360) / vol_21_diaria
    
    # 6. Variable 12: Probabilidad de crisis sistémica (se rellenará externamente tras M-SSSM)
    df["xi_3"] = 0.33 # Default prior plano para evitar NaNs en las primeras fases
    
    # Lista de las 4 columnas del tensor final (excluyendo Z_252d para la red neuronal)
    features_list = [
        "Z_21d", "Z_126d", "MACD_2", "xi_3"
    ]
    
    # Eliminar filas con NaNs iniciales debido a rolling windows
    # La ventana mas larga es Vol_YZ_252 y MACD_3 (144d)
    # Por seguridad, el warmup del dataset sera de 252 dias.
    
    return df, features_list
    df = df.copy()
    ohlc_cols = ["Open", "High", "Low", "Close"]
    invalid_ohlc = (df[ohlc_cols] <= 0).any(axis=1)
    if invalid_ohlc.any():
        df.loc[invalid_ohlc, ohlc_cols] = np.nan
    if "Spread" in df.columns:
        df["Spread"] = df["Spread"].where(df["Spread"] >= 0, np.nan)
