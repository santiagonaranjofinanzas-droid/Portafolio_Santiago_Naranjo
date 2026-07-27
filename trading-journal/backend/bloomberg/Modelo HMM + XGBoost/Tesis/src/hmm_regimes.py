import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from tqdm import tqdm
import pickle
import os
import hashlib

class HMMRegimes:
    """
    Modelo Oculto de Markov para identificar regímenes de mercado a partir del ISRI.
    """
    def __init__(self, n_regimes=2, covariance_type="full", n_iter=1000):
        self.n_regimes = n_regimes
        self.model = GaussianHMM(
            n_components=n_regimes, 
            covariance_type=covariance_type, 
            n_iter=n_iter,
            random_state=42
        )
        self.regimes = None
        
    def fit_predict(self, isri_series, training_split=None, use_cache=False, cache_dir='../cache'):
        """
        Entrena el HMM y predice los estados ocultos con inferencia causal (Filtro Forward).
        Operatividad mejorada con sistema de caché y barra de progreso.
        """
        X = isri_series.values.reshape(-1, 1)
        
        # Tarea 2: Optimización Operativa (Sistema de Caché)
        if use_cache:
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir)
            
            # Generar hash basado en la data de entrada y el split
            data_hash = hashlib.md5(isri_series.to_json().encode()).hexdigest()
            split_str = str(training_split) if training_split else "no_split"
            cache_file = os.path.join(cache_dir, f"hmm_cache_{data_hash}_{split_str}.pkl")
            
            if os.path.exists(cache_file):
                print(f"INFO: Cargando predicciones HMM desde caché: {cache_file}")
                with open(cache_file, 'rb') as f:
                    cached_results = pickle.load(f)
                self.regimes = cached_results
                return cached_results

        if training_split is not None:
            # 1. AJUSTE (Entrenamiento puro)
            train_mask = isri_series.index <= training_split
            X_train = X[train_mask]
            self.model.fit(X_train)
            
            # 2. INFERENCIA CAUSAL (Evitar Fuga 2)
            # Para datos in-sample usamos el bloque. 
            # Para datos out-of-sample realizamos inferencia expansiva (incremental).
            # Por simplicidad y rigor absoluto, haremos inferencia incremental para toda la serie.
            probs_list = []
            states_list = []
            
            # Tarea 2: Optimización Operativa (Barra de Progreso)
            # Nota: Esto emula el filtro Forward puro al no ver el futuro de la secuencia
            print(f"Iniciando inferencia HMM causal (O(N^2))...")
            for i in tqdm(range(1, len(X) + 1), desc="Filtrado Forward"):
                # Inferencia usando ventana hasta i
                X_slice = X[:i]
                current_probs = self.model.predict_proba(X_slice)[-1]
                current_state = self.model.predict(X_slice)[-1]
                probs_list.append(current_probs)
                states_list.append(current_state)
                
            probs = np.array(probs_list)
            states = np.array(states_list)
        else:
            # WARNING: Ajuste global y suavizado (Smoothing) detectado
            self.model.fit(X)
            probs = self.model.predict_proba(X)
            states = self.model.predict(X)
        
        # Crear DataFrame de resultados
        results = pd.DataFrame(
            probs, 
            index=isri_series.index, 
            columns=[f'Prob_State_{i}' for i in range(self.n_regimes)]
        )
        results['State'] = states
        self.regimes = results
        
        # Guardar en caché si está habilitado
        if use_cache:
            with open(cache_file, 'wb') as f:
                pickle.dump(results, f)
            print(f"INFO: Predicciones HMM guardadas en caché: {cache_file}")
        
        return results

    def get_state_stats(self, isri_series):
        """Asocia cada estado con estadísticas del ISRI para caracterizarlos."""
        if self.regimes is None:
            return None
            
        combined = pd.concat([isri_series, self.regimes['State']], axis=1)
        stats = combined.groupby('State').agg(['mean', 'std', 'count'])
        return stats

if __name__ == "__main__":
    from data_engine import DataEngine
    from pca_isri import PCAEngine
    
    # Simulación de pipeline completo hasta HMM
    engine = DataEngine()
    df_raw = engine.download_data(start_date='2018-01-01')
    df_clean, _ = engine.preprocess(df_raw)
    
    pca_tool = PCAEngine()
    isri = pca_tool.fit_isri(df_clean)
    
    hmm_tool = HMMRegimes(n_regimes=3) # Probamos con 3 estados: Tranquilo, Transición, Estrés
    hmm_results = hmm_tool.fit_predict(isri)
    
    print("\nEstadísticas del ISRI por Estado Oculto (HMM):")
    print(hmm_tool.get_state_stats(isri))
    print("\nÚltimas filas de probabilidades de régimen:")
    print(hmm_results.tail())
