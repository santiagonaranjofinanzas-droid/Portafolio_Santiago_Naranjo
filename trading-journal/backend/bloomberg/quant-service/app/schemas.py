from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any

class PredictionRequest(BaseModel):
    features: Dict[str, float] = Field(..., description="Características de los activos. Claves: SP500, GOLD, OIL, BOND10Y, USD")
    state_vector: List[float] = Field(..., description="Vector de estado anterior P(S_t-1  y_1:t-1)")
    timestamp: str = Field(..., description="Timestamp de la vela confirmada (ISO 8601)")

class ModelHealth(BaseModel):
    psi: float
    kl_div: float
    status: str
    psi_trend: str

class PredictionResponse(BaseModel):
    regime_probabilities: Dict[str, float]
    state_vector: List[float]
    stress_probability_t5: float
    confidence_score: float
    regime_entropy: float
    omega_quant: float
    model_health: ModelHealth
    timestamp: str
    model_version: str
    feature_version: str
    inference_time_ms: int

class FallbackResponse(BaseModel):
    status: str = "fallback"
    reason: str
    regime_probabilities: Optional[Dict[str, float]] = None

class ModelInfoResponse(BaseModel):
    model_version: str
    feature_version: str
    feature_names: List[str]
    hmm_n_states: int
    hmm_pi_0: List[float]
    status: str
