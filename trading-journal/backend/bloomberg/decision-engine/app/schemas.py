from pydantic import BaseModel
from typing import Dict, Optional, List

class DecisionRequest(BaseModel):
    current_nav: float
    quant_output: Dict
    mirofish_output: Optional[Dict] = None
    old_weights: Optional[Dict] = None
    market_state: str = "calm"
    historical_r_quant: Optional[List[float]] = None
    historical_r_narr: Optional[List[float]] = None
    historical_returns_df_json: Optional[str] = None # JSON string of a dataframe

class DecisionResponse(BaseModel):
    weights: Dict[str, float]
    exposure_total: float
    rebalance_required: bool
    tca_blocked: bool
    fail_safe_active: bool
    fail_safe_level: Optional[str]
    fallback_active: bool
    decision_inputs: Dict
    timestamp: str
    cycle_id: str
