from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.deployment.h18_mt5_parity import (
    H18_BY_MAGIC,
    aggregate_mt5_deals,
    compare_h18_decisions,
    compare_h18_risk_decisions,
    python_h18_decisions,
    replay_mt5_risk_inputs,
)


def _bars(n: int = 900) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=n, freq="15min", tz="UTC")
    x = np.arange(n, dtype=float)
    close = 10_000.0 * np.exp(0.00008 * x + 0.001 * np.sin(x / 11.0))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame(
        {
            "open": open_,
            "high": np.maximum(open_, close) + 1.0,
            "low": np.minimum(open_, close) - 1.0,
            "close": close,
        },
        index=index,
    )


def test_frozen_magic_mapping_and_comparator_self_check():
    assert H18_BY_MAGIC[6001]["momentum_horizons_h1"] == (12, 24, 48)
    assert H18_BY_MAGIC[6002]["momentum_horizons_h1"] == (24, 48, 96)
    expected = python_h18_decisions(
        _bars(), magic=6001, start_utc="2025-01-06T00:00:00Z"
    )
    assert len(expected) > 20
    result = compare_h18_decisions(expected, expected.copy())
    assert result["approved"]
    altered = expected.copy()
    altered.loc[0, "score"] += 1e-4
    assert not compare_h18_decisions(expected, altered)["approved"]


def test_mt5_deal_ledger_aggregates_to_trade(tmp_path: Path):
    path = tmp_path / "deals.csv"
    pd.DataFrame(
        [
            {
                "magic": 6001,
                "position_id": 77,
                "utc_time": "2026-07-13T10:00:00Z",
                "entry_type": 0,
                "deal_type": 0,
                "volume": 1.0,
                "price": 20_000.0,
                "profit": 0.0,
                "commission": -3.0,
                "swap": 0.0,
                "fee": 0.0,
            },
            {
                "magic": 6001,
                "position_id": 77,
                "utc_time": "2026-07-14T10:00:00Z",
                "entry_type": 1,
                "deal_type": 1,
                "volume": 1.0,
                "price": 20_100.0,
                "profit": 2_000.0,
                "commission": -3.0,
                "swap": -1.0,
                "fee": 0.0,
            },
        ]
    ).to_csv(path, index=False)
    trades = aggregate_mt5_deals(path, magic=6001)
    assert len(trades) == 1
    assert trades.iloc[0]["side"] == 1
    assert trades.iloc[0]["pnl"] == 1993.0


def test_ea_sources_lock_magic_and_demo_guard():
    root = Path(__file__).resolve().parents[1] / "mt5"
    ea_6001 = (root / "Experts" / "H18_TREND10_6001.mq5").read_text(encoding="utf-8")
    ea_6002 = (root / "Experts" / "H18_TREND11_6002.mq5").read_text(encoding="utf-8")
    core = (root / "Include" / "H18_SlowTrend_Core.mqh").read_text(encoding="utf-8")
    assert "const long H18_MAGIC=6001" in ea_6001
    assert "12,24,48,6.0" in ea_6001
    assert "const long H18_MAGIC=6002" in ea_6002
    assert "24,48,96,6.0" in ea_6002
    assert "trade_mode!=ACCOUNT_TRADE_MODE_DEMO" in core
    assert "margin_mode!=ACCOUNT_MARGIN_MODE_RETAIL_HEDGING" in core
    assert "PERIOD_M15" in core
    assert "InpTradingEnabled=false" in ea_6001
    assert "InpTradingEnabled=false" in ea_6002
    assert "m_logical_position" in core
    assert "FILE_COMMON" in core
    assert 'H18_Institutional_Risk.mqh' in core
    assert "m_risk.AuthorizeLong" in core
    assert "m_trade.OrderCheck" in core
    assert "decision.disaster_stop" in core
    assert "retcode!=TRADE_RETCODE_DONE" in core
    risk = (root / "Include" / "H18_Institutional_Risk.mqh").read_text(encoding="utf-8")
    assert "m_per_sleeve_risk=0.0025" in risk
    assert "m_aggregate_risk=0.0050" in risk
    assert "m_disaster_atr=8.0" in risk
    assert "BELOW_MINIMUM_SAFE_VOLUME" in risk


def test_risk_parity_requires_identical_authorizations_and_sizing():
    columns = {
        "magic": [6001], "approved": [1], "reason": ["APPROVED"],
        "volume": [0.12], "executive_stop": [19_700.0], "disaster_stop": [19_600.0],
        "requested_risk_cash": [250.0], "authorized_risk_cash": [96.0],
        "existing_portfolio_risk_cash": [0.0], "throttle": [1.0],
    }
    expected = pd.DataFrame(columns)
    assert compare_h18_risk_decisions(expected, expected.copy())["approved"]
    altered = expected.copy()
    altered.loc[0, "volume"] = 0.13
    assert not compare_h18_risk_decisions(expected, altered)["approved"]


def test_risk_log_can_be_independently_replayed(tmp_path: Path):
    path = tmp_path / "risk.csv"
    raw = {
        "magic": [6001], "approved": [1], "reason": ["APPROVED"],
        "volume": [0.04], "executive_stop": [19700.0], "disaster_stop": [19600.0],
        "requested_risk_cash": [250.0], "authorized_risk_cash": [320.0],
        "existing_portfolio_risk_cash": [0.0], "throttle": [1.0],
        "entry_price": [20000.0], "atr_h1": [50.0], "vol_h1": [0.005],
        "equity": [100000.0], "balance": [100000.0], "free_margin": [80000.0],
        "margin_level_pct": [800.0], "day_start_equity": [100000.0],
        "high_water_equity": [100000.0], "tick_size": [0.01], "tick_value": [0.20],
        "volume_min": [0.01], "volume_max": [10.0], "volume_step": [0.01],
        "margin_per_lot": [1000.0], "maximum_volume": [10.0],
    }
    pd.DataFrame(raw).to_csv(path, index=False)
    replay = replay_mt5_risk_inputs(path, magic=6001)
    # The independent formula is authoritative; the hand-written MQL row is intentionally wrong.
    assert replay.iloc[0]["approved"] == 1
    assert replay.iloc[0]["volume"] != raw["volume"][0]
    observed = pd.DataFrame(raw)
    assert not compare_h18_risk_decisions(replay, observed)["approved"]
