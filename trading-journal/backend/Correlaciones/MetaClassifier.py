"""
MetaClassifier.py - Capa de Inteligencia Artificial (Fase III)

Clase encargada del entrenamiento jerárquico híbrido del meta-clasificador:
1. Capa Estocástica: Ajuste del TVTP-HMM (Time-Varying Transition Probabilities)
   no supervisado para derivar la probabilidad de estado estresado (xi_t).
2. Capa Predictiva: Ajuste del clasificador XGBoost con restricciones
   de monotonicidad lógica y búsqueda bayesiana de hiperparámetros (Optuna).
3. Framework de Validación: Validación Cruzada Combinatoria con Purga y
   Embargo (CPCV) para mitigar el sesgo de supervivencia y leakage temporal.
"""

import logging
import itertools
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from xgboost import XGBClassifier
import optuna
import numba as nb
import time

#Desactivar los logs detallados de Optuna para mantener limpia la consola
optuna.logging.set_verbosity(optuna.logging.WARNING)

#Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("MetaClassifier")


@nb.njit
def _sigmoid(x):
    """
    Función sigmoide numéricamente estable.
    """
    if x >= 0:
        z = np.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = np.exp(x)
        return z / (1.0 + z)


@nb.njit
def _log_sum_exp(a, b):
    """
    Operador Log-Sum-Exp para prevenir desbordamiento numérico.
    """
    max_val = max(a, b)
    if max_val < -1e50:
        return -1e50
    return max_val + np.log(np.exp(a - max_val) + np.exp(b - max_val))


@nb.njit
def _causal_filtered_prob_log_space(returns, z, gamma_0, gamma_1, mu, sigma):
    """
    Filtro Forward Puro implementado en espacio logarítmico.
    Garantiza inferencia causal estricta para producción en MT5 y elimina NaNs.
    """
    T = len(returns)
    log_alpha = np.zeros((T, 2))
    
    # Inicialización a t=0
    p_01_0 = _sigmoid(np.dot(gamma_0, z[0]))
    p_11_0 = _sigmoid(np.dot(gamma_1, z[0]))
    
    # Estado estacionario aproximado logarítmico
    denom_0 = p_01_0 + 1.0 - p_11_0
    pi_1_0 = p_01_0 / denom_0 if denom_0 > 1e-8 else 0.5
    log_pi_1 = np.log(pi_1_0 + 1e-15)
    log_pi_0 = np.log(1.0 - pi_1_0 + 1e-15)
    
    # Densidades de emisión iniciales en espacio logarítmico
    log_b0 = -np.log(np.sqrt(2.0 * np.pi) * sigma[0]) - 0.5 * ((returns[0] - mu[0]) / sigma[0])**2
    log_b1 = -np.log(np.sqrt(2.0 * np.pi) * sigma[1]) - 0.5 * ((returns[0] - mu[1]) / sigma[1])**2
    
    log_alpha[0, 0] = log_pi_0 + log_b0
    log_alpha[0, 1] = log_pi_1 + log_b1
    
    # Bucle Forward autorregresivo
    for t in range(1, T):
        p_01 = _sigmoid(np.dot(gamma_0, z[t]))
        p_11 = _sigmoid(np.dot(gamma_1, z[t]))
        
        log_p_00 = np.log(1.0 - p_01 + 1e-15)
        log_p_01 = np.log(p_01 + 1e-15)
        log_p_10 = np.log(1.0 - p_11 + 1e-15)
        log_p_11 = np.log(p_11 + 1e-15)
        
        log_b0 = -np.log(np.sqrt(2.0 * np.pi) * sigma[0]) - 0.5 * ((returns[t] - mu[0]) / sigma[0])**2
        log_b1 = -np.log(np.sqrt(2.0 * np.pi) * sigma[1]) - 0.5 * ((returns[t] - mu[1]) / sigma[1])**2
        
        # Combinación de transiciones vía Log-Sum-Exp
        log_a0 = _log_sum_exp(log_alpha[t-1, 0] + log_p_00, log_alpha[t-1, 1] + log_p_10)
        log_a1 = _log_sum_exp(log_alpha[t-1, 0] + log_p_01, log_alpha[t-1, 1] + log_p_11)
        
        log_alpha[t, 0] = log_a0 + log_b0
        log_alpha[t, 1] = log_a1 + log_b1
        
    # Extraer la probabilidad filtrada en escala lineal de forma segura
    filtered_prob_state_1 = np.zeros(T)
    for t in range(T):
        max_log = max(log_alpha[t, 0], log_alpha[t, 1])
        denom = np.exp(log_alpha[t, 0] - max_log) + np.exp(log_alpha[t, 1] - max_log)
        filtered_prob_state_1[t] = np.exp(log_alpha[t, 1] - max_log) / denom
        
    return filtered_prob_state_1


