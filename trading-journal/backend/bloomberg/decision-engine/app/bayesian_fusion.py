import numpy as np
from app.config import NARRATIVE_DECAY_LAMBDA

class BayesianFusion:
    def __init__(self, r_quant_hist: list = None, r_narr_hist: list = None):
        """
        Inicializa calculando percentiles históricos para normalización robusta y tau para asimetría.
        """
        self.r_quant_hist = r_quant_hist if r_quant_hist and len(r_quant_hist) > 10 else [-1, 1]
        self.r_narr_hist = r_narr_hist if r_narr_hist and len(r_narr_hist) > 10 else [-1, 1]
        
        # Percentiles para R_quant
        self.rq_min = np.percentile(self.r_quant_hist, 1)
        self.rq_max = np.percentile(self.r_quant_hist, 99)
        if self.rq_max == self.rq_min: self.rq_max = self.rq_min + 1e-5
        
        # Percentiles para R_narr
        self.rn_min = np.percentile(self.r_narr_hist, 1)
        self.rn_max = np.percentile(self.r_narr_hist, 99)
        if self.rn_max == self.rn_min: self.rn_max = self.rn_min + 1e-5

        # Tau: std de la diferencia
        if r_quant_hist and r_narr_hist and len(r_quant_hist) == len(r_narr_hist):
            diff = np.array(r_quant_hist) - np.array(r_narr_hist)
            self.tau = np.std(diff)
        else:
            self.tau = 0.5
        if self.tau == 0: self.tau = 1e-5

    def normalize_r(self, r, r_min, r_max):
        # Clip para evitar valores extremos y normalizar a [-1, 1]
        r_clipped = np.clip(r, r_min, r_max)
        return 2 * ((r_clipped - r_min) / (r_max - r_min)) - 1

    def sigmoid(self, x):
        return 1 / (1 + np.exp(-x))

    def fuse(self, r_quant: float, omega_quant: float, mirofish_output: dict = None, hours_since_narrative: float = 0.0) -> dict:
        r_quant_norm = self.normalize_r(r_quant, self.rq_min, self.rq_max)

        # Estado NARRATIVE_UNAVAILABLE
        if mirofish_output is None:
            return {
                "R_combined": r_quant_norm,
                "omega_combined": omega_quant,
                "w_narr_final": 0.0,
                "R_quant_norm": r_quant_norm,
                "R_narr_norm": 0.0,
                "status": "NARRATIVE_UNAVAILABLE"
            }

        r_narr = mirofish_output.get("R_narr", 0.0)
        omega_narr = mirofish_output.get("omega_narr", float('inf'))

        if omega_narr == float('inf') or omega_narr > 1e6:
            return {
                "R_combined": r_quant_norm,
                "omega_combined": omega_quant,
                "w_narr_final": 0.0,
                "R_quant_norm": r_quant_norm,
                "R_narr_norm": 0.0,
                "status": "NARRATIVE_UNAVAILABLE"
            }

        r_narr_norm = self.normalize_r(r_narr, self.rn_min, self.rn_max)

        # 1. Peso Bayesiano Base
        prec_narr = 1.0 / (omega_narr + 1e-5)
        prec_quant = 1.0 / (omega_quant + 1e-5)
        w_narr_star = prec_narr / (prec_narr + prec_quant)

        # 2. Modulación de Asimetría
        asymmetry_mod = 0.15 + 0.25 * self.sigmoid((r_narr_norm - r_quant_norm) / self.tau)
        w_narr_asym = w_narr_star * asymmetry_mod

        # 3. Narrative Decay
        w_narr_final = w_narr_asym * np.exp(-NARRATIVE_DECAY_LAMBDA * (hours_since_narrative / 24.0))

        # Vistas combinadas
        r_combined = (1 - w_narr_final) * r_quant_norm + w_narr_final * r_narr_norm
        omega_combined = 1.0 / (prec_quant + prec_narr)

        return {
            "R_combined": r_combined,
            "omega_combined": omega_combined,
            "w_narr_final": w_narr_final,
            "R_quant_norm": r_quant_norm,
            "R_narr_norm": r_narr_norm,
            "status": "FUSED"
        }
