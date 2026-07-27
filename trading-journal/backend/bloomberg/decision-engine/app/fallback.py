from app.config import RISK_PARITY_BASE

def get_context_aware_fallback(market_state: str, current_weights: dict) -> dict:
    if market_state == "calm":
        action = "HOLD_AND_ALERT"
        base = current_weights if current_weights else RISK_PARITY_BASE
        weights = base.copy()
        if "CASH" not in weights:
            weights["CASH"] = 1.0 - sum(weights.values())
    elif market_state == "uncertain":
        action = "REDUCE_EXPOSURE_20"
        base = current_weights if current_weights else RISK_PARITY_BASE
        weights = {k: v * 0.8 for k, v in base.items() if k != "CASH"}
        weights["CASH"] = 1.0 - sum(weights.values())
    else:
        action = "MOVE_TO_SAFE_BASE"
        weights = RISK_PARITY_BASE.copy()
        weights["CASH"] = 1.0 - sum(weights.values())

    return {
        "action_taken": action,
        "weights": weights
    }
