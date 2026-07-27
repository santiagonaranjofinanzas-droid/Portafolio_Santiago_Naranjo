"""
TopologyEngine.py - Extractor Geométrico-Espectral (Fase II)

Clase encargada de procesar las matrices de covarianza H_t y correlación R_t
para extraer las características espectrales, informacionales y de redes.

Métricas extraídas:
1. Autovalor Dominante (lambda_1) y Ratio de Absorción (GAR) (RMT).
2. Entropía Espectral de Von Neumann Normalizada.
3. Distancia de Frobenius y Divergencia Kullback-Leibler estable (KLD Cholesky).
4. Longitud Media del Árbol (MTL) y Centralidad de Grado Máximo (MST Kruskal).
"""

import logging
import numpy as np
import pandas as pd
from scipy.linalg import cho_factor, cho_solve
import numba as nb
import time

#Configuración de logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TopologyEngine")


@nb.njit
def _find(parent, i):
    """
    Función Find con compresión de camino (Path Compression) para Union-Find.
    """
    path = []
    while parent[i] != i:
        path.append(i)
        i = parent[i]
    for node in path:
        parent[node] = i
    return i


@nb.njit
def _union(parent, rank, i, j):
    """
    Función Union por rango para Union-Find.
    Retorna True si la unión fue exitosa (no había ciclo), False en caso contrario.
    """
    root_i = _find(parent, i)
    root_j = _find(parent, j)
    if root_i != root_j:
        if rank[root_i] < rank[root_j]:
            parent[root_i] = root_j
        elif rank[root_i] > rank[root_j]:
            parent[root_j] = root_i
        else:
            parent[root_j] = root_i
            rank[root_i] += 1
        return True
    return False


@nb.njit
def _kruskal_mst_numba(N, edges):
    """
    Algoritmo de Kruskal optimizado para calcular la MTL y la centralidad de grado máximo.
    
    Args:
        N: Número de nodos (activos).
        edges: Matriz de aristas de tamaño (E, 3) donde las columnas son [u, v, peso].
    """
    # Ordenar aristas por peso de menor a mayor
    weights = edges[:, 2]
    sort_idx = np.argsort(weights)
    
    parent = np.arange(N)
    rank = np.zeros(N, dtype=np.int32)
    
    mst_weight_sum = 0.0
    mst_edges_count = 0
    degrees = np.zeros(N, dtype=np.int32)
    
    for idx in sort_idx:
        u = int(edges[idx, 0])
        v = int(edges[idx, 1])
        w = edges[idx, 2]
        
        if _union(parent, rank, u, v):
            mst_weight_sum += w
            degrees[u] += 1
            degrees[v] += 1
            mst_edges_count += 1
            if mst_edges_count == N - 1:
                break
                
    # Longitud media del árbol (Mean Tree Length)
    mtl = mst_weight_sum / (N - 1)
    # Centralidad de grado máximo en el árbol
    max_cent = np.max(degrees)
    
    return mtl, max_cent


@nb.njit
def _process_mst_history_numba(R):
    """
    Filtra secuencialmente las matrices de correlación R_t para construir el MST de Kruskal
    en cada paso de tiempo y derivar las métricas de red complejas.
    """
    T, N, _ = R.shape
    E = N * (N - 1) // 2
    
    mtl_history = np.zeros(T)
    max_cent_history = np.zeros(T)
    
    for t in range(T):
        R_t = R[t]
        edges = np.zeros((E, 3))
        idx = 0
        for i in range(N):
            for j in range(i):
                # Distancia métrica de Mantegna
                dist = np.sqrt(2.0 * (1.0 - R_t[i, j]))
                edges[idx, 0] = i
                edges[idx, 1] = j
                edges[idx, 2] = dist
                idx += 1
                
        mtl, max_cent = _kruskal_mst_numba(N, edges)
        mtl_history[t] = mtl
        max_cent_history[t] = max_cent
        
    return mtl_history, max_cent_history


