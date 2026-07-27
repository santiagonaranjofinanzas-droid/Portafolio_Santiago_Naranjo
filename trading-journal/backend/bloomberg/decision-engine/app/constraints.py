import redis
from app.config import TCA_CHURN_THRESHOLD, DRAWDOWN_LEVELS, COOLDOWN_BARS

class ConstraintEngine:
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client

    def update_hwm_and_get_drawdown(self, current_nav: float) -> float:
        """Calcula el drawdown actual y actualiza el HWM en Redis."""
        if self.redis is None:
            return 0.0
            
        hwm_str = self.redis.get("portfolio:hwm")
        
        if not hwm_str:
            self.redis.set("portfolio:hwm", current_nav)
            return 0.0
            
        hwm = float(hwm_str)
        drawdown = (current_nav - hwm) / hwm
        
        if current_nav > hwm:
            self.redis.set("portfolio:hwm", current_nav)
            drawdown = 0.0
            
        return drawdown

    def check_cooldown(self) -> bool:
        if self.redis and self.redis.exists("portfolio:cooldown_until"):
            return True
        return False

    def activate_cooldown(self):
        if self.redis:
            self.redis.setex("portfolio:cooldown_until", 86400 * COOLDOWN_BARS, "active")

    def apply_failsafes(self, raw_weights: dict, drawdown: float) -> tuple:
        exposure_multiplier = 1.0
        fail_safe_level = None
        
        if drawdown <= DRAWDOWN_LEVELS["critical"]:
            exposure_multiplier = 0.0
            fail_safe_level = "critical"
            self.activate_cooldown()
        elif drawdown <= DRAWDOWN_LEVELS["severe"]:
            exposure_multiplier = 0.3
            fail_safe_level = "severe"
        elif drawdown <= DRAWDOWN_LEVELS["mild"]:
            exposure_multiplier = 0.7
            fail_safe_level = "mild"

        final_weights = {k: v * exposure_multiplier for k, v in raw_weights.items()}
        final_weights["CASH"] = 1.0 - sum(final_weights.values())
        return final_weights, fail_safe_level

    def apply_tca(self, new_weights: dict, old_weights: dict) -> bool:
        if not old_weights:
            return True
        total_churn = sum(abs(new_weights.get(k, 0) - old_weights.get(k, 0)) for k in new_weights.keys() if k != "CASH")
        return total_churn > TCA_CHURN_THRESHOLD
