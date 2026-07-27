from __future__ import annotations

import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from NAS100_RESEARCH_V2.mean_reversion_v2 import LocalTrendConfig, RobustLocalLinearTrend
from NAS100_RESEARCH_V2.mean_reversion_v2.model import _huber_ar1


def synthetic_prices(n: int = 2_600, seed: int = 17) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    phi = 0.88
    residual = np.zeros(n)
    for i in range(1, n):
        residual[i] = phi * residual[i - 1] + rng.normal(0.0, 8e-4)
    level = (
        np.log(18_000.0)
        + np.arange(n) * 1e-5
        + np.cumsum(rng.normal(0.0, 1e-5, n))
    )
    index = pd.date_range("2020-01-01", periods=n, freq="15min")
    return pd.DataFrame({"close": np.exp(level + residual)}, index=index)


def test_recovers_stationary_transient_residual_and_gate() -> None:
    data = synthetic_prices()
    model = RobustLocalLinearTrend(LocalTrendConfig(min_train_observations=200)).fit(data.iloc[:2_000])
    estimate = model.ar1_

    assert 0.75 < estimate.phi < 0.96
    assert estimate.ci_high < 1.0
    assert 2.0 <= estimate.half_life <= 16.0
    assert estimate.gate_passed


def test_filter_is_prefix_invariant_to_future_changes() -> None:
    data = synthetic_prices()
    train, test = data.iloc[:1_800], data.iloc[1_800:].copy()
    model = RobustLocalLinearTrend().fit(train)
    baseline = model.filter(test)
    changed = test.copy()
    changed.iloc[300:, 0] *= np.linspace(1.2, 1.8, len(changed) - 300)
    counterfactual = model.filter(changed)

    columns = ["level", "residual", "z_residual", "innovation_z", "structural_break"]
    pdt.assert_frame_equal(baseline.iloc[:300][columns], counterfactual.iloc[:300][columns])


def test_warmup_must_precede_test_and_is_not_returned() -> None:
    data = synthetic_prices(1_000)
    model = RobustLocalLinearTrend().fit(data.iloc[:600])
    warmup = data.iloc[550:600]
    test = data.iloc[600:700]
    output = model.filter(test, warmup=warmup)
    assert output.index.equals(test.index)
    assert len(output) == len(test)

    with pytest.raises(ValueError, match="warmup must end"):
        model.filter(test, warmup=data.iloc[590:610])


def test_no_missing_values_are_backfilled() -> None:
    data = synthetic_prices(800)
    model = RobustLocalLinearTrend().fit(data.iloc[:500])
    output = model.filter(data.iloc[500:], warmup=data.iloc[495:500])
    # Five causal warmup rows plus 27 test rows are needed for min_periods=32.
    assert output["rolling_innovation_scale"].iloc[:26].isna().all()
    assert output["rolling_innovation_scale"].iloc[26:].notna().all()


def test_near_unit_root_residual_is_rejected_by_ar_confidence_gate() -> None:
    rng = np.random.default_rng(91)
    random_walk = np.cumsum(rng.normal(0.0, 1.0, 2_000))
    estimate = _huber_ar1(random_walk, LocalTrendConfig())
    assert not estimate.gate_passed
    assert (
        "PHI_UPPER_CI_NOT_BELOW_ONE" in estimate.gate_reasons
        or "HALF_LIFE_OUTSIDE_ALLOWED_RANGE" in estimate.gate_reasons
        or "PHI_AT_OR_ABOVE_LIMIT" in estimate.gate_reasons
    )
