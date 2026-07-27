import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf
from app.config import COV_MATRIX_MODE, COV_MIN_WINDOW, RISK_PARITY_BASE, ASSETS

class BlackLittermanOptimizer:
    def __init__(self, historical_returns: pd.DataFrame = None):
        """
        Calcula la matriz de covarianza Sigma usando Ledoit-Wolf shrinkage.
        historical_returns debe ser un df con retornos de los activos ["QQQ", "GLD"].
        """
        self.assets = ASSETS
        self.w_eq = np.array([RISK_PARITY_BASE.get(a, 0.0) for a in self.assets])
        
        # Matriz estática de fallback (basada en estimaciones de ejemplo QQQ y GLD)
        base_cov = np.array([
            [0.0400, -0.0020],
            [-0.0020, 0.0225]
        ])
        if "CASH" in self.assets:
            n = len(self.assets)
            self.static_cov = np.zeros((n, n), dtype=float)
            qqq_idx = self.assets.index("QQQ") if "QQQ" in self.assets else None
            gld_idx = self.assets.index("GLD") if "GLD" in self.assets else None
            if qqq_idx is not None and gld_idx is not None:
                self.static_cov[qqq_idx, qqq_idx] = base_cov[0, 0]
                self.static_cov[qqq_idx, gld_idx] = base_cov[0, 1]
                self.static_cov[gld_idx, qqq_idx] = base_cov[1, 0]
                self.static_cov[gld_idx, gld_idx] = base_cov[1, 1]
            cash_idx = self.assets.index("CASH")
            self.static_cov[cash_idx, cash_idx] = 1e-6
        else:
            self.static_cov = base_cov

        if COV_MATRIX_MODE == "dynamic" and historical_returns is not None and len(historical_returns) >= COV_MIN_WINDOW:
            returns = historical_returns.copy()
            for asset in self.assets:
                if asset not in returns.columns:
                    returns[asset] = 0.0
            returns = returns[self.assets]

            # Ledoit-Wolf shrinkage estimator
            lw = LedoitWolf().fit(returns)
            self.sigma = lw.covariance_
        else:
            self.sigma = self.static_cov

        # Regularizar para evitar singularidad
        self.sigma = self.sigma + np.eye(len(self.assets)) * 1e-8

    def optimize(self, r_combined: float, omega_combined: float, risk_aversion: float = 2.5) -> dict:
        """
        Simplificación B-L con 2 activos: 
        Asumimos que R_combined indica la preferencia relativa QQQ vs GLD.
        P_{view} = [1, -1] (Vista: QQQ superará a GLD por r_combined)
        Q = r_combined
        Omega = omega_combined
        """
        # Excesos de retorno implícitos del mercado (Pi)
        pi = risk_aversion * self.sigma.dot(self.w_eq)
        
        if omega_combined is None:
            omega_combined = 0.5

        # Vista (P) construida dinámicamente según la posición de QQQ y GLD
        P_list = []
        for asset in self.assets:
            if asset == "QQQ":
                P_list.append(1.0)
            elif asset == "GLD":
                P_list.append(-1.0)
            else:
                P_list.append(0.0)
        P = np.array([P_list])  # View: QQQ - GLD
        
        p_sigma_p = float(P.dot(self.sigma).dot(P.T).item())
        view_vol = float(np.sqrt(max(p_sigma_p, 1e-8)))
        Q = np.array([r_combined * view_vol])
        
        tau = 0.05 # Escalar de incertidumbre del prior

        # Omega escalado en unidades de retorno
        p_tau_sigma_p = float(P.dot(tau * self.sigma).dot(P.T).item())
        omega_scale = float(np.clip(0.5 + omega_combined, 0.1, 2.0))
        Omega = np.array([[max(p_tau_sigma_p, 1e-8) * omega_scale]])
        
        # Matemática de Black-Litterman
        tau_sigma_inv = np.linalg.inv(tau * self.sigma)
        P_T = P.T
        Omega_inv = np.linalg.inv(Omega)
        
        # Nuevo retorno esperado (E[R])
        term1 = np.linalg.inv(tau_sigma_inv + P_T.dot(Omega_inv).dot(P))
        term2 = tau_sigma_inv.dot(pi) + P_T.dot(Omega_inv).dot(Q)
        er_bl = term1.dot(term2)
        
        # Nuevos pesos óptimos
        w_bl = np.linalg.inv(risk_aversion * self.sigma).dot(er_bl)
        
        # Normalizar para que sumen a la exposición máxima deseada (ej. 1.0)
        # Asegurar pesos >= 0 (long-only)
        w_bl = np.maximum(w_bl, 0)
        total_w = np.sum(w_bl)
        if total_w > 0:
            w_bl = w_bl / total_w
            
        return {self.assets[i]: float(w_bl[i]) for i in range(len(self.assets))}
