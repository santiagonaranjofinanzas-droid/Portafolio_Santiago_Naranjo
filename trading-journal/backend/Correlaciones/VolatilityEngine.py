"""
VolatilityEngine.py - Motor de Volatilidad Dinámica (Fase I)

Clase orientada a objetos para la estimación en dos etapas de la matriz de
covarianza condicional H_t para un portafolio de N activos financieros.

Etapas:
1. GJR-GARCH(1,1) univariados ajustados en paralelo.
2. Dinámica DCC regularizada con Shrinkage-Target (Ledoit-Wolf) de residuos.

Optimizador acelerado con Numba JIT para cálculo de verosimilitud de Cholesky estable.
"""

import logging
import multiprocessing
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from sklearn.covariance import ledoit_wolf
import numba as nb
import time
import warnings
from arch.univariate.base import DataScaleWarning

#Ignoramos advertencias de escala de datos de GARCH para no saturar los logs
warnings.filterwarnings('ignore', category=DataScaleWarning)

#Configuración del registrador (logger)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("VolatilityEngine")

#Helper a nivel de módulo para la paralelización
def _fit_single_garch_helper(args):
    """
    Función helper fuera de la clase para permitir que multiprocessing realice la serialización (pickling).
    """
    series, name, p, o, q, dist, mean = args
    try:
        from arch import arch_model
        # Desactivamos el despliegue de salidas para no contaminar la consola
        model = arch_model(series, vol="GARCH", p=p, o=o, q=q, dist=dist, mean=mean)
        res = model.fit(disp="off", show_warning=False)
        return name, res.conditional_volatility.values, res.std_resid.values, res.params.to_dict(), None
    except Exception as e:
        return name, None, None, None, str(e)


@nb.njit
def _solve_lower_triangular(L, b):
    """
    Resuelve el sistema L * y = b donde L es una matriz triangular inferior (Cholesky).
    Algoritmo de sustitución hacia adelante (Forward Substitution).
    """
    n = L.shape[0]
    y = np.zeros(n)
    for i in range(n):
        val = b[i]
        for j in range(i):
            val -= L[i, j] * y[j]
        y[i] = val / L[i, i]
    return y


@nb.njit
def _dcc_likelihood_numba(epsilon, Q_bar_star, a, b):
    """
    Calcula la log-verosimilitud negativa de la correlación DCC en Numba.
    Utiliza descomposición de Cholesky para evitar underflow en determinantes de alta dimensión (N=26).
    """
    if a + b >= 1.0 or a < 0.0 or b < 0.0:
        return 1e10
        
    T, N = epsilon.shape
    Q_t = Q_bar_star.copy()
    log_lik = 0.0
    const_part = (1.0 - a - b) * Q_bar_star
    
    for t in range(T):
        if t > 0:
            eps_prev = epsilon[t-1]
            outer = np.outer(eps_prev, eps_prev)
            Q_t = const_part + a * outer + b * Q_t
        
        d = np.diag(Q_t)
        # Penalización extrema para evitar varianzas proxy no positivas
        for i in range(N):
            if d[i] <= 0:
                return 1e10
        
        d_inv_sqrt = 1.0 / np.sqrt(d)
        
        # Reconstruir R_t de forma JIT-compatible
        R_t = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                R_t[i, j] = Q_t[i, j] * d_inv_sqrt[i] * d_inv_sqrt[j]
        
        # Descomposición Cholesky R_t = L_t * L_t^T
        try:
            L_t = np.linalg.cholesky(R_t)
        except:
            # Si la matriz no es definida positiva, retornamos una penalización alta
            return 1e10
        
        # Log-determinante robusto mediante Cholesky
        log_det_R = 0.0
        for i in range(N):
            log_det_R += 2.0 * np.log(L_t[i, i])
            
        # epsilon_t^T * R_t^-1 * epsilon_t
        eps_t = epsilon[t]
        y_t = _solve_lower_triangular(L_t, eps_t)
        
        eps_R_eps = 0.0
        for i in range(N):
            eps_R_eps += y_t[i] * y_t[i]
            
        eps_eps = 0.0
        for i in range(N):
            eps_eps += eps_t[i] * eps_t[i]
            
        log_lik += log_det_R + eps_R_eps - eps_eps
        
    return 0.5 * log_lik


