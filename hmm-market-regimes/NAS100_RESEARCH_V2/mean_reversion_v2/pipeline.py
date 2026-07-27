"""High-level fold API for integrating MR V2 into nested validation."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .backtest import BacktestResult, run_mean_reversion_backtest
from .config import MeanReversionV2Config
from .falsification import FalsificationReport, build_falsification_report
from .model import RobustLocalLinearTrend
from .signals import SignalGenerationResult, generate_reentry_signals


@dataclass(frozen=True)
class FoldEvaluation:
    filtered: pd.DataFrame
    signals: SignalGenerationResult
    backtest: BacktestResult
    falsification: FalsificationReport


class MeanReversionV2:
    """Orchestrator whose learned state is scoped to exactly one train fold."""

    def __init__(self, config: MeanReversionV2Config  None = None):
        self.config = config or MeanReversionV2Config()
        self.model = RobustLocalLinearTrend(self.config.model)

    def fit(self, train: pd.DataFrame  pd.Series) -> "MeanReversionV2":
        self.model.fit(train)
        return self

    def filter(
        self,
        test: pd.DataFrame  pd.Series,
        warmup: pd.DataFrame  pd.Series  None = None,
    ) -> pd.DataFrame:
        filtered = self.model.filter(test, warmup=warmup)
        # Execution observables are not model features, but preserving them
        # lets the signal cost gate use the contemporaneous broker spread.
        if isinstance(test, pd.DataFrame):
            for column in ("spread_price", "spread_median", "spread"):
                if column in test.columns:
                    filtered[column] = test[column].to_numpy()
        return filtered

    def generate(self, filtered: pd.DataFrame) -> SignalGenerationResult:
        return generate_reentry_signals(
            filtered,
            self.config.signal,
            self.config.backtest.costs,
            self.model.ar1_,
            model_transform=self.config.model.transform,
        )

    def backtest(self, bars: pd.DataFrame, signals: pd.DataFrame) -> BacktestResult:
        return run_mean_reversion_backtest(bars, signals, self.config.backtest)

    def falsify(self, bars: pd.DataFrame, filtered: pd.DataFrame) -> FalsificationReport:
        return build_falsification_report(
            self.model,
            bars,
            filtered,
            self.config.signal,
            self.config.backtest.costs,
            self.config.falsification,
        )

    def evaluate_fold(
        self,
        train: pd.DataFrame,
        test: pd.DataFrame,
        warmup: pd.DataFrame  None = None,
    ) -> FoldEvaluation:
        self.fit(train)
        filtered = self.filter(test, warmup=warmup)
        generated = self.generate(filtered)
        backtest = self.backtest(test, generated.frame)
        report = self.falsify(test, filtered)
        return FoldEvaluation(filtered, generated, backtest, report)
