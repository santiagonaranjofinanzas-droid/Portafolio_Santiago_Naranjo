from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pandas as pd

from Capa_4.backtest_metrics import BacktestAssumptions
from Capa_4.tick_backtest import TickBacktestConfig, run_tick_backtest


def test_tick_costs_and_bid_ask() -> None:
    index = pd.date_range("2026-01-05 14:00:00", periods=4, freq="15min")
    signals = pd.DataFrame(
        {
            "Regime_Buffer_18": [1, 0, 0, 0],
            "ML_Master_Strength": [0.9, 0.0, 0.0, 0.0],
            "Vol_Projected_Sigma": [0.01, 0.01, 0.01, 0.01],
        },
        index=index,
    )
    with tempfile.TemporaryDirectory() as tmp:
        month = Path(tmp) / "year=2026" / "month=1"
        month.mkdir(parents=True)
        ticks = pd.DataFrame(
            {
                "timestamp": [index[1], index[1] + pd.Timedelta(minutes=1), index[1] + pd.Timedelta(minutes=2)],
                "bid": [100.50, 102.10, 103.00],
                "ask": [101.00, 102.60, 103.50],
            }
        )
        ticks.to_parquet(month / "ticks.parquet", index=False)
        cfg = BacktestAssumptions(
            initial_balance=10_000.0,
            risk_percent=1.0,
            min_strength=0.35,
            vol_multiplier=1.0,
            reward_risk=1.5,
            max_lot=10.0,
            point=0.01,
            tick_size=0.01,
            tick_value=0.20,
            spread_price=0.0,
            slippage_price=0.10,
            commission_per_lot=3.0,
            min_lot=0.01,
            lot_step=0.01,
        )
        trades, cashflows, _ = run_tick_backtest(signals, cfg, TickBacktestConfig(Path(tmp), max_holding_bars=2))
        assert len(trades) == 1
        assert trades.iloc[0]["entry_price"] == 101.10
        assert len(cashflows) >= 1
        assert trades.iloc[0]["pnl"] < 200.0, "slippage/commission were not deducted"


def test_release_is_fail_closed() -> None:
    decision = json.loads((Path(__file__).parent / "results" / "release_decision.json").read_text(encoding="utf-8"))
    assert decision["live_trading_locked"] is True
    assert decision["decisions"]["MEAN_REVERSION"] == "REJECTED"
    assert decision["decisions"]["TREND_FOLLOW"] == "REJECTED"
    assert decision["decisions"]["PORTFOLIO"] == "REJECTED"


if __name__ == "__main__":
    test_tick_costs_and_bid_ask()
    test_release_is_fail_closed()
    print("OK: NAS100 institutional self-test")
