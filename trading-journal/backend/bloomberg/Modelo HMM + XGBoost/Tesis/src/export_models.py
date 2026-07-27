"""
export_models.py
----------------
Script de exportación de artefactos para el microservicio FastAPI (Fase 1).
Ejecutar UNA VEZ después del entrenamiento completo del pipeline.

Genera:
    models/scaler_params.pkl   — Límites de winsorización + mu/sigma del training set
    models/xgb.pkl             — Modelo XGBoost entrenado
    models/hmm.pkl             — Modelo HMM con matrices de transición y emisión
    models/hmm_prior.pkl       — Prior estacionario π₀ para bootstrap del state_vector

Uso:
    python export_models.py

IMPORTANTE: Este script debe ejecutarse desde el mismo contexto que main_pipeline.py,
con acceso a los datos de entrenamiento originales (X_train).
"""

import os
import json
import pickle
import joblib
import numpy as np
import pandas as pd

#─────────────────────────────────────────────
#CONFIGURACIÓN
#─────────────────────────────────────────────
OUTPUT_DIR = "models"
FEATURE_VERSION = "fv_1.0.3"   # Incrementar si cambia el pipeline de features
MODEL_VERSION   = "v1.3.2"     # Incrementar si se re-entrena el modelo
WINSOR_LOWER_Q  = 0.01         # Percentil 1% — igual que en entrenamiento
WINSOR_UPPER_Q  = 0.99         # Percentil 99% — igual que en entrenamiento

os.makedirs(OUTPUT_DIR, exist_ok=True)


#─────────────────────────────────────────────
#PASO 0: IMPORTAR Y EJECUTAR TU PIPELINE
#─────────────────────────────────────────────
from main_pipeline import run_thesis_pipeline

print("Ejecutando pipeline principal para obtener modelos...")
results = run_thesis_pipeline()

X_train    = results['train_returns']   # pd.DataFrame con retornos del training set (sin escalar)
xgb_model  = results['xgb_model']       # modelo XGBoost entrenado
hmm_model  = results['hmm_model']       # modelo HMM entrenado
#────────────────────────────────────────────────────

assert X_train is not None,   "X_train no está definido. Conecta tu pipeline arriba."
assert xgb_model is not None, "xgb_model no está definido. Conecta tu pipeline arriba."
assert hmm_model is not None, "hmm_model no está definido. Conecta tu pipeline arriba."


#─────────────────────────────────────────────
#ARTEFACTO 1: scaler_params.pkl
#Encapsula winsorización + Z-score con los
#parámetros FIJOS del training set.
#─────────────────────────────────────────────
print("\n[1/4] Exportando scaler_params.pkl ...")

winsor_lower = X_train.quantile(WINSOR_LOWER_Q)
winsor_upper = X_train.quantile(WINSOR_UPPER_Q)

X_winsorized = X_train.clip(lower=winsor_lower, upper=winsor_upper, axis=1)

mu    = X_winsorized.mean()
sigma = X_winsorized.std()

#Validación: sigma no debe tener ceros (división por cero en inferencia)
zero_sigma = sigma[sigma == 0]
if not zero_sigma.empty:
    raise ValueError(
        f"Las siguientes features tienen sigma=0 en el training set: "
        f"{zero_sigma.index.tolist()}\n"
        f"Revisar si hay features constantes o mal calculadas."
    )

scaler_params = {
    "feature_names":  X_train.columns.tolist(),
    "winsor_lower":   winsor_lower.to_dict(),
    "winsor_upper":   winsor_upper.to_dict(),
    "mu":             mu.to_dict(),
    "sigma":          sigma.to_dict(),
    "feature_version": FEATURE_VERSION,
    "model_version":   MODEL_VERSION,
    "winsor_lower_q":  WINSOR_LOWER_Q,
    "winsor_upper_q":  WINSOR_UPPER_Q,
}

path_scaler = os.path.join(OUTPUT_DIR, "scaler_params.pkl")
joblib.dump(scaler_params, path_scaler)
print(f"     Guardado: {path_scaler}")
print(f"    Features ({len(scaler_params['feature_names'])}): {scaler_params['feature_names']}")


