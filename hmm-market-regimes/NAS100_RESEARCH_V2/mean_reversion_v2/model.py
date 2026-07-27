"""Causal robust local-linear-trend model with an AR(1) transient residual."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from .config import LocalTrendConfig


def _mad_scale(values: np.ndarray, floor: float = 1e-12) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return floor
    median = float(np.median(values))
    scale = 1.4826 * float(np.median(np.abs(values - median)))
    if not np.isfinite(scale) or scale <= floor:
        scale = float(np.std(values, ddof=1)) if values.size > 1 else floor
    return max(scale, floor)


def _huber_loss(z: float, c: float) -> float:
    az = abs(z)
    return 0.5 * z * z if az <= c else c * az - 0.5 * c * c


@dataclass(frozen=True)
class AR1Estimate:
    intercept: float
    phi: float
    standard_error: float
    ci_low: float
    ci_high: float
    half_life: float
    observations: int
    hac_lags: int
    converged: bool
    gate_passed: bool
    gate_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["gate_reasons"] = list(self.gate_reasons)
        return result


@dataclass(frozen=True)
class ModelFitSummary:
    transform: str
    observations: int
    selected_level_q_ratio: float
    selected_slope_q_ratio: float
    observation_variance: float
    process_level_variance: float
    process_slope_variance: float
    robust_forecast_score: float
    residual_scale: float
    innovation_scale: float
    ar1: AR1Estimate

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["ar1"] = self.ar1.to_dict()
        return result


def _huber_ar1(residual: np.ndarray, cfg: LocalTrendConfig) -> AR1Estimate:
    """Fit intercept + AR(1) with Huber IRLS and a Newey-West sandwich CI."""

    residual = np.asarray(residual, dtype=float)
    valid = np.isfinite(residual)
    residual = residual[valid]
    if residual.size < 12:
        raise ValueError("at least 12 finite residual observations are required for AR(1)")

    y = residual[1:]
    x = np.column_stack([np.ones(residual.size - 1), residual[:-1]])
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    converged = False
    weights = np.ones_like(y)

    for _ in range(100):
        error = y - x @ beta
        scale = _mad_scale(error, cfg.variance_floor**0.5)
        standardized = error / scale
        weights = np.minimum(1.0, cfg.huber_c / np.maximum(np.abs(standardized), 1e-12))
        root_w = np.sqrt(weights)
        updated = np.linalg.lstsq(x * root_w[:, None], y * root_w, rcond=None)[0]
        if np.max(np.abs(updated - beta)) < 1e-10:
            beta = updated
            converged = True
            break
        beta = updated

    error = y - x @ beta
    score_vectors = x * (weights * error)[:, None]
    bread = (x.T @ (weights[:, None] * x)) / len(y)
    bread_inv = np.linalg.pinv(bread)
    lags = cfg.ar_hac_lags
    if lags is None:
        lags = max(1, int(np.floor(4.0 * (len(y) / 100.0) ** (2.0 / 9.0))))
    lags = min(int(lags), max(0, len(y) - 2))
    meat = score_vectors.T @ score_vectors / len(y)
    for lag in range(1, lags + 1):
        kernel_weight = 1.0 - lag / (lags + 1.0)
        gamma = score_vectors[lag:].T @ score_vectors[:-lag] / len(y)
        meat += kernel_weight * (gamma + gamma.T)
    covariance = bread_inv @ meat @ bread_inv / len(y)
    se_phi = float(np.sqrt(max(covariance[1, 1], 0.0)))
    zcrit = float(norm.ppf(0.5 + cfg.ar_confidence / 2.0))
    phi = float(beta[1])
    ci_low = phi - zcrit * se_phi
    ci_high = phi + zcrit * se_phi
    half_life = float(-np.log(2.0) / np.log(phi)) if 0.0 < phi < 1.0 else float("inf")

    reasons: list[str] = []
    if not converged:
        reasons.append("AR1_IRLS_NOT_CONVERGED")
    if phi <= cfg.min_phi:
        reasons.append("PHI_NOT_POSITIVE")
    if phi >= cfg.max_phi:
        reasons.append("PHI_AT_OR_ABOVE_LIMIT")
    if ci_high >= 1.0:
        reasons.append("PHI_UPPER_CI_NOT_BELOW_ONE")
    if not cfg.min_half_life <= half_life <= cfg.max_half_life:
        reasons.append("HALF_LIFE_OUTSIDE_ALLOWED_RANGE")

    return AR1Estimate(
        intercept=float(beta[0]),
        phi=phi,
        standard_error=se_phi,
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        half_life=half_life,
        observations=int(len(y)),
        hac_lags=lags,
        converged=converged,
        gate_passed=not reasons,
        gate_reasons=tuple(reasons),
    )


class RobustLocalLinearTrend:
    """Fold-safe estimator for ``price = local trend + transient residual``.

    ``fit`` selects variances and estimates the residual AR(1) on training data.
    ``filter`` freezes every fitted parameter and processes test observations in
    timestamp order.  Signals may therefore be acted on only at the next bar.
    """

    def __init__(self, config: LocalTrendConfig  None = None):
        self.config = config or LocalTrendConfig()
        self.fit_summary_: ModelFitSummary  None = None
        self.training_filter_: pd.DataFrame  None = None
        self._terminal_state: np.ndarray  None = None
        self._terminal_covariance: np.ndarray  None = None
        self._terminal_innovations: np.ndarray  None = None
        self._fitted = False

    @staticmethod
    def _coerce_prices(data: pd.DataFrame  pd.Series) -> pd.Series:
        if isinstance(data, pd.Series):
            prices = data.copy()
        elif "close" in data.columns:
            prices = data["close"].copy()
        else:
            raise ValueError("data must be a Series or contain a 'close' column")
        prices = pd.to_numeric(prices, errors="coerce").astype(float)
        if prices.index.has_duplicates:
            raise ValueError("price index contains duplicate timestamps")
        if not prices.index.is_monotonic_increasing:
            raise ValueError("price index must be monotonically increasing")
        if prices.isna().any() or not np.isfinite(prices.to_numpy()).all():
            raise ValueError("prices must be finite and cannot contain missing values")
        return prices

    def _transform(self, prices: np.ndarray) -> np.ndarray:
        if self.config.transform == "log":
            if np.any(prices <= 0):
                raise ValueError("log transform requires strictly positive prices")
            return np.log(prices)
        return prices.copy()

    def _inverse(self, values: np.ndarray) -> np.ndarray:
        return np.exp(values) if self.config.transform == "log" else values.copy()

    def _initial_state(self, first_value: float, observation_variance: float) -> tuple[np.ndarray, np.ndarray]:
        state = np.array([first_value, 0.0], dtype=float)
        covariance = np.diag([observation_variance * 10.0, observation_variance]).astype(float)
        return state, covariance

    def _run_filter(
        self,
        values: np.ndarray,
        state: np.ndarray,
        covariance: np.ndarray,
        observation_variance: float,
        process_level_variance: float,
        process_slope_variance: float,
    ) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray, float]:
        n = len(values)
        predicted_level = np.empty(n)
        filtered_level = np.empty(n)
        filtered_slope = np.empty(n)
        residual = np.empty(n)
        innovation = np.empty(n)
        innovation_std = np.empty(n)
        huber_weight = np.empty(n)
        score = np.empty(n)

        transition = np.array([[1.0, 1.0], [0.0, 1.0]])
        observation = np.array([1.0, 0.0])
        process_covariance = np.diag([process_level_variance, process_slope_variance])
        identity = np.eye(2)

        for i, value in enumerate(values):
            predicted_state = transition @ state
            predicted_covariance = transition @ covariance @ transition.T + process_covariance
            predicted_level[i] = predicted_state[0]
            raw_innovation = value - predicted_state[0]
            base_s = float(observation @ predicted_covariance @ observation + observation_variance)
            base_s = max(base_s, self.config.variance_floor)
            raw_z = raw_innovation / np.sqrt(base_s)
            weight = min(1.0, self.config.huber_c / max(abs(raw_z), 1e-12))
            effective_r = observation_variance / max(weight * weight, 1e-12)
            effective_s = float(observation @ predicted_covariance @ observation + effective_r)
            gain = (predicted_covariance @ observation) / max(effective_s, self.config.variance_floor)
            state = predicted_state + gain * raw_innovation
            # Joseph form protects positive semi-definiteness under robust R inflation.
            kh = np.outer(gain, observation)
            covariance = (
                (identity - kh) @ predicted_covariance @ (identity - kh).T
                + np.outer(gain, gain) * effective_r
            )
            covariance = 0.5 * (covariance + covariance.T)

            filtered_level[i] = state[0]
            filtered_slope[i] = state[1]
            residual[i] = value - state[0]
            innovation[i] = raw_innovation
            innovation_std[i] = raw_innovation / np.sqrt(effective_s)
            huber_weight[i] = weight
            score[i] = np.log(max(effective_s, self.config.variance_floor)) + 2.0 * _huber_loss(raw_z, self.config.huber_c)

        result = {
            "predicted_level": predicted_level,
            "filtered_level": filtered_level,
            "filtered_slope": filtered_slope,
            "residual": residual,
            "innovation": innovation,
            "innovation_std": innovation_std,
            "huber_weight": huber_weight,
            "robust_score": score,
        }
        burn = min(self.config.score_burn_in, max(0, n - 1))
        mean_score = float(np.mean(score[burn:]))
        return result, state, covariance, mean_score

    def _format_output(
        self,
        raw: dict[str, np.ndarray],
        prices: pd.Series,
        residual_scale: float,
        innovation_scale: float,
        ar_gate: bool,
        innovation_prefix: np.ndarray  None = None,
    ) -> pd.DataFrame:
        level_price = self._inverse(raw["filtered_level"])
        predicted_price = self._inverse(raw["predicted_level"])
        z_residual = raw["residual"] / residual_scale
        prefix = (
            np.asarray(innovation_prefix, dtype=float)
            if innovation_prefix is not None
            else np.empty(0, dtype=float)
        )
        combined_innovation = np.concatenate([prefix, raw["innovation"]])
        rolling_combined = (
            pd.Series(combined_innovation)
            .rolling(
                self.config.structural_scale_window,
                min_periods=self.config.structural_scale_min_periods,
            )
            .apply(lambda x: _mad_scale(np.asarray(x), self.config.variance_floor**0.5), raw=False)
        )
        rolling_scale = pd.Series(
            rolling_combined.to_numpy()[-len(prices) :], index=prices.index
        )
        scale_ratio = rolling_scale / innovation_scale
        break_by_jump = np.abs(raw["innovation"] / innovation_scale) >= self.config.structural_break_z
        break_by_scale = scale_ratio >= self.config.structural_scale_multiplier
        structural_break = break_by_jump  break_by_scale.fillna(False).to_numpy()

        return pd.DataFrame(
            {
                "close": prices.to_numpy(dtype=float),
                "predicted_level": raw["predicted_level"],
                "level": raw["filtered_level"],
                "slope": raw["filtered_slope"],
                "predicted_level_price": predicted_price,
                "level_price": level_price,
                "residual": raw["residual"],
                "residual_scale": residual_scale,
                "z_residual": z_residual,
                "innovation": raw["innovation"],
                "innovation_z": raw["innovation"] / innovation_scale,
                "huber_weight": raw["huber_weight"],
                "rolling_innovation_scale": rolling_scale.to_numpy(),
                "structural_scale_ratio": scale_ratio.to_numpy(),
                "structural_break": structural_break.astype(bool),
                "phi_gate_passed": bool(ar_gate),
            },
            index=prices.index,
        )

    def fit(self, train: pd.DataFrame  pd.Series) -> "RobustLocalLinearTrend":
        prices = self._coerce_prices(train)
        if len(prices) < self.config.min_train_observations:
            raise ValueError(
                f"training sample has {len(prices)} rows; "
                f"minimum is {self.config.min_train_observations}"
            )
        values = self._transform(prices.to_numpy())
        diff_scale = _mad_scale(np.diff(values), self.config.variance_floor**0.5)
        observation_variance = max(0.5 * diff_scale * diff_scale, self.config.variance_floor)

        candidates: list[tuple[float, float, float, dict[str, np.ndarray], np.ndarray, np.ndarray]] = []
        for level_ratio in self.config.level_q_ratios:
            for slope_ratio in self.config.slope_q_ratios:
                q_level = observation_variance * level_ratio
                q_slope = observation_variance * slope_ratio
                state, covariance = self._initial_state(values[0], observation_variance)
                raw, state, covariance, score = self._run_filter(
                    values,
                    state,
                    covariance,
                    observation_variance,
                    q_level,
                    q_slope,
                )
                candidates.append((score, level_ratio, slope_ratio, raw, state, covariance))

        score, level_ratio, slope_ratio, raw, terminal_state, terminal_covariance = min(
            candidates, key=lambda item: (item[0], item[1], item[2])
        )
        residual_tail = raw["residual"][self.config.ar_burn_in :]
        residual_scale = _mad_scale(residual_tail, self.config.variance_floor**0.5)
        innovation_scale = _mad_scale(raw["innovation"][self.config.ar_burn_in :], self.config.variance_floor**0.5)
        ar1 = _huber_ar1(residual_tail, self.config)
        self.fit_summary_ = ModelFitSummary(
            transform=self.config.transform,
            observations=len(prices),
            selected_level_q_ratio=float(level_ratio),
            selected_slope_q_ratio=float(slope_ratio),
            observation_variance=observation_variance,
            process_level_variance=observation_variance * level_ratio,
            process_slope_variance=observation_variance * slope_ratio,
            robust_forecast_score=score,
            residual_scale=residual_scale,
            innovation_scale=innovation_scale,
            ar1=ar1,
        )
        self._terminal_state = terminal_state.copy()
        self._terminal_covariance = terminal_covariance.copy()
        prefix_length = max(0, self.config.structural_scale_window - 1)
        self._terminal_innovations = raw["innovation"][-prefix_length:].copy()
        self.training_filter_ = self._format_output(
            raw, prices, residual_scale, innovation_scale, ar1.gate_passed
        )
        self._fitted = True
        return self

    def filter(
        self,
        test: pd.DataFrame  pd.Series,
        warmup: pd.DataFrame  pd.Series  None = None,
    ) -> pd.DataFrame:
        """Causally filter a test fold with every estimated parameter frozen.

        With no ``warmup``, the terminal state of the fitted training fold is
        used.  A supplied warmup must end before the test starts; it is used to
        initialise a fresh state and is never returned or scored.
        """

        if not self._fitted or self.fit_summary_ is None:
            raise RuntimeError("fit must be called before filter")
        test_prices = self._coerce_prices(test)
        if test_prices.empty:
            raise ValueError("test sample cannot be empty")
        summary = self.fit_summary_

        if warmup is None:
            assert self._terminal_state is not None and self._terminal_covariance is not None
            state = self._terminal_state.copy()
            covariance = self._terminal_covariance.copy()
            innovation_prefix = self._terminal_innovations
        else:
            warmup_prices = self._coerce_prices(warmup)
            if warmup_prices.empty:
                raise ValueError("warmup sample cannot be empty")
            if warmup_prices.index[-1] >= test_prices.index[0]:
                raise ValueError("warmup must end strictly before the first test timestamp")
            warmup_values = self._transform(warmup_prices.to_numpy())
            state, covariance = self._initial_state(warmup_values[0], summary.observation_variance)
            warmup_raw, state, covariance, _ = self._run_filter(
                warmup_values,
                state,
                covariance,
                summary.observation_variance,
                summary.process_level_variance,
                summary.process_slope_variance,
            )
            prefix_length = max(0, self.config.structural_scale_window - 1)
            innovation_prefix = warmup_raw["innovation"][-prefix_length:]

        values = self._transform(test_prices.to_numpy())
        raw, _, _, _ = self._run_filter(
            values,
            state,
            covariance,
            summary.observation_variance,
            summary.process_level_variance,
            summary.process_slope_variance,
        )
        return self._format_output(
            raw,
            test_prices,
            summary.residual_scale,
            summary.innovation_scale,
            summary.ar1.gate_passed,
            innovation_prefix=innovation_prefix,
        )

    def fit_transform(self, train: pd.DataFrame  pd.Series) -> pd.DataFrame:
        self.fit(train)
        assert self.training_filter_ is not None
        return self.training_filter_.copy()

    @property
    def ar1_(self) -> AR1Estimate:
        if self.fit_summary_ is None:
            raise RuntimeError("model has not been fitted")
        return self.fit_summary_.ar1

    def summary(self) -> dict[str, Any]:
        if self.fit_summary_ is None:
            raise RuntimeError("model has not been fitted")
        return self.fit_summary_.to_dict()
