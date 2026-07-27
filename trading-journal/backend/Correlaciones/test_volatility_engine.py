"""
test_volatility_engine.py - Script de verificación y prueba de rendimiento
para VolatilityEngine.py.
"""

import os
import sys
import numpy as np
import pandas as pd
import time

#Añadimos la ruta de la tesis para poder importar VolatilityEngine
sys.path.append(r"c:\Users\YOUR_USERNAME\Desktop\Universidad\Tesis_2026\Tesis_Repotenciada")

try:
    from VolatilityEngine import VolatilityEngine
    print("Módulo VolatilityEngine importado con éxito.")
except Exception as e:
    print(f"Error al importar VolatilityEngine: {str(e)}")
    sys.exit(1)

def generate_synthetic_data(T=500, N=26, seed=42):
    """
    Genera retornos sintéticos con dinámica de volatilidad y correlaciones predefinidas.
    """
    np.random.seed(seed)
    
    # Matriz de covarianza base (identidad con correlaciones moderadas)
    base_corr = np.eye(N)
    for i in range(N):
        for j in range(i):
            corr = 0.3 if (i - j) % 2 == 0 else -0.1
            base_corr[i, j] = corr
            base_corr[j, i] = corr
            
    # Asegurar positividad definida
    eigvals, eigvecs = np.linalg.eigh(base_corr)
    eigvals = np.maximum(eigvals, 0.1)
    base_corr = eigvecs @ np.diag(eigvals) @ eigvecs.T
    d = np.diag(base_corr)
    base_corr = base_corr / np.sqrt(np.outer(d, d))
    
    # Generar volatilidades dinámicas univariadas (procesos GARCH)
    vols = np.zeros((T, N))
    returns = np.zeros((T, N))
    
    # Inicialización de vols
    vols[0, :] = 0.015  # Volatilidad diaria inicial ~24% anualizada
    
    # Coeficientes GARCH comunes
    omega = 0.000005
    alpha = 0.05
    gamma = 0.05
    beta = 0.85
    
    # Generar
    for t in range(T):
        # Generar shock multivariado normal con correlación base_corr
        shocks = np.random.multivariate_normal(np.zeros(N), base_corr)
        
        # Calcular retornos
        returns[t, :] = shocks * vols[t, :]
        
        # Actualizar vols para t+1
        if t < T - 1:
            for i in range(N):
                shock_val = returns[t, i]
                # Efecto apalancamiento (GJR-GARCH)
                asym = shock_val**2 if shock_val < 0 else 0
                vols[t+1, i] = np.sqrt(
                    omega + alpha * (shock_val**2) + gamma * asym + beta * (vols[t, i]**2)
                )
                
    dates = pd.date_range(end="2026-06-08", periods=T, freq="B")
    columns = [f"Asset_{i+1}" for i in range(N)]
    return pd.DataFrame(returns, index=dates, columns=columns)

def run_verification():
    print("=" * 60)
    print("INICIANDO PRUEBAS DE VERIFICACIÓN DE VOLATILITYENGINE")
    print("=" * 60)
    
    T, N = 500, 26
    print(f"Generando {T} observaciones de retornos sintéticos para {N} activos...")
    data = generate_synthetic_data(T=T, N=N)
    print("Retornos sintéticos generados con éxito.")
    print(data.head())
    
    # Inicializar motor
    print("\nInicializando VolatilityEngine...")
    engine = VolatilityEngine(data, garch_p=1, garch_o=1, garch_q=1)
    
    # Ejecutar ajuste completo
    print("\nEjecutando ajuste (fit) en dos etapas...")
    start_time = time.time()
    # Usamos n_jobs=2 para validar la paralelización sin sobrecargar CPU del usuario
    engine.fit(n_jobs=2)
    elapsed = time.time() - start_time
    
    print("\n" + "-" * 50)
    print("VERIFICACIÓN DE RESULTADOS:")
    print("-" * 50)
    print(f"Tiempo de cómputo total: {elapsed:.2f} segundos.")
    
    # Verificar parámetros DCC
    print(f"DCC Parámetro a: {engine.dcc_a:.6f}")
    print(f"DCC Parámetro b: {engine.dcc_b:.6f}")
    print(f"Suma (a + b): {engine.dcc_a + engine.dcc_b:.6f}")
    
    # Test 1: Comprobar formas
    H = engine.get_conditional_covariances()
    R = engine.get_conditional_correlations()
    
    assert H.shape == (T, N, N), f"Forma incorrecta de H_t: {H.shape}"
    assert R.shape == (T, N, N), f"Forma incorrecta de R_t: {R.shape}"
    print("Test 1 (Dimensiones de Tensores): APROBADO")
    
    # Test 2: Comprobar NaNs
    assert not np.isnan(H).any(), "¡H_t contiene valores NaN!"
    assert not np.isnan(R).any(), "¡R_t contiene valores NaN!"
    print("Test 2 (Estabilidad Numérica - Sin NaNs): APROBADO")
    
    # Test 3: Verificar que las correlaciones estén acotadas en [-1, 1]
    assert np.all(R >= -1.0) and np.all(R <= 1.0), "¡Existen correlaciones fuera del rango [-1, 1]!"
    # Verificar que la diagonal es 1
    for t in range(min(T, 5)):
        diag = np.diag(R[t])
        assert np.allclose(diag, 1.0, atol=1e-5), f"¡La diagonal en t={t} no es exactamente 1.0! Diag: {diag[:5]}"
    print("Test 3 (Propiedades de Correlación - R_t): APROBADO")
    
    # Test 4: Persistencia y carga de datos
    temp_file = "temp_volatility_results.npz"
    try:
        engine.save(temp_file)
        loaded = np.load(temp_file, allow_pickle=True)
        try:
            assert loaded['H'].shape == H.shape
            assert loaded['R'].shape == R.shape
            assert len(loaded['assets']) == N
            assert loaded['assets'][0] == "Asset_1"
        finally:
            loaded.close()
        print("Test 4 (Persistencia en Archivo .npz): APROBADO")
    finally:
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except Exception as e:
                print(f"Advertencia al eliminar archivo temporal: {e}")
            
    print("\n" + "=" * 60)
    print("¡TODAS LAS PRUEBAS DE VOLATILITYENGINE SE COMPLETARON CON ÉXITO!")
    print("=" * 60)

if __name__ == "__main__":
    # Necesario para que multiprocessing funcione correctamente en Windows
    run_verification()