@nb.njit
def _tvtp_hmm_log_likelihood_log_space(returns, z, gamma_0, gamma_1, mu, sigma):
    """
    Calcula la log-verosimilitud exacta en espacio logarítmico para la optimización.
    Evita por completo cualquier underflow / overflow numérico de punto flotante.
    """
    T = len(returns)
    log_alpha = np.zeros((T, 2))
    
    # Inicialización a t=0
    p_01_0 = _sigmoid(np.dot(gamma_0, z[0]))
    p_11_0 = _sigmoid(np.dot(gamma_1, z[0]))
    denom = p_01_0 + 1.0 - p_11_0
    
    pi_1 = p_01_0 / denom if denom > 1e-8 else 0.5
    pi_0 = 1.0 - pi_1
    
    log_b0 = -np.log(np.sqrt(2.0 * np.pi) * sigma[0]) - 0.5 * ((returns[0] - mu[0]) / sigma[0])**2
    log_b1 = -np.log(np.sqrt(2.0 * np.pi) * sigma[1]) - 0.5 * ((returns[0] - mu[1]) / sigma[1])**2
    
    log_alpha[0, 0] = np.log(pi_0 + 1e-15) + log_b0
    log_alpha[0, 1] = np.log(pi_1 + 1e-15) + log_b1
    
    for t in range(1, T):
        p_01 = _sigmoid(np.dot(gamma_0, z[t]))
        p_11 = _sigmoid(np.dot(gamma_1, z[t]))
        
        log_p_00 = np.log(1.0 - p_01 + 1e-15)
        log_p_01 = np.log(p_01 + 1e-15)
        log_p_10 = np.log(1.0 - p_11 + 1e-15)
        log_p_11 = np.log(p_11 + 1e-15)
        
        log_b0 = -np.log(np.sqrt(2.0 * np.pi) * sigma[0]) - 0.5 * ((returns[t] - mu[0]) / sigma[0])**2
        log_b1 = -np.log(np.sqrt(2.0 * np.pi) * sigma[1]) - 0.5 * ((returns[t] - mu[1]) / sigma[1])**2
        
        log_a0 = _log_sum_exp(log_alpha[t-1, 0] + log_p_00, log_alpha[t-1, 1] + log_p_10)
        log_a1 = _log_sum_exp(log_alpha[t-1, 0] + log_p_01, log_alpha[t-1, 1] + log_p_11)
        
        log_alpha[t, 0] = log_a0 + log_b0
        log_alpha[t, 1] = log_a1 + log_b1
        
    return _log_sum_exp(log_alpha[T-1, 0], log_alpha[T-1, 1])


def _fit_tvtp_hmm_python(returns, z):
    """
    Calibra el TVTP-HMM sobre las observaciones usando L-BFGS-B y verosimilitud logarítmica.
    Asegura la parsimonia y resuelve el label switching mediante penalizaciones.
    """
    def objective(theta):
        gamma_0 = theta[0:3]
        gamma_1 = theta[3:6]
        mu = theta[6:8]
        sigma = np.exp(theta[8:10])
        
        # Penalización para forzar mu_0 > mu_1 (Evita intercambio de etiquetas)
        penalty = 0.0
        if mu[0] < mu[1]:
            penalty = 1e3 * (mu[1] - mu[0])**2
            
        log_lik = _tvtp_hmm_log_likelihood_log_space(returns, z, gamma_0, gamma_1, mu, sigma)
        return -log_lik + penalty
        
    # Inicialización robusta basada en la media y desviación clásica
    mu_0 = np.mean(returns[returns > 0]) if np.any(returns > 0) else 0.0005
    mu_1 = np.mean(returns[returns < 0]) if np.any(returns < 0) else -0.001
    sigma_0 = np.std(returns[returns > 0]) if np.any(returns > 0) else 0.01
    sigma_1 = np.std(returns[returns < 0]) if np.any(returns < 0) else 0.03
    
    initial_guess = np.array([
        -1.5, 0.0, 0.0,          # gamma_0 (Transición 0 -> 1 controlada)
        1.5, 0.0, 0.0,           # gamma_1 (Persistencia del estado 1)
        mu_0, mu_1,
        np.log(sigma_0), np.log(sigma_1)
    ])
    
    bounds = [
        (-10, 10), (-10, 10), (-10, 10),
        (-10, 10), (-10, 10), (-10, 10),
        (0.0, 0.2), (-0.2, 0.0),
        (-8.0, 0.0), (-8.0, 0.0)
    ]
    
    res = minimize(objective, initial_guess, method="L-BFGS-B", bounds=bounds)
    
    # Extraer parámetros calibrados
    opt_gamma_0 = res.x[0:3]
    opt_gamma_1 = res.x[3:6]
    opt_mu = res.x[6:8]
    opt_sigma = np.exp(res.x[8:10])
    
    return opt_gamma_0, opt_gamma_1, opt_mu, opt_sigma


