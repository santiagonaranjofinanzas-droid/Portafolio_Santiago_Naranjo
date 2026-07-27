import uuid
import datetime
import redis
import pandas as pd
from app.bayesian_fusion import BayesianFusion
from app.black_litterman import BlackLittermanOptimizer
from app.constraints import ConstraintEngine
from app.fallback import get_context_aware_fallback
from app.config import ASSET_LIMITS, STRESS_PENALTY_ALPHA, EXPOSURE_FLOOR, EXPOSURE_CEIL, REGIME_RETURN_TILT

try:
    from app.mapping import resolve_proxy
except ImportError:
    try:
        from .mapping import resolve_proxy
    except ImportError:
        def resolve_proxy(symbol: str) -> str  None:
            sym_upper = symbol.upper()
            if "XAU" in sym_upper or "GOLD" in sym_upper: return "GLD"
            if "NAS" in sym_upper or "QQQ" in sym_upper: return "QQQ"
            if "EURUSD" in sym_upper: return "EURUSD"
            if "USDJPY" in sym_upper or "JPY" in sym_upper: return "USDJPY"
            return None

def _normalize_weights_with_cash(weights: dict) -> dict:
    if not weights:
        return {"CASH": 1.0}

    cleaned = {}
    for key, value in weights.items():
        try:
            val = float(value)
        except (TypeError, ValueError):
            continue
        cleaned[key] = max(0.0, val)

    if not cleaned:
        return {"CASH": 1.0}

    non_cash = {k: v for k, v in cleaned.items() if k != "CASH"}
    total_non_cash = sum(non_cash.values())
    if total_non_cash > 1.0:
        non_cash = {k: v / total_non_cash for k, v in non_cash.items()}
        total_non_cash = 1.0
    non_cash["CASH"] = max(0.0, 1.0 - total_non_cash)
    return non_cash

def calculate_exposure_metrics(positions: list, equity: float) -> dict:
    """Calculates gross and net nominal exposures for derivative positions"""
    gross_exposure = 0.0
    net_exposure = 0.0
    exposures_by_proxy = {}
    gross_by_proxy = {}
    estimated_positions = 0
    
    for pos in positions:
        symbol = pos.get("symbol")
        if not symbol:
            continue
        volume = float(pos.get("volume", 0.0))
        price_curr = float(pos.get("price_current", 0.0) or pos.get("price_open", 0.0) or 0.0)
        type_op = int(pos.get("type", 0)) # 0 = Buy, 1 = Sell
        
        # Contract size lookup
        contract_size = float(pos.get("contract_size") or 0.0)
        if contract_size == 0.0:
            estimated_positions += 1
            sym_upper = symbol.upper()
            if "XAU" in sym_upper or "GOLD" in sym_upper:
                contract_size = 100.0
            elif "EURUSD" in sym_upper or "GBPUSD" in sym_upper or "USDJPY" in sym_upper:
                contract_size = 100000.0
            elif "BTC" in sym_upper:
                contract_size = 1.0
            else:
                contract_size = 10.0
                
        # Currency conversion to USD
        conv_rate = float(pos.get("currency_conversion_rate") or pos.get("conversion_rate") or 0.0)
        sym_upper = symbol.upper()
        if conv_rate <= 0.0:
            conv_rate = 1.0
            # A missing conversion is acceptable only for USD-denominated
            # instruments. Flag every other case as an estimate.
            if not sym_upper.endswith("USD") and "US100" not in sym_upper and "QQQ" not in sym_upper:
                estimated_positions += 1
            
        nominal = volume * contract_size * price_curr * conv_rate
        direction = 1.0 if type_op == 0 else -1.0
        signed_nominal = nominal * direction
        
        proxy = resolve_proxy(symbol) or "CASH"
        
        gross_exposure += nominal
        net_exposure += signed_nominal
        
        exposures_by_proxy[proxy] = exposures_by_proxy.get(proxy, 0.0) + signed_nominal
        gross_by_proxy[proxy] = gross_by_proxy.get(proxy, 0.0) + nominal
        
    equity_val = equity if equity > 0 else 1.0
    weights_by_proxy = {k: v / equity_val for k, v in exposures_by_proxy.items()}
    
    return {
        "gross_exposure": round(gross_exposure, 2),
        "net_exposure": round(net_exposure, 2),
        "exposures_by_proxy": {k: round(v, 2) for k, v in exposures_by_proxy.items()},
        "gross_by_proxy": {k: round(v, 2) for k, v in gross_by_proxy.items()},
        "weights_by_proxy": {k: round(v, 4) for k, v in weights_by_proxy.items()},
        "estimated_positions": estimated_positions,
        "data_quality": "verified" if estimated_positions == 0 else "estimated"
    }


