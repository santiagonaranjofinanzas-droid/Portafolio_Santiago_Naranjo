"""Reproducible diagnostic for the preregistered H18 institutional overlay.

Historical output is explicitly non-approving because the development sample
was already consumed.  Only future holdout/forward evidence can unlock live.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.trend_v2 import (
    SlowTrendConfig,
    build_slow_trend_features,
    generate_slow_trend_signals,
)
from NAS100_RESEARCH_V2.validation.metrics import block_bootstrap, deflated_sharpe_ratio

from .h18_portfolio_backtest import run_h18_portfolio_backtest
from .institutional import InstitutionalRiskPolicy, InstrumentSpec


CONFIGS = {
    6001: SlowTrendConfig(momentum_horizons_h1=(12, 24, 48)),
    6002: SlowTrendConfig(momentum_horizons_h1=(24, 48, 96)),
}


def _pf(values: np.ndarray) -> float:
    gains = values[values > 0].sum()
    losses = -values[values < 0].sum()
    return float(gains / losses) if losses > 0 else float("inf") if gains > 0 else 0.0


def evaluate(bars: pd.DataFrame) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    required = {"open", "high", "low", "close"}
    if required.difference(bars.columns):
        raise ValueError("bars require open/high/low/close")
    signals = {
        magic: generate_slow_trend_signals(build_slow_trend_features(bars, cfg), cfg)
        for magic, cfg in CONFIGS.items()
    }
    if "axi_spread_profile" in bars.columns:
        for frame in signals.values():
            frame["spread_price"] = bars["axi_spread_profile"].to_numpy(float)
    policy = InstitutionalRiskPolicy()
    spec = InstrumentSpec("NAS100.fs", 0.01, 0.20, 0.01, 10.0, 0.01, 1_000.0)
    result = run_h18_portfolio_backtest(signals, policy=policy, spec=spec)
    daily_pnl = result.equity.resample("1D").last().ffill().diff().dropna().to_numpy(float)
    daily_returns = result.equity.resample("1D").last().ffill().pct_change().dropna().to_numpy(float)
    robustness = block_bootstrap(daily_pnl, samples=10_000, block_size=5, seed=60012)
    dsr_probability, dsr_z = deflated_sharpe_ratio(daily_returns, trials=142)
    fold_pfs: list[float] = []
    if not result.trades.empty:
        ordered = result.trades.sort_values("exit_time")
        for chunk in np.array_split(ordered, 7):
            fold_pfs.append(_pf(chunk["net_pnl"].to_numpy(float)) if len(chunk) else 0.0)
    gates = {
        "profit_factor_ge_1_20": result.metrics["profit_factor"] >= 1.20,
        "drawdown_le_15pct": abs(result.metrics["max_drawdown_pct"]) <= 15.0,
        "daily_sharpe_ge_1": result.metrics["daily_sharpe"] >= 1.0,
        "dsr_ge_0_95": dsr_probability >= 0.95,
        "bootstrap_pf_p05_gt_1": robustness["pf_p05"] > 1.0,
        "bootstrap_expectancy_p05_gt_0": robustness["expectancy_p05"] > 0.0,
        "bootstrap_probability_positive_ge_95pct": robustness["probability_positive"] >= 0.95,
        "all_diagnostic_fold_pf_ge_1": bool(fold_pfs) and min(fold_pfs) >= 1.0,
    }
    report = {
        "policy": asdict(policy),
        "scope": "CONSUMED_DEVELOPMENT_HISTORY_DIAGNOSTIC_ONLY",
        "live_approval_allowed": False,
        "metrics": result.metrics,
        "bootstrap": robustness,
        "deflated_sharpe": {"trials": 142, "probability": dsr_probability, "z_stat": dsr_z},
        "chronological_trade_block_pf": fold_pfs,
        "diagnostic_gates": gates,
        "all_diagnostic_gates_passed": all(gates.values()),
        "status": "FUTURE_EVIDENCE_REQUIRED_LIVE_LOCKED",
    }
    return report, result.trades, result.risk_events


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    bars = pd.read_parquet(args.bars)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report, trades, events = evaluate(bars)
    (args.output_dir / "h18_institutional_risk_diagnostic.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    trades.to_csv(args.output_dir / "h18_institutional_risk_trades.csv", index=False)
    events.to_csv(args.output_dir / "h18_institutional_risk_events.csv", index=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
