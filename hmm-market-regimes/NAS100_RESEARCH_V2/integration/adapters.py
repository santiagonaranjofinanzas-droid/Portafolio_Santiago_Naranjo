"""Causal fold evaluators for Trend V2, momentum benchmarks and MR V2."""

from __future__ import annotations

from dataclasses import asdict, replace

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.mean_reversion_v2 import (
    BacktestConfig as MRBacktestConfig,
    CostConfig as MRCostConfig,
    MeanReversionV2,
    MeanReversionV2Config,
    generate_reentry_signals,
)
from NAS100_RESEARCH_V2.trend_v2 import (
    BacktestConfig as TrendBacktestConfig,
    TrendV2Config,
    TrendV2Model,
    SignalState,
    build_causal_features,
    build_slow_trend_features,
    generate_momentum_benchmarks,
    generate_momentum_benchmark_signals,
    generate_slow_trend_signals,
    generate_trend_signals,
    run_bar_backtest,
)
from NAS100_RESEARCH_V2.validation.costs import CostScenario
from NAS100_RESEARCH_V2.validation.runner import CandidateSpec, FoldRun
from NAS100_RESEARCH_V2.validation.splits import OuterFold

from .contracts import (
    assert_prefix_invariant,
    config_digest,
    dataframe_fingerprint,
    normalize_trades,
    stable_data,
    strict_dataclass_override,
    validate_candidate,
    validate_fold_inputs,
    validate_next_open_trades,
)


def _scenario_spread(bars: pd.DataFrame, scenario: CostScenario, base_spread: float = 2.5) -> pd.DataFrame:
    result = bars.copy()
    if "axi_spread_profile" in result.columns:
        scale = scenario.spread_price / base_spread
        result["spread_price"] = result["axi_spread_profile"].to_numpy(float) * scale
    else:
        result["spread_price"] = float(scenario.spread_price)
    return result


