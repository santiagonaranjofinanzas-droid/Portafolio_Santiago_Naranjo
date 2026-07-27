import os
import pandas as pd
import numpy as np

#Lista de activos por categoría y su respectivo ticker en yfinance
UNIVERSO_TICKERS = {
    # Índices Bursátiles
    "SPX500": "^GSPC",
    "NAS100": "^NDX",
    "DJI30": "^DJI",
    "GER30": "^GDAXI",
    "EU50": "^STOXX50E",
    "UK100": "^FTSE",
    "JPN225": "^N225",
    # Divisas (G10 FX Spot)
    "EURUSD": "EURUSD=X",
    "USDJPY": "JPY=X",
    "GBPUSD": "GBPUSD=X",
    "AUDUSD": "AUDUSD=X",
    "USDCHF": "CHF=X",
    "USDCAD": "CAD=X",
    # Materias Primas (Commodities)
    "XAUUSD": "GC=F",   # Oro
    "XAGUSD": "SI=F",   # Plata
    "Cobre": "HG=F",
    "Brent": "BZ=F",
    "WTI": "CL=F",
    "GasNatural": "NG=F",
    "Cafe": "KC=F",
    "Azucar": "SB=F",
    "Trigo": "ZW=F",
    "Maiz": "ZC=F",
    "Soja": "ZS=F",
    # Renta Fija (Fixed Income)
    "US10Y": "ZN=F",    # US 10-Year Note Future
    "BUND": "IEF"     # US 7-10 Year Treasury Bond ETF (proxy de BUND)
}

def generar_datos_friccion_sintetico(df_precios, ticker_key):
    """
    Genera spreads y swaps overnight realistas basados en la categoría del activo.
    """
    n = len(df_precios)
    # Tasas de interés de referencia promedio (anuales)
    interes_base = 0.05  # 5% aproximado (e.g. SOFR)
    markup_admin = 0.025 # 2.5% markup del broker CFD
    
    # Costos promedio por categoría
    if ticker_key in ["EURUSD", "USDJPY", "GBPUSD", "AUDUSD", "USDCHF", "USDCAD"]:
        # Divisas (Spot FX): spreads muy bajos, swaps basados en diferenciales de tasas
        spread_pct = 0.0001 # 1 pip promedio
        swap_long = - (interes_base + markup_admin)
        swap_short = (interes_base - markup_admin) # Puede ser positivo o negativo
    elif ticker_key in ["SPX500", "NAS100", "DJI30", "GER30", "EU50", "UK100", "JPN225"]:
        # Índices (CFDs sobre Futuros): sin swap nocturno
        spread_pct = 0.0003 # 0.03% spread
        swap_long = 0.0
        swap_short = 0.0
    elif ticker_key in ["XAUUSD", "XAGUSD", "Cobre", "Brent", "WTI", "GasNatural", "Cafe", "Azucar", "Trigo", "Maiz", "Soja"]:
        # Commodities (CFDs sobre Futuros): sin swap nocturno
        spread_pct = 0.0008 # 0.08% spread
        # Las materias primas agrícolas y energía en CFDs reales tienen spreads más amplios
        if ticker_key in ["Cafe", "Azucar", "Trigo", "Maiz", "Soja", "GasNatural"]:
            spread_pct = 0.0015 # 0.15% spread para agrícolas y gas
        swap_long = 0.0
        swap_short = 0.0
    else:
        # Renta Fija
        spread_pct = 0.0004
        swap_long = - 0.03
        swap_short = 0.01

    # Generamos arrays
    df_precios["Spread"] = df_precios["Close"] * spread_pct
    df_precios["SwapLong"] = swap_long
    df_precios["SwapShort"] = swap_short
    
    return df_precios

