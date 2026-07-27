import numpy as np
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6380"))

#Configuración Fusión Bayesiana
R_NORM_WINDOW = 252
NARRATIVE_DECAY_LAMBDA = np.log(2) / 3

#Configuración Black-Litterman
COV_MATRIX_MODE = "dynamic"   # "static" o "dynamic"
COV_WINDOW_DAYS = 252
COV_MIN_WINDOW  = 60

#Configuración de Universo y Constraints
ASSETS = ["QQQ", "GLD", "CASH"]
BASE_EXPOSURE = 1.0  # 100% invertido
RISK_PARITY_BASE = {"QQQ": 0.60, "GLD": 0.35, "CASH": 0.05}  # Base pasiva teórica

#Límites por activo (min/max) en proporción del capital
ASSET_LIMITS = {
    "QQQ": {"min": 0.0, "max": 0.85},
    "GLD": {"min": 0.0, "max": 0.60},
    "CASH": {"min": 0.02, "max": 0.50}
}

#Penalización por riesgo (stress) sobre exposición
STRESS_PENALTY_ALPHA = 0.7
EXPOSURE_FLOOR = 0.10
EXPOSURE_CEIL = 1.00

#Tilt de retorno esperado por régimen (heurístico)
REGIME_RETURN_TILT = {
    "low": 0.20,
    "transition": 0.00,
    "high": -0.20
}

#TCA (Transaction Cost Analysis)
TCA_CHURN_THRESHOLD = 0.02  # 2% mínimo de cambio para rebalancear

#Fail-Safe (Max Drawdown)
DRAWDOWN_LEVELS = {
    "mild": -0.05,     # -5% -> Reducir 30%
    "severe": -0.08,   # -8% -> Reducir 70%
    "critical": -0.10  # -10% -> Halt
}
COOLDOWN_BARS = 2