class TrendFoldEvaluator:
    """Evaluate one preregistered Trend or momentum specification per fold."""

    def __init__(self, *, prefix_diagnostic: bool = True) -> None:
        self.prefix_diagnostic = prefix_diagnostic
        self._models: dict[str, TrendV2Model] = {}
        self._signals: dict[str, tuple[pd.DataFrame, dict]] = {}

    def __call__(
        self,
        train: pd.DataFrame,
        test: pd.DataFrame,
        candidate: CandidateSpec,
        costs: CostScenario,
        fold: OuterFold,
    ) -> FoldRun:
        validate_fold_inputs(train, test, fold)
        validate_candidate(candidate, allowed_top_level={"strategy", "model", "backtest"})
        strategy = candidate.parameters.get("strategy")
        if strategy not in {
            "trend_v2",
            "momentum_long_only",
            "momentum_short_only",
            "momentum_long_short",
            "slow_trend_long",
        }:
            raise ValueError(f"unknown Trend strategy: {strategy}")
        model_cfg = strict_dataclass_override(
            TrendV2Config(), candidate.parameters.get("model", {}), path="model"
        )
        bt_cfg = strict_dataclass_override(
            TrendBacktestConfig(
                fixed_units=None,
                target_annual_volatility=0.10,
                tick_size=0.01,
                tick_value=0.20,
                min_units=0.01,
                max_units=10.0,
                unit_step=0.01,
            ),
            candidate.parameters.get("backtest", {}),
            path="backtest",
        )
        train_key = dataframe_fingerprint(train)
        test_key = dataframe_fingerprint(test)
        signal_key = config_digest(
            {"train": train_key, "test": test_key, "strategy": strategy, "model": asdict(model_cfg)}
        )
        if signal_key not in self._signals:
            if strategy == "trend_v2":
                fit_key = config_digest(
                    {"train": train_key, "features": asdict(model_cfg.features), "regime": asdict(model_cfg.regime)}
                )
                model = self._models.get(fit_key)
                if model is None:
                    model = TrendV2Model(model_cfg).fit(train)
                    self._models[fit_key] = model
                transformed = model.transform(test)
                assert model.training_transform_ is not None
                valid_train = model.training_transform_["feature_valid"].astype(bool)
                last = model.training_transform_.loc[valid_train].iloc[-1]
                active = bool(
                    last["filtered_regime"] == "TRENDABLE"
                    and last["p_trendable"] >= model_cfg.signals.trend_probability
                    and last["p_shock"] <= model_cfg.signals.maximum_shock_probability
                )
                initial_state = SignalState(
                    active_episode=active,
                    confirmation_count=model_cfg.signals.confirmation_bars if active else 0,
                    episode_consumed=active,
                    logical_position=0,
                )
                signals = generate_trend_signals(transformed, model_cfg.signals, initial_state)
                diagnostics = model.diagnostics()
                diagnostics["candidate_signal_config"] = asdict(model_cfg.signals)
                regime = diagnostics["regime"]
                if not bool(regime.get("identified", False)):
                    raise RuntimeError("REGIME_IDENTIFICATION_FAILED")
                if self.prefix_diagnostic and len(test) >= 200:
                    prefix_n = max(100, len(test) // 2)
                    shorter = model.transform(test.iloc[:prefix_n])
                    assert_prefix_invariant(
                        transformed,
                        shorter,
                        columns=("momentum_score", "p_trendable", "p_range", "p_shock"),
                    )
            elif strategy == "slow_trend_long":
                context = train.iloc[-model_cfg.slow_trend.context_bars :]
                combined = pd.concat([context, test])
                full_features = build_slow_trend_features(combined, model_cfg.slow_trend)
                features = full_features.iloc[len(context) :].copy()
                features.index = test.index
                signals = generate_slow_trend_signals(features, model_cfg.slow_trend)
                diagnostics = {
                    "component": "h18_asymmetric_slow_trend",
                    "strategy": strategy,
                    "uses_regime_model": False,
                    "direction": "long_only",
                    "decision_clock": "completed_UTC_H1_only",
                    "execution_clock": "next_M15_open",
                    "universe_policy": "single_preregistered_tradable_NAS100.fs_no_constituent_selection",
                    "survivorship_scope": "index_CFD_history_not_surviving_equity_constituents",
                    "slow_trend_config": asdict(model_cfg.slow_trend),
                }
                if self.prefix_diagnostic and len(test) >= 200:
                    prefix_n = max(100, len(test) // 2)
                    shorter_combined = pd.concat([context, test.iloc[:prefix_n]])
                    shorter = build_slow_trend_features(
                        shorter_combined, model_cfg.slow_trend
                    ).iloc[len(context) :]
                    shorter.index = test.index[:prefix_n]
                    assert_prefix_invariant(
                        features,
                        shorter,
                        columns=("slow_momentum_score", "slow_atr_h1", "slow_vol_h1"),
                    )
            else:
                context = train.iloc[-model_cfg.features.context_bars :]
                combined = pd.concat([context, test])
                features = build_causal_features(combined, model_cfg.features).iloc[len(context) :]
                features.index = test.index
                if strategy == "momentum_short_only":
                    signals = generate_momentum_benchmark_signals(
                        features, threshold=model_cfg.signals.momentum_threshold, direction_mode="short"
                    )
                else:
                    signals = generate_momentum_benchmarks(
                        features, threshold=model_cfg.signals.momentum_threshold
                    )[strategy]
                diagnostics = {
                    "component": "time_series_momentum_benchmark",
                    "strategy": strategy,
                    "volatility_target": bt_cfg.target_annual_volatility,
                    "uses_regime_model": False,
                }
            self._signals[signal_key] = (signals, stable_data(diagnostics))
        signals, diagnostics = self._signals[signal_key]
        scenario_bars = _scenario_spread(signals, costs)
        scenario_cfg = replace(
            bt_cfg,
            spread_price=float(costs.spread_price),
            spread_column="spread_price",
            slippage_price=float(costs.slippage_price),
            commission_per_unit_per_side=float(costs.commission_per_lot_per_side),
        )
        backtest = run_bar_backtest(scenario_bars, scenario_cfg)
        if backtest.trades.empty:
            normalized = normalize_trades(backtest.trades)
        else:
            cash_before = backtest.trades["cash_after"] - backtest.trades["net_pnl"]
            normalized = normalize_trades(
                backtest.trades,
                return_pct=backtest.trades["net_pnl"].to_numpy(float)
                / cash_before.to_numpy(float)
                * 100.0,
            )
            validate_next_open_trades(
                normalized, signals, signal_column="entry_signal", side_encoding="numeric"
            )
        return FoldRun(
            normalized,
            {
                **diagnostics,
                "cost_scenario": stable_data(costs),
                "latency_modelled_at_bar_level": False,
                "backtest_metrics": stable_data(backtest.metrics),
            },
        )

    def training_run(
        self,
        bars: pd.DataFrame,
        candidate: CandidateSpec,
        costs: CostScenario,
    ) -> FoldRun:
        """Create a filtered in-training path used only for inner CPCV.

        Regime hyperparameters are fixed before this path is inspected.  CPCV
        therefore selects signal/execution variants, never the HMM by PnL.
        """

        from .contracts import validate_bars

        validate_bars(bars, label="inner training bars")
        validate_candidate(candidate, allowed_top_level={"strategy", "model", "backtest"})
        strategy = candidate.parameters.get("strategy")
        model_cfg = strict_dataclass_override(
            TrendV2Config(), candidate.parameters.get("model", {}), path="model"
        )
        bt_cfg = strict_dataclass_override(
            TrendBacktestConfig(
                fixed_units=None,
                target_annual_volatility=0.10,
                tick_size=0.01,
                tick_value=0.20,
                min_units=0.01,
                max_units=10.0,
                unit_step=0.01,
            ),
            candidate.parameters.get("backtest", {}),
            path="backtest",
        )
        data_key = dataframe_fingerprint(bars)
        key = config_digest(
            {"scope": "training", "data": data_key, "strategy": strategy, "model": asdict(model_cfg)}
        )
        if key not in self._signals:
            if strategy == "trend_v2":
                fit_key = config_digest(
                    {"train": data_key, "features": asdict(model_cfg.features), "regime": asdict(model_cfg.regime)}
                )
                model = self._models.get(fit_key)
                if model is None:
                    model = TrendV2Model(model_cfg).fit(bars)
                    self._models[fit_key] = model
                assert model.training_transform_ is not None
                signals = generate_trend_signals(
                    model.training_transform_, model_cfg.signals, SignalState()
                )
                diagnostics = model.diagnostics()
                diagnostics["candidate_signal_config"] = asdict(model_cfg.signals)
                if not bool(diagnostics["regime"].get("identified", False)):
                    raise RuntimeError("REGIME_IDENTIFICATION_FAILED")
            elif strategy == "slow_trend_long":
                features = build_slow_trend_features(bars, model_cfg.slow_trend)
                signals = generate_slow_trend_signals(features, model_cfg.slow_trend)
                diagnostics = {
                    "component": "h18_asymmetric_slow_trend",
                    "strategy": strategy,
                    "uses_regime_model": False,
                    "direction": "long_only",
                    "decision_clock": "completed_UTC_H1_only",
                    "execution_clock": "next_M15_open",
                    "universe_policy": "single_preregistered_tradable_NAS100.fs_no_constituent_selection",
                    "survivorship_scope": "index_CFD_history_not_surviving_equity_constituents",
                    "slow_trend_config": asdict(model_cfg.slow_trend),
                }
            elif strategy in {"momentum_long_only", "momentum_short_only", "momentum_long_short"}:
                features = build_causal_features(bars, model_cfg.features)
                if strategy == "momentum_short_only":
                    signals = generate_momentum_benchmark_signals(
                        features, threshold=model_cfg.signals.momentum_threshold, direction_mode="short"
                    )
                else:
                    signals = generate_momentum_benchmarks(
                        features, threshold=model_cfg.signals.momentum_threshold
                    )[strategy]
                diagnostics = {
                    "component": "time_series_momentum_benchmark",
                    "strategy": strategy,
                    "uses_regime_model": False,
                }
            else:
                raise ValueError(f"unknown Trend strategy: {strategy}")
            self._signals[key] = (signals, stable_data(diagnostics))
        signals, diagnostics = self._signals[key]
        scenario_bars = _scenario_spread(signals, costs)
        cfg = replace(
            bt_cfg,
            spread_price=float(costs.spread_price),
            spread_column="spread_price",
            slippage_price=float(costs.slippage_price),
            commission_per_unit_per_side=float(costs.commission_per_lot_per_side),
        )
        result = run_bar_backtest(scenario_bars, cfg)
        normalized = normalize_trades(
            result.trades,
            return_pct=(
                result.trades["net_pnl"].to_numpy(float)
                / (result.trades["cash_after"] - result.trades["net_pnl"]).to_numpy(float)
                * 100.0
                if not result.trades.empty
                else None
            ),
        )
        return FoldRun(normalized, {**diagnostics, "scope": "INNER_CPCV_TRAINING_PATH"})


class MeanReversionFoldEvaluator:
    """Evaluate residual MR with model/signals frozen across cost stresses."""

    def __init__(self, *, prefix_diagnostic: bool = True) -> None:
        self.prefix_diagnostic = prefix_diagnostic
        self._models: dict[str, MeanReversionV2] = {}
        self._signals: dict[str, tuple[pd.DataFrame, dict]] = {}

    def __call__(
        self,
        train: pd.DataFrame,
        test: pd.DataFrame,
        candidate: CandidateSpec,
        costs: CostScenario,
        fold: OuterFold,
    ) -> FoldRun:
        validate_fold_inputs(train, test, fold)
        validate_candidate(candidate, allowed_top_level={"model", "signal", "backtest"})
        cfg = strict_dataclass_override(
            MeanReversionV2Config(), candidate.parameters, path="mean_reversion"
        )
        train_key = dataframe_fingerprint(train)
        test_key = dataframe_fingerprint(test)
        fit_key = config_digest({"train": train_key, "model": asdict(cfg.model)})
        model = self._models.get(fit_key)
        if model is None:
            model = MeanReversionV2(cfg).fit(train)
            self._models[fit_key] = model
        signal_key = config_digest(
            {"fit": fit_key, "test": test_key, "signal": asdict(cfg.signal), "base_cost": asdict(cfg.backtest.costs)}
        )
        if signal_key not in self._signals:
            filtered = model.filter(test)
            generated = generate_reentry_signals(
                filtered,
                cfg.signal,
                cfg.backtest.costs,
                model.model.ar1_,
                model_transform=cfg.model.transform,
            )
            if self.prefix_diagnostic and len(test) >= 200:
                prefix_n = max(100, len(test) // 2)
                shorter = model.filter(test.iloc[:prefix_n])
                assert_prefix_invariant(filtered, shorter, columns=("residual", "z_residual"))
            diagnostics = {
                "component": "mean_reversion_v2",
                "model": model.model.summary(),
                "signal_events": stable_data(generated.events),
            }
            self._signals[signal_key] = (generated.frame, stable_data(diagnostics))
        signals, diagnostics = self._signals[signal_key]
        scenario_cost = replace(
            cfg.backtest.costs,
            spread_price=float(costs.spread_price),
            slippage_price_per_side=float(costs.slippage_price),
            commission_per_lot_per_side=float(costs.commission_per_lot_per_side),
        )
        scenario_cfg: MRBacktestConfig = replace(cfg.backtest, costs=scenario_cost)
        scenario_bars = _scenario_spread(test, costs)
        # Call the pure function so scenario costs cannot be shadowed by the
        # cached model facade's original backtest configuration.
        from NAS100_RESEARCH_V2.mean_reversion_v2 import run_mean_reversion_backtest

        backtest = run_mean_reversion_backtest(scenario_bars, signals, scenario_cfg)
        normalized = normalize_trades(
            backtest.trades,
            return_pct=(
                backtest.trades["return_on_entry_balance"].to_numpy(float) * 100.0
                if not backtest.trades.empty
                else None
            ),
        )
        if not normalized.empty:
            audit_signals = signals.copy()
            audit_signals["combined_signal"] = (
                audit_signals["mr_long_signal"].astype(int)
                - audit_signals["mr_short_signal"].astype(int)
            )
            validate_next_open_trades(
                normalized,
                audit_signals,
                signal_column="combined_signal",
                side_encoding="text",
            )
        return FoldRun(
            normalized,
            {
                **diagnostics,
                "cost_scenario": stable_data(costs),
                "latency_modelled_at_bar_level": False,
                "backtest_metrics": stable_data(backtest.metrics),
            },
        )

    def training_run(
        self,
        bars: pd.DataFrame,
        candidate: CandidateSpec,
        costs: CostScenario,
    ) -> FoldRun:
        from NAS100_RESEARCH_V2.mean_reversion_v2 import run_mean_reversion_backtest
        from .contracts import validate_bars

        validate_bars(bars, label="inner training bars")
        validate_candidate(candidate, allowed_top_level={"model", "signal", "backtest"})
        cfg = strict_dataclass_override(
            MeanReversionV2Config(), candidate.parameters, path="mean_reversion"
        )
        data_key = dataframe_fingerprint(bars)
        fit_key = config_digest({"train": data_key, "model": asdict(cfg.model)})
        model = self._models.get(fit_key)
        if model is None:
            model = MeanReversionV2(cfg).fit(bars)
            self._models[fit_key] = model
        assert model.model.training_filter_ is not None
        filtered = model.model.training_filter_.copy()
        generated = generate_reentry_signals(
            filtered,
            cfg.signal,
            cfg.backtest.costs,
            model.model.ar1_,
            model_transform=cfg.model.transform,
        )
        scenario_cost = replace(
            cfg.backtest.costs,
            spread_price=float(costs.spread_price),
            slippage_price_per_side=float(costs.slippage_price),
            commission_per_lot_per_side=float(costs.commission_per_lot_per_side),
        )
        scenario_cfg = replace(cfg.backtest, costs=scenario_cost)
        result = run_mean_reversion_backtest(
            _scenario_spread(bars, costs), generated.frame, scenario_cfg
        )
        normalized = normalize_trades(
            result.trades,
            return_pct=(
                result.trades["return_on_entry_balance"].to_numpy(float) * 100.0
                if not result.trades.empty
                else None
            ),
        )
        return FoldRun(
            normalized,
            {
                "component": "mean_reversion_v2",
                "scope": "INNER_CPCV_TRAINING_PATH",
                "model": stable_data(model.model.summary()),
                "signal_events": stable_data(generated.events),
            },
        )
