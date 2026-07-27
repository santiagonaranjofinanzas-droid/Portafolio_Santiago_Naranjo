"""Backtest simulator for HRP-RMT portfolio — Fase F5.

Implements the monthly rebalance loop with:
- Point-in-time data governance (§8)
- Cost model under Base scenario (§7)
- Rebalance buffer of 3% aggregate turnover (§18.2)
- Volatility targeting at 12% annualized with EMA smoothing (§18.3-18.4)
- Immediate reduction when σ_forecast > 18% (§18.5)
- PnL via arithmetic simple returns: R_p,t = Σ w_i,t-1 * R_i,t (§8.3)
- No look-ahead bias: all decisions use data available at t-1 (§8.1)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

import numpy as np
import pandas as pd

from backtest.cost_model import (
    CostScenario,
    calculate_rebalance_cost,
    build_spread_panel,
    get_static_spread,
)
from backtest.metrics import calculate_metrics, calculate_weight_metrics


#---------------------------------------------------------------------------
#Configuration
#---------------------------------------------------------------------------
@dataclass(frozen=True)
class BacktestConfig:
    """Immutable configuration for a backtest run."""

    # Strategy
    weight_function: Callable  # (returns_window, eligible_tickers, **kwargs) -> pd.Series
    weight_kwargs: dict = field(default_factory=dict)

    # Timing
    lookback: int = 252  # §14.2
    start_date: str  None = None
    end_date: str  None = None

    # Costs
    cost_scenario: str = "base"  # §7.2

    # Rebalance buffer (§18.2)
    rebalance_buffer: float = 0.03

    # Volatility targeting (§18.3)
    vol_target: float = 0.12  # 12% annualized
    vol_target_enabled: bool = True
    vol_smoothing_alpha: float = 0.33  # §18.4
    vol_emergency_threshold: float = 0.18  # §18.5

    # Portfolio
    initial_capital: float = 1_000_000.0
    cash_ticker: str = "BIL"

    # Label for reporting
    label: str = "HRP-RMT"


#---------------------------------------------------------------------------
#Result container
#---------------------------------------------------------------------------
@dataclass
class BacktestResult:
    """Container for backtest output."""

    daily_returns: pd.Series
    daily_nav: pd.Series
    weights_history: pd.DataFrame
    turnover_history: pd.Series
    cost_history: pd.Series
    rebalance_dates: list
    skipped_rebalances: list
    config: BacktestConfig
    metrics: dict = field(default_factory=dict)
    weight_metrics: dict = field(default_factory=dict)


#---------------------------------------------------------------------------
#Data loading helper
#---------------------------------------------------------------------------
def load_returns_panel(
    data_dir: str,
    tickers: list[str],
    price_col: str = "adjClose",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load price CSVs and build panels of returns, prices, highs, lows, volumes.

    Returns
    -------
    tuple of (returns_panel, prices_panel, spread_panel, adv_panel)
        All DataFrames indexed by date with tickers as columns.
    """
    import os

    all_prices = {}
    all_highs = {}
    all_lows = {}
    all_volumes = {}

    for ticker in tickers:
        fpath = os.path.join(data_dir, f"{ticker}.csv")
        if not os.path.exists(fpath):
            continue

        df = pd.read_csv(fpath, parse_dates=["date"])
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        df = df.set_index("date").sort_index()

        if price_col not in df.columns:
            continue

        all_prices[ticker] = df[price_col]
        if "adjHigh" in df.columns:
            all_highs[ticker] = df["adjHigh"]
        if "adjLow" in df.columns:
            all_lows[ticker] = df["adjLow"]
        if "adjVolume" in df.columns:
            all_volumes[ticker] = df["adjVolume"]

    prices_panel = pd.DataFrame(all_prices)
    returns_panel = prices_panel.pct_change()  # simple returns (§8.3)

    highs_panel = pd.DataFrame(all_highs)
    lows_panel = pd.DataFrame(all_lows)
    volumes_panel = pd.DataFrame(all_volumes)

    # Spread: calibrated static matrix + dynamic OHLC scaling (institutional review)
    spread_panel = build_spread_panel(highs_panel, lows_panel)

    # ADV in USD: rolling 20-day mean of volume * price
    dollar_volume = volumes_panel * prices_panel
    adv_panel = dollar_volume.rolling(20, min_periods=5).mean()

    return returns_panel, prices_panel, spread_panel, adv_panel