class TopologyEngine:
    """
    Clase que implementa el análisis de topología y descomposición espectral
    de las covarianzas y correlaciones condicionales dinámicas.
    """
    
    def __init__(self, H: np.ndarray, R: np.ndarray, assets: list, dates: pd.Index):
        """
        Inicializa el extractor con los tensores de volatilidad.
        
        Args:
            H: Tensor (T, N, N) de covarianzas condicionales.
            R: Tensor (T, N, N) de correlaciones condicionales.
            assets: Lista de N nombres de activos.
            dates: Índice de fechas de tamaño T.
        """
        self.H = H
        self.R = R
        self.assets = assets
        self.dates = dates
        self.T, self.N, _ = H.shape
        
        if len(self.assets) != self.N:
            raise ValueError("La lista de activos no coincide con la dimensión del tensor.")
        if len(self.dates) != self.T:
            raise ValueError("El índice de fechas no coincide con la longitud temporal del tensor.")
            
        logger.info(f"TopologyEngine inicializado para N={self.N} activos y T={self.T} periodos.")

    def compute_spectral_features(self, k=3):
        """
        Calcula el autovalor dominante, el Ratio de Absorción Global (GAR) y
        la entropía espectral normalizada de Von Neumann.
        """
        logger.info("Computando características espectrales mediante RMT...")
        start_time = time.time()
        
        lambda_dominant = np.zeros(self.T)
        gar = np.zeros(self.T)
        entropy_spectral = np.zeros(self.T)
        
        ln_N = np.log(self.N)
        
        for t in range(self.T):
            # Obtener autovalores (np.linalg.eigh devuelve en orden ascendente para matrices simétricas)
            eigvals = np.linalg.eigh(self.R[t])[0]
            # Invertir para tener orden descendente
            eigvals = eigvals[::-1]
            
            # Autovalor dominante
            lambda_dominant[t] = eigvals[0]
            
            # Ratio de Absorción Global (GAR) con k factores primarios
            gar[t] = np.sum(eigvals[:k]) / self.N
            
            # Entropía de Von Neumann normalizada
            # Nos aseguramos que no existan autovalores no positivos por ruido numérico
            tilde_lambda = eigvals / self.N
            tilde_lambda = np.clip(tilde_lambda, 1e-15, 1.0)
            
            ent_val = -np.sum(tilde_lambda * np.log(tilde_lambda)) / ln_N
            entropy_spectral[t] = ent_val
            
        elapsed = time.time() - start_time
        logger.info(f"Características espectrales computadas en {elapsed:.2f} segundos.")
        
        return pd.DataFrame({
            "lambda_dominant": lambda_dominant,
            "gar": gar,
            "entropy_spectral": entropy_spectral
        }, index=self.dates)

    def compute_kld_and_frobenius(self, stable_window=252):
        """
        Calcula la distancia de Frobenius y la Divergencia Kullback-Leibler
        de manera numéricamente estable utilizando la descomposición de Cholesky.
        
        Args:
            stable_window: Número de observaciones iniciales para calcular la línea de base estable.
                           Si se pasa un entero, usa las primeras `stable_window` muestras.
                           Si es una matriz (N, N), se usa directamente como H_stable.
        """
        logger.info("Computando distancia de Frobenius y Divergencia KLD robusta...")
        start_time = time.time()
        
        # 1. Definir matrices de referencia estables
        if isinstance(stable_window, int):
            logger.info(f"Calculando línea de base estable usando los primeros {stable_window} días...")
            H_stable = np.mean(self.H[:stable_window], axis=0)
            R_stable = np.mean(self.R[:stable_window], axis=0)
        else:
            # stable_window es una tupla o matriz directamente
            H_stable = stable_window
            # Extraer correlación estable
            d = np.diag(H_stable)
            d_inv_sqrt = 1.0 / np.sqrt(d)
            R_stable = np.outer(d_inv_sqrt, d_inv_sqrt) * H_stable
            
        # Aplicamos regularización Ridge (Tikhonov) para evitar problemas de singularidad (ej. activos correlacionados nativamente)
        H_stable_reg = H_stable + np.eye(self.N) * 1e-6
            
        # Cholesky de la covarianza estable de referencia regularizada
        L_stable = np.linalg.cholesky(H_stable_reg)
        c_stable = (L_stable, True)  # Para cho_solve (lower=True)
        log_det_stable = 2.0 * np.sum(np.log(np.diag(L_stable)))
        
        kld = np.zeros(self.T)
        frobenius = np.zeros(self.T)
        
        # 2. Calcular distancia de Frobenius de correlaciones de forma vectorizada
        diff_R = self.R - R_stable
        frobenius = np.sqrt(np.sum(diff_R ** 2, axis=(1, 2)))
        
        # 3. Calcular KLD para cada paso temporal
        for t in range(self.T):
            H_t = self.H[t]
            
            # Obtener factor de Cholesky de la covarianza condicional actual
            try:
                L_t = np.linalg.cholesky(H_t)
            except:
                # Ridge por si existe ruido numérico que rompa la definición positiva
                H_t_ridge = H_t + np.eye(self.N) * 1e-8
                L_t = np.linalg.cholesky(H_t_ridge)
                
            log_det_t = 2.0 * np.sum(np.log(np.diag(L_t)))
            
            # Tr(H_stable^-1 * H_t) utilizando el factor de Cholesky de H_stable
            # Resuelve H_stable * X_t = H_t
            X_t = cho_solve(c_stable, H_t)
            tr_val = np.trace(X_t)
            
            log_det_diff = log_det_stable - log_det_t
            
            kld[t] = 0.5 * (tr_val - self.N + log_det_diff)
            
        elapsed = time.time() - start_time
        logger.info(f"Distancias KLD y Frobenius computadas en {elapsed:.2f} segundos.")
        
        return pd.DataFrame({
            "frobenius_distance": frobenius,
            "kld": kld
        }, index=self.dates)

    def compute_network_features(self):
        """
        Calcula la longitud promedio del árbol (MTL) y la centralidad de grado
        máximo a partir del MST dinámico de Kruskal acelerado en Numba.
        """
        logger.info("Computando características topológicas de red (MST Kruskal JIT)...")
        start_time = time.time()
        
        mtl, max_centrality = _process_mst_history_numba(self.R)
        
        elapsed = time.time() - start_time
        logger.info(f"Características de red computadas en {elapsed:.2f} segundos.")
        
        return pd.DataFrame({
            "mtl": mtl,
            "max_centrality": max_centrality
        }, index=self.dates)

    def extract_features(self, k=3, stable_window=252):
        """
        Ejecuta todas las rutinas de extracción y devuelve un DataFrame unificado.
        """
        logger.info("Iniciando extracción consolidada de características latentes...")
        start_time = time.time()
        
        df_spect = self.compute_spectral_features(k=k)
        df_dist = self.compute_kld_and_frobenius(stable_window=stable_window)
        df_net = self.compute_network_features()
        
        # Unir todos los DataFrames
        df_features = pd.concat([df_spect, df_dist, df_net], axis=1)
        
        total_time = time.time() - start_time
        logger.info(f"Extracción finalizada. Generadas {df_features.shape[1]} características para T={self.T} días en {total_time:.2f} segundos.")
        
        return df_features
