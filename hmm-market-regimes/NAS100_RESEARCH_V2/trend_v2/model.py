"""Fold-safe end-to-end API for Trend V2."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import numpy as np
import pandas as pd

from .backtest import BacktestResult, run_bar_backtest
from .config import BacktestConfig, TrendV2Config
from .features import REGIME_FEATURES, build_causal_features
from .regime import STATE_NAMES, StickyStudentTHMM, default_regime_feature_frame
from .signals import (
    SignalState,
    generate_momentum_benchmarks,
    generate_trend_signals,
)


class TrendV2Model:
    """Train/filter/signal facade intended for rolling and nested validation.

    Typical fold use::

        model = TrendV2Model().fit(train_bars)
        transformed = model.transform(test_bars)
        signals = model.generate_signals(transformed)

    ``transform`` uses the saved tail of the train fold only to warm up rolling
    features. HMM filtering starts from the last train filtered probability and
    never performs an OOS backward pass.
    """

    def __init__(self, config: TrendV2Config  None = None) -> None:
        self.config = config or TrendV2Config()
        self.regime_model = StickyStudentTHMM(self.config.regime)
        self.training_features_: pd.DataFrame  None = None
        self.training_transform_: pd.DataFrame  None = None
        self._training_context: pd.DataFrame  None = None
        self._default_oos_signal_state: SignalState  None = None

    @property
    def is_fitted(self) -> bool:
        return self.regime_model.is_fitted

    @staticmethod
    def _attach_probabilities(
        features: pd.DataFrame,
        probabilities: pd.DataFrame,
    ) -> pd.DataFrame:
        out = features.copy()
        for column in probabilities.columns:
            out[column] = probabilities[column]
        probability_columns = ["p_trendable", "p_range", "p_shock"]
        values = out[probability_columns].to_numpy(dtype=float)
        valid = np.isfinite(values).all(axis=1)
        state = np.full(len(out), "UNAVAILABLE", dtype=object)
        state[valid] = np.asarray(STATE_NAMES, dtype=object)[np.argmax(values[valid], axis=1)]
        out["filtered_regime"] = state
        return out

    def fit(self, train_bars: pd.DataFrame) -> "TrendV2Model":
        """Fit every learned quantity on ``train_bars`` only."""

        features = build_causal_features(train_bars, self.config.features)
        valid = features["feature_valid"].astype(bool)
        regime_features = default_regime_feature_frame(features.loc[valid])
        self.regime_model.fit(regime_features)
        probabilities = pd.DataFrame(
            np.nan,
            index=features.index,
            columns=["p_trendable", "p_range", "p_shock"],
            dtype=float,
        )
        assert self.regime_model.training_filtered_probabilities_ is not None
        probabilities.loc[valid, :] = self.regime_model.training_filtered_probabilities_.to_numpy()
        transformed = self._attach_probabilities(features, probabilities)
        self.training_features_ = features
        self.training_transform_ = transformed
        context_length = min(len(train_bars), self.config.features.context_bars)
        self._training_context = train_bars.iloc[-context_length:].copy()

        last = transformed.loc[valid].iloc[-1]
        training_active = bool(
            last["filtered_regime"] == "TRENDABLE"
            and last["p_trendable"] >= self.config.signals.trend_probability
            and last["p_shock"] <= self.config.signals.maximum_shock_probability
        )
        # If the transition happened in train, it is already consumed at the OOS
        # boundary. This prevents an artificial first-bar fold entry.
        self._default_oos_signal_state = SignalState(
            active_episode=training_active,
            confirmation_count=self.config.signals.confirmation_bars if training_active else 0,
            episode_consumed=training_active,
            logical_position=0,
        )
        return self

    def transform(
        self,
        test_bars: pd.DataFrame,
        context: pd.DataFrame  None = None,
        initial_probability: np.ndarray  None = None,
    ) -> pd.DataFrame:
        """Build causal OOS features and return filtered state probabilities.

        ``context`` is a feature warm-up prefix and is never returned or fitted.
        By default the train tail captured by :meth:`fit` is used. It must end
        before the first test observation.
        """

        if not self.is_fitted or self._training_context is None:
            raise RuntimeError("TrendV2Model must be fitted before transform")
        prefix = self._training_context if context is None else context
        prefix = prefix.iloc[-self.config.features.context_bars :].copy()
        if len(test_bars) == 0:
            return build_causal_features(test_bars, self.config.features)
        if len(prefix) and set(prefix.index).intersection(test_bars.index):
            raise ValueError("context and test indices must not overlap")
        combined = pd.concat([prefix, test_bars], axis=0)
        if not combined.index.is_monotonic_increasing:
            raise ValueError("context must precede test_bars chronologically")
        combined_features = build_causal_features(combined, self.config.features)
        features = combined_features.iloc[len(prefix) :].copy()
        features.index = test_bars.index
        valid = features["feature_valid"].astype(bool)
        probabilities = pd.DataFrame(
            np.nan,
            index=features.index,
            columns=["p_trendable", "p_range", "p_shock"],
            dtype=float,
        )
        if valid.any():
            selected = default_regime_feature_frame(features.loc[valid])
            initial = (
                self.regime_model.last_filtered_probability_
                if initial_probability is None
                else np.asarray(initial_probability, dtype=float)
            )
            filtered = self.regime_model.filter(selected, initial_probability=initial)
            probabilities.loc[valid, :] = filtered.to_numpy()
            probabilities.attrs["last_filtered_probability"] = filtered.iloc[-1].to_numpy()
        out = self._attach_probabilities(features, probabilities)
        out.attrs["initial_signal_state"] = self._default_oos_signal_state
        if valid.any():
            out.attrs["last_filtered_probability"] = probabilities.loc[valid].iloc[-1].to_numpy()
        return out

    def filter(
        self,
        test_bars: pd.DataFrame,
        context: pd.DataFrame  None = None,
        initial_probability: np.ndarray  None = None,
    ) -> pd.DataFrame:
        """Alias for :meth:`transform`, emphasizing causal filtered inference."""

        return self.transform(test_bars, context, initial_probability)

    def generate_signals(
        self,
        transformed: pd.DataFrame,
        initial_state: SignalState  None = None,
    ) -> pd.DataFrame:
        if initial_state is None:
            initial_state = transformed.attrs.get(
                "initial_signal_state", self._default_oos_signal_state
            )
        return generate_trend_signals(transformed, self.config.signals, initial_state)

    def generate_benchmarks(self, features: pd.DataFrame) -> dict[str, pd.DataFrame]:
        return generate_momentum_benchmarks(
            features, threshold=self.config.signals.momentum_threshold
        )

    def backtest(
        self,
        signals: pd.DataFrame,
        config: BacktestConfig  None = None,
    ) -> BacktestResult:
        return run_bar_backtest(signals, config)

    def diagnostics(self) -> dict[str, Any]:
        return {
            "component": "TrendV2Model",
            "causal_inference": True,
            "oos_probabilities": "filtered_not_smoothed",
            "regime_controls_direction": False,
            "configuration": asdict(self.config),
            "regime": self.regime_model.diagnostics(),
            "regime_features": list(REGIME_FEATURES),
        }
