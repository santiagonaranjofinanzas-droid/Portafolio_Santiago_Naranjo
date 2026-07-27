import pandas as pd
import numpy as np

class PreprocessEngine:
    def __init__(self, scaler_params: dict):
        self.feature_names = scaler_params["feature_names"]
        self.lower = pd.Series(scaler_params["winsor_lower"])
        self.upper = pd.Series(scaler_params["winsor_upper"])
        self.mu = pd.Series(scaler_params["mu"])
        self.sigma = pd.Series(scaler_params["sigma"])
        self.feature_version = scaler_params["feature_version"]

    def preprocess(self, raw_features: dict) -> np.ndarray:
        """
        Aplica winsorización y escalado Z-score estricto con parámetros del training set.
        """
        # Verificar que las features esperadas estén presentes
        for fn in self.feature_names:
            if fn not in raw_features:
                raise ValueError(f"Falta la feature requerida: {fn}")
        
        # Convertir a Series para alinear fácilmente (ordenando según feature_names)
        x = pd.to_numeric(pd.Series(raw_features)[self.feature_names], errors="coerce")
        x = x.replace([np.inf, -np.inf], np.nan).fillna(0.0)
        
        # 1. Winsorización estricta (clip)
        x_clipped = x.clip(lower=self.lower, upper=self.upper)
        
        # 2. Z-score con mu y sigma fijos
        safe_sigma = self.sigma.replace(0.0, 1.0)
        x_scaled = ((x_clipped - self.mu) / safe_sigma).replace([np.inf, -np.inf], 0.0).fillna(0.0)
        
        return x_scaled.values
