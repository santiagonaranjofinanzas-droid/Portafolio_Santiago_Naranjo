"""Robust three-state sticky Student-t hidden Markov regime model.

The model deliberately uses filtered probabilities for all out-of-sample
decisions. Forward-backward probabilities are used only inside the IS EM fit.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import gammaln, logsumexp

from .config import RegimeConfig
from .features import REGIME_FEATURES


STATE_NAMES: tuple[str, ...] = ("TRENDABLE", "RANGE", "SHOCK")


class RobustScaler:
    """Median/MAD scaler fitted only on the training fold."""

    def __init__(self, floor: float = 1e-6) -> None:
        self.floor = float(floor)
        self.center_: np.ndarray  None = None
        self.scale_: np.ndarray  None = None

    def fit(self, values: np.ndarray) -> "RobustScaler":
        values = np.asarray(values, dtype=float)
        center = np.median(values, axis=0)
        mad = 1.4826 * np.median(np.abs(values - center), axis=0)
        std = np.std(values, axis=0, ddof=1)
        scale = np.where(mad > self.floor, mad, std)
        scale = np.where(np.isfinite(scale) & (scale > self.floor), scale, 1.0)
        self.center_ = center
        self.scale_ = scale
        return self

    def transform(self, values: np.ndarray) -> np.ndarray:
        if self.center_ is None or self.scale_ is None:
            raise RuntimeError("RobustScaler must be fitted before transform")
        scaled = (np.asarray(values, dtype=float) - self.center_) / self.scale_
        # Winsorisation is fixed ex ante and prevents one bad quote from
        # numerically dominating a full EM iteration.
        return np.clip(scaled, -12.0, 12.0)


class StickyStudentTHMM:
    """Diagonal multivariate Student-t HMM with a sticky transition prior.

    State labels are semantically identified after fitting and always exposed
    in the fixed order TRENDABLE, RANGE, SHOCK. The sticky Dirichlet prior is a
    practical HSMM-like duration regularizer without an additional dependency.
    """

    def __init__(self, config: RegimeConfig  None = None) -> None:
        self.config = config or RegimeConfig()
        if self.config.degrees_of_freedom <= 2.0:
            raise ValueError("degrees_of_freedom must exceed 2")
        self.scaler = RobustScaler(self.config.robust_scale_floor)
        self.feature_names_: tuple[str, ...]  None = None
        self.initial_prob_: np.ndarray  None = None
        self.transition_: np.ndarray  None = None
        self.means_: np.ndarray  None = None
        self.variances_: np.ndarray  None = None
        self.last_filtered_probability_: np.ndarray  None = None
        self.training_filtered_probabilities_: pd.DataFrame  None = None
        self.diagnostics_: dict[str, Any]  None = None
        self.log_likelihood_history_: list[float] = []

    @property
    def is_fitted(self) -> bool:
        return self.means_ is not None

    def _check_frame(self, features: pd.DataFrame) -> np.ndarray:
        if not isinstance(features, pd.DataFrame):
            raise TypeError("features must be a pandas DataFrame")
        if self.feature_names_ is None:
            names = tuple(str(c) for c in features.columns)
        else:
            names = self.feature_names_
            missing = set(names).difference(features.columns)
            if missing:
                raise ValueError(f"Missing fitted feature columns: {sorted(missing)}")
        values = features.loc[:, names].to_numpy(dtype=float)
        if values.ndim != 2 or len(values) < 1:
            raise ValueError("At least one feature row is required")
        if not np.isfinite(values).all():
            raise ValueError("Regime features must all be finite")
        return values

    @staticmethod
    def _initial_partition(x: np.ndarray, names: tuple[str, ...]) -> np.ndarray:
        index = {name: i for i, name in enumerate(names)}

        def col(name: str) -> np.ndarray:
            return x[:, index[name]] if name in index else np.zeros(len(x))

        shock_score = (
            col("jump_score_96")
            + 0.75 * col("log_vol_ratio_16_96")
            + 0.65 * col("hour_range_log_ratio")
            + 0.20 * col("hour_activity_log_ratio")
        )
        trend_score = (
            col("trend_strength_16")
            + col("efficiency_ratio_32")
            - 0.15 * np.maximum(shock_score, 0.0)
        )
        n = len(x)
        minimum = max(2, int(round(0.15 * n)))
        shock_count = min(max(minimum, int(round(0.20 * n))), n - 2 * minimum)
        labels = np.ones(n, dtype=int)  # RANGE
        shock_order = np.argsort(shock_score)
        shock_rows = shock_order[-shock_count:]
        labels[shock_rows] = 2
        remaining = np.flatnonzero(labels != 2)
        trend_count = min(max(minimum, int(round(0.35 * n))), len(remaining) - minimum)
        trend_rows = remaining[np.argsort(trend_score[remaining])[-trend_count:]]
        labels[trend_rows] = 0
        return labels

    def _log_emissions(self, x: np.ndarray) -> np.ndarray:
        assert self.means_ is not None and self.variances_ is not None
        nu = self.config.degrees_of_freedom
        dimension = x.shape[1]
        result = np.empty((len(x), 3), dtype=float)
        constant = gammaln((nu + dimension) / 2.0) - gammaln(nu / 2.0)
        constant -= 0.5 * dimension * np.log(nu * np.pi)
        for state in range(3):
            variance = np.maximum(self.variances_[state], self.config.variance_floor)
            delta = np.sum((x - self.means_[state]) ** 2 / variance, axis=1)
            result[:, state] = (
                constant
                - 0.5 * np.sum(np.log(variance))
                - 0.5 * (nu + dimension) * np.log1p(delta / nu)
            )
        return result

    def _forward(
        self,
        log_emission: np.ndarray,
        initial_prob: np.ndarray  None = None,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        assert self.transition_ is not None and self.initial_prob_ is not None
        initial = self.initial_prob_ if initial_prob is None else np.asarray(initial_prob, dtype=float)
        initial = np.maximum(initial, 1e-300)
        initial /= initial.sum()
        log_transition = np.log(np.maximum(self.transition_, 1e-300))
        log_alpha = np.empty_like(log_emission)
        scales = np.empty(len(log_emission), dtype=float)
        first = np.log(initial) + log_emission[0]
        scales[0] = logsumexp(first)
        log_alpha[0] = first - scales[0]
        for row in range(1, len(log_emission)):
            prediction = logsumexp(log_alpha[row - 1][:, None] + log_transition, axis=0)
            joint = prediction + log_emission[row]
            scales[row] = logsumexp(joint)
            log_alpha[row] = joint - scales[row]
        return log_alpha, scales, float(scales.sum())

    def _forward_backward(
        self,
        log_emission: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
        assert self.transition_ is not None
        log_alpha, scales, likelihood = self._forward(log_emission)
        log_transition = np.log(np.maximum(self.transition_, 1e-300))
        log_beta = np.zeros_like(log_alpha)
        for row in range(len(log_emission) - 2, -1, -1):
            log_beta[row] = logsumexp(
                log_transition
                + log_emission[row + 1][None, :]
                + log_beta[row + 1][None, :],
                axis=1,
            ) - scales[row + 1]
        log_gamma = log_alpha + log_beta
        log_gamma -= logsumexp(log_gamma, axis=1, keepdims=True)
        gamma = np.exp(log_gamma)
        transition_counts = np.zeros((3, 3), dtype=float)
        for row in range(len(log_emission) - 1):
            log_xi = (
                log_alpha[row][:, None]
                + log_transition
                + log_emission[row + 1][None, :]
                + log_beta[row + 1][None, :]
            )
            log_xi -= logsumexp(log_xi)
            transition_counts += np.exp(log_xi)
        return gamma, transition_counts, likelihood, np.exp(log_alpha)

    def _semantic_order(self) -> list[int]:
        assert self.means_ is not None and self.feature_names_ is not None
        names = {name: i for i, name in enumerate(self.feature_names_)}

        def state_column(name: str) -> np.ndarray:
            return self.means_[:, names[name]] if name in names else np.zeros(3)

        shock_scores = (
            state_column("jump_score_96")
            + 0.75 * state_column("log_vol_ratio_16_96")
            + 0.65 * state_column("hour_range_log_ratio")
            + 0.20 * state_column("hour_activity_log_ratio")
        )
        shock = int(np.argmax(shock_scores))
        candidates = [state for state in range(3) if state != shock]
        trend_scores = (
            state_column("trend_strength_16")
            + state_column("efficiency_ratio_32")
            - 0.15 * np.maximum(shock_scores, 0.0)
        )
        trend = max(candidates, key=lambda state: float(trend_scores[state]))
        range_state = next(state for state in candidates if state != trend)
        return [trend, range_state, shock]

    def _reorder_states(self, order: list[int]) -> None:
        assert self.initial_prob_ is not None
        assert self.transition_ is not None
        assert self.means_ is not None
        assert self.variances_ is not None
        self.initial_prob_ = self.initial_prob_[order]
        self.initial_prob_ /= self.initial_prob_.sum()
        self.transition_ = self.transition_[np.ix_(order, order)]
        self.means_ = self.means_[order]
        self.variances_ = self.variances_[order]

    def fit(self, features: pd.DataFrame) -> "StickyStudentTHMM":
        """Fit on one training fold; no row outside ``features`` is accessed."""

        self.feature_names_ = tuple(str(c) for c in features.columns)
        raw = self._check_frame(features)
        if len(raw) < 60:
            raise ValueError("At least 60 valid training rows are required")
        x = self.scaler.fit(raw).transform(raw)
        labels = self._initial_partition(x, self.feature_names_)
        global_mean = np.mean(x, axis=0)
        global_variance = np.maximum(np.var(x, axis=0), self.config.variance_floor)
        self.means_ = np.vstack(
            [np.mean(x[labels == state], axis=0) for state in range(3)]
        )
        self.variances_ = np.vstack(
            [
                np.maximum(np.var(x[labels == state], axis=0), self.config.variance_floor)
                for state in range(3)
            ]
        )
        off_diagonal = (1.0 - 0.94) / 2.0
        self.transition_ = np.full((3, 3), off_diagonal, dtype=float)
        np.fill_diagonal(self.transition_, 0.94)
        label_counts = np.bincount(labels, minlength=3).astype(float)
        self.initial_prob_ = (label_counts + 1.0) / (len(labels) + 3.0)
        self.log_likelihood_history_ = []
        converged = False

        for iteration in range(self.config.max_iter):
            log_emission = self._log_emissions(x)
            gamma, transition_counts, likelihood, _ = self._forward_backward(log_emission)
            self.log_likelihood_history_.append(likelihood)
            nu = self.config.degrees_of_freedom
            dimension = x.shape[1]
            new_means = np.empty_like(self.means_)
            new_variances = np.empty_like(self.variances_)
            for state in range(3):
                variance = np.maximum(self.variances_[state], self.config.variance_floor)
                delta = np.sum((x - self.means_[state]) ** 2 / variance, axis=1)
                latent_scale = (nu + dimension) / (nu + delta)
                weighted_gamma = gamma[:, state] * latent_scale
                mean_denominator = weighted_gamma.sum() + self.config.mean_shrinkage
                new_means[state] = (
                    np.sum(weighted_gamma[:, None] * x, axis=0)
                    + self.config.mean_shrinkage * global_mean
                ) / mean_denominator
                residual = x - new_means[state]
                variance_denominator = gamma[:, state].sum() + self.config.variance_shrinkage
                new_variances[state] = (
                    np.sum(weighted_gamma[:, None] * residual**2, axis=0)
                    + self.config.variance_shrinkage * global_variance
                ) / variance_denominator
            self.means_ = new_means
            self.variances_ = np.maximum(new_variances, self.config.variance_floor)

            prior = np.full((3, 3), self.config.transition_prior, dtype=float)
            prior += np.eye(3) * self.config.sticky_prior
            transition = transition_counts + prior
            transition = np.maximum(transition, self.config.transition_floor)
            self.transition_ = transition / transition.sum(axis=1, keepdims=True)
            self.initial_prob_ = (gamma[0] + 1.0) / (gamma[0].sum() + 3.0)

            if iteration > 0:
                improvement = self.log_likelihood_history_[-1] - self.log_likelihood_history_[-2]
                scale = 1.0 + abs(self.log_likelihood_history_[-2])
                if abs(improvement) / scale < self.config.tolerance:
                    converged = True
                    break

        self._reorder_states(self._semantic_order())
        log_emission = self._log_emissions(x)
        gamma, _, final_likelihood, filtered = self._forward_backward(log_emission)
        self.last_filtered_probability_ = filtered[-1].copy()
        probability_columns = [f"p_{name.lower()}" for name in STATE_NAMES]
        self.training_filtered_probabilities_ = pd.DataFrame(
            filtered, index=features.index, columns=probability_columns
        )
        self.diagnostics_ = self._build_diagnostics(
            gamma=gamma,
            filtered=filtered,
            pseudo_labels=self._initial_partition(x, self.feature_names_),
            final_likelihood=final_likelihood,
            converged=converged,
            iterations=len(self.log_likelihood_history_),
        )
        return self

    def _build_diagnostics(
        self,
        gamma: np.ndarray,
        filtered: np.ndarray,
        pseudo_labels: np.ndarray,
        final_likelihood: float,
        converged: bool,
        iterations: int,
    ) -> dict[str, Any]:
        assert self.transition_ is not None
        assert self.means_ is not None
        assert self.variances_ is not None
        assert self.scaler.center_ is not None and self.scaler.scale_ is not None
        occupancy = gamma.mean(axis=0)
        separations: dict[str, float] = {}
        minimum_separation = np.inf
        for left in range(3):
            for right in range(left + 1, 3):
                pooled = 0.5 * (self.variances_[left] + self.variances_[right])
                distance = float(
                    np.sqrt(np.mean((self.means_[left] - self.means_[right]) ** 2 / pooled))
                )
                key = f"{STATE_NAMES[left]}__{STATE_NAMES[right]}"
                separations[key] = distance
                minimum_separation = min(minimum_separation, distance)
        expected_duration = 1.0 / np.maximum(1.0 - np.diag(self.transition_), 1e-9)
        raw_means = self.scaler.center_[None, :] + self.means_ * self.scaler.scale_[None, :]
        one_hot = np.eye(3, dtype=float)[pseudo_labels]
        brier = float(np.mean(np.sum((filtered - one_hot) ** 2, axis=1) / 3.0))
        log_score = float(np.mean(np.log(np.maximum(filtered[np.arange(len(filtered)), pseudo_labels], 1e-12))))
        confidence = filtered.max(axis=1)
        correct = (filtered.argmax(axis=1) == pseudo_labels).astype(float)
        ece = 0.0
        for lower in np.linspace(0.0, 0.9, 10):
            selected = (confidence >= lower) & (confidence < lower + 0.1)
            if selected.any():
                ece += float(selected.mean()) * abs(float(correct[selected].mean()) - float(confidence[selected].mean()))
        warnings: list[str] = []
        for state, value in zip(STATE_NAMES, occupancy):
            if value < self.config.min_state_occupancy:
                warnings.append(f"{state} occupancy {value:.3f} below minimum")
        if minimum_separation < self.config.min_state_separation:
            warnings.append(f"minimum state separation {minimum_separation:.3f} below minimum")
        if np.any(np.diag(self.transition_) > 0.995):
            warnings.append("one or more transition probabilities are on the persistence boundary")
        variance_boundary = bool(np.any(self.variances_ <= self.config.variance_floor * 1.001))
        if variance_boundary:
            warnings.append("one or more emission variances reached the variance floor")
        if not converged:
            warnings.append("EM did not meet the configured convergence tolerance")
        identified = (
            bool(converged)
            and bool(np.all(occupancy >= self.config.min_state_occupancy))
            and bool(minimum_separation >= self.config.min_state_separation)
            and not bool(np.any(np.diag(self.transition_) > 0.995))
            and not variance_boundary
        )
        return {
            "model": "sticky_diagonal_student_t_hmm",
            "state_order": list(STATE_NAMES),
            "feature_order": list(self.feature_names_ or ()),
            "config": asdict(self.config),
            "converged": bool(converged),
            "identified": identified,
            "iterations": int(iterations),
            "log_likelihood": float(final_likelihood),
            "average_log_likelihood": float(final_likelihood / len(gamma)),
            "filtered_pseudo_label_log_score": log_score,
            "filtered_pseudo_label_brier": brier,
            "filtered_calibration_ece": float(ece),
            "pnl_used_for_regime_selection": False,
            "state_occupancy": {
                state: float(value) for state, value in zip(STATE_NAMES, occupancy)
            },
            "transition_matrix": self.transition_.tolist(),
            "expected_duration_bars": {
                state: float(value) for state, value in zip(STATE_NAMES, expected_duration)
            },
            "minimum_state_separation": float(minimum_separation),
            "pairwise_state_separation": separations,
            "state_feature_means": {
                state: {
                    feature: float(value)
                    for feature, value in zip(self.feature_names_ or (), row)
                }
                for state, row in zip(STATE_NAMES, raw_means)
            },
            "warnings": warnings,
        }

    def filter(
        self,
        features: pd.DataFrame,
        initial_probability: np.ndarray  None = None,
    ) -> pd.DataFrame:
        """Sequentially filter probabilities; no backward/smoothed pass is run."""

        if not self.is_fitted:
            raise RuntimeError("Model must be fitted before filter")
        raw = self._check_frame(features)
        x = self.scaler.transform(raw)
        log_emission = self._log_emissions(x)
        log_alpha, _, _ = self._forward(log_emission, initial_probability)
        filtered = np.exp(log_alpha)
        columns = [f"p_{state.lower()}" for state in STATE_NAMES]
        return pd.DataFrame(filtered, index=features.index, columns=columns)

    def transform(
        self,
        features: pd.DataFrame,
        initial_probability: np.ndarray  None = None,
    ) -> pd.DataFrame:
        return self.filter(features, initial_probability)

    def diagnostics(self) -> dict[str, Any]:
        if self.diagnostics_ is None:
            raise RuntimeError("Model must be fitted before diagnostics")
        return self.diagnostics_


def default_regime_feature_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Select the canonical regime inputs in their preregistered order."""

    missing = set(REGIME_FEATURES).difference(features.columns)
    if missing:
        raise ValueError(f"Missing canonical regime features: {sorted(missing)}")
    return features.loc[:, REGIME_FEATURES]
