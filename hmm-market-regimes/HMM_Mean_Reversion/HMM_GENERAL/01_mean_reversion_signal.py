import os
import pandas as pd
import numpy as np


def add_mean_reversion_filters(
    df: pd.DataFrame,
    atr_window: int = 384,
    atr_block_quantile: float = 0.85,
    accel_window: int = 384,
    accel_quantile: float = 0.60,
    slope_quantile: float = 0.60,
) -> pd.DataFrame:
    """
    Adds ex-ante blocking filters for mean reversion entries.

    The filters use only shifted/rolling information available before the next
    bar opens:
    - high ATR percentile blocks microstructural stress.
    - strong Kalman/HMA slope in breakout direction blocks falling-knife entries.
    - acceleration must be below its rolling threshold to confirm exhaustion.
    """
    atr = df["ATR_14"].astype(float)
    accel = df.get("Raw_Accel_Mag", pd.Series(0.0, index=df.index)).astype(float).abs()
    kalman_slope = df.get("Kalman_Slope", pd.Series(0.0, index=df.index)).astype(float)
    hma_slope = df.get("HMA_Raw_Slope", pd.Series(0.0, index=df.index)).astype(float)
    trend_slope = kalman_slope + hma_slope

    min_periods = max(20, atr_window // 4)
    atr_threshold = atr.shift(1).rolling(atr_window, min_periods=min_periods).quantile(atr_block_quantile)
    accel_threshold = accel.shift(1).rolling(accel_window, min_periods=min_periods).quantile(accel_quantile)
    slope_abs_threshold = trend_slope.abs().shift(1).rolling(accel_window, min_periods=min_periods).quantile(slope_quantile)

    df["MR_ATR_Threshold"] = atr_threshold.bfill()
    df["MR_Accel_Threshold"] = accel_threshold.bfill()
    df["MR_SlopeAbs_Threshold"] = slope_abs_threshold.bfill()
    df["MR_Volatility_Blocked"] = (atr >= df["MR_ATR_Threshold"]).astype(int)
    df["MR_Accel_Blocked"] = (accel >= df["MR_Accel_Threshold"]).astype(int)
    df["MR_Strong_Up_Blocked"] = ((trend_slope > df["MR_SlopeAbs_Threshold"]) & (df["MR_SlopeAbs_Threshold"] > 0)).astype(int)
    df["MR_Strong_Down_Blocked"] = ((trend_slope < -df["MR_SlopeAbs_Threshold"]) & (df["MR_SlopeAbs_Threshold"] > 0)).astype(int)
    return df


def calculate_z_dev_in_memory(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula la desviación normalizada Z_dev en memoria usando operaciones vectorizadas.
    """
    close = df["close"].to_numpy(dtype=float)
    kalman_mean = df["Kalman_Precio_Medio"].to_numpy(dtype=float)
    atr = df["ATR_14"].to_numpy(dtype=float)
    
    # Operación vectorizada con np.where para evitar división por cero
    df["Z_dev"] = np.where(atr > 1e-8, (close - kalman_mean) / np.maximum(atr, 1e-8), 0.0)
    df = add_mean_reversion_filters(df)
    return df

def generate_mean_reversion_signals(signals_csv: str, z_entry_long: float, z_entry_short: float, output_csv: str):
    """
    Lee las señales de Capa 2, calcula Z_dev de forma eficiente y guarda las señales.
    """
    if not os.path.exists(signals_csv):
        raise FileNotFoundError(f"No se encontró el archivo de señales base: {signals_csv}")
        
    df = pd.read_csv(signals_csv, index_col=0, parse_dates=True)
    df = calculate_z_dev_in_memory(df)
    
    regime = df["Regime_Buffer_18"].to_numpy(dtype=float)
    z_dev = df["Z_dev"].to_numpy(dtype=float)
    exec_regime = df["Regime_Buffer_18"].shift(1).fillna(0).to_numpy(dtype=float)
    exec_z_dev = df["Z_dev"].shift(1).fillna(0).to_numpy(dtype=float)
    exec_vol_blocked = df["MR_Volatility_Blocked"].shift(1).fillna(1).to_numpy(dtype=bool)
    exec_accel_blocked = df["MR_Accel_Blocked"].shift(1).fillna(1).to_numpy(dtype=bool)
    exec_up_blocked = df["MR_Strong_Up_Blocked"].shift(1).fillna(1).to_numpy(dtype=bool)
    exec_down_blocked = df["MR_Strong_Down_Blocked"].shift(1).fillna(1).to_numpy(dtype=bool)
    
    mr_entry_long = (regime == 0) & (z_dev < -z_entry_long)
    mr_entry_short = (regime == 0) & (z_dev > z_entry_short)
    common_filter = (exec_regime == 0) & ~exec_vol_blocked & ~exec_accel_blocked
    mr_exec_long = common_filter & ~exec_down_blocked & (exec_z_dev < -z_entry_long)
    mr_exec_short = common_filter & ~exec_up_blocked & (exec_z_dev > z_entry_short)
    
    df["MR_Entry_Long"] = mr_entry_long.astype(int)
    df["MR_Entry_Short"] = mr_entry_short.astype(int)
    df["MR_Exec_Long_Next_Open"] = mr_exec_long.astype(int)
    df["MR_Exec_Short_Next_Open"] = mr_exec_short.astype(int)
    
    # Guardar a CSV manteniendo el índice de fechas
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=True)
    print(f"[+] Señales de Mean Reversion generadas en: {output_csv} (Velas: {len(df)})")

if __name__ == "__main__":
    pass
