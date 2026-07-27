"""
test_meta_classifier.py - Script de prueba de integración de extremo a extremo
que valida el pipeline completo: Volatilidad + Topología + Clasificación CPCV.
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
    from MetaClassifier import MetaClassifier
    print("Módulos importados correctamente.")
except Exception as e:
    print(f"Error al importar módulos: {e}")
    sys.exit(1)

def generate_synthetic_data(T=500, N=26, seed=42):
    """
    Genera retornos sintéticos GARCH con co-movimientos dinámicos.
    """
    np.random.seed(seed)
    base_corr = np.eye(N)
    for i in range(N):
        for j in range(i):
            corr = 0.4 if (i - j) % 2 == 0 else -0.1
            base_corr[i, j] = corr
            base_corr[j, i] = corr
            
    eigvals, eigvecs = np.linalg.eigh(base_corr)
    eigvals = np.maximum(eigvals, 0.1)
    base_corr = eigvecs @ np.diag(eigvals) @ eigvecs.T
    d = np.diag(base_corr)
    base_corr = base_corr / np.sqrt(np.outer(d, d))
    
    vols = np.zeros((T, N))
    returns = np.zeros((T, N))
    vols[0, :] = 0.02  # Mayor volatilidad para simular crisis
    omega, alpha, gamma, beta = 0.00001, 0.06, 0.06, 0.82
    
    for t in range(T):
        # En el medio de la muestra (t de 200 a 250), simulamos una crisis aumentando shocks y correlaciones
        if 200 <= t <= 250:
            shocks = np.random.multivariate_normal(np.zeros(N), base_corr * 1.5 - 0.5 * np.eye(N))
            returns[t, :] = shocks * vols[t, :] * 2.5  # Pánico (altas volatilidades y caídas)
            # Retorno negativo sistémico
            returns[t, :] -= 0.02
        else:
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

def compute_drawdown_target(prices, H=63, threshold=0.08):
    """
    Calcula el target y_t de recesión/drawdown en una ventana de lookahead H.
    """
    T = len(prices)
    y = np.zeros(T, dtype=int)
    for t in range(T - H):
        future_prices = prices[t : t + H + 1]
        peaks = np.maximum.accumulate(future_prices)
        drawdowns = (peaks - future_prices) / peaks
        max_dd = np.max(drawdowns[1:])
        y[t] = 1 if max_dd > threshold else 0
    # Rellenamos el extremo final con el último estado para tener longitud T completa
    y[T-H:] = y[T-H-1]
    return pd.Series(y)

def run_end_to_end_test():
    print("=" * 70)
    print("INICIANDO PRUEBAS DE EXTREMO A EXTREMO DEL META-CLASIFICADOR")
    print("=" * 70)
    
    T, N = 500, 26
    print("1. Generando datos históricos sintéticos...")
    data = generate_synthetic_data(T=T, N=N)
    
    # Simular precios para reconstruir drawdown de SPX500 (Asset_1)
    spx_returns = data["Asset_1"].values
    spx_prices = 100.0 * np.exp(np.cumsum(spx_returns))
    
    # Calcular objetivo supervisado
    print("2. Calculando target de drawdown futuro (SPX500 MaxDD > 8%)...")
    y = compute_drawdown_target(spx_prices, H=40, threshold=0.08)
    print(f"Target calculado. Distribución de clases: {np.bincount(y)} (0: Normal, 1: Crisis)")
    
    # 3. Ajustar VolatilityEngine
    print("\n3. Ajustando VolatilityEngine (GJR-GARCH + DCC)...")
    v_engine = VolatilityEngine(data)
    v_engine.fit(n_jobs=2)
    
    H = v_engine.get_conditional_covariances()
    R = v_engine.get_conditional_correlations()
    
    # 4. Ajustar TopologyEngine
    print("\n4. Extrayendo características topológicas con TopologyEngine...")
    t_engine = TopologyEngine(H, R, v_engine.assets, v_engine.dates)
    X = t_engine.extract_features(k=3, stable_window=100)
    
    # 5. Iniciar MetaClassifier
    # Usamos n_groups=5, n_test_groups=1, purge_window=40, embargo_window=10 para adaptarnos a T=500
    print("\n5. Inicializando MetaClassifier y ejecutando optimización bayesiana...")
    clf = MetaClassifier(n_groups=5, n_test_groups=1, purge_window=40, embargo_window=10)
    
    # Ejecutar hiperoptimización rápida (Optuna)
    clf.optimize_hyperparameters(X, y, spx_returns, n_trials=5)
    
    # Ejecutar validación CPCV out-of-sample
    print("\nEjecutando validación cruzada combinatoria CPCV...")
    cpcv_results = clf.run_cpcv_validation(X, y, spx_returns)
    
    # Ajustar el modelo final definitivo sobre todo el historial
    print("\n6. Ajustando modelo final híbrido jerárquico definitivo...")
    clf.fit_final_model(X, y, spx_returns)
    
    # Realizar predicciones
    print("\nEjecutando predicciones finales (fase de producción)...")
    probs, xi = clf.predict_proba(X, spx_returns)
    
    # 7. Verificaciones de rigor matemático y estabilidad
    print("\n" + "-" * 50)
    print("VERIFICACIÓN DE RESULTADOS EXTREMO A EXTREMO:")
    print("-" * 50)
    print(f"MCC out-of-sample obtenido (CPCV): {cpcv_results['mcc']:.4f}")
    print(f"Brier Score out-of-sample (Calibración): {cpcv_results['brier']:.4f}")
    print(f"PR-AUC out-of-sample: {cpcv_results['pr_auc']:.4f}")
    
    # Tests lógicos
    assert probs.shape == (T,), f"Forma incorrecta de probabilidades predichas: {probs.shape}"
    assert xi.shape == (T,), f"Forma incorrecta de variable de estado HMM: {xi.shape}"
    assert not np.isnan(probs).any(), "¡Las probabilidades predichas contienen NaNs!"
    assert not np.isnan(xi).any(), "¡La variable de estado del HMM contiene NaNs!"
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0), "¡Las probabilidades están fuera de [0, 1]!"
    assert np.all(xi >= 0.0) and np.all(xi <= 1.0), "¡La variable xi está fuera de [0, 1]!"
    
    print("\nTest 1 (Forma y tipos de salida de predicción): APROBADO")
    print("Test 2 (Estabilidad Numérica - Sin NaNs en inferencia): APROBADO")
    print("Test 3 (Acotación de probabilidades [0, 1]): APROBADO")
    
    print("\n" + "=" * 70)
    print("¡EL PIPELINE COMPLETO DE LA TESIS HA SIDO VERIFICADO CON ÉXITO EXTREMO A EXTREMO!")
    print("=" * 70)

if __name__ == "__main__":
    run_end_to_end_test()