class MetaClassifier:
    """
    Clase de Inteligencia Artificial que entrena de forma jerárquica el
    meta-clasificador con validación CPCV cruzada robusta.
    """
    
    def __init__(self, n_groups=6, n_test_groups=2, purge_window=126, embargo_window=21):
        """
        Args:
            n_groups: Número de particiones totales en CPCV.
            n_test_groups: Número de particiones elegidas para test.
            purge_window: Ventana total de purga (w + H).
            embargo_window: Ventana de embargo (E).
        """
        self.n_groups = n_groups
        self.n_test_groups = n_test_groups
        self.purge_window = purge_window
        self.embargo_window = embargo_window
        
        # Parámetros del modelo final
        self.best_xgb_params = None
        self.hmm_params = None  # Parámetros del TVTP-HMM final ajustado
        self.model_final = None  # Clasificador XGBoost ajustado sobre toda la muestra
        
        logger.info(f"MetaClassifier inicializado. Configuración CPCV: {n_groups} grupos, "
                    f"{n_test_groups} grupos de test. Purga: {purge_window} días. Embargo: {embargo_window} días.")

    def _generate_cpcv_splits(self, T):
        """
        Genera los índices de entrenamiento y prueba de la CPCV.
        """
        group_size = T // self.n_groups
        groups = []
        for i in range(self.n_groups):
            start = i * group_size
            end = T if i == self.n_groups - 1 else (i + 1) * group_size
            groups.append((start, end))
            
        test_combos = list(itertools.combinations(range(self.n_groups), self.n_test_groups))
        
        splits = []
        for combo in test_combos:
            # Identificar rangos de test
            test_ranges = [groups[idx] for idx in combo]
            
            # Crear máscara de entrenamiento
            train_mask = np.ones(T, dtype=bool)
            
            for start, end in test_ranges:
                # Excluir test
                train_mask[start:end] = False
                
                # Purgar antes del test
                purge_start = max(0, start - self.purge_window)
                train_mask[purge_start:start] = False
                
                # Purgar y embargo después del test
                embargo_end = min(T, end + self.purge_window + self.embargo_window)
                train_mask[end:embargo_end] = False
                
            train_idx = np.where(train_mask)[0]
            
            # Concatenar índices de test
            test_idx = []
            for start, end in test_ranges:
                test_idx.extend(list(range(start, end)))
            test_idx = np.array(test_idx)
            
            if len(train_idx) > 0 and len(test_idx) > 0:
                splits.append((train_idx, test_idx))
                
        return splits

    def run_cpcv_validation(self, X: pd.DataFrame, y: pd.Series, spx_returns: np.ndarray):
        """
        Ejecuta la validación cruzada combinatoria out-of-sample (OOS).
        """
        logger.info("Iniciando Validación Cruzada Combinatoria con Purga y Embargo (CPCV)...")
        start_time = time.time()
        
        T = len(X)
        splits = self._generate_cpcv_splits(T)
        logger.info(f"Generadas {len(splits)} combinaciones de splits CPCV válidos.")
        
        # Estructuras para almacenar predicciones fuera de muestra
        # En CPCV, una muestra puede estar en el test de múltiples splits
        oos_preds_list = {i: [] for i in range(T)}
        
        # Mapeo de restricciones monótonas para XGBoost
        # X tiene columnas: ['lambda_dominant', 'gar', 'entropy_spectral', 'frobenius_distance', 'kld', 'mtl', 'max_centrality']
        # Añadiremos 'xi' como la característica número 8 (HMM state probability)
        # Monotonía: +1 para lambda, gar, frob, kld, centrality, xi. -1 para entropy y mtl.
        monotone_constraints = (1, 1, -1, 1, 1, -1, 1, 1)
        
        # Extraer variables para el TVTP-HMM
        # z_t = [1, entropy_spectral, mtl]
        z = np.column_stack((
            np.ones(T),
            X["entropy_spectral"].values,
            X["mtl"].values
        ))
        
        # Ejecutar splits
        for i, (train_idx, test_idx) in enumerate(splits):
            logger.info(f"Procesando Split {i+1}/{len(splits)}... (Train size: {len(train_idx)}, Test size: {len(test_idx)})")
            
            # 1. Ajustar el TVTP-HMM en los datos de entrenamiento
            gamma_0, gamma_1, mu, sigma = _fit_tvtp_hmm_python(spx_returns[train_idx], z[train_idx])
            
            # 2. Extraer probabilidades causales filtradas en espacio logarítmico para evitar leakage temporal
            xi = _causal_filtered_prob_log_space(spx_returns, z, gamma_0, gamma_1, mu, sigma)
            
            # 3. Construir conjuntos de entrenamiento y prueba expandidos con xi
            X_train = np.column_stack((X.iloc[train_idx].values, xi[train_idx]))
            y_train = y.iloc[train_idx].values
            
            X_test = np.column_stack((X.iloc[test_idx].values, xi[test_idx]))
            y_test = y.iloc[test_idx].values
            
            # 4. Ajustar XGBoost (utilizando hiperparámetros robustos por defecto)
            model = XGBClassifier(
                n_estimators=100,
                max_depth=4,
                learning_rate=0.05,
                reg_alpha=0.5,
                reg_lambda=1.0,
                monotone_constraints=monotone_constraints,
                eval_metric="logloss",
                random_state=42
            )
            
            model.fit(X_train, y_train)
            
            # 5. Predecir probabilidades de test
            preds = model.predict_proba(X_test)[:, 1]
            
            # Acumular
            for t_idx, pred in zip(test_idx, preds):
                oos_preds_list[t_idx].append(pred)
                
        # Consolidar predicciones OOS (promediar predicciones por instante temporal)
        y_pred_oos = np.zeros(T)
        valid_indices = []
        for idx in range(T):
            if len(oos_preds_list[idx]) > 0:
                y_pred_oos[idx] = np.mean(oos_preds_list[idx])
                valid_indices.append(idx)
            else:
                y_pred_oos[idx] = np.nan
                
        valid_indices = np.array(valid_indices)
        
        # Eliminar registros sin predicciones OOS (por purgas extremas en extremos)
        y_true_valid = y.iloc[valid_indices].values
        y_pred_valid = y_pred_oos[valid_indices]
        
        # Calcular métricas de validación out-of-sample (OOS)
        from sklearn.metrics import precision_recall_curve, auc, matthews_corrcoef, brier_score_loss
        
        # MCC con umbral 0.5
        y_pred_class = (y_pred_valid > 0.5).astype(int)
        mcc = matthews_corrcoef(y_true_valid, y_pred_class)
        
        # Brier Score (calibración)
        brier = brier_score_loss(y_true_valid, y_pred_valid)
        
        # PR-AUC
        precision, recall, _ = precision_recall_curve(y_true_valid, y_pred_valid)
        pr_auc = auc(recall, precision)
        
        elapsed = time.time() - start_time
        logger.info(f"CPCV finalizada en {elapsed:.2f} segundos.")
        logger.info(f"Resultados OOS: MCC = {mcc:.4f}, Brier Score = {brier:.4f}, PR-AUC = {pr_auc:.4f}")
        
        return {
            "mcc": mcc,
            "brier": brier,
            "pr_auc": pr_auc,
            "y_pred_oos": y_pred_oos
        }

    def optimize_hyperparameters(self, X: pd.DataFrame, y: pd.Series, spx_returns: np.ndarray, n_trials=15):
        """
        Ajusta los mejores hiperparámetros de regularización de XGBoost usando búsqueda bayesiana de Optuna.
        """
        logger.info(f"Iniciando optimización bayesiana en Optuna ({n_trials} iteraciones)...")
        
        T = len(X)
        z = np.column_stack((
            np.ones(T),
            X["entropy_spectral"].values,
            X["mtl"].values
        ))
        
        monotone_constraints = (1, 1, -1, 1, 1, -1, 1, 1)
        y_val = y.values
        
        def objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 50, 150),
                "max_depth": trial.suggest_int("max_depth", 3, 6),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-2, 5.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-1, 10.0, log=True),
                "monotone_constraints": monotone_constraints,
                "eval_metric": "logloss",
                "random_state": 42
            }
            
            # Evaluar con validación cruzada temporal sin fugas de datos (Data Leakage)
            from sklearn.model_selection import TimeSeriesSplit
            from sklearn.metrics import log_loss
            
            cv = TimeSeriesSplit(n_splits=3)
            losses = []
            for train_idx, val_idx in cv.split(X.values):
                # Evitar pliegues degenerados si los datos de entrenamiento o validación solo tienen una clase
                if len(np.unique(y_val[train_idx])) < 2 or len(np.unique(y_val[val_idx])) < 2:
                    losses.append(0.69315)  # Log-loss de un clasificador aleatorio p=0.5
                    continue
                    
                # Ajustar el HMM únicamente en el pliegue de entrenamiento del trial
                gamma_0, gamma_1, mu, sigma = _fit_tvtp_hmm_python(spx_returns[train_idx], z[train_idx])
                
                # Extraer probabilidad causal filtrada para todo el historial
                xi = _causal_filtered_prob_log_space(spx_returns, z, gamma_0, gamma_1, mu, sigma)
                
                # Conjunto de datos expandido libre de fugas de datos
                X_exp = np.column_stack((X.values, xi))
                
                model = XGBClassifier(**params)
                model.fit(X_exp[train_idx], y_val[train_idx])
                preds = model.predict_proba(X_exp[val_idx])[:, 1]
                losses.append(log_loss(y_val[val_idx], preds, labels=[0, 1]))
                
            return np.mean(losses)
            
        study = optuna.create_study(direction="minimize")
        study.optimize(objective, n_trials=n_trials)
        
        self.best_xgb_params = study.best_params
        logger.info(f"Optimización Optuna finalizada. Mejores parámetros: {self.best_xgb_params}")
        return self

    def fit_final_model(self, X: pd.DataFrame, y: pd.Series, spx_returns: np.ndarray):
        """
        Entrena el modelo jerárquico híbrido definitivo utilizando la muestra histórica completa.
        """
        logger.info("Entrenando el modelo jerárquico híbrido definitivo sobre todo el historial...")
        start_time = time.time()
        
        T = len(X)
        z = np.column_stack((
            np.ones(T),
            X["entropy_spectral"].values,
            X["mtl"].values
        ))
        
        # 1. Ajustar el TVTP-HMM final
        gamma_0, gamma_1, mu, sigma = _fit_tvtp_hmm_python(spx_returns, z)
        self.hmm_params = {
            "gamma_0": gamma_0,
            "gamma_1": gamma_1,
            "mu": mu,
            "sigma": sigma
        }
        
        # Generar probabilidad latente filtrada causal final xi_t
        xi = _causal_filtered_prob_log_space(spx_returns, z, gamma_0, gamma_1, mu, sigma)
        
        # 2. Construir DataFrame final expandido
        X_final = np.column_stack((X.values, xi))
        
        # Usar parámetros optimizados o por defecto
        if self.best_xgb_params is None:
            logger.info("Utilizando hiperparámetros robustos por defecto para XGBoost.")
            self.best_xgb_params = {
                "n_estimators": 100,
                "max_depth": 4,
                "learning_rate": 0.05,
                "reg_alpha": 0.5,
                "reg_lambda": 1.0
            }
            
        monotone_constraints = (1, 1, -1, 1, 1, -1, 1, 1)
        
        # 3. Ajustar XGBoost definitivo
        self.model_final = XGBClassifier(
            **self.best_xgb_params,
            monotone_constraints=monotone_constraints,
            eval_metric="logloss",
            random_state=42
        )
        self.model_final.fit(X_final, y.values)
        
        elapsed = time.time() - start_time
        logger.info(f"Modelo final ajustado correctamente en {elapsed:.2f} segundos.")
        return self

    def predict_proba(self, X: pd.DataFrame, spx_returns: np.ndarray):
        """
        Realiza inferencia en producción para un nuevo vector X_t,
        calculando xi_t mediante el filtro HMM estable y evaluando XGBoost.
        """
        if self.model_final is None or self.hmm_params is None:
            raise ValueError("El modelo debe estar entrenado antes de predecir. Llama a fit_final_model() primero.")
            
        T = len(X)
        z = np.column_stack((
            np.ones(T),
            X["entropy_spectral"].values,
            X["mtl"].values
        ))
        
        # Extraer parámetros HMM
        gamma_0 = self.hmm_params["gamma_0"]
        gamma_1 = self.hmm_params["gamma_1"]
        mu = self.hmm_params["mu"]
        sigma = self.hmm_params["sigma"]
        
        # Computar xi_t de manera causal y estable usando el filtro Forward en espacio logarítmico
        xi = _causal_filtered_prob_log_space(spx_returns, z, gamma_0, gamma_1, mu, sigma)
        
        # Expandir características
        X_exp = np.column_stack((X.values, xi))
        
        # Predecir probabilidades
        probs = self.model_final.predict_proba(X_exp)[:, 1]
        
        return probs, xi
