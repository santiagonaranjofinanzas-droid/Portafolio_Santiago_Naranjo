"""
analyze_detection_capacity.py - Análisis estadístico de la capacidad de detección de crisis,
métricas de rendimiento y lead-time del meta-clasificador.
"""

import sys
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, classification_report, roc_auc_score, average_precision_score
import time

#Agregar la ruta del espacio de trabajo
sys.path.append(r"c:\Users\YOUR_USERNAME\Desktop\Universidad\Tesis_2026\Tesis_Repotenciada")

from VolatilityEngine import VolatilityEngine
from TopologyEngine import TopologyEngine
from MetaClassifier import MetaClassifier

def generate_multi_crisis_data(T=1200, N=26, seed=42):
    """
    Genera una serie temporal realista de 1200 días (~5 años) con 3 eventos
    de crisis distintos de diferente duración e intensidad.
    """
    np.random.seed(seed)
    
    # Matriz de correlación estable (bajo co-movimiento)
    stable_corr = np.eye(N)
    for i in range(N):
        for j in range(i):
            stable_corr[i, j] = 0.15 if (i - j) % 3 == 0 else -0.05
            stable_corr[j, i] = stable_corr[i, j]
            
    # Matriz de correlación de crisis (alta sincronización)
    crisis_corr = np.eye(N)
    for i in range(N):
        for j in range(i):
            crisis_corr[i, j] = 0.65 if (i - j) % 2 == 0 else 0.35
            crisis_corr[j, i] = crisis_corr[i, j]
            
    # Asegurar positividad definida
    for mat in [stable_corr, crisis_corr]:
        val, vec = np.linalg.eigh(mat)
        val = np.maximum(val, 0.1)
        mat[:, :] = vec @ np.diag(val) @ vec.T
        d = np.diag(mat)
        mat[:, :] = mat / np.sqrt(np.outer(d, d))
        
    vols = np.zeros((T, N))
    returns = np.zeros((T, N))
    vols[0, :] = 0.015
    
    # Coeficientes GARCH
    omega, alpha, gamma, beta = 0.000005, 0.04, 0.04, 0.88
    
    # Definir periodos de crisis (crash de mercado)
    # Evento 1: t=250 a 300 (Corto pero violento)
    # Evento 2: t=600 a 680 (Recesión prolongada)
    # Evento 3: t=950 a 1020 (Pánico repentino)
    crisis_periods = [(250, 300), (600, 680), (950, 1020)]
    
    def is_crisis(t):
        for start, end in crisis_periods:
            if start <= t <= end:
                return True
        return False
        
    for t in range(T):
        if is_crisis(t):
            # Alta correlación y volatilidad multiplicada
            shocks = np.random.multivariate_normal(np.zeros(N), crisis_corr)
            returns[t, :] = shocks * vols[t, :] * 2.2
            # Sesgo negativo en renta variable (Asset_1 a Asset_7)
            returns[t, :7] -= 0.018
        else:
            # Estado estable normal
            shocks = np.random.multivariate_normal(np.zeros(N), stable_corr)
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
    return pd.DataFrame(returns, index=dates, columns=columns), crisis_periods

def compute_drawdown_target(prices, H=63, threshold=0.10):
    """
    Reconstruye el target y_t basándose en el drawdown futuro máximo en H días.
    """
    T = len(prices)
    y = np.zeros(T, dtype=int)
    for t in range(T - H):
        future_prices = prices[t : t + H + 1]
        peaks = np.maximum.accumulate(future_prices)
        drawdowns = (peaks - future_prices) / peaks
        max_dd = np.max(drawdowns[1:])
        y[t] = 1 if max_dd > threshold else 0
    y[T-H:] = y[T-H-1]
    return pd.Series(y)

