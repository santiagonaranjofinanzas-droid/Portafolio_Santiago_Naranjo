from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from hmmlearn.hmm import GaussianHMM
from scipy.optimize import linear_sum_assignment
from scipy.special import gammaln


def gaussian_log_density(x: np.ndarray, means: np.ndarray, variances: np.ndarray) -> np.ndarray:
    if variances.ndim == 3:
        variances = np.diagonal(variances, axis1=1, axis2=2)
    variances = np.clip(variances, 1e-6, None)
    delta = x[:, None, :] - means[None, :, :]
    return -0.5 * (
        np.log(2 * np.pi * variances)[None, :, :] + delta * delta / variances[None, :, :]
    ).sum(axis=2)


def student_t_log_density(
    x: np.ndarray, means: np.ndarray, scales_squared: np.ndarray, degrees_freedom: float
) -> np.ndarray:
    scales_squared = np.clip(scales_squared, 1e-6, None)
    delta_squared = (x[:, None, :] - means[None, :, :]) ** 2
    nu = float(degrees_freedom)
    constant = gammaln((nu + 1.0) / 2.0) - gammaln(nu / 2.0)
    log_density = (
        constant
        - 0.5 * (np.log(nu * np.pi) + np.log(scales_squared))[None, :, :]
        - ((nu + 1.0) / 2.0) * np.log1p(delta_squared / (nu * scales_squared[None, :, :]))
    )
    return log_density.sum(axis=2)


def filtered_hmm_probabilities(
    x: np.ndarray,
    startprob: np.ndarray,
    transmat: np.ndarray,
    means: np.ndarray,
    covars: np.ndarray,
) -> tuple[np.ndarray, float]:
    log_emission = gaussian_log_density(x, means, covars)
    result = np.zeros_like(log_emission)
    alpha = np.asarray(startprob, float).copy()
    log_likelihood = 0.0
    for t in range(len(x)):
        if t:
            alpha = alpha @ transmat
        shifted = np.exp(log_emission[t] - log_emission[t].max())
        alpha *= shifted
        scale = alpha.sum()
        if not np.isfinite(scale) or scale <= 0:
            alpha[:] = 1.0 / len(alpha)
            scale = 1.0
        else:
            alpha /= scale
        log_likelihood += np.log(scale) + log_emission[t].max()
        result[t] = alpha
    return result, float(log_likelihood)


@dataclass
class HMMBenchmark:
    n_states: int = 4
    max_iter: int = 100
    tolerance: float = 1e-4
    random_state: int = 0

    def fit(self, x: np.ndarray) -> "HMMBenchmark":
        self.model_ = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=self.max_iter,
            tol=self.tolerance,
            random_state=self.random_state,
            min_covar=1e-5,
        ).fit(x)
        return self

    def filtered_proba(self, x: np.ndarray) -> np.ndarray:
        result, _ = filtered_hmm_probabilities(
            x,
            self.model_.startprob_,
            self.model_.transmat_,
            self.model_.means_,
            np.diagonal(self.model_.covars_, axis1=1, axis2=2),
        )
        return result

    def score_filtered(self, x: np.ndarray) -> float:
        return filtered_hmm_probabilities(
            x,
            self.model_.startprob_,
            self.model_.transmat_,
            self.model_.means_,
            np.diagonal(self.model_.covars_, axis1=1, axis2=2),
        )[1]


def _runs(states: np.ndarray) -> list[tuple[int, int]]:
    if not len(states):
        return []
    boundaries = np.r_[0, np.flatnonzero(np.diff(states) != 0) + 1, len(states)]
    return [(int(states[a]), int(b - a)) for a, b in zip(boundaries[:-1], boundaries[1:])]


def _poisson_hazard(mean_duration: np.ndarray, max_duration: int) -> np.ndarray:
    support = np.arange(1, max_duration + 1)
    hazard = np.zeros((len(mean_duration), max_duration), float)
    for state, mean in enumerate(mean_duration):
        lam = max(float(mean) - 1.0, 0.1)
        log_pmf = -lam + (support - 1) * np.log(lam) - gammaln(support)
        pmf = np.exp(log_pmf - log_pmf.max())
        pmf /= pmf.sum()
        survival = np.cumsum(pmf[::-1])[::-1]
        hazard[state] = pmf / np.clip(survival, 1e-15, None)
        hazard[state, -1] = 1.0
    return hazard


