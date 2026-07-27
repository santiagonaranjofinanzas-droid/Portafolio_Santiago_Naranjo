import numpy as np

from hsmm_xau.opportunity import OpportunityModel


def test_opportunity_model_outputs_bounded_probabilities():
    rng = np.random.default_rng(11)
    x = rng.normal(size=(600, 5))
    y = (x[:, 0] - 0.5 * x[:, 1] + rng.normal(size=600) > 0).astype(float)
    model = OpportunityModel(random_state=11, max_iter=1000).fit(
        x[:400], y[:400], x[400:500], y[400:500]
    )
    probability = model.predict_proba(x[500:])
    assert np.all((probability >= 0) & (probability <= 1))
    assert probability.std() > 0
    economic_indices = np.flatnonzero(model.economic_calibration_mask_)
    assert economic_indices.min() >= 400 // 3 * 2 - 400 // 2
    assert economic_indices.max() == 99
