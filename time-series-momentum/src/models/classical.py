import numpy as np
import pandas as pd
from xgboost import XGBRegressor

def entrenar_xgboost(train_dfs, features, max_depth=3, n_estimators=100, learning_rate=0.05, random_state=42):
    """
    Capa 6 (Machine Learning Clásico):
    Entrena un XGBRegressor global (pooled) sobre un conjunto de DataFrames de entrenamiento.
    Cada DataFrame en train_dfs debe contener las columnas de features y la columna 'target'.
    """
    X_list = []
    y_list = []
    
    for df in train_dfs:
        if len(df) == 0:
            continue
        # Asegurarse de que no haya NaNs en las características ni en el target
        valid_df = df.dropna(subset=features + ["target"])
        if len(valid_df) > 0:
            X_list.append(valid_df[features].values)
            y_list.append(valid_df["target"].values)
            
    if len(X_list) == 0:
        return None
        
    X = np.vstack(X_list)
    y = np.concatenate(y_list)
    
    # Entrenar el regresor XGBoost
    # Limitamos max_depth para evitar sobreajuste agresivo en series de tiempo financieras ruidosas
    model = XGBRegressor(
        max_depth=max_depth,
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        random_state=random_state,
        reg_alpha=1.5,
        reg_lambda=5.0,
        subsample=0.8,
        colsample_bytree=0.8,
        n_jobs=-1
    )
    model.fit(X, y)
    
    return model