@dataclass
class ExplicitDurationHSMM:
    """Robust explicit-duration model with Poisson duration and causal filtering.

    Parameters are initialized by an HMM and re-estimated from its training-only
    Viterbi segmentation. Online inference is the exact forward filter of the
    augmented (state, elapsed-duration) representation.
    """

    n_states: int = 4
    max_duration: int = 64
    max_iter: int = 100
    tolerance: float = 1e-4
    random_state: int = 0
    min_covar: float = 1e-5
    emission_family: str = "gaussian"
    emission_df: float = 5.0
    robust_location: bool = False

    def fit(self, x: np.ndarray) -> "ExplicitDurationHSMM":
        initializer = GaussianHMM(
            n_components=self.n_states,
            covariance_type="diag",
            n_iter=self.max_iter,
            tol=self.tolerance,
            random_state=self.random_state,
            min_covar=self.min_covar,
        ).fit(x)
        states = initializer.predict(x)
        runs = _runs(states)
        self.means_ = initializer.means_.copy()
        self.covars_ = np.diagonal(np.asarray(initializer.covars_), axis1=1, axis2=2).copy()
        if self.robust_location or self.emission_family == "student_t":
            for state in range(self.n_states):
                sample = x[states == state]
                if len(sample) < 3:
                    continue
                center = np.median(sample, axis=0)
                robust_scale = 1.4826 * np.median(np.abs(sample - center), axis=0)
                self.means_[state] = center
                self.covars_[state] = np.clip(robust_scale**2, self.min_covar, None)
        self.startprob_ = np.bincount(states[: min(len(states), 32)], minlength=self.n_states) + 1.0
        self.startprob_ /= self.startprob_.sum()
        transitions = np.ones((self.n_states, self.n_states), float) * 1e-3
        np.fill_diagonal(transitions, 0.0)
        durations: list[list[int]] = [[] for _ in range(self.n_states)]
        for (state, duration), next_run in zip(runs, runs[1:] + [(runs[-1][0], 0)]):
            durations[state].append(duration)
            if next_run[1] and next_run[0] != state:
                transitions[state, next_run[0]] += 1.0
        row_sum = transitions.sum(axis=1, keepdims=True)
        self.transmat_ = np.divide(
            transitions,
            row_sum,
            out=np.full_like(transitions, 1.0 / max(self.n_states - 1, 1)),
            where=row_sum > 0,
        )
        np.fill_diagonal(self.transmat_, 0.0)
        self.transmat_ /= self.transmat_.sum(axis=1, keepdims=True)
        self.mean_duration_ = np.array(
            [np.mean(values) if values else 2.0 for values in durations], dtype=float
        ).clip(1.1, self.max_duration)
        self.hazard_ = _poisson_hazard(self.mean_duration_, self.max_duration)
        self.training_runs_ = runs
        self.training_log_likelihood_ = self.score_filtered(x)
        return self

    def filtered_proba(self, x: np.ndarray, return_age: bool = False):
        log_emission = (
            student_t_log_density(x, self.means_, self.covars_, self.emission_df)
            if self.emission_family == "student_t"
            else gaussian_log_density(x, self.means_, self.covars_)
        )
        alpha = np.zeros((self.n_states, self.max_duration), float)
        alpha[:, 0] = self.startprob_
        probabilities = np.zeros((len(x), self.n_states), float)
        expected_age = np.zeros((len(x), self.n_states), float)
        log_likelihood = 0.0
        age_values = np.arange(1, self.max_duration + 1)
        for t in range(len(x)):
            if t:
                prior = np.zeros_like(alpha)
                exit_mass = (alpha * self.hazard_).sum(axis=1)
                prior[:, 0] = exit_mass @ self.transmat_
                prior[:, 1:] = alpha[:, :-1] * (1.0 - self.hazard_[:, :-1])
                alpha = prior
            emission = np.exp(log_emission[t] - log_emission[t].max())
            alpha *= emission[:, None]
            scale = alpha.sum()
            if not np.isfinite(scale) or scale <= 0:
                alpha[:] = 0.0
                alpha[:, 0] = 1.0 / self.n_states
                scale = 1.0
            else:
                alpha /= scale
            log_likelihood += np.log(scale) + log_emission[t].max()
            probabilities[t] = alpha.sum(axis=1)
            expected_age[t] = (alpha * age_values).sum(axis=1) / np.clip(
                probabilities[t], 1e-15, None
            )
        if return_age:
            return probabilities, expected_age, float(log_likelihood)
        return probabilities

    def score_filtered(self, x: np.ndarray) -> float:
        return self.filtered_proba(x, return_age=True)[2]


def semantic_state_map(means: np.ndarray, feature_names: list[str]) -> dict[str, int]:
    """Apply a frozen statistical taxonomy without using OOS returns."""
    index = {name: i for i, name in enumerate(feature_names)}

    def col(name: str) -> np.ndarray:
        return means[:, index[name]] if name in index else np.zeros(len(means))

    def rank(values: np.ndarray) -> np.ndarray:
        return np.argsort(np.argsort(values)).astype(float)

    er = rank(col("efficiency_ratio_32"))
    vol = rank(col("realized_vol_32"))
    acf = rank(col("return_acf1_64"))
    vr = rank(col("variance_ratio_64"))
    mr_score = -er - acf - vr
    mr = int(np.argmax(mr_score))
    breakout_candidates = np.array([state not in {mr} for state in range(len(means))])
    breakout = int(np.argmax(np.where(breakout_candidates, 2 * vol + er, -np.inf)))
    trend_candidates = np.array([state not in {mr, breakout} for state in range(len(means))])
    trend = int(np.argmax(np.where(trend_candidates, er + vr + acf, -np.inf)))
    remaining = [state for state in range(len(means)) if state not in {mr, breakout, trend}]
    neutral = remaining[0] if remaining else trend
    return {"mean_reversion": mr, "breakout": breakout, "trend": trend, "neutral": neutral}


def hungarian_state_map(
    anchor_centroids: dict[str, np.ndarray], current_centroids: np.ndarray
) -> tuple[dict[str, int], dict[str, float]]:
    """Match current states to frozen semantic centroids without using outcomes."""
    names = list(anchor_centroids)
    anchor = np.vstack([anchor_centroids[name] for name in names])
    cost = np.linalg.norm(anchor[:, None, :] - current_centroids[None, :, :], axis=2)
    rows, cols = linear_sum_assignment(cost)
    mapping = {names[row]: int(col) for row, col in zip(rows, cols)}
    distances = {names[row]: float(cost[row, col]) for row, col in zip(rows, cols)}
    return mapping, distances
