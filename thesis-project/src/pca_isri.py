import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import seaborn as sns

class PCAEngine:
    """
    Motor de PCA para la creación del Índice Sintético de Rotación Inter-Mercado (ISRI).
    """
    def __init__(self, n_components=1):
        self.n_components = n_components
        self.pca = PCA(n_components=n_components)
        self.loadings = None
        
    def fit_isri(self, df_scaled, training_split=None):
        """
        Calcula el PCA y extrae el ISRI con prevención de fugas.
        
        Args:
            df_scaled: DataFrame con retornos normalizados.
            training_split: Fecha o índice para ajustar el PCA solo con el pasado.
        """
        if training_split is not None:
            # Ajustar solo con el set de entrenamiento para evitar fuga de matriz de covarianza
            train_data = df_scaled.loc[:training_split]
            self.pca.fit(train_data)
        else:
            # WARNING: Ajuste global detectado.
            self.pca.fit(df_scaled)
            
        # Transformar toda la serie usando los pesos del entrenamiento
        isri_values = self.pca.transform(df_scaled)
        
        # Guardar factores de carga (loadings)
        self.loadings = pd.DataFrame(
            self.pca.components_.T,
            index=df_scaled.columns,
            columns=[f'PC{i+1}' for i in range(self.n_components)]
        )
        
        # El ISRI es el primer componente principal
        isri_series = pd.Series(isri_values[:, 0], index=df_scaled.index, name='ISRI')
        
        return isri_series

    def get_explained_variance(self):
        """Retorna la varianza explicada por el PC1."""
        return self.pca.explained_variance_ratio_[0]

if __name__ == "__main__":
    # Prueba rápida con datos dummy representativos
    from data_engine import DataEngine
    
    engine = DataEngine()
    df_raw = engine.download_data(start_date='2018-01-01')
    df_clean, _ = engine.preprocess(df_raw)
    
    pca_tool = PCAEngine()
    isri = pca_tool.fit_isri(df_clean)
    
    print(f"Varianza explicada por PC1 (ISRI): {pca_tool.get_explained_variance():.2%}")
    print("\nLoadings (Contribución de cada activo al ISRI):")
    print(pca_tool.loadings)
    
    # Visualización básica
    plt.figure(figsize=(12, 6))
    isri.plot(title="Índice Sintético de Rotación Inter-Mercado (ISRI) - PC1")
    plt.axhline(0, color='red', linestyle='--', alpha=0.5)
    plt.show()
