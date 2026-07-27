import numpy as np

from hsmm_xau.models import ExplicitDurationHSMM, HMMBenchmark, hungarian_state_map


def synthetic_states(seed=4):
    rng = np.random.default_rng(seed)
    chunks = []
    for _ in range(20):
        chunks.append(rng.normal(-2, 0.3, size=(rng.integers(8, 15), 2)))
        chunks.append(rng.normal(2, 0.3, size=(rng.integers(3, 7), 2)))
    return np.vstack(chunks)


def test_hsmm_filtered_probabilities_sum_to_one_and_are_causal():
    x = synthetic_states()
    model = ExplicitDurationHSMM(n_states=2, max_duration=20, max_iter=25, random_state=1).fit(x)
    full = model.filtered_proba(x)
    prefix = model.filtered_proba(x[:100])
    np.testing.assert_allclose(full.sum(axis=1), 1.0, atol=1e-10)
    np.testing.assert_allclose(full[:100], prefix, atol=1e-10)
    assert np.all(model.mean_duration_ > 1)


def test_hmm_benchmark_uses_filtered_probabilities():
    x = synthetic_states()
    model = HMMBenchmark(n_states=2, max_iter=25, random_state=2).fit(x)
    full = model.filtered_proba(x)
    prefix = model.filtered_proba(x[:80])
    np.testing.assert_allclose(full[:80], prefix)


def test_student_t_hsmm_is_causal():
    x = synthetic_states()
    model = ExplicitDurationHSMM(
        n_states=2,
        max_duration=20,
        max_iter=25,
        random_state=3,
        emission_family="student_t",
        emission_df=5.0,
        robust_location=True,
    ).fit(x)
    full = model.filtered_proba(x)
    prefix = model.filtered_proba(x[:90])
    np.testing.assert_allclose(full[:90], prefix, atol=1e-10)
    np.testing.assert_allclose(full.sum(axis=1), 1.0, atol=1e-10)


def test_hungarian_matching_recovers_permutation():
    anchor = {"a": np.array([0.0, 0.0]), "b": np.array([5.0, 5.0])}
    mapping, distances = hungarian_state_map(anchor, np.array([[5.1, 5.0], [0.1, 0.0]]))
    assert mapping == {"a": 1, "b": 0}
    assert max(distances.values()) < 0.2
