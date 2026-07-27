import numpy as np
import pandas as pd

from hsmm_xau.equilibrium import add_equilibrium
from hsmm_xau.features import assert_causal, build_features


def sample_frame(n=400):
    rng = np.random.default_rng(7)
    index = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 2000 * np.exp(np.cumsum(rng.normal(0, 0.0005, n)))
    frame = pd.DataFrame(index=index)
    frame["mid_close"] = close
    frame["mid_high"] = close * 1.0002
    frame["mid_low"] = close * 0.9998
    frame["spread_mean"] = 0.2 + rng.random(n) * 0.05
    frame["tick_count"] = rng.integers(100, 500, n)
    return frame


def config():
    return {
        "equilibrium": {
            "kalman_process_variance": 1e-6,
            "kalman_observation_variance": 1e-4,
            "z_window": 96,
            "ewma_span": 96,
        },
        "features": {"windows": [16, 32, 64, 96]},
    }


def test_equilibrium_is_prefix_invariant():
    frame = sample_frame()
    full = add_equilibrium(frame, config()).iloc[:300]
    prefix = add_equilibrium(frame.iloc[:300], config())
    np.testing.assert_allclose(full.equilibrium, prefix.equilibrium, equal_nan=True)


def test_features_are_prefix_invariant():
    frame = add_equilibrium(sample_frame(), config())
    assert_causal(build_features, frame, config(), 300)