#─────────────────────────────────────────────
#ARTEFACTO 2: xgb.pkl
#─────────────────────────────────────────────
print("[2/4] Exportando xgb.pkl ...")

path_xgb = os.path.join(OUTPUT_DIR, "xgb.pkl")
joblib.dump(xgb_model, path_xgb)
print(f"     Guardado: {path_xgb}")


#─────────────────────────────────────────────
#ARTEFACTO 3: hmm.pkl
#Exporta el objeto HMM completo.
#hmmlearn guarda internamente:
#  - transmat_    : Matriz de transición A (n_states x n_states)
#  - emissionprob_: Probabilidades de emisión B
#  - startprob_   : Prior inicial
#─────────────────────────────────────────────
print("[3/4] Exportando hmm.pkl ...")

path_hmm = os.path.join(OUTPUT_DIR, "hmm.pkl")
with open(path_hmm, "wb") as f:
    pickle.dump(hmm_model, f)
print(f"     Guardado: {path_hmm}")

#Verificación rápida de matrices
if hasattr(hmm_model, "transmat_"):
    print(f"    Matriz de transición:\n{np.round(hmm_model.transmat_, 3)}")


#─────────────────────────────────────────────
#ARTEFACTO 4: hmm_prior.pkl
#Prior estacionario π₀: distribución de largo
#plazo del HMM. Se usa para inicializar el
#state_vector cuando no hay historia previa
#(primer arranque) o cuando el gap temporal
#supera MAX_STATE_GAP_BARS.
##El prior estacionario es el eigenvector
#izquierdo de la matriz de transición A
#asociado al eigenvalor 1.
#─────────────────────────────────────────────
print("[4/4] Exportando hmm_prior.pkl ...")

A = hmm_model.transmat_
eigenvalues, eigenvectors = np.linalg.eig(A.T)

#Identificar el eigenvalor más cercano a 1
idx_stationary = np.argmin(np.abs(eigenvalues - 1.0))
pi_0 = np.real(eigenvectors[:, idx_stationary])
pi_0 = pi_0 / pi_0.sum()   # Normalizar a distribución de probabilidad

#Sanidad: todos los valores deben ser positivos
assert np.all(pi_0 >= 0), "Prior estacionario tiene valores negativos. Revisar HMM."
assert abs(pi_0.sum() - 1.0) < 1e-6, "Prior estacionario no suma 1."

hmm_prior = {
    "pi_0":           pi_0.tolist(),
    "n_states":       int(hmm_model.n_components),
    "model_version":  MODEL_VERSION,
}

path_prior = os.path.join(OUTPUT_DIR, "hmm_prior.pkl")
joblib.dump(hmm_prior, path_prior)
print(f"     Guardado: {path_prior}")
print(f"    Prior estacionario π₀: {np.round(pi_0, 4)}")


#─────────────────────────────────────────────
#RESUMEN DE EXPORTACIÓN
#─────────────────────────────────────────────
print("\n" + "─" * 50)
print("EXPORTACIÓN COMPLETADA")
print("─" * 50)

artifacts = {
    "scaler_params.pkl": path_scaler,
    "xgb.pkl":           path_xgb,
    "hmm.pkl":           path_hmm,
    "hmm_prior.pkl":     path_prior,
}

manifest = {
    "model_version":    MODEL_VERSION,
    "feature_version":  FEATURE_VERSION,
    "artifacts":        {k: os.path.abspath(v) for k, v in artifacts.items()},
    "feature_names":    scaler_params["feature_names"],
    "hmm_n_states":     hmm_prior["n_states"],
    "hmm_pi_0":         hmm_prior["pi_0"],
}

manifest_path = os.path.join(OUTPUT_DIR, "manifest.json")
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2)

print(f"\n  Manifest guardado en: {manifest_path}\n")
for name, path in artifacts.items():
    size_kb = os.path.getsize(path) / 1024
    print(f"  [{size_kb:6.1f} KB]  {name}")

print("\n  Próximo paso: conectar estos artefactos en predict.py (FastAPI)")
print("─" * 50)