def run_portfolio_stress_tests(weights: dict, current_nav: float) -> dict:
    """Deterministic shadow scenarios used as approval gates."""
    normalized = _normalize_weights_with_cash(weights)
    shocks = {
        "equity_selloff": {"QQQ": -0.20, "GLD": 0.03, "CASH": 0.0},
        "inflation_shock": {"QQQ": -0.10, "GLD": 0.08, "CASH": 0.0},
        "liquidity_crisis": {"QQQ": -0.28, "GLD": -0.07, "CASH": 0.0},
    }
    scenarios = {}
    worst_loss = 0.0
    for name, asset_shocks in shocks.items():
        portfolio_return = sum(normalized.get(asset, 0.0) * shock for asset, shock in asset_shocks.items())
        pnl = current_nav * portfolio_return
        worst_loss = min(worst_loss, portfolio_return)
        scenarios[name] = {"return": round(portfolio_return, 6), "pnl": round(pnl, 2)}
    return {
        "methodology_version": "sentinel-stress-v1",
        "scenarios": scenarios,
        "worst_case_return": round(worst_loss, 6),
        "worst_case_pnl": round(current_nav * worst_loss, 2),
        "approval_gate_passed": worst_loss >= -0.12,
    }


def _with_shadow_controls(result: dict, current_nav: float) -> dict:
    stress_tests = run_portfolio_stress_tests(result.get("weights", {"CASH": 1.0}), current_nav)
    blocked = bool(result.get("recommendations_blocked")) or not stress_tests["approval_gate_passed"]
    result["stress_tests"] = stress_tests
    result["shadow_mode"] = True
    result["execution_allowed"] = False
    result["approval_status"] = "blocked" if blocked else "pending"
    return result

def _apply_asset_limits(weights: dict, asset_limits: dict, enforce_mins: bool = True) -> dict:
    cleaned = _normalize_weights_with_cash(weights)
    limited = {}

    for asset in asset_limits.keys():
        if asset not in cleaned:
            cleaned[asset] = 0.0

    for asset, value in cleaned.items():
        limits = asset_limits.get(asset, {"min": 0.0, "max": 1.0})
        min_v = limits.get("min", 0.0) if enforce_mins else 0.0
        max_v = limits.get("max", 1.0)
        limited[asset] = min(max(value, min_v), max_v)

    non_cash = {k: v for k, v in limited.items() if k != "CASH"}
    total_non_cash = sum(non_cash.values())
    if total_non_cash > 1.0:
        scale = 1.0 / total_non_cash
        non_cash = {k: v * scale for k, v in non_cash.items()}
        total_non_cash = 1.0

    cash = max(0.0, 1.0 - total_non_cash)
    cash_limits = asset_limits.get("CASH", {"min": 0.0, "max": 1.0})
    cash_min = cash_limits.get("min", 0.0) if enforce_mins else 0.0
    cash_max = cash_limits.get("max", 1.0)

    if cash < cash_min:
        target_non_cash = max(0.0, 1.0 - cash_min)
        if total_non_cash > 0:
            scale = target_non_cash / total_non_cash
            non_cash = {k: v * scale for k, v in non_cash.items()}
        cash = cash_min

    if cash > cash_max:
        target_non_cash = max(0.0, 1.0 - cash_max)
        if total_non_cash > 0:
            scale = target_non_cash / total_non_cash
            non_cash = {k: v * scale for k, v in non_cash.items()}
        cash = cash_max

    non_cash["CASH"] = cash
    return non_cash

def _apply_risk_penalty(weights: dict, stress_prob: float) -> tuple[dict, float]:
    multiplier = 1.0 - (STRESS_PENALTY_ALPHA * max(0.0, min(1.0, stress_prob)))
    multiplier = max(EXPOSURE_FLOOR, min(EXPOSURE_CEIL, multiplier))

    scaled = {k: (v * multiplier) for k, v in weights.items() if k != "CASH"}
    total_non_cash = sum(scaled.values())
    scaled["CASH"] = max(0.0, 1.0 - total_non_cash)
    return scaled, multiplier

