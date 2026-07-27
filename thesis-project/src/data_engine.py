import yfinance as yf
import pandas as pd
import numpy as np
from scipy.stats import mstats
from sklearn.preprocessing import StandardScaler

class DataEngine:
    """
    Motor de datos para descargar y preprocesar series financieras multi-activo.
    """
    def __init__(self, tickers=None):
        if tickers is None:
            # Configuración por defecto alineada con la tesis
            self.tickers = {
                'SP500': '^GSPC',    # Acciones
                'GOLD': 'GC=F',      # Oro
                'OIL': 'CL=F',      # Petróleo
                'BOND10Y': '^TNX',   # Bonos 10Y
                'USD': 'DX-Y.NYB'    # Índice Dólar (ajustado para yfinance)
            }
        else:
            self.tickers = tickers
        
    def download_data(self, start_date='2010-01-01', end_date=None):
        """Descarga precios de cierre ajustados."""
        print(f"Descargando datos para: {list(self.tickers.keys())}")
        raw_df = yf.download(list(self.tickers.values()), start=start_date, end=end_date, auto_adjust=False)
        if 'Adj Close' in raw_df.columns:
            data = raw_df['Adj Close']
        else:
            data = raw_df['Close']
        
        # Mapear nombres a etiquetas legibles
        inv_map = {v: k for k, v in self.tickers.items()}
        data = data.rename(columns=inv_map)
        
        # Limpieza básica
        return data

    def preprocess(self, df, training_split=None):
        """
        Pipeline de preprocesamiento robusto: Split -> ffill/dropna independientes -> Retornos -> Winsorización Local -> Escalamiento.
        """
        # 1. Split y Limpieza independientes para evitar look-ahead bias (Fuga de Información Tipo 1)
        if training_split is not None:
            df_train = df.loc[:training_split].ffill().dropna()
            df_test = df.loc[training_split:].ffill().dropna()
            
            # Retornos calculados de forma aislada
            returns_train = np.log(df_train / df_train.shift(1))
            returns_test = np.log(df_test / df_test.shift(1))
            
            # Corrección macroeconómica para BOND10Y (rendimiento a precio de bono)
            if 'BOND10Y' in returns_train.columns:
                returns_train['BOND10Y'] = -returns_train['BOND10Y']
            if 'BOND10Y' in returns_test.columns:
                returns_test['BOND10Y'] = -returns_test['BOND10Y']
                
            returns_train = returns_train.dropna()
            returns_test = returns_test.dropna()
            
            returns = pd.concat([returns_train, returns_test])
        else:
            df_clean = df.ffill().dropna()
            returns = np.log(df_clean / df_clean.shift(1))
            if 'BOND10Y' in returns.columns:
                returns['BOND10Y'] = -returns['BOND10Y']
            returns = returns.dropna()
        
        # 2. Winsorización local (Previene Fuga 1)
        if training_split is not None:
            train_returns = returns.loc[:training_split]
            lower = train_returns.quantile(0.01)
            upper = train_returns.quantile(0.99)
        else:
            lower = returns.quantile(0.01)
            upper = returns.quantile(0.99)
            
        returns_winsorized = returns.clip(lower=lower, upper=upper, axis=1)
        
        # 3. Normalización Z-score con prevención de fuga
        scaler = StandardScaler()
        
        if training_split is not None:
            train_data = returns_winsorized.loc[:training_split]
            scaler.fit(train_data)
        else:
            scaler.fit(returns_winsorized)
            
        returns_scaled = pd.DataFrame(
            scaler.transform(returns_winsorized),
            index=returns_winsorized.index,
            columns=returns_winsorized.columns
        )
        
        return returns_scaled, scaler

if __name__ == "__main__":
    engine = DataEngine()
    df_raw = engine.download_data(start_date='2015-01-01')
    df_clean, scaler = engine.preprocess(df_raw, training_split='2021-12-31')
    print("\nPrimeras filas de datos procesados (Z-score):")
    print(df_clean.head())
    print(f"\nDimensiones finales: {df_clean.shape}")