#---------------------------------------------------------------------------
#Rebalance date identification
#---------------------------------------------------------------------------
def get_month_end_dates(date_index: pd.DatetimeIndex) -> list[pd.Timestamp]:
    """Identify the last trading day of each month from the date index.

    Implements §6.1: rebalance on last business session of each month.
    """
    monthly_groups = date_index.to_series().groupby(
        [date_index.year, date_index.month]
    )
    return [group.iloc[-1] for _, group in monthly_groups]


#---------------------------------------------------------------------------
#Forecast volatility
#---------------------------------------------------------------------------
def forecast_portfolio_volatility(
    returns_window: pd.DataFrame,
    weights: pd.Series,
    periods_per_year: int = 252,
) -> float:
    """Annualized forecast volatility for the portfolio given current weights.

    Uses trailing empirical covariance on the lookback window.
    """
    common = returns_window.columns.intersection(weights.index)
    if len(common) == 0:
        return 0.0

    ret_clean = returns_window[common].dropna()
    w = weights.reindex(common, fill_value=0.0).values

    if len(ret_clean) < 5:
        return 0.0

    cov = ret_clean.cov().values
    port_var = w @ cov @ w
    return float(np.sqrt(max(port_var, 0.0) * periods_per_year))


#---------------------------------------------------------------------------
#Main simulator
#---------------------------------------------------------------------------
def run_backtest(
    returns_panel: pd.DataFrame,
    prices_panel: pd.DataFrame,
    spread_panel: pd.DataFrame,
    adv_panel: pd.DataFrame,
    config: BacktestConfig,
) -> BacktestResult:
    """Execute the full backtest simulation.

    Parameters
    ----------
    returns_panel : pd.DataFrame
        Daily simple returns (dates × tickers).
    prices_panel : pd.DataFrame
        Adjusted close prices (dates × tickers).
    spread_panel : pd.DataFrame
        Estimated spread fractions (dates × tickers).
    adv_panel : pd.DataFrame
        Average daily volume in USD (dates × tickers).
    config : BacktestConfig
        Backtest configuration.

    Returns
    -------
    BacktestResult
    """
    # Filter date range
    dates = returns_panel.index.sort_values()
    if config.start_date:
        dates = dates[dates >= pd.Timestamp(config.start_date)]
    if config.end_date:
        dates = dates[dates <= pd.Timestamp(config.end_date)]

    if len(dates) < config.lookback + 22:
        raise ValueError(
            f"Insufficient data: {len(dates)} dates < lookback({config.lookback}) + 22."
        )

    # Identify rebalance dates (last session of each month)
    rebalance_dates = get_month_end_dates(dates)

    # Only keep rebalance dates that have enough lookback history
    min_date = dates[0] + pd.Timedelta(days=int(config.lookback * 1.5))
    rebalance_dates = [d for d in rebalance_dates if d >= min_date]

    # Cost scenario
    cost_scenario = CostScenario.from_name(config.cost_scenario)

    # State variables
    current_weights = pd.Series(dtype=float)
    exposure = 1.0  # volatility targeting exposure
    nav = config.initial_capital

    # Output containers
    daily_returns_list = []
    daily_nav_list = []
    weights_records = []
    turnover_records = []
    cost_records = []
    skipped = []
    executed_rebalances = []

    tickers = returns_panel.columns.tolist()

    for i, date in enumerate(dates):
        # -----------------------------------------------------------------
        # Daily PnL (before any rebalance on this date)
        # -----------------------------------------------------------------
        if not current_weights.empty and i > 0:
            day_returns = returns_panel.loc[date].reindex(current_weights.index, fill_value=0.0)
            port_ret = float((current_weights * day_returns).sum())

            # Apply exposure scaling from volatility targeting
            port_ret_scaled = port_ret * exposure

            nav *= (1 + port_ret_scaled)
            daily_returns_list.append((date, port_ret_scaled))
            daily_nav_list.append((date, nav))

            # Drift weights forward based on individual returns
            drifted = current_weights * (1 + day_returns)
            drift_sum = drifted.sum()
            if drift_sum > 0:
                current_weights = drifted / drift_sum
        else:
            daily_returns_list.append((date, 0.0))
            daily_nav_list.append((date, nav))

        # -----------------------------------------------------------------
        # Rebalance if this is a month-end date
        # -----------------------------------------------------------------
        if date not in rebalance_dates:
            continue

        # Lookback window for covariance estimation: [date - L, date - 1]
        # Strictly PIT: only data available up to and including this date
        date_loc = dates.get_loc(date)
        lookback_start = max(0, date_loc - config.lookback)
        window_dates = dates[lookback_start:date_loc]  # excludes current date for decisions

        if len(window_dates) < 22:
            skipped.append((date, "insufficient_lookback"))
            continue

        returns_window = returns_panel.loc[window_dates].dropna(axis=1, how="all")
        eligible_tickers = returns_window.columns.tolist()

        if len(eligible_tickers) < 3:
            skipped.append((date, "too_few_eligible_tickers"))
            continue

        # -----------------------------------------------------------------
        # Calculate target weights using the configured strategy
        # -----------------------------------------------------------------
        try:
            target_weights = config.weight_function(
                returns_window, eligible_tickers, **config.weight_kwargs
            )
        except Exception as e:
            skipped.append((date, f"weight_calculation_error: {e}"))
            continue

        # Ensure weights are aligned and sum to 1
        target_weights = target_weights.reindex(eligible_tickers, fill_value=0.0)
        w_sum = target_weights.sum()
        if w_sum > 0:
            target_weights = target_weights / w_sum
        else:
            skipped.append((date, "zero_weight_sum"))
            continue

        # -----------------------------------------------------------------
        # Volatility Targeting (§18.3-18.5)
        # -----------------------------------------------------------------
        if config.vol_target_enabled:
            sigma_forecast = forecast_portfolio_volatility(
                returns_window, target_weights
            )

            if sigma_forecast > 0:
                raw_exposure = min(1.0, config.vol_target / sigma_forecast)
            else:
                raw_exposure = 1.0

            # Emergency reduction (§18.5): no smoothing if σ > 18%
            if sigma_forecast > config.vol_emergency_threshold:
                exposure = raw_exposure
            else:
                # EMA smoothing (§18.4)
                exposure = (
                    config.vol_smoothing_alpha * raw_exposure
                    + (1 - config.vol_smoothing_alpha) * exposure
                )

            # No leverage allowed (§5)
            exposure = min(exposure, 1.0)

        # -----------------------------------------------------------------
        # Rebalance Buffer (§18.2)
        # -----------------------------------------------------------------
        if not current_weights.empty:
            # Compute aggregate turnover
            old_w = current_weights.reindex(eligible_tickers, fill_value=0.0)
            new_w = target_weights
            turnover = float((old_w - new_w).abs().sum())

            if turnover < config.rebalance_buffer:
                skipped.append((date, f"buffer_skip_turnover={turnover:.4f}"))
                continue
        else:
            old_w = pd.Series(0.0, index=eligible_tickers)
            turnover = float(target_weights.abs().sum())

        # -----------------------------------------------------------------
        # Calculate rebalance costs (§7.4)
        # -----------------------------------------------------------------
        day_prices = prices_panel.loc[date].reindex(eligible_tickers, fill_value=1.0)
        day_spreads = spread_panel.loc[date].reindex(eligible_tickers)
        day_advs = adv_panel.loc[date].reindex(eligible_tickers, fill_value=1e9)

        # Replace NaN with calibrated static defaults per ticker
        for t in eligible_tickers:
            if pd.isna(day_spreads.get(t, np.nan)):
                day_spreads[t] = get_static_spread(t)
        day_advs = day_advs.fillna(1e9)

        total_cost, _ = calculate_rebalance_cost(
            old_weights=old_w,
            new_weights=target_weights,
            portfolio_value=nav,
            prices=day_prices,
            spreads=day_spreads,
            advs=day_advs,
            scenario=cost_scenario,
        )

        # Deduct cost from NAV
        nav -= total_cost

        # Update weights
        current_weights = target_weights.copy()

        # Record
        executed_rebalances.append(date)
        weights_records.append((date, target_weights.to_dict()))
        turnover_records.append((date, turnover))
        cost_records.append((date, total_cost))

    # -----------------------------------------------------------------
    # Build result DataFrames
    # -----------------------------------------------------------------
    daily_returns = pd.Series(
        {d: r for d, r in daily_returns_list}, name="portfolio_return"
    )
    daily_nav = pd.Series(
        {d: v for d, v in daily_nav_list}, name="nav"
    )

    weights_history = pd.DataFrame(
        {d: w for d, w in weights_records}
    ).T
    weights_history.index.name = "date"

    turnover_history = pd.Series(
        {d: t for d, t in turnover_records}, name="turnover"
    )
    cost_history = pd.Series(
        {d: c for d, c in cost_records}, name="cost_usd"
    )

    # Calculate metrics
    metrics = calculate_metrics(daily_returns)
    weight_mets = calculate_weight_metrics(weights_history)

    result = BacktestResult(
        daily_returns=daily_returns,
        daily_nav=daily_nav,
        weights_history=weights_history,
        turnover_history=turnover_history,
        cost_history=cost_history,
        rebalance_dates=executed_rebalances,
        skipped_rebalances=skipped,
        config=config,
        metrics=metrics,
        weight_metrics=weight_mets,
    )

    return result
