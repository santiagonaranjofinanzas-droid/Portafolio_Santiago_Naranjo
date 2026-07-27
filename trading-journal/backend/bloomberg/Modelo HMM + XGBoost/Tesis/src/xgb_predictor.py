import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score
import optuna

class XGBPredictor:
    """
    Clasificador XGBoost para predecir transiciones de régimen y eventos de riesgo.
    """
    def __init__(self, objective='binary:logistic'):
        self.model = None
        self.params = {
            'objective': objective,
            'eval_metric': 'auc',
            'random_state': 42
        }
        
    def prepare_target(self, isri_series, hmm_states, horizon=5, threshold=-0.02):
        """
        Define el target: 1 si hay un drawdown significativo o cambio de estado en t+horizon.
        """
        # Evento A: Cambio a estado de estrés (asumiendo que el estado con menor media es estrés)
        # Para fines de simplificación en el prototipo, detectamos cambios de estado discretos
        state_changes = (hmm_states.shift(-horizon) != hmm_states).astype(int)
        
        # Evento B: Retorno negativo extremo en el horizonte
        # (Usaríamos los retornos del SP500 para una validación financiera real)
        
        return state_changes.dropna()

    def train_with_optuna(self, X, y, n_trials=50):
        """Optimización bayesiana de hiperparámetros."""
        # Tarea 1: Mitigación del Desbalance de Clases
        # Calculamos el ratio negativos/positivos dinámicamente sobre el set de entrenamiento
        pos_cases = np.sum(y == 1)
        neg_cases = np.sum(y == 0)
        # Manejo de división por cero por seguridad estadística
        scale_weight = neg_cases / pos_cases if pos_cases > 0 else 1.0
        
        print(f"INFO: Ratio de desbalance detectado: {scale_weight:.2f} (neg/pos)")
        
        # Inyectamos el parámetro en la configuración base
        self.params['scale_pos_weight'] = scale_weight

        def objective(trial):
            param = {
                'max_depth': trial.suggest_int('max_depth', 3, 10),
                'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.2),
                'n_estimators': trial.suggest_int('n_estimators', 100, 500),
                'subsample': trial.suggest_float('subsample', 0.6, 1.0),
                'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            }
            model = xgb.XGBClassifier(**param, **self.params)
            
            # Validación cruzada para series temporales con EMBARGO
            tscv = TimeSeriesSplit(n_splits=3)
            aucs = []
            embargo_period = 10 # 10 días de embargo (2x el horizonte)
            
            for train_idx, val_idx in tscv.split(X):
                # Aplicar Embargo: Eliminar los últimos 'embargo_period' días del entrenamiento
                # si están demasiado cerca del inicio de la validación.
                if len(train_idx) > embargo_period:
                    effective_train_idx = train_idx[:-embargo_period]
                else:
                    effective_train_idx = train_idx
                    
                X_t, X_v = X.iloc[effective_train_idx], X.iloc[val_idx]
                y_t, y_v = y.iloc[effective_train_idx], y.iloc[val_idx]
                
                # Tarea 1: Corrección del Optimizador Bayesiano
                # Verificamos si hay ambas clases en el fold de validación
                # Esto previene el ruido de AUC = 0.5 cuando no hay eventos de estrés
                if len(np.unique(y_v)) > 1:
                    model.fit(X_t, y_t)
                    preds = model.predict_proba(X_v)[:, 1]
                    score = roc_auc_score(y_v, preds)
                    aucs.append(score if not np.isnan(score) else 0.5)
            
            return np.mean(aucs) if aucs else 0.5

        study = optuna.create_study(direction='maximize')
        study.optimize(objective, n_trials=n_trials)
        
        print(f"\nMejores hiperparámetros: {study.best_params}")
        self.model = xgb.XGBClassifier(**study.best_params, **self.params)
        self.model.fit(X, y)
        
    def predict(self, X):
        return self.model.predict_proba(X)[:, 1]

if __name__ == "__main__":
    # La validación completa se realizará en el script de integración principal
    print("XGBPredictor cargado. Listo para entrenamiento y validación walk-forward.")
