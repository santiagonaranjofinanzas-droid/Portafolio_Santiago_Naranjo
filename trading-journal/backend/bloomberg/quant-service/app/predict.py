import os
import time
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from app.schemas import PredictionRequest, PredictionResponse, ModelHealth
from app.preprocess import PreprocessEngine

class DecisionEngine:
    def __init__(self, xgb_model, hmm_model, hmm_prior, scaler_params, pca_loadings):
        self.xgb_model = xgb_model
        self.hmm_model = hmm_model
        self.hmm_prior = hmm_prior
        self.pca_loadings = pca_loadings  # vector of loadings
        self.preprocess_engine = PreprocessEngine(scaler_params)
        self.n_states = hmm_prior["n_states"]
        self.feature_version = scaler_params["feature_version"]
        self.model_version = scaler_params["model_version"]
        self.models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models")

    def _sort_hmm_states(self):
        """
        Garantiza que el estado 0 sea el de menor volatilidad y el N sea el de mayor.
        Esto previene que las predicciones de XGBoost fallen al recalibrar.
        """
        if self.hmm_model is None: return
        
        # Ordenar por la varianza de las emisiones (emisiones de ISRI)
        means = self.hmm_model.means_.flatten()
        variances = self.hmm_model.covars_.flatten()
        
        # En HMM de una sola variable (ISRI), usamos la varianza para identificar estrés
        new_order = np.argsort(variances)
        
        self.hmm_model.means_ = self.hmm_model.means_[new_order]
        self.hmm_model.covars_ = self.hmm_model.covars_[new_order]
        self.hmm_model.transmat_ = self.hmm_model.transmat_[np.ix_(new_order, new_order)]
        self.hmm_model.startprob_ = self.hmm_model.startprob_[new_order]

    def calibrate(self, historical_features_df: pd.DataFrame):
        """
        Recalibra el HMM con datos recientes. 
        Este proceso es ligero porque usa los parámetros actuales como punto de partida.
        """
        try:
            # 1. Preprocesar serie completa
            isri_series = []
            for _, row in historical_features_df.iterrows():
                try:
                    feat_dict = row.to_dict()
                    x_s = self.preprocess_engine.preprocess(feat_dict)
                    isri_series.append(self.compute_isri(x_s))
                except:
                    continue
            
            if len(isri_series) < 50:
                return {"status": "error", "message": "Insufficient data for calibration"}

            X = np.array(isri_series).reshape(-1, 1)
            
            # 2. Re-entrenar HMM (Pocas iteraciones, warm start implícito)
            self.hmm_model.n_iter = 50 
            self.hmm_model.init_params = ""
            self.hmm_model.fit(X)
            
            # 3. Normalizar Orden de Estados (CRÍTICO)
            self._sort_hmm_states()
            
            # 4. Persistir (Opcional, pero recomendado para Render)
            import pickle
            with open(os.path.join(self.models_dir, "hmm.pkl"), "wb") as f:
                pickle.dump(self.hmm_model, f)
            
            return {"status": "success", "message": "HMM Calibrated and Sorted"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def compute_isri(self, x_scaled: np.ndarray) -> float:
        """
        Calcula el ISRI usando los pesos de PCA (primera componente principal).
        x_scaled es (1, n_features). pca_loadings es (n_features, 1) o (n_features,)
        """
        isri_value = np.dot(x_scaled, self.pca_loadings)
        return float(np.asarray(isri_value).squeeze())

    def hmm_forward_step(self, y_t: float, prior_state_vector: List[float]) -> np.ndarray:
        """
        Filtro Forward HMM: P(S_t  y_1:t)
        """
        prior_state = np.array(prior_state_vector, dtype=float)
        if prior_state.shape[0] != self.n_states:
            prior_state = np.array(self.hmm_prior["pi_0"], dtype=float)
        # Ensure it sums to 1
        if prior_state.sum() == 0:
            prior_state = np.array(self.hmm_prior["pi_0"], dtype=float)
        else:
            prior_state = prior_state / prior_state.sum()

        transmat = self.hmm_model.transmat_
        
        # P(S_t  y_1:t-1) = sum_{S_{t-1}} P(S_t  S_{t-1}) * P(S_{t-1}  y_{1:t-1})
        predicted_state = transmat.T @ prior_state
        
        # Emission probability P(y_t  S_t)
        # _compute_log_likelihood expects a 2D array (n_samples, n_features)
        y_obs = np.array([[y_t]])
        log_emission = self.hmm_model._compute_log_likelihood(y_obs)[0]
        # Prevent underflow/overflow by shifting
        log_emission -= np.max(log_emission)
        emission_probs = np.exp(log_emission)
        
        # Update step: P(S_t  y_1:t) \propto P(y_t  S_t) * predicted_state
        posterior = emission_probs * predicted_state
        if posterior.sum() == 0:
            posterior = predicted_state  # Fallback if emission is 0
        posterior = posterior / posterior.sum()
        
        return posterior

    def predict(self, request: PredictionRequest) -> PredictionResponse:
        started_at = time.perf_counter()
        # 1. Preprocesamiento (Winsorización + Z-score)
        x_scaled = self.preprocess_engine.preprocess(request.features)
        
        # 2. Computar ISRI
        isri_t = self.compute_isri(x_scaled)
        
        # 3. HMM Forward Step (Inferencia de Régimen Actual)
        new_state_vector = self.hmm_forward_step(isri_t, request.state_vector)
        
        # Nombrar regímenes basado en su media de ISRI (Asumiendo 3 regímenes: low, transition, high)
        # Los mapeos precisos dependen de las medias del HMM, simplificaremos asumiendo un orden.
        # En producción deberíamos mapear según hmm_model.means_
        means = self.hmm_model.means_.flatten()
        sorted_indices = np.argsort(means)
        
        # Map states to their qualitative labels
        regime_names = ["low", "transition", "high"]
        regime_probs = {}
        for i, idx in enumerate(sorted_indices):
            if i < len(regime_names):
                regime_probs[regime_names[i]] = float(new_state_vector[idx])
            else:
                regime_probs[f"state_{idx}"] = float(new_state_vector[idx])

        # 4. Predicción XGBoost (Estrés en t+5)
        # Las features para XGBoost son [isri, Prob_State_0, Prob_State_1, ...]
        xgb_features = [isri_t] + new_state_vector.tolist()
        # Create DataFrame to match training feature names if required by XGBoost
        # Assuming training features were ['ISRI', 'Prob_State_0', 'Prob_State_1', ...]
        feature_names = ['ISRI'] + [f'Prob_State_{i}' for i in range(self.n_states)]
        X_xgb = pd.DataFrame([xgb_features], columns=feature_names)
        
        stress_prob = float(self.xgb_model.predict_proba(X_xgb)[0, 1])
        
        # 5. Cálculos de Confiabilidad y Entropía
        # Entropía de Shannon normalizada
        entropy = -np.sum(new_state_vector * np.log(new_state_vector + 1e-9)) / np.log(self.n_states)
        
        # Omega Quant (Incertidumbre). A mayor entropía, mayor omega.
        omega_quant = float(entropy * 0.5 + 0.1) 
        
        # Confidence score (1 - uncertainty)
        confidence_score = 1.0 - omega_quant

        # 6. Responder
        return PredictionResponse(
            regime_probabilities=regime_probs,
            state_vector=new_state_vector.tolist(),
            stress_probability_t5=stress_prob,
            confidence_score=confidence_score,
            regime_entropy=float(entropy),
            omega_quant=omega_quant,
            model_health=ModelHealth(
                psi=0.0,
                kl_div=0.0,
                status="UNVALIDATED",
                psi_trend="INSUFFICIENT_HISTORY"
            ),
            timestamp=request.timestamp,
            model_version=self.model_version,
            feature_version=self.feature_version,
            inference_time_ms=max(1, int((time.perf_counter() - started_at) * 1000))
        )