@nb.njit
def _generate_covariances_numba(epsilon, Q_bar_star, a, b, conditional_vols):
    """
    Filtro final JIT-compilado para reconstruir las matrices de covarianza condicional (H)
    y correlación condicional (R) sobre el historial completo.
    """
    a = max(0.0, min(a, 0.999))
    b = max(0.0, min(b, 0.999))
    if a + b >= 1.0:
        a, b = 0.01, 0.98
        
    T, N = epsilon.shape
    Q_t = Q_bar_star.copy()
    const_part = (1.0 - a - b) * Q_bar_star
    
    H = np.zeros((T, N, N))
    R = np.zeros((T, N, N))
    
    for t in range(T):
        if t > 0:
            eps_prev = epsilon[t-1]
            outer = np.outer(eps_prev, eps_prev)
            Q_t = const_part + a * outer + b * Q_t
        
        d = np.diag(Q_t)
        for i in range(N):
            if d[i] <= 0:
                d[i] = 1e-8
                
        d_inv_sqrt = 1.0 / np.sqrt(d)
        
        for i in range(N):
            for j in range(N):
                r_val = Q_t[i, j] * d_inv_sqrt[i] * d_inv_sqrt[j]
                # Acotación por estabilidad
                if r_val > 1.0:
                    r_val = 1.0
                elif r_val < -1.0:
                    r_val = -1.0
                R[t, i, j] = r_val
                H[t, i, j] = r_val * conditional_vols[t, i] * conditional_vols[t, j]
                
    return H, R