def descargar_universo(data_dir="data"):
    """
    Descarga los datos históricos del universo y los guarda como CSV.
    """
    os.makedirs(data_dir, exist_ok=True)
    try:
        import yfinance as yf
    except ImportError:
        print("Librería 'yfinance' no instalada. Por favor ejecuta 'pip install yfinance'.")
        return False

    print("Iniciando descarga del universo de CFDs desde Yahoo Finance...")
    for key, ticker in UNIVERSO_TICKERS.items():
        csv_path = os.path.join(data_dir, f"{key}.csv")
        print(f"Descargando {key} ({ticker})...")
        try:
            # Descargamos los últimos 10 años de datos diarios
            df = yf.download(ticker, period="10y", interval="1d")
            if df.empty:
                print(f"Error: No se obtuvieron datos para {key}")
                continue
            
            # Limpieza y aplanamiento de columnas si Yahoo Finance descarga multi-index
            df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
            df = df.reset_index()
            
            # Renombrar columnas a formato estándar
            df = df.rename(columns={
                "Date": "Date",
                "Open": "Open",
                "High": "High",
                "Low": "Low",
                "Close": "Close",
                "Adj Close": "AdjClose",
                "Volume": "Volume"
            })
            
            # Rellenar datos faltantes (forward fill, backward fill)
            df = df.ffill().bfill()
            
            # Generar columnas de spreads y swaps sintéticos consistentes
            df = generar_datos_friccion_sintetico(df, key)
            
            # Guardar a CSV
            df.to_csv(csv_path, index=False)
            print(f"Guardado exitosamente: {csv_path} ({len(df)} registros)")
            
        except Exception as e:
            print(f"Fallo al procesar {key}: {str(e)}")
            
    print("Descarga e ingestión de datos completada.")
    return True

def cargar_activo(key, data_dir="data"):
    """
    Carga los datos de un activo desde su archivo CSV local.
    """
    csv_path = os.path.join(data_dir, f"{key}.csv")
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"El archivo {csv_path} no existe. Por favor ejecuta la descarga primero.")
    
    df = pd.read_csv(csv_path)
    df["Date"] = pd.to_datetime(df["Date"])
    return df

def calcular_overnight_gap_rezagado(df):
    """
    Calcula el Overnight Gap Normalizado Rezagado Z_{i, t-1}^{(gap)} de forma causal.
    Requiere que la volatilidad Yang-Zhang de 5 días ya esté calculada en el dataframe.
    """
    # Gap de apertura de hoy: ln(Open_t / Close_{t-1})
    df["Gap_Raw"] = np.log(df["Open"] / df["Close"].shift(1))
    
    # Se rezaga un día para evitar look-ahead bias (ERR-05 v2):
    # La variable Z_{i, t-1}^{(gap)} representa el gap observado ayer, disponible al cierre de ayer.
    df["Gap_Raw_Rezagado"] = df["Gap_Raw"].shift(1)
    
    # Normalización por volatilidad Yang-Zhang de 5 días rezagada (ex-ante)
    # Z_{i, t-1}^{(gap)} = ln(O_{t-1} / C_{t-2}) / (vol_YZ_{t-1}(5) / sqrt(252))
    # Nota: la volatilidad de Yang-Zhang en t-1 usa información hasta t-1 inclusive (causal para t).
    df["Z_gap"] = df["Gap_Raw_Rezagado"] / (df["Vol_YZ_5"].shift(1) / np.sqrt(252))
    
    return df

def actualizar_csvs_locales(data_dir="data"):
    print("Actualizando swaps y spreads en los archivos CSV locales...")
    for f in os.listdir(data_dir):
        if f.endswith(".csv"):
            ticker_key = f.replace(".csv", "")
            csv_path = os.path.join(data_dir, f)
            df = pd.read_csv(csv_path)
            # Re-generar swaps y spreads según las nuevas reglas
            df = generar_datos_friccion_sintetico(df, ticker_key)
            df.to_csv(csv_path, index=False)
            print(f"Actualizado: {csv_path}")

if __name__ == "__main__":
    actualizar_csvs_locales()
