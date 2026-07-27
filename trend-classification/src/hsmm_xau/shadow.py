from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .walkforward import _opportunity_matrix


def infer_latest(
    dataset_path: Path,
    model_path: Path,
    output_log: Path,
    research_approved: bool = False,
    kill_switch: bool = True,
) -> dict:
    frame = pd.read_parquet(dataset_path).sort_index()
    bundle = joblib.load(model_path)
    features = bundle["feature_names"]
    recent = frame.iloc[-max(256, bundle["model"].max_duration * 3) :]
    x = bundle["scaler"].transform(bundle["imputer"].transform(recent[features]))
    x = np.clip(x, -10, 10)
    probabilities, ages, _ = bundle["model"].filtered_proba(x, return_age=True)
    state_map = bundle["state_map"]
    state_names = bundle["state_names"]
    opportunity_matrix = _opportunity_matrix(
        recent,
        bundle["opportunity_features"],
        probabilities,
        ages,
        state_map,
        state_names,
        "all",
    )
    p_success = float(bundle["opportunity_model"].predict_proba(opportunity_matrix)[-1])
    state_probability = {name: float(probabilities[-1, state_map[name]]) for name in state_names}
    expected_value = p_success * float(bundle["calibration_gain"]) - (1.0 - p_success) * float(
        bundle["calibration_loss"]
    )
    row = recent.iloc[-1]
    z = float(row.residual_z)
    direction = "SHORT" if z > 0 else "LONG"
    decision = bundle["decision"]
    signal_passes = bool(
        abs(z) >= 1.5
        and state_probability["mean_reversion"] >= float(decision["mr_probability_threshold"])
        and state_probability["breakout"] < float(decision["max_breakout_probability"])
        and p_success >= float(decision["min_success_probability"])
        and expected_value > float(decision["min_expected_value"])
    )
    trade_allowed = bool(signal_passes and research_approved and not kill_switch)
    result = {
        "inference_time_utc": datetime.now(timezone.utc).isoformat(),
        "timestamp": recent.index[-1].isoformat(),
        **{f"p_{name}": probability for name, probability in state_probability.items()},
        "p_opportunity": p_success,
        "expected_regime_bars_elapsed": float(ages[-1, state_map["mean_reversion"]]),
        "estimated_half_life": None
        if not np.isfinite(row.get("half_life_64", np.nan))
        else float(row.half_life_64),
        "equilibrium_zscore": z,
        "equilibrium_stability": float(row.equilibrium_stability),
        "expected_net_value": expected_value,
        "signal_direction": direction,
        "trade_allowed": trade_allowed,
        "signal_passes": signal_passes,
        "research_approved": research_approved,
        "kill_switch": kill_switch,
        "model_version": bundle["config_version"],
    }
    output_log.parent.mkdir(parents=True, exist_ok=True)
    with output_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False) + "\n")
    return result