def analyze_performance():
    T, N = 1200, 26
    print("1. Generando serie temporal multivariada con 3 eventos de crisis históricos...")
    data, crisis_periods = generate_multi_crisis_data(T=T, N=N)
    
    spx_returns = data["Asset_1"].values
    spx_prices = 100.0 * np.exp(np.cumsum(spx_returns))
    
    # Calcular drawdown futuro
    y = compute_drawdown_target(spx_prices, H=63, threshold=0.08)
    
    # 2. Ajustar pipeline
    print("2. Corriendo el pipeline DCC-GARCH y Extractor Espectral...")
    v_engine = VolatilityEngine(data)
    v_engine.fit(n_jobs=2)
    
    H_t = v_engine.get_conditional_covariances()
    R_t = v_engine.get_conditional_correlations()
    
    t_engine = TopologyEngine(H_t, R_t, v_engine.assets, v_engine.dates)
    X = t_engine.extract_features(k=3, stable_window=150)
    
    # 3. Clasificación CPCV y Modelo Final
    print("3. Ajustando y validando MetaClassifier (CPCV)...")
    clf = MetaClassifier(n_groups=6, n_test_groups=2, purge_window=63, embargo_window=21)
    
    # Validación CPCV
    cpcv_results = clf.run_cpcv_validation(X, y, spx_returns)
    
    # Ajustar final
    clf.fit_final_model(X, y, spx_returns)
    probs, xi = clf.predict_proba(X, spx_returns)
    
    # 4. Análisis Estadístico del Desempeño
    y_pred_class = (probs > 0.5).astype(int)
    
    print("\n" + "=" * 60)
    print("MÉTRICAS CLÁSICAS DE EVALUACIÓN (IN-SAMPLE FINAL):")
    print("=" * 60)
    print(classification_report(y, y_pred_class, target_names=["Estable (0)", "Crisis (1)"]))
    
    cm = confusion_matrix(y, y_pred_class)
    tn, fp, fn, tp = cm.ravel()
    
    sensitivity = tp / (tp + fn)
    specificity = tn / (tn + fp)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * (precision * sensitivity) / (precision + sensitivity) if (precision + sensitivity) > 0 else 0.0
    
    print("-" * 50)
    print(f"Sensibilidad (Tasa de Detección de Crisis): {sensitivity:.2%}")
    print(f"Especificidad (Tasa de Detección de Calma): {specificity:.2%}")
    print(f"Precisión (Confianza en Señales de Crisis): {precision:.2%}")
    print(f"Tasa de Falsas Alarmas (1 - Especificidad): {1.0 - specificity:.2%}")
    print(f"F1-Score del Meta-Clasificador: {f1:.4f}")
    print(f"Rendimiento CPCV OOS MCC: {cpcv_results['mcc']:.4f}")
    
    # 5. Análisis de Lead-Time de Anticipación
    # Medimos cuántos días antes de que empiece físicamente la crisis
    # (definida por crisis_periods) el modelo ya activa la probabilidad > 0.50.
    print("\n" + "=" * 60)
    print("ANÁLISIS DE CAPACIDAD DE ANTICIPACIÓN (LEAD-TIME):")
    print("=" * 60)
    
    lead_times = []
    for event_idx, (start_idx, end_idx) in enumerate(crisis_periods):
        # Buscamos la primera señal de alerta (prob > 0.5) en los 63 días anteriores al inicio
        search_start = max(0, start_idx - 63)
        alert_idx = None
        for t_idx in range(search_start, start_idx):
            if y_pred_class[t_idx] == 1:
                alert_idx = t_idx
                break
                
        if alert_idx is not None:
            lead_time_days = start_idx - alert_idx
            lead_times.append(lead_time_days)
            print(f"Evento de Crisis {event_idx+1} (Día {start_idx}): Detección anticipada con {lead_time_days} días de anticipación (Lead-Time).")
        else:
            print(f"Evento de Crisis {event_idx+1} (Día {start_idx}): No detectada anticipadamente (Fallo de Alerta Temprana).")
            
    if len(lead_times) > 0:
        print(f"Lead-Time Promedio de Alerta Temprana: {np.mean(lead_times):.1f} días de negociación.")
    else:
        print("El modelo no anticipó las crisis previas en el rango de búsqueda.")
        
    print("\n" + "=" * 60)
    print("ESTADÍSTICAS COMPLEMENTARIAS DE INFERENCIA:")
    print("=" * 60)
    # Mostrar la correlación de la probabilidad de crisis con el autovalor dominante y la entropía espectral
    corr_lambda = np.corrcoef(probs, X["lambda_dominant"].values)[0, 1]
    corr_entropy = np.corrcoef(probs, X["entropy_spectral"].values)[0, 1]
    corr_mtl = np.corrcoef(probs, X["mtl"].values)[0, 1]
    corr_hmm = np.corrcoef(probs, xi)[0, 1]
    
    print(f"Correlación (Probabilidad Crisis vs Autovalor Dominante): {corr_lambda:.4f} (Esperado: Alta/Positiva)")
    print(f"Correlación (Probabilidad Crisis vs Entropía Espectral): {corr_entropy:.4f} (Esperado: Alta/Negativa)")
    print(f"Correlación (Probabilidad Crisis vs Contracción MST - MTL): {corr_mtl:.4f} (Esperado: Alta/Negativa)")
    print(f"Correlación (Probabilidad Crisis vs Variable Latente HMM): {corr_hmm:.4f} (Esperado: Alta/Positiva)")
    print("=" * 60)

if __name__ == "__main__":
    analyze_performance()
