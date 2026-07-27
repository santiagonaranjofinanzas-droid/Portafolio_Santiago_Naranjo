import pandas as pd
import numpy as np
import xgboost as xgb
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import classification_report, roc_auc_score
import optuna
import shap
import matplotlib.pyplot as plt

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
        (Mantenido por compatibilidad retrospectiva)
        """
        state_changes = (hmm_states.shift(-horizon) != hmm_states).astype(int)
        return state_changes.dropna()

    def prepare_academic_target(self, df_raw, hmm_states=None, horizon=5):
        """
        Target basado en realidades financieras: 1 si el S&P 500 experimenta un
        drawdown extremo (retorno acumulado a futuro < cuantil 5% de retornos históricos) en los próximos 'horizon' días.
        """
        # Calcular retornos del S&P500
        sp500_prices = df_raw['SP500'].ffill().dropna()
        sp500_returns = np.log(sp500_prices / sp500_prices.shift(1)).dropna()
        
        # Retornos acumulados hacia adelante en la ventana (horizonte)
        forward_returns = sp500_returns.rolling(window=horizon).sum().shift(-horizon)
        
        # Umbral del cuantil 5% (evento de estrés del mercado)
        threshold = sp500_returns.quantile(0.05)
        
        # 1 si el S&P500 cae por debajo de su cuantil 5% en los próximos 'horizon' días
        target = (forward_returns < threshold).astype(int)
        return target.dropna()

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
            
            # Validación cruzada para series temporales con PURGA y EMBARGO
            tscv = TimeSeriesSplit(n_splits=3)
            aucs = []
            horizon = 5  # Horizonte de predicción del target
            embargo_period = 10 # 10 días de embargo (2x el horizonte) para evitar correlación serial
            
            # Purga: Remover las últimas 'horizon' observaciones de train_idx
            # ya que sus etiquetas y_t dependen de información de retorno futuro (hasta t+horizon),
            # lo que solapa con el conjunto de validación val_idx.
            # Embargo: Remover 'embargo_period' días para mitigar correlación serial de características.
            # El buffer de embargo de 10 días absorbe y cubre completamente la purga de 5 días.
            purge_and_embargo = max(horizon, embargo_period)
            
            for train_idx, val_idx in tscv.split(X):
                if len(train_idx) > purge_and_embargo:
                    effective_train_idx = train_idx[:-purge_and_embargo]
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

    def explain_model_shap(self, X, output_path=None):
        """
        Genera valores SHAP para interpretabilidad del modelo.
        Devuelve el explainer y los valores SHAP, y opcionalmente guarda el summary plot.
        """
        if self.model is None:
            raise ValueError("El modelo debe estar entrenado antes de usar SHAP.")
            
        print("Calculando SHAP values para auditoría XAI...")
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(X)
        
        if output_path:
            plt.figure(figsize=(10, 6))
            shap.summary_plot(shap_values, X, show=False)
            plt.tight_layout()
            plt.savefig(output_path)
            plt.close()
            print(f"SHAP summary plot guardado en: {output_path}")
            
        return explainer, shap_values

if __name__ == "__main__":
    # La validación completa se realizará en el script de integración principal
    print("XGBPredictor cargado. Listo para entrenamiento y validación walk-forward.")