class VolatilityEngine:
    """
    Motor de Volatilidad para ajustar modelos univariados GJR-GARCH y
    correlación dinámica condicionada DCC con Shrinkage-Target de Ledoit-Wolf.
    """
    
    def __init__(self, returns: pd.DataFrame, garch_p=1, garch_o=1, garch_q=1, 
                 garch_dist="normal", garch_mean="Constant"):
        """
        Inicializa el motor con un dataframe de log-retornos.
        
        Args:
            returns: pd.DataFrame con fechas como índice y activos como columnas.
            garch_p: Orden de retornos al cuadrado en GARCH.
            garch_o: Orden de asimetría en GJR-GARCH (o=1 para capturar efecto apalancamiento).
            garch_q: Orden de varianzas rezagadas en GARCH.
            garch_dist: Distribución de residuos univariados ('normal', 'studentst', etc.).
            garch_mean: Modelo de media ('Constant', 'Zero', etc.).
        """
        if returns.isnull().any().any():
            raise ValueError("El DataFrame de retornos contiene valores NaN. Por favor, límpialos primero.")
            
        self.returns = returns
        self.dates = returns.index
        self.assets = returns.columns.tolist()
        self.N = len(self.assets)
        self.T = len(returns)
        
        # Parámetros GARCH
        self.garch_p = garch_p
        self.garch_o = garch_o
        self.garch_q = garch_q
        self.garch_dist = garch_dist
        self.garch_mean = garch_mean
        
        # Variables de salida de ajuste
        self.conditional_vols = None  # Matriz (T, N) de volatilidades condicionales
        self.standardized_residuals = None  # Matriz (T, N) de residuos estandarizados
        self.garch_parameters = {}  # Parámetros óptimos univariados por activo
        
        # Parámetros DCC
        self.dcc_a = None
        self.dcc_b = None
        self.Q_bar_star = None  # Matriz incondicional shrunk
        self.dcc_fit_time = None
        
        # Tensores resultantes de covarianza y correlación
        self.H_t = None  # Matriz condicional de covarianza (T, N, N)
        self.R_t = None  # Matriz condicional de correlación (T, N, N)
        
        logger.info(f"VolatilityEngine inicializado con N={self.N} activos y T={self.T} observaciones.")

    def fit_univariate_garch(self, n_jobs=-1):
        """
        Etapa 1: Ajusta los modelos univariados GJR-GARCH en paralelo.
        """
        logger.info("Etapa 1: Ajustando modelos univariados GJR-GARCH en paralelo...")
        start_time = time.time()
        
        # Preparación de argumentos para cada proceso
        tasks = []
        for asset in self.assets:
            tasks.append((self.returns[asset], asset, self.garch_p, self.garch_o, 
                          self.garch_q, self.garch_dist, self.garch_mean))
            
        conditional_vols = np.zeros((self.T, self.N))
        std_residuals = np.zeros((self.T, self.N))
        
        # Selección del número de hilos de procesamiento
        if n_jobs == -1:
            cpu_count = multiprocessing.cpu_count()
            # Dejamos 1 core libre por cortesía del sistema operativo
            n_jobs = max(1, cpu_count - 1)
            
        n_jobs = min(n_jobs, self.N)
        logger.info(f"Utilizando {n_jobs} cores de procesamiento para paralelizar GARCH.")
        
        success_count = 0
        if n_jobs > 1:
            try:
                with multiprocessing.Pool(processes=n_jobs) as pool:
                    results = pool.map(_fit_single_garch_helper, tasks)
            except Exception as e:
                logger.warning(f"Fallo en multiprocessing: {str(e)}. Reintentando en hilo único.")
                results = [_fit_single_garch_helper(task) for task in tasks]
        else:
            results = [_fit_single_garch_helper(task) for task in tasks]
            
        for name, vol, resid, params, err in results:
            idx = self.assets.index(name)
            if err is not None:
                logger.error(f"Fallo al ajustar GARCH para {name}: {err}. Ajustando estimador de desviación móvil estándar.")
                # Fallback: Desviación estándar clásica de ventana
                std_rolling = self.returns[name].rolling(window=21, min_periods=1).std().fillna(self.returns[name].std()).values
                conditional_vols[:, idx] = std_rolling
                std_residuals[:, idx] = self.returns[name].values / std_rolling
                self.garch_parameters[name] = {"fallback": "moving_average_std"}
            else:
                conditional_vols[:, idx] = vol
                std_residuals[:, idx] = resid
                self.garch_parameters[name] = params
                success_count += 1
                
        self.conditional_vols = conditional_vols
        self.standardized_residuals = std_residuals
        
        elapsed = time.time() - start_time
        logger.info(f"Etapa 1 finalizada. Ajustados {success_count}/{self.N} activos con éxito en {elapsed:.2f} segundos.")
        return self

    def fit_dcc(self):
        """
        Etapa 2: Estima los parámetros de correlación dinámica DCC (a, b) usando
        regularización Shrinkage-Target de Ledoit-Wolf en la matriz incondicional.
        """
        if self.standardized_residuals is None:
            raise ValueError("Debes ejecutar 'fit_univariate_garch()' antes de ajustar el DCC.")
            
        logger.info("Etapa 2: Calculando Shrinkage-Target Ledoit-Wolf sobre residuos estandarizados...")
        start_time = time.time()
        
        # Calcular covarianza regularizada
        cov_shrunk, shrink_coef = ledoit_wolf(self.standardized_residuals)
        logger.info(f"Shrinkage de Ledoit-Wolf completado. Coeficiente de contracción óptimo: {shrink_coef:.4f}")
        
        # Convertir a matriz de correlación incondicional Q_bar_star
        d = np.diag(cov_shrunk)
        d_inv_sqrt = 1.0 / np.sqrt(d)
        self.Q_bar_star = np.outer(d_inv_sqrt, d_inv_sqrt) * cov_shrunk
        
        # Asegurarse que la diagonal es exactamente 1 (por precisión de flotante)
        np.fill_diagonal(self.Q_bar_star, 1.0)
        
        logger.info("Iniciando optimización de verosimilitud DCC-GARCH calibrada mediante Numba...")
        
        # Función objetivo a minimizar (verosimilitud negativa)
        def objective(params):
            a, b = params
            return _dcc_likelihood_numba(self.standardized_residuals, self.Q_bar_star, a, b)
            
        # Restricciones y límites
        # a >= 1e-4, b >= 1e-4 para estabilidad numérica
        bounds = ((1e-4, 0.999), (1e-4, 0.999))
        
        # Restricción: a + b <= 0.999 (estacionariedad de la correlación)
        def constraint_stationarity(params):
            a, b = params
            return 0.999 - (a + b)
            
        constraints = [{"type": "ineq", "fun": constraint_stationarity}]
        
        # Punto de inicio (valores conservadores comunes en finanzas)
        initial_guess = np.array([0.03, 0.95])
        
        # Optimizar
        opt_res = minimize(
            objective, 
            initial_guess, 
            method="SLSQP", 
            bounds=bounds, 
            constraints=constraints,
            options={"ftol": 1e-6, "disp": False}
        )
        
        if not opt_res.success:
            logger.warning(f"La optimización SLSQP no convergió completamente: {opt_res.message}. Utilizando mejores parámetros aproximados.")
            
        self.dcc_a, self.dcc_b = opt_res.x
        self.dcc_fit_time = time.time() - start_time
        
        logger.info(f"Optimización finalizada en {self.dcc_fit_time:.2f} segundos.")
        logger.info(f"Parámetros DCC óptimos: a = {self.dcc_a:.6f}, b = {self.dcc_b:.6f} (Suma: {self.dcc_a + self.dcc_b:.6f})")
        
        # Generar las matrices de covarianza (H) y correlación (R) finales
        logger.info("Filtrando la serie temporal histórica para generar H_t y R_t...")
        self.H_t, self.R_t = _generate_covariances_numba(
            self.standardized_residuals,
            self.Q_bar_star,
            self.dcc_a,
            self.dcc_b,
            self.conditional_vols
        )
        
        logger.info(f"Tensores generados correctamente. Forma de H_t: {self.H_t.shape}")
        return self

    def fit(self, n_jobs=-1):
        """
        Ejecuta el pipeline completo de ajuste en dos etapas.
        """
        self.fit_univariate_garch(n_jobs=n_jobs)
        self.fit_dcc()
        return self

    def get_conditional_covariances(self):
        """
        Devuelve el tensor tridimensional H_t de covarianzas condicionales (T, N, N).
        """
        if self.H_t is None:
            raise ValueError("Debes ejecutar el método 'fit()' antes de extraer las covarianzas.")
        return self.H_t

    def get_conditional_correlations(self):
        """
        Devuelve el tensor tridimensional R_t de correlaciones condicionales (T, N, N).
        """
        if self.R_t is None:
            raise ValueError("Debes ejecutar el método 'fit()' antes de extraer las correlaciones.")
        return self.R_t

    def save(self, filepath: str):
        """
        Guarda los resultados estructurados en un archivo comprimido .npz para persistencia.
        """
        if self.H_t is None:
            raise ValueError("No hay datos ajustados para guardar. Corre 'fit()' primero.")
            
        np.savez_compressed(
            filepath,
            H=self.H_t,
            R=self.R_t,
            conditional_vols=self.conditional_vols,
            residuals=self.standardized_residuals,
            assets=np.array(self.assets, dtype=object),
            dates=np.array(self.dates.astype(str), dtype=object),
            dcc_params=np.array([self.dcc_a, self.dcc_b])
        )
        logger.info(f"Resultados del ajuste persistidos exitosamente en {filepath}")
