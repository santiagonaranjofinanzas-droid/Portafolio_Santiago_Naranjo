"""Fail-closed adapters between research models and validation runners."""

from .adapters import MeanReversionFoldEvaluator, TrendFoldEvaluator

__all__ = ["MeanReversionFoldEvaluator", "TrendFoldEvaluator"]
