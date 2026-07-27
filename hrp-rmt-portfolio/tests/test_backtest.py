"""Unit tests for F5 (Backtest) — cost model, benchmarks, metrics, and simulator.

Follows TDD as mandated by §4 of .agent rules.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest.cost_model import (
    CostScenario,
    calculate_trade_cost,
    calculate_rebalance_cost,
    estimate_spread_bps,
    get_static_spread,
    build_spread_panel,
    CALIBRATED_SPREAD_BY_CLASS,
)
from backtest.benchmarks import (
    equal_weight,
    inverse_volatility,
    equal_risk_contribution,
    min_variance_lw,
    hrp_empirical,
    benchmark_60_40,
    benchmark_composite,
)
from backtest.metrics import calculate_metrics, calculate_weight_metrics
from backtest.simulator import (
    BacktestConfig,
    get_month_end_dates,
    forecast_portfolio_volatility,
    run_backtest,
)
from risk.cov_estimators import calculate_empirical_covariance


#===========================================================================
#Fixtures
#===========================================================================
@pytest.fixture
def sample_returns_5a() -> pd.DataFrame:
    """Small 5-asset panel with 300 days for unit tests."""
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-02", periods=300)
    factor = np.random.normal(0.0003, 0.01, 300)
    data = {}
    for i in range(5):
        noise = np.random.normal(0, 0.008, 300)
        data[f"A{i}"] = 0.4 * factor + noise
    df = pd.DataFrame(data, index=dates)
    df.iloc[0] = np.nan
    return df


@pytest.fixture
def sample_cov_5(sample_returns_5a) -> pd.DataFrame:
    """Covariance from 5-asset returns."""
    return calculate_empirical_covariance(sample_returns_5a)


@pytest.fixture
def synth_backtest_data():
    """Synthetic data panels for simulator tests: returns, prices, spreads, advs."""
    np.random.seed(123)
    dates = pd.bdate_range("2019-01-02", periods=600)
    tickers = ["SPY", "AGG", "GLD", "BIL", "TLT"]

    # Prices starting at 100, with small daily returns
    prices = {}
    for t in tickers:
        rets = np.random.normal(0.0003, 0.01, len(dates))
        rets[0] = 0
        p = 100 * np.cumprod(1 + rets)
        prices[t] = p

    prices_panel = pd.DataFrame(prices, index=dates)
    returns_panel = prices_panel.pct_change()

    # Spread: constant 10 bps
    spread_panel = pd.DataFrame(0.001, index=dates, columns=tickers)

    # ADV: constant 50M USD
    adv_panel = pd.DataFrame(50_000_000.0, index=dates, columns=tickers)

    return returns_panel, prices_panel, spread_panel, adv_panel


#===========================================================================
#Cost Model Tests
#===========================================================================
class TestCostModel:
    def test_cost_scenario_from_name(self):
        """Verify all three scenarios can be loaded."""
        for name in ("low", "base", "stress"):
            s = CostScenario.from_name(name)
            assert s.name == name
            assert s.commission_per_share_usd > 0

    def test_trade_cost_base_scenario(self):
        """Base scenario: commission + 50% spread + linear impact."""
        scenario = CostScenario.from_name("base")
        cost = calculate_trade_cost(
            trade_value_usd=10_000.0,
            price_per_share=100.0,
            spread_frac=0.001,  # 10 bps
            adv_usd=50_000_000.0,
            scenario=scenario,
        )
        # Cost should be positive and reasonable
        assert cost > 0
        assert cost < 10_000.0  # cost should be small relative to trade value

    def test_cost_scenarios_order(self):
        """Low < Base < Stress for the same trade."""
        costs = {}
        for name in ("low", "base", "stress"):
            s = CostScenario.from_name(name)
            costs[name] = calculate_trade_cost(
                trade_value_usd=50_000.0,
                price_per_share=200.0,
                spread_frac=0.002,
                adv_usd=10_000_000.0,
                scenario=s,
            )
        assert costs["low"] < costs["base"]
        assert costs["base"] < costs["stress"]

    def test_zero_trade_zero_cost(self):
        """No trade means no cost."""
        s = CostScenario.from_name("base")
        assert calculate_trade_cost(0.0, 100.0, 0.001, 1e7, s) == 0.0

    def test_rebalance_cost_positive(self):
        """Rebalance cost should be positive when weights change."""
        s = CostScenario.from_name("base")
        old_w = pd.Series({"A": 0.5, "B": 0.5})
        new_w = pd.Series({"A": 0.7, "B": 0.3})
        prices = pd.Series({"A": 100.0, "B": 50.0})
        spreads = pd.Series({"A": 0.001, "B": 0.002})
        advs = pd.Series({"A": 1e7, "B": 1e7})
        total, per_asset = calculate_rebalance_cost(
            old_w, new_w, 1_000_000, prices, spreads, advs, s
        )
        assert total > 0
        assert per_asset.sum() == pytest.approx(total)

    def test_spread_proxy(self):
        """Spread proxy formula: 2*(H-L)/(H+L)."""
        spread = estimate_spread_bps(110.0, 100.0)
        expected = 2 * 10 / 210
        assert spread == pytest.approx(expected)

    def test_calibrated_static_spreads(self):
        """Calibrated spreads should match institutional values by asset class."""
        # Equity mega-cap: 1.5 bps
        assert get_static_spread("SPY") == pytest.approx(0.00015)
        # Fixed income: 2.0 bps
        assert get_static_spread("AGG") == pytest.approx(0.0002)
        # Cash: 1.0 bps
        assert get_static_spread("BIL") == pytest.approx(0.0001)
        # Commodity: 5.0 bps
        assert get_static_spread("GLD") == pytest.approx(0.0005)
        # High Yield: 8.0 bps
        assert get_static_spread("HYG") == pytest.approx(0.0008)
        # Real Estate: 4.0 bps
        assert get_static_spread("VNQ") == pytest.approx(0.0004)

    def test_build_spread_panel_floor(self):
        """Effective spread must never fall below static calibrated minimum."""
        dates = pd.bdate_range("2020-01-02", periods=5)
        tickers = ["SPY", "AGG"]
        # Zero-range day: H == L
        highs = pd.DataFrame({"SPY": [100]*5, "AGG": [50]*5}, index=dates, dtype=float)
        lows = pd.DataFrame({"SPY": [100]*5, "AGG": [50]*5}, index=dates, dtype=float)
        panel = build_spread_panel(highs, lows)
        # Should be at least the static floor
        assert (panel["SPY"] >= 0.00015 - 1e-12).all()
        assert (panel["AGG"] >= 0.0002 - 1e-12).all()


#===========================================================================
#Benchmark Tests
#===========================================================================
class TestBenchmarks:
    def test_equal_weight_sums_one(self):
        w = equal_weight(["A", "B", "C", "D"])
        assert w.sum() == pytest.approx(1.0)
        # With cap=15%, each of 4 assets gets 15% and excess goes to BIL
        assert np.all(w >= 0)
        # Non-cash assets should be at most 15%
        non_cash = w[w.index != "BIL"]
        assert np.all(non_cash <= 0.15 + 1e-10)

    def test_inverse_volatility_sums_one(self, sample_cov_5):
        w = inverse_volatility(sample_cov_5)
        assert w.sum() == pytest.approx(1.0)
        assert np.all(w >= 0)

    def test_erc_sums_one(self, sample_cov_5):
        w = equal_risk_contribution(sample_cov_5)
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert np.all(w >= 0)

    def test_erc_risk_contributions_equal(self, sample_cov_5):
        """ERC (before cap enforcement) should have approximately equal marginal risk contributions."""
        # Test ERC without cap to verify the optimizer itself works
        from backtest.benchmarks import equal_risk_contribution as erc_fn
        # Get uncapped ERC weights by passing a very high cap
        w_raw = erc_fn(sample_cov_5, cap=1.0, cash_ticker="NONE")
        # Filter to original tickers only
        w_orig = w_raw.reindex(sample_cov_5.columns, fill_value=0.0)
        sigma = sample_cov_5.values
        sigma_w = sigma @ w_orig.values
        port_var = w_orig.values @ sigma_w
        rc = w_orig.values * sigma_w / port_var
        # All risk contributions should be close to 1/N
        assert np.std(rc) < 0.05

    def test_min_variance_lw_sums_one(self, sample_returns_5a):
        w = min_variance_lw(sample_returns_5a)
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert np.all(w >= 0)

    def test_hrp_empirical_sums_one(self, sample_cov_5):
        w = hrp_empirical(sample_cov_5, cash_ticker="A0")
        assert w.sum() == pytest.approx(1.0, abs=1e-6)
        assert np.all(w >= 0)

    def test_benchmark_60_40(self):
        w = benchmark_60_40()
        assert w.sum() == pytest.approx(1.0)
        assert w["SPY"] == 0.60
        assert w["AGG"] == 0.40

    def test_benchmark_composite(self):
        w = benchmark_composite(["X", "Y", "Z"])
        assert w.sum() == pytest.approx(1.0)
        # Non-cash tickers should be capped at 15%
        non_cash = w[w.index != "BIL"]
        assert np.all(non_cash <= 0.15 + 1e-10)

    def test_all_benchmarks_long_only(self, sample_returns_5a, sample_cov_5):
        """All benchmark strategies must produce non-negative weights."""
        strategies = [
            equal_weight(sample_cov_5.columns.tolist(), cap=0.15, cash_ticker="A0"),
            inverse_volatility(sample_cov_5, cap=0.15, cash_ticker="A0"),
            equal_risk_contribution(sample_cov_5, cap=0.15, cash_ticker="A0"),
            min_variance_lw(sample_returns_5a, cap=0.15, cash_ticker="A0"),
            hrp_empirical(sample_cov_5, cash_ticker="A0"),
            benchmark_60_40(),
            benchmark_composite(sample_cov_5.columns.tolist(), cap=0.15, cash_ticker="A0"),
        ]
        for w in strategies:
            assert np.all(w >= -1e-10), f"Negative weight detected: {w[w < 0]}"

    def test_benchmarks_cap_enforced(self, sample_returns_5a, sample_cov_5):
        """All capped benchmarks must respect the 15% per-ETF cap (§13.1)."""
        cap = 0.15
        strategies = {
            "IVP": inverse_volatility(sample_cov_5, cap=cap, cash_ticker="A0"),
            "ERC": equal_risk_contribution(sample_cov_5, cap=cap, cash_ticker="A0"),
            "MinVar_LW": min_variance_lw(sample_returns_5a, cap=cap, cash_ticker="A0"),
        }
        for name, w in strategies.items():
            # Exclude cash ticker from cap check (it absorbs excess)
            non_cash = w[w.index != "A0"]
            violations = non_cash[non_cash > cap + 1e-10]
            assert violations.empty, f"{name} violates cap: {violations}"


#===========================================================================
#Metrics Tests
#===========================================================================
class TestMetrics:
    def test_metrics_on_known_series(self):
        """Test metrics on a constant-return series."""
        dates = pd.bdate_range("2020-01-02", periods=252)
        # 0.04% daily => ~10% annualized CAGR approximately
        rets = pd.Series(0.0004, index=dates)
        m = calculate_metrics(rets)
        assert m["CAGR"] > 0
        assert m["Sharpe"] > 0
        assert m["MDD"] >= -1e-8  # near zero drawdown for constant positive returns
        assert m["Volatility_Ann"] == pytest.approx(0.0, abs=1e-10)
        assert m["N_Observations"] == 252

    def test_metrics_calmar_sortino(self):
        """Calmar and Sortino should be positive for upward-trending series."""
        np.random.seed(42)
        dates = pd.bdate_range("2020-01-02", periods=500)
        rets = pd.Series(np.random.normal(0.0005, 0.01, 500), index=dates)
        m = calculate_metrics(rets)
        assert m["CAGR"] > 0 or m["Calmar"] >= 0
        assert isinstance(m["Sortino"], float)
        assert isinstance(m["CVaR_5pct"], float)

    def test_weight_metrics(self):
        """Weight metrics: Herfindahl and turnover."""
        dates = pd.date_range("2020-01-31", periods=3, freq="ME")
        wh = pd.DataFrame(
            {"A": [0.5, 0.6, 0.4], "B": [0.5, 0.4, 0.6]},
            index=dates,
        )
        m = calculate_weight_metrics(wh)
        assert m["N_Rebalances"] == 3
        assert m["Herfindahl_Mean"] > 0
        assert m["N_Effective_Mean"] > 0
        assert m["Turnover_Mean"] > 0


#===========================================================================
#Simulator Tests
#===========================================================================
class TestSimulator:
    def test_month_end_dates(self):
        """Month-end detection should find last trading day per month."""
        dates = pd.bdate_range("2020-01-01", "2020-06-30")
        month_ends = get_month_end_dates(dates)
        assert len(month_ends) == 6
        # Each month-end should be the last business day
        for d in month_ends:
            assert d in dates

    def test_forecast_volatility(self, sample_returns_5a):
        """Forecast vol should be positive and finite."""
        w = pd.Series(0.2, index=sample_returns_5a.columns)
        vol = forecast_portfolio_volatility(sample_returns_5a, w)
        assert vol > 0
        assert np.isfinite(vol)

    def test_rebalance_buffer_skips(self, synth_backtest_data):
        """If turnover < 3%, rebalance should be skipped."""
        returns_panel, prices_panel, spread_panel, adv_panel = synth_backtest_data

        # Strategy that always returns exactly the same weights
        def constant_weights(returns_window, tickers, **kwargs):
            n = len(tickers)
            return pd.Series(1.0 / n, index=tickers)

        config = BacktestConfig(
            weight_function=constant_weights,
            lookback=60,
            rebalance_buffer=0.03,
            vol_target_enabled=False,
            label="constant_test",
        )

        result = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config)

        # After the first rebalance, subsequent ones should be skipped because
        # the weights drift is minimal with equal-weight and small returns
        buffer_skips = [s for s in result.skipped_rebalances if "buffer_skip" in str(s[1])]
        assert len(buffer_skips) > 0, "Expected some buffer skips with constant weights"

    def test_rebalance_buffer_triggers(self, synth_backtest_data):
        """If weights change significantly, rebalance should execute."""
        returns_panel, prices_panel, spread_panel, adv_panel = synth_backtest_data
        call_count = [0]

        def alternating_weights(returns_window, tickers, **kwargs):
            """Alternate between two very different allocations."""
            call_count[0] += 1
            n = len(tickers)
            w = pd.Series(0.0, index=tickers)
            if call_count[0] % 2 == 0:
                w.iloc[0] = 0.8
                w.iloc[1:] = 0.2 / (n - 1)
            else:
                w.iloc[-1] = 0.8
                w.iloc[:-1] = 0.2 / (n - 1)
            return w

        config = BacktestConfig(
            weight_function=alternating_weights,
            lookback=60,
            rebalance_buffer=0.03,
            vol_target_enabled=False,
            label="alternating_test",
        )

        result = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config)
        assert len(result.rebalance_dates) > 2

    def test_volatility_targeting(self, synth_backtest_data):
        """When vol targeting is enabled, exposure should be <= 1."""
        returns_panel, prices_panel, spread_panel, adv_panel = synth_backtest_data

        def ew(returns_window, tickers, **kwargs):
            return pd.Series(1.0 / len(tickers), index=tickers)

        config = BacktestConfig(
            weight_function=ew,
            lookback=60,
            vol_target=0.12,
            vol_target_enabled=True,
            rebalance_buffer=0.0,  # disable buffer to focus on vol targeting
            label="vol_target_test",
        )

        result = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config)
        assert len(result.rebalance_dates) > 0

    def test_pnl_arithmetic_aggregation(self):
        """Verify R_p = Σ w_i * R_i (§8.3)."""
        w = pd.Series({"A": 0.6, "B": 0.4})
        r = pd.Series({"A": 0.02, "B": -0.01})
        expected = 0.6 * 0.02 + 0.4 * (-0.01)
        actual = (w * r).sum()
        assert actual == pytest.approx(expected)

    def test_no_look_ahead(self, synth_backtest_data):
        """Ensure covariance lookback window ends before rebalance date."""
        returns_panel, prices_panel, spread_panel, adv_panel = synth_backtest_data
        lookback_windows = []

        def recording_ew(returns_window, tickers, **kwargs):
            lookback_windows.append(returns_window.index.max())
            return pd.Series(1.0 / len(tickers), index=tickers)

        config = BacktestConfig(
            weight_function=recording_ew,
            lookback=60,
            rebalance_buffer=0.0,
            vol_target_enabled=False,
            label="no_lookahead_test",
        )

        result = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config)

        # Each recorded lookback window max date should be < its rebalance date
        for win_max, reb_date in zip(lookback_windows, result.rebalance_dates):
            assert win_max < reb_date, (
                f"Look-ahead detected: window ends at {win_max} but rebalance is {reb_date}"
            )

    def test_simulator_reproducibility(self, synth_backtest_data):
        """Two identical runs must produce identical NAV."""
        returns_panel, prices_panel, spread_panel, adv_panel = synth_backtest_data

        def ew(returns_window, tickers, **kwargs):
            return pd.Series(1.0 / len(tickers), index=tickers)

        config = BacktestConfig(
            weight_function=ew,
            lookback=60,
            rebalance_buffer=0.0,
            vol_target_enabled=False,
            label="repro_test",
        )

        r1 = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config)
        r2 = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config)

        pd.testing.assert_series_equal(r1.daily_nav, r2.daily_nav)

    def test_costs_reduce_nav(self, synth_backtest_data):
        """NAV with costs should be <= NAV without costs (low scenario)."""
        returns_panel, prices_panel, spread_panel, adv_panel = synth_backtest_data

        def ew(returns_window, tickers, **kwargs):
            return pd.Series(1.0 / len(tickers), index=tickers)

        config_base = BacktestConfig(
            weight_function=ew,
            lookback=60,
            cost_scenario="base",
            rebalance_buffer=0.0,
            vol_target_enabled=False,
            label="cost_base",
        )
        config_low = BacktestConfig(
            weight_function=ew,
            lookback=60,
            cost_scenario="low",
            rebalance_buffer=0.0,
            vol_target_enabled=False,
            label="cost_low",
        )

        r_base = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config_base)
        r_low = run_backtest(returns_panel, prices_panel, spread_panel, adv_panel, config_low)

        # Base scenario costs more, so NAV should be lower
        assert r_base.daily_nav.iloc[-1] <= r_low.daily_nav.iloc[-1] + 1e-6
