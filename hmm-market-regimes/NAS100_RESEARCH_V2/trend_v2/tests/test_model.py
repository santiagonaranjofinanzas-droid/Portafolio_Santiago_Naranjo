from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from NAS100_RESEARCH_V2.trend_v2 import RegimeConfig, TrendV2Config, TrendV2Model


def _research_config() -> TrendV2Config:
    return TrendV2Config(
        regime=replace(
            RegimeConfig(),
            max_iter=35,
            tolerance=2e-5,
            min_state_occupancy=0.02,
            min_state_separation=0.01,
        )
    )


def test_fold_api_filters_probabilities_and_reports_identification(synthetic_bars):
    train = synthetic_bars.iloc[:900]
    test = synthetic_bars.iloc[900:]
    model = TrendV2Model(_research_config()).fit(train)
    transformed = model.transform(test)
    probability = transformed[["p_trendable", "p_range", "p_shock"]]
    assert np.isfinite(probability.to_numpy()).all()
    assert np.allclose(probability.sum(axis=1), 1.0, atol=1e-12)
    assert set(transformed["filtered_regime"].unique()).issubset(
        {"TRENDABLE", "RANGE", "SHOCK"}
    )
    diagnostics = model.diagnostics()["regime"]
    assert diagnostics["state_order"] == ["TRENDABLE", "RANGE", "SHOCK"]
    assert sum(diagnostics["state_occupancy"].values()) == pytest.approx(1.0)
    assert len(diagnostics["transition_matrix"]) == 3
    assert isinstance(diagnostics["identified"], bool)


def test_oos_filter_is_prefix_invariant(synthetic_bars):
    model = TrendV2Model(_research_config()).fit(synthetic_bars.iloc[:850])
    shorter = model.transform(synthetic_bars.iloc[850:1000])
    longer = model.transform(synthetic_bars.iloc[850:1100])
    columns = ["p_trendable", "p_range", "p_shock"]
    assert np.allclose(
        shorter[columns].to_numpy(),
        longer.loc[shorter.index, columns].to_numpy(),
        atol=1e-12,
    )


def test_train_and_test_may_not_overlap(synthetic_bars):
    model = TrendV2Model(_research_config()).fit(synthetic_bars.iloc[:850])
    overlapping_context = synthetic_bars.iloc[800:900]
    with pytest.raises(ValueError, match="must not overlap"):
        model.transform(synthetic_bars.iloc[850:950], context=overlapping_context)
