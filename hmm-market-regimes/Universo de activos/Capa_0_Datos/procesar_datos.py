import os
import sys
import pandas as pd
import numpy as np

#Configurar codificación de salida
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def procesar_datos_activo(ruta_origen: str, asset_name: str, ruta_destino: str = None) -> str:
    """
    Capa 0: Carga datos, normaliza columnas, realiza agregación temporal a M15 si son ticks,
    calcula log-retornos y guarda en formato Parquet optimizado.
    """
    print("=========================================================================")
    print(f" CAPA 0: CONSOLIDACIÓN DE LAGO DE DATOS - {asset_name.upper()}")
    print("=========================================================================")
    
    if not os.path.exists(ruta_origen):
        raise FileNotFoundError(f"Archivo de origen no encontrado: {ruta_origen}")
        
    _, ext = os.path.splitext(ruta_origen.lower())
    
    # Cargar datos
    if ext == '.parquet':
        df = pd.read_parquet(ruta_origen)
    elif ext == '.csv':
        try:
            df = pd.read_csv(ruta_origen, sep=None, engine='python')
        except Exception:
            df = pd.read_csv(ruta_origen, sep=',')
    else:
        raise ValueError(f"Formato de archivo no soportado: {ext}. Use .csv o .parquet")
        
    # Normalizar nombres de columnas a minúsculas, removiendo espacios y brackets < >
    df.columns = [c.lower().strip().replace('<', '').replace('>', '') for c in df.columns]
    
    # Si el índice ya es un DatetimeIndex, o si el nombre del índice es temporal
    if isinstance(df.index, pd.DatetimeIndex):
        print(" Se detectó un índice temporal (DatetimeIndex) en el archivo de origen.")
        df = df.sort_index()
    elif df.index.name and df.index.name.lower().strip().replace('<', '').replace('>', '') in ['timestamp', 'time', 'date', 'datetime', 'fecha', 't']:
        print(f" Se detectó índice temporal por nombre: '{df.index.name}'")
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
    else:
        # Buscar columna temporal
        col_time = None
        for col in ['timestamp', 'time', 'date', 'datetime', 'fecha', 't']:
            if col in df.columns:
                col_time = col
                break
                
        if col_time is not None:
            df[col_time] = pd.to_datetime(df[col_time])
            df = df.sort_values(by=col_time)
            df = df.set_index(col_time)
            print(f" Datos indexados y ordenados usando la columna '{col_time}'.")
        else:
            raise KeyError(f"No se encontró una columna de fecha/hora en los datos de entrada. Columnas: {list(df.columns)}")
    
    # Comprobar si los datos son ticks (tienen bid/ask sin ohlc completo) o si son velas (ohlc completo)
    tiene_ohlc = all(col in df.columns for col in ['open', 'high', 'low', 'close'])
    tiene_bid = 'bid' in df.columns
    
    if tiene_ohlc:
        print(" Se detectaron columnas OHLC completas. Procediendo con saneamiento de velas...")
        df_m15 = df[['open', 'high', 'low', 'close']].copy()
        # Remuestrear si el usuario tiene datos de otro timeframe (ej. M1 o M5) a M15
        # Si ya están en M15, el remuestreo los mantiene igual
        df_m15 = df_m15.resample('15min').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
    elif tiene_bid:
        print(" Se detectaron datos a nivel de Ticks (columna 'bid'). Agrupando a velas M15...")
        df_m15 = df.resample('15min').agg(
            open=('bid', 'first'),
            high=('bid', 'max'),
            low=('bid', 'min'),
            close=('bid', 'last')
        ).dropna()
    else:
        # Si solo tiene close u otra columna
        col_close = None
        for col in ['close', 'close_raw', 'ultimo', 'last', 'c']:
            if col in df.columns:
                col_close = col
                break
        if col_close is None:
            raise KeyError(f"No se pudieron encontrar columnas OHLC ni columnas de precio de cierre. Columnas: {list(df.columns)}")
            
        print(f" Se detectó columna de precio '{col_close}'. Reconstruyendo velas M15 ficticias...")
        df_m15 = df.resample('15min').agg(
            open=(col_close, 'first'),
            high=(col_close, 'max'),
            low=(col_close, 'min'),
            close=(col_close, 'last')
        ).dropna()

    # Calcular log-retornos para la inferencia HMM
    df_m15['returns'] = np.log(df_m15['close'] / df_m15['close'].shift(1))
    df_m15 = df_m15.dropna()
    
    if not ruta_destino:
        dir_actual = os.path.dirname(os.path.abspath(__file__))
        dir_datos = os.path.abspath(os.path.join(dir_actual, "..", "datos"))
        os.makedirs(dir_datos, exist_ok=True)
        ruta_destino = os.path.join(dir_datos, f"{asset_name.upper()}_M15_Training.parquet")
        
    df_m15.to_parquet(ruta_destino, engine='pyarrow', compression='snappy')
    
    print(f" CAPA 0 COMPLETADA")
    print(f" • Destino del lago de datos: {ruta_destino}")
    print(f" • Volumen total de velas M15: {df_m15.shape[0]}")
    print(f" • Ventana temporal: {df_m15.index.min()} a {df_m15.index.max()}")
    print("=========================================================================\n")
    return ruta_destino

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        procesar_datos_activo(sys.argv[1], sys.argv[2])
    else:
        print("Uso: python procesar_datos.py <ruta_origen> <nombre_activo>")
