from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class GateDecision:
    stage: str
    approved: bool
    checks: tuple[dict, ...]


def load_policy(path: str  Path  None = None) -> dict:
    target = Path(path) if path else Path(__file__).with_name("research_policy.json")
    return json.loads(target.read_text(encoding="utf-8"))


def evaluate_gates(metrics: dict, robustness: dict, fold_metrics: list[dict], stage: str = "research", policy: dict  None = None) -> GateDecision:
    config = (policy or load_policy())[stage]
    fold_pf = [float(item["profit_factor"]) for item in fold_metrics]
    median_fold_pf = float(np.median(fold_pf)) if fold_pf else 0.0
    fold_trades = [int(item.get("closed_trades", 0)) for item in fold_metrics]
    paired_required = bool(robustness.get("paired_comparison_required", True))
    checks = [
        {"name": "closed_trades", "value": metrics.get("closed_trades", 0), "required": config["min_closed_trades"], "passed": metrics.get("closed_trades", 0) >= config["min_closed_trades"]},
        {"name": "profit_factor", "value": metrics.get("profit_factor", 0.0), "required": config["min_profit_factor"], "passed": metrics.get("profit_factor", 0.0) >= config["min_profit_factor"]},
        {"name": "median_fold_pf", "value": median_fold_pf, "required": config["min_median_fold_pf"], "passed": bool(fold_pf) and median_fold_pf >= config["min_median_fold_pf"]},
        {"name": "minimum_fold_pf", "value": min(fold_pf) if fold_pf else 0.0, "required": config["min_fold_pf"], "passed": bool(fold_pf) and min(fold_pf) >= config["min_fold_pf"]},
        {"name": "minimum_fold_trades", "value": min(fold_trades) if fold_trades else 0, "required": config["min_trades_per_fold"], "passed": bool(fold_trades) and min(fold_trades) >= config["min_trades_per_fold"]},
        {"name": "daily_sharpe", "value": metrics.get("daily_sharpe", 0.0), "required": config["min_daily_sharpe"], "passed": metrics.get("daily_sharpe", 0.0) >= config["min_daily_sharpe"]},
        {"name": "dsr", "value": metrics.get("dsr_probability", 0.0), "required": config["min_dsr"], "passed": metrics.get("dsr_probability", 0.0) >= config["min_dsr"]},
        {"name": "drawdown", "value": metrics.get("max_drawdown_pct", -100.0), "required": -config["max_drawdown_pct"], "passed": abs(metrics.get("max_drawdown_pct", -100.0)) <= config["max_drawdown_pct"]},
        {"name": "bootstrap_pf_p05", "value": robustness.get("pf_p05", 0.0), "required": config["min_bootstrap_pf_p05"], "passed": robustness.get("pf_p05", 0.0) > config["min_bootstrap_pf_p05"]},
        {"name": "bootstrap_expectancy_p05", "value": robustness.get("expectancy_p05", -1.0), "required": 0.0, "passed": robustness.get("expectancy_p05", -1.0) > 0.0},
        {"name": "bootstrap_probability_positive", "value": robustness.get("probability_positive", 0.0), "required": config["min_probability_positive"], "passed": robustness.get("probability_positive", 0.0) >= config["min_probability_positive"]},
        {"name": "pbo", "value": robustness.get("pbo", 1.0), "required": config["max_pbo"], "passed": robustness.get("pbo", 1.0) <= config["max_pbo"]},
        {"name": "worst_quarter_pf", "value": metrics.get("worst_quarter_profit_factor", 0.0), "required": config["min_worst_quarter_pf"], "passed": metrics.get("worst_quarter_profit_factor", 0.0) >= config["min_worst_quarter_pf"]},
        {"name": "winner_concentration", "value": metrics.get("top5_winner_share_pct", 100.0), "required": config["max_top5_winner_share_pct"], "passed": metrics.get("top5_winner_share_pct", 100.0) <= config["max_top5_winner_share_pct"]},
        {"name": "neighbor_stability", "value": robustness.get("neighbor_positive_fraction", 0.0), "required": config["min_neighbor_positive_fraction"], "passed": robustness.get("neighbor_positive_fraction", 0.0) >= config["min_neighbor_positive_fraction"]},
        {"name": "adverse_cost_pf", "value": robustness.get("adverse_cost_pf", 0.0), "required": config["min_adverse_cost_pf"], "passed": robustness.get("adverse_cost_pf", 0.0) >= config["min_adverse_cost_pf"]},
        {"name": "crisis_cost_pf", "value": robustness.get("crisis_cost_pf", 0.0), "required": config["min_crisis_cost_pf"], "passed": robustness.get("crisis_cost_pf", 0.0) >= config["min_crisis_cost_pf"]},
        {"name": "paired_delta_expectancy_p05", "value": robustness.get("delta_expectancy_p05", 0.0) if paired_required else "NOT_APPLICABLE", "required": 0.0, "passed": (not paired_required) or robustness.get("delta_expectancy_p05", -1.0) > 0.0},
        {"name": "paired_probability_improvement", "value": robustness.get("probability_improvement", 1.0) if paired_required else "NOT_APPLICABLE", "required": config["min_probability_improvement"], "passed": (not paired_required) or robustness.get("probability_improvement", 0.0) >= config["min_probability_improvement"]},
    ]
    return GateDecision(stage=stage, approved=all(bool(item["passed"]) for item in checks), checks=tuple(checks))
