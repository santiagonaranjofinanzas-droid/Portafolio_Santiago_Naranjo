import numpy as np
from scipy.optimize import minimize
import os
import sys

#Resolver rutas absolutas del paquete para el linter de Pyrefly
ruta_actual = os.path.dirname(os.path.abspath(__file__))
ruta_raiz = os.path.abspath(os.path.join(ruta_actual, ".."))
ruta_capa2 = os.path.join(ruta_raiz, "Capa_2")

if ruta_raiz not in sys.path:
    sys.path.insert(0, ruta_raiz)
if ruta_capa2 not in sys.path:
    sys.path.insert(0, ruta_capa2)

from Capa_2.sovereign_signal import log_t_student_density, log_normal_jump_density
from Capa_1.sovereign_core import CStateSpace

class CSystemCalibrator:
    @staticmethod
    def estimate_moments_distribution(returns: np.ndarray, jump_sigma_k: float = 3.0) -> tuple:
        """
        Estimador por Momentos (MoM) exacto mapeado desde Sovereign_Signal.mq5.
        Aísla los saltos estocásticos utilizando el umbral condicional k*sigma.
        """
        mean_r = np.mean(returns)
        m2 = np.mean((returns - mean_r) ** 2)
        m4 = np.mean((returns - mean_r) ** 4)
        kurtosis = (m4 / (m2 * m2)) - 3.0 if m2 > 1e-20 else 0.0
        
        if kurtosis > 0.01:
            nu_opt = max(2.5, min(30.0, (6.0 / kurtosis) + 4.0))
        else:
            nu_opt = 4.88
            
        lr_sigma = np.std(returns, ddof=1)
        threshold = jump_sigma_k * lr_sigma
        jump_count = sum(1 for r in returns if abs(r) > threshold)
        
        lambda_opt = max(0.01, min(0.30, float(jump_count) / len(returns)))
        return nu_opt, lambda_opt, lr_sigma

    @staticmethod
    def optimize_hmm_matrix(returns: np.ndarray, mu_rets: np.ndarray, sig_rets: np.ndarray, 
                             kurtosis_vec: np.ndarray, nu_d: float, lambda_j: float) -> tuple:
        """
        Maximización de Verosimilitud (MLE) mediante el filtro Forward de Hamilton.
        Garantiza la paridad de reentrenamiento 1 a 1 evaluando la densidad conjunta del modelo.
        """
        rates_total = len(returns)
        
        def hmm_forward_log_likelihood(params):
            p_bull, p_bear = params
            if not (0.75 <= p_bull <= 0.995) or not (0.75 <= p_bear <= 0.995):
                return 1e10
                
            # Inicialización de la probabilidad de estado inicial (Equiprobable)
            p1 = 0.5
            total_log_lik = 0.0
            
            # Simulación secuencial estricta del filtro analítico de Sovereign
            for i in range(165, rates_total):
                ret = returns[i]
                sig_t = max(sig_rets[i], 1e-10)
                lr_sig = max(sig_rets[i], 1e-10) # Proxy local para calibración estática
                
                # Paso predictivo de la ecuación de Chapman-Kolmogorov
                p1_pred = p_bull * p1 + (1.0 - p_bear) * (1.0 - p1)
                p0_pred = 1.0 - p1_pred
                
                # Estimación local del drift OU para romper la simetría del HMM
                ou_window = 165
                ou_start = max(2, i - ou_window + 1)
                mu_bull_ou, mu_bear_ou = CStateSpace.estimate_ou_drift(
                    returns, ou_start, min(ou_window, i - ou_start + 1), lr_sig
                )
                
                # Evaluación de densidades condicionales direccionales
                ll1 = log_t_student_density(ret, mu_bull_ou, sig_t, nu_d)
                ll0 = log_t_student_density(ret, -mu_bear_ou, sig_t, nu_d)
                
                kurt_mult = max(2.0, min(10.0, np.sqrt(max(kurtosis_vec[i] + 3.0, 3.0))))
                sig_jump = max(lr_sig * kurt_mult, 1e-10)
                ll_jump = log_normal_jump_density(ret, sig_jump)
                
                ll_max = max(max(ll1, ll0), ll_jump)
                
                lik1_mix = (1.0 - lambda_j) * np.exp(ll1 - ll_max) + lambda_j * np.exp(ll_jump - ll_max)
                lik0_mix = (1.0 - lambda_j) * np.exp(ll0 - ll_max) + lambda_j * np.exp(ll_jump - ll_max)
                
                lik1 = p1_pred * lik1_mix
                lik0 = p0_pred * lik0_mix
                norm_f = lik1 + lik0
                
                if norm_f > 1e-14:
                    p1 = lik1 / norm_f
                    total_log_lik += np.log(norm_f) + ll_max
                else:
                    p1 = p1_pred
                    
            return -total_log_lik / rates_total

        # Límites e inicialización del optimizador numérico L-BFGS-B
        x0 = [0.980, 0.980]
        bounds = [(0.75, 0.995), (0.75, 0.995)]
        
        res = minimize(hmm_forward_log_likelihood, x0, method='L-BFGS-B', bounds=bounds)
        if res.success:
            return res.x[0], res.x[1]
        return 0.980, 0.980