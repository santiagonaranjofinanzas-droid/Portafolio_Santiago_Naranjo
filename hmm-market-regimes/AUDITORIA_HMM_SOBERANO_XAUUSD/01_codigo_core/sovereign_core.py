import numpy as np

class CStatistics:
    STABILITY_CLAMP = 20.0
    EPSILON = 1e-12

    @staticmethod
    def logistic_clamped(z: float) -> float:
        """Clonación estricta de LogisticClamped con mitigación de overflow."""
        clamped_z = max(-CStatistics.STABILITY_CLAMP, min(CStatistics.STABILITY_CLAMP, z))
        return 1.0 / (1.0 + np.exp(-clamped_z))

    @staticmethod
    def calculate_z_score(value: float, mean: float, std: float) -> float:
        """Clonación estricta de CalculateZScore con control de indeterminación."""
        if std < CStatistics.EPSILON:
            return 0.0
        return (value - mean) / std


class CVolatilityEngine:
    EPSILON = 1e-12

    @staticmethod
    def step_gjr_garch(prev_innov: float, prev_sigma2: float, var_target: float, 
                        alpha: float, gamma: float, beta: float) -> float:
        """
        Paso inductivo secuencial GJR-GARCH(1,1).
        Impone estacionariedad estricta antes del cálculo de la varianza condicional.
        """
        persistence = alpha + beta + (gamma / 2.0)
        
        # Escalamiento de coeficientes si la persistencia es no estacionaria
        if persistence >= 1.0:
            scale = 0.99 / persistence
            alpha *= scale
            beta *= scale
            gamma *= scale
            persistence = 0.99
            
        omega = var_target * (1.0 - persistence)
        indicator = 1.0 if prev_innov < 0.0 else 0.0
        eps2 = prev_innov * prev_innov
        
        current_sigma2 = omega + alpha * eps2 + gamma * indicator * eps2 + beta * prev_sigma2
        return max(current_sigma2, CVolatilityEngine.EPSILON)


class CStateSpace:
    EPSILON = 1e-12

    @staticmethod
    def step_kalman(measurement: float, prev_x: float, p_state: float, q: float, r: float) -> tuple:
        """
        Filtro de Kalman de un solo estado con actualización recursiva secuencial.
        Garantiza la paridad trackeando la covarianza del error (P).
        """
        p_pred = p_state + q
        k_gain = p_pred / (p_pred + r)
        x_new = prev_x + k_gain * (measurement - prev_x)
        p_state_new = (1.0 - k_gain) * p_pred
        return x_new, p_state_new

    @staticmethod
    def estimate_ou_drift(rets: np.ndarray, start: int, count: int, lr_sigma: float) -> tuple:
        """
        Estimador de Deriva Ornstein-Uhlenbeck mediante regresión lineal en ventana móvil.
        Aplica restricciones ergódicas y clipping asintótico idéntico a MQL5.
        """
        if count < 4:
            return CStateSpace.EPSILON, CStateSpace.EPSILON
            
        sx, sy, sxx, sxy = 0.0, 0.0, 0.0, 0.0
        for k in range(count - 1):
            x = rets[start + k]
            y = rets[start + k + 1]
            sx += x
            sy += y
            sxx += x * x
            sxy += x * y
            
        denom = (count - 1) * sxx - sx * sx
        ar1 = ((count - 1) * sxy - sx * sy) / denom if abs(denom) > CStateSpace.EPSILON else 0.0
        ar1 = max(-0.9999, min(0.9999, ar1)) # Restricción de ergodicidad
        
        intercept = (sy - ar1 * sx) / (count - 1)
        mu_ou = intercept / (1.0 - ar1) if abs(1.0 - ar1) > CStateSpace.EPSILON else 0.0
        
        # Límite asintótico de seguridad basado en la volatilidad de largo plazo
        max_drift = 2.0 * max(lr_sigma, CStateSpace.EPSILON)
        mu_ou = max(-max_drift, min(max_drift, mu_ou))
        
        mu_bull = max(mu_ou, CStateSpace.EPSILON)
        mu_bear = max(-mu_ou, CStateSpace.EPSILON)
        
        return mu_bull, mu_bear