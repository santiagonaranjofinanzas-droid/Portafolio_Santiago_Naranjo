"""
test_topology_engine.py - Script de prueba de integración de extremo a extremo
para VolatilityEngine.py y TopologyEngine.py.
"""

import sys
import numpy as np
import pandas as pd
import time

#Agregar la ruta al path para importar los módulos locales
sys.path.append(r"c:\Users\YOUR_USERNAME\Desktop\Universidad\Tesis_2026\Tesis_Repotenciada")

try:
    from VolatilityEngine import VolatilityEngine
    from TopologyEngine import TopologyEngine
    print("Módulos importados correctamente.")
except Exception as e:
    print(f"Error al importar módulos: {e}")
    sys.exit(1)

def generate_synthetic_data(T=500, N=26, seed=42):
    """
    Generador de retornos sintéticos con dinámicas GARCH.
    """
    np.random.seed(seed)
    base_corr = np.eye(N)
    for i in range(N):
        for j in range(i):
            corr = 0.3 if (i - j) % 2 == 0 else -0.1
            base_corr[i, j] = corr
            base_corr[j, i] = corr
            
    eigvals, eigvecs = np.linalg.eigh(base_corr)
    eigvals = np.maximum(eigvals, 0.1)
    base_corr = eigvecs @ np.diag(eigvals) @ eigvecs.T
    d = np.diag(base_corr)
    base_corr = base_corr / np.sqrt(np.outer(d, d))
    
    vols = np.zeros((T, N))
    returns = np.zeros((T, N))
    vols[0, :] = 0.015
    omega, alpha, gamma, beta = 0.000005, 0.05, 0.05, 0.85
    
    for t in range(T):
        shocks = np.random.multivariate_normal(np.zeros(N), base_corr)
        returns[t, :] = shocks * vols[t, :]
        if t < T - 1:
            for i in range(N):
                s_val = returns[t, i]
                asym = s_val**2 if s_val < 0 else 0
                vols[t+1, i] = np.sqrt(
                    omega + alpha * (s_val**2) + gamma * asym + beta * (vols[t, i]**2)
                )
                
    dates = pd.date_range(end="2026-06-08", periods=T, freq="B")
    columns = [f"Asset_{i+1}" for i in range(N)]
    return pd.DataFrame(returns, index=dates, columns=columns)

def run_integration_test():
    print("=" * 60)
    print("INICIANDO TEST DE INTEGRACIÓN: VOLATILITY + TOPOLOGY")
    print("=" * 60)
    
    T, N = 500, 26
    data = generate_synthetic_data(T=T, N=N)
    
    # 1. Ajustar Motor de Volatilidad
    print("\n[Fase I] Ajustando VolatilityEngine...")
    v_engine = VolatilityEngine(data)
    v_engine.fit(n_jobs=2)
    
    H = v_engine.get_conditional_covariances()
    R = v_engine.get_conditional_correlations()
    
    # 2. Inicializar Motor de Topología
    print("\n[Fase II] Inicializando TopologyEngine...")
    t_engine = TopologyEngine(H, R, v_engine.assets, v_engine.dates)
    
    # 3. Extraer características
    print("\nExtrayendo características latentes consolidando RMT, KLD y MST...")
    start_time = time.time()
    features = t_engine.extract_features(k=3, stable_window=100)
    elapsed = time.time() - start_time
    
    print("\n" + "-" * 50)
    print("VERIFICACIÓN DE CARACTERÍSTICAS:")
    print("-" * 50)
    print(f"Tiempo de extracción de características: {elapsed:.3f} segundos.")
    print(f"Dimensiones del DataFrame de características: {features.shape}")
    print(features.head())
    print("\nEstadísticas descriptivas de las características:")
    print(features.describe().T[['mean', 'min', 'max']])
    
    # Pruebas de validación lógica
    expected_cols = [
        "lambda_dominant", "gar", "entropy_spectral", 
        "frobenius_distance", "kld", "mtl", "max_centrality"
    ]
    
    # Test 1: Comprobar columnas y dimensiones
    assert list(features.columns) == expected_cols, f"¡Las columnas no coinciden! Encontradas: {list(features.columns)}"
    assert features.shape == (T, len(expected_cols)), f"Dimensiones incorrectas: {features.shape}"
    print("Test 1 (Columnas e Integridad de Características): APROBADO")
    
    # Test 2: Comprobar estabilidad numérica (sin NaNs)
    assert not features.isnull().any().any(), "¡El DataFrame contiene valores NaN!"
    print("Test 2 (Estabilidad Numérica - Sin NaNs): APROBADO")
    
    # Test 3: Validar rango de Entropía Espectral Normalizada [0, 1]
    assert (features["entropy_spectral"] >= 0.0).all() and (features["entropy_spectral"] <= 1.0).all(), \
        "¡Entropía espectral normalizada fuera de límites [0, 1]!"
    print("Test 3 (Entropía Espectral Normalizada acotada [0, 1]): APROBADO")
    
    # Test 4: Validar propiedad no negativa de KLD
    # Permitimos un margen mínimo de precisión de coma flotante de -1e-5
    assert (features["kld"] >= -1e-5).all(), \
        f"¡Divergencia KLD negativa detectada! Mínimo encontrado: {features['kld'].min()}"
    print("Test 4 (Rigor Matemático de la Divergencia KLD >= 0): APROBADO")
    
    # Test 5: Propiedades del Árbol de Expansión Mínima (MTL y Grado Centralidad)
    assert (features["mtl"] > 0.0).all() and (features["mtl"] <= 2.0).all(), \
        "¡Longitud del árbol MTL fuera de límites métricos esperados!"
    assert (features["max_centrality"] >= 1).all() and (features["max_centrality"] <= N - 1).all(), \
        "¡Centralidad de grado máximo fuera de los límites lógicos de un árbol (1 a N-1)!"
    print("Test 5 (Propiedades Topológicas del MST y MTL): APROBADO")
    
    print("\n" + "=" * 60)
    print("¡TEST DE INTEGRACIÓN EXTREMO A EXTREMO COMPLETADO CON ÉXITO!")
    print("=" * 60)

if __name__ == "__main__":
    run_integration_test()
