from __future__ import annotations

import numpy as np

from NAS100_RESEARCH_V2.trend_v2 import (
    REGIME_FEATURES,
    build_causal_features,
    causal_prefix_invariant,
)


def test_features_are_prefix_invariant(synthetic_bars):
    assert causal_prefix_invariant(synthetic_bars, prefix_length=850)


def test_feature_schema_and_bounds(synthetic_bars):
    features = build_causal_features(synthetic_bars)
    assert set(REGIME_FEATURES).issubset(features.columns)
    assert {"momentum_16", "momentum_32", "momentum_64", "momentum_score", "atr"}.issubset(
        features.columns
    )
    valid = features.loc[features["feature_valid"], list(REGIME_FEATURES)]
    assert len(valid) > 500
    assert np.isfinite(valid.to_numpy()).all()
    assert features["efficiency_ratio_32"].dropna().between(0.0, 1.0 + 1e-10).all()
    assert (features["atr"].dropna() > 0.0).all()


def test_current_activity_does_not_normalize_itself(synthetic_bars):
    changed = synthetic_bars.copy()
    location = 800
    changed.iloc[location, changed.columns.get_loc("tick_volume")] *= 100.0
    original_features = build_causal_features(synthetic_bars)
    changed_features = build_causal_features(changed)
    # Current ratio changes, but all prior rows remain bit-for-bit invariant.
    assert np.allclose(
        original_features["hour_activity_log_ratio"].iloc[:location].to_numpy(),
        changed_features["hour_activity_log_ratio"].iloc[:location].to_numpy(),
        equal_nan=True,
    )
    assert changed_features["hour_activity_log_ratio"].iloc[location] > original_features[
        "hour_activity_log_ratio"
    ].iloc[location]
