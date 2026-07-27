from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from backend.app.engine import calculate_stats


def _trades(count: int = 40, verified_r: bool = True) -> pd.DataFrame:
    start = datetime(2025, 1, 1)
    pnl = np.array([120.0, -80.0] * (count // 2))
    return pd.DataFrame(
        {
            "position_id": range(1, count + 1),
            "entrytime": [start + timedelta(days=i) for i in range(count)],
            "exittime": [start + timedelta(days=i, hours=1) for i in range(count)],
            "netpnl": pnl,
            "commission": [-1.0] * count,
            "valid_sl": [verified_r] * count,
            "r_multiple": ([1.2, -0.8] * (count // 2)) if verified_r else [None] * count,
            "mae_r": [-0.5] * count,
            "mfe_r": [1.0] * count,
        }
    )


def test_unverified_r_is_not_promoted_to_expectancy() -> None:
    result = calculate_stats(_trades(40, verified_r=False), 10_000.0, pd.DataFrame())
    assert result["summary"]["expectancy"] is None
    assert result["summary"]["sqn"] is None
    assert result["quant"]["verified_r_count"] == 0
    assert result["history"][0]["r_multiple_source"] == "estimated_loss_proxy"


def test_missing_capital_marks_relative_metrics_unavailable() -> None:
    result = calculate_stats(_trades(), None, pd.DataFrame())
    assert result["methodology"]["capital_verified"] is False
    assert result["summary"]["start_cap"] is None
    assert result["summary"]["total_return"] is None
    assert result["risk"]["var"] is None


def test_risk_confidence_and_significance_are_explicit() -> None:
    result = calculate_stats(_trades(), 10_000.0, pd.DataFrame())
    assert result["methodology"]["risk_confidence"] == 0.99
    assert result["quant"]["significance"] in {"High", "Moderate", "Low (Noise)"}
    assert 0.0 <= result["perf"]["optimal_risk_kelly"] <= 0.25


def test_equity_curve_starts_from_funded_capital() -> None:
    trades = _trades(2)
    funded_at = trades["entrytime"].min() - timedelta(days=3)

    result = calculate_stats(trades, 100_000.0, pd.DataFrame(), capital_start_time=funded_at)

    assert result["methodology"]["capital_verified"] is True
    assert result["summary"]["start_cap"] == 100_000.0
    assert result["equity_curve"][0]["equity"] == 100_000.0
    assert result["equity_curve"][-1]["equity"] == 100_040.0


def test_small_live_account_keeps_positive_funding_baseline() -> None:
    trades = _trades(2)

    result = calculate_stats(trades, 502.0, pd.DataFrame(), capital_start_time=trades["entrytime"].min())

    assert result["methodology"]["capital_verified"] is True
    assert result["equity_curve"][0]["equity"] == 502.0
    assert result["equity_curve"][-1]["equity"] == 542.0