def _compute_r_quant(quant_output: dict) -> float:
    regimes = quant_output.get("regime_probabilities", {}) or {}
    r_quant = 0.0
    for key, tilt in REGIME_RETURN_TILT.items():
        r_quant += float(regimes.get(key, 0.0)) * float(tilt)
    return max(-1.0, min(1.0, r_quant))

def run_decision_engine(
    current_nav: float,
    quant_output: dict,
    mirofish_output: dict = None,
    old_weights: dict = None,
    market_state: str = "calm",
    historical_r_quant: list = None,
    historical_r_narr: list = None,
    historical_returns_df: pd.DataFrame = None,
    redis_client: redis.Redis = None,
    is_mt5_stale: bool = False,
    positions: list = None,
    margin_risk: float = 0.0,
    portfolio_limits: dict = None
) -> dict:
    timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    cycle_id = f"cycle_{uuid.uuid4().hex[:5]}"

    # STRICT CHECK: If MT5 is stale/disconnected, preserve last valid state and block recommendations
    if is_mt5_stale:
        safe_weights = _normalize_weights_with_cash(old_weights) if old_weights else {"CASH": 1.0}
        return _with_shadow_controls({
            "weights": safe_weights,
            "exposure_total": sum(v for k, v in safe_weights.items() if k != "CASH"),
            "rebalance_required": False,
            "tca_blocked": False,
            "fail_safe_active": False,
            "fail_safe_level": None,
            "fallback_active": False,
            "recommendations_blocked": True,
            "status": "stale",
            "decision_inputs": {},
            "timestamp": timestamp,
            "cycle_id": cycle_id
        }, current_nav)

    # Resolve dynamic limits (Account -> Org -> Global hierarchy)
    # Default conservative limits: QQQ max 40%, GLD max 20%, CASH min 10%
    max_qqq = 0.40
    max_gld = 0.20
    min_cash = 0.10
    
    if portfolio_limits:
        max_qqq = portfolio_limits.get("max_allocation_qqq", 0.40)
        max_gld = portfolio_limits.get("max_allocation_gld", 0.20)
        min_cash = portfolio_limits.get("min_cash", 0.10)
        
    dynamic_limits = {
        "QQQ": {"min": 0.0, "max": max_qqq},
        "GLD": {"min": 0.0, "max": max_gld},
        "CASH": {"min": min_cash, "max": 1.0}
    }

    # Calculate derivative exposures
    exposure_stats = calculate_exposure_metrics(positions or [], current_nav)

    # 100% CASH if no open positions verified
    if positions is not None and not positions:
        current_weights = {"CASH": 1.0}
    elif positions:
        current_weights = exposure_stats["weights_by_proxy"]
    else:
        current_weights = _normalize_weights_with_cash(old_weights) if old_weights else {"CASH": 1.0}
    if positions is not None:
        old_weights = current_weights

    if positions is not None and not positions:
        return _with_shadow_controls({
            "weights": {"CASH": 1.0},
            "exposure_total": 0.0,
            "rebalance_required": False,
            "tca_blocked": False,
            "fail_safe_active": False,
            "fail_safe_level": None,
            "fallback_active": False,
            "recommendations_blocked": False,
            "status": "no_open_positions",
            "current_exposures": exposure_stats,
            "margin_risk": margin_risk,
            "decision_inputs": {"portfolio_basis": "verified_open_positions", "target_basis": "cash_only"},
            "timestamp": timestamp,
            "cycle_id": cycle_id,
        }, current_nav)

    # Fallback if Quant fails
    if not quant_output or quant_output.get("status") == "fallback" or not quant_output.get("regime_probabilities"):
        fallback_res = get_context_aware_fallback(market_state, old_weights)
        fallback_weights = _apply_asset_limits(fallback_res["weights"], dynamic_limits)
        return _with_shadow_controls({
            "weights": fallback_weights,
            "exposure_total": sum(v for k, v in fallback_weights.items() if k != "CASH"),
            "rebalance_required": True,
            "tca_blocked": False,
            "fail_safe_active": False,
            "fail_safe_level": None,
            "fallback_active": True,
            "recommendations_blocked": False,
            "status": "fallback",
            "current_exposures": exposure_stats,
            "margin_risk": margin_risk,
            "decision_inputs": {
                "fallback_action": fallback_res["action_taken"],
                "market_state": market_state
            },
            "timestamp": timestamp,
            "cycle_id": cycle_id
        }, current_nav)

    fusion = BayesianFusion(historical_r_quant, historical_r_narr)
    bl_opt = BlackLittermanOptimizer(historical_returns_df)
    constraints = ConstraintEngine(redis_client)

    # 1. HWM y Drawdown
    drawdown = constraints.update_hwm_and_get_drawdown(current_nav)
    hwm = float(redis_client.get("portfolio:hwm")) if redis_client and redis_client.exists("portfolio:hwm") else current_nav

    # Verificar Cooldown
    if constraints.check_cooldown():
        safe_weights = _normalize_weights_with_cash(old_weights) if old_weights else {"CASH": 1.0}
        return _with_shadow_controls({
            "weights": safe_weights,
            "exposure_total": sum(v for k, v in safe_weights.items() if k != "CASH"),
            "rebalance_required": False,
            "tca_blocked": False,
            "fail_safe_active": True,
            "fail_safe_level": "cooldown_active",
            "fallback_active": False,
            "recommendations_blocked": False,
            "status": "cooldown",
            "current_exposures": exposure_stats,
            "margin_risk": margin_risk,
            "decision_inputs": {},
            "timestamp": timestamp,
            "cycle_id": cycle_id
        }, current_nav)

    # 2. Fusión Bayesiana
    stress_prob = quant_output.get("stress_probability_t5", 0.5)
    r_quant = _compute_r_quant(quant_output)
    omega_quant = quant_output.get("omega_quant", 0.5)

    fused_views = fusion.fuse(r_quant, omega_quant, mirofish_output)
    
    # 3. Black-Litterman
    raw_weights = bl_opt.optimize(fused_views["R_combined"], fused_views["omega_combined"])
    raw_weights = _apply_asset_limits(raw_weights, dynamic_limits, enforce_mins=True)

    # Penalización por riesgo (stress) como modificador de exposición
    penalized_weights, exposure_multiplier = _apply_risk_penalty(raw_weights, stress_prob)

    # 4. Restricciones y Fail-Safes
    safe_weights, fail_safe_level = constraints.apply_failsafes(penalized_weights, drawdown)
    safe_weights = _apply_asset_limits(safe_weights, dynamic_limits, enforce_mins=fail_safe_level is None)
    
    rebalance = True
    tca_blocked = False
    # No bloquear un fail-safe por TCA
    if fail_safe_level is None:
        if not constraints.apply_tca(safe_weights, old_weights):
            rebalance = False
            tca_blocked = True
            safe_weights = _apply_asset_limits(old_weights, dynamic_limits, enforce_mins=True) if old_weights else safe_weights

    exposure_total = sum(v for k, v in safe_weights.items() if k != "CASH")

    return _with_shadow_controls({
        "weights": safe_weights,
        "exposure_total": exposure_total,
        "rebalance_required": rebalance,
        "tca_blocked": tca_blocked,
        "fail_safe_active": fail_safe_level is not None,
        "fail_safe_level": fail_safe_level,
        "fallback_active": False,
        "recommendations_blocked": False,
        "status": "healthy",
        "current_exposures": exposure_stats,
        "margin_risk": margin_risk,
        "decision_inputs": {
            "R_quant": round(r_quant, 4),
            "R_narr": mirofish_output.get("R_narr", 0.0) if mirofish_output else 0.0,
            "w_narr_final": round(fused_views["w_narr_final"], 4),
            "omega_quant": round(omega_quant, 4),
            "omega_narr": mirofish_output.get("omega_narr", float('inf')) if mirofish_output else float('inf'),
            "stress_prob": round(stress_prob, 4),
            "stress_exposure_multiplier": round(exposure_multiplier, 4),
            "drawdown_current": round(drawdown, 4),
            "hwm": round(hwm, 2)
        },
        "timestamp": timestamp,
        "cycle_id": cycle_id
    }, current_nav)
