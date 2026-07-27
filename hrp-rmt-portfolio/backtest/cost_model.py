"""Cost model for backtest simulation.

Implements §7.2 and §7.4 of the protocol:
- Three scenarios: Low, Base, Stress.
- Base is the ONLY scenario used for hyperparameter selection, ranking, DSR, PBO and
  composite score.  Low and Stress are sensitivity-only.
- Expense ratios are NOT double-counted when using adjusted prices (§7.3).

Spread estimation uses a calibrated static matrix by asset class (institutional review),
with an optional dynamic scaling factor from OHLC range for stress microstructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


#---------------------------------------------------------------------------
#§7.2 – Scenario parameters
#---------------------------------------------------------------------------
COST_SCENARIOS: dict[str, dict] = {
    "low": {
        "commission_per_share_usd": 0.005,
        "min_commission_per_order_usd": 0.0,
        "slippage_pct_of_spread": 0.25,
        "spread_method": "mean_20d",
        "market_impact": "none",
        "regulatory_fees": False,
    },
    "base": {
        "commission_per_share_usd": 0.005,
        "min_commission_per_order_usd": 1.0,
        "slippage_pct_of_spread": 0.50,
        "spread_method": "mean_20d",
        "market_impact": "linear_by_adv",
        "regulatory_fees": True,
    },
    "stress": {
        "commission_per_share_usd": 0.005,
        "min_commission_per_order_usd": 1.0,
        "slippage_pct_of_spread": 1.00,
        "spread_method": "p95",
        "market_impact": "quadratic",
        "regulatory_fees": True,
    },
}


#---------------------------------------------------------------------------
#Calibrated static spread matrix by asset class (in fraction, not bps)
#---------------------------------------------------------------------------
#Institutional calibration: reflects actual screen spreads for liquid ETFs
#traded via MOC or block execution.  Values are in fraction (1 bp = 0.0001).
CALIBRATED_SPREAD_BY_CLASS: dict[str, float] = {
    # Equity: mega-cap US & developed market ETFs
    "Equity": 0.00015,          # 1.5 bps
    # Fixed Income: liquid treasuries and IG corporates
    "Fixed Income": 0.0002,     # 2.0 bps
    # Cash: T-bills, money market
    "Cash": 0.0001,             # 1.0 bps
    # Commodity: gold, broad commodity
    "Commodity": 0.0005,        # 5.0 bps
    # Real Estate: REIT ETFs
    "Real Estate": 0.0004,      # 4.0 bps
    # High Yield / EM bonds
    "High Yield": 0.0008,       # 8.0 bps
}

#Ticker -> asset class mapping from universe config
#This is loaded from config/universe_v1_etf_longonly.csv but we provide
#a hardcoded fallback for the V1 universe to avoid file-system dependency
#in unit tests.
TICKER_ASSET_CLASS: dict[str, str] = {
    # Equity
    "SPY": "Equity", "VTI": "Equity", "QQQ": "Equity", "IWM": "Equity",
    "EFA": "Equity", "IEFA": "Equity", "VGK": "Equity", "EWJ": "Equity",
    "EEM": "Equity", "VWO": "Equity", "FXI": "Equity",
    "XLF": "Equity", "XLK": "Equity", "XLE": "Equity", "XLV": "Equity",
    "XLI": "Equity", "XLY": "Equity", "XLP": "Equity", "XLU": "Equity",
    "XLB": "Equity", "XLRE": "Equity",
    "USMV": "Equity", "MTUM": "Equity", "VLUE": "Equity", "QUAL": "Equity",
    # Fixed Income
    "AGG": "Fixed Income", "BND": "Fixed Income", "TLT": "Fixed Income",
    "IEF": "Fixed Income", "SHY": "Fixed Income", "TIP": "Fixed Income",
    "LQD": "Fixed Income", "BNDX": "Fixed Income", "EMB": "Fixed Income",
    # High Yield (uses dedicated spread tier)
    "HYG": "High Yield",
    # Cash
    "BIL": "Cash", "SGOV": "Cash",
    # Commodity
    "GLD": "Commodity", "IAU": "Commodity", "SLV": "Commodity",
    "DBC": "Commodity", "USO": "Commodity",
    # Real Estate
    "VNQ": "Real Estate", "VNQI": "Real Estate", "RWX": "Real Estate",
}

#Dynamic scaling factor for OHLC range proxy contribution
#spread_effective = spread_static + DYNAMIC_SCALE * spread_ohlc_proxy
#This captures microstructural widening under stress while keeping normal
#days converging to institutional minimums.
DYNAMIC_SPREAD_SCALE: float = 0.05


@dataclass(frozen=True)
class CostScenario:
    """Immutable snapshot of a cost scenario configuration."""

    name: str
    commission_per_share_usd: float
    min_commission_per_order_usd: float
    slippage_pct_of_spread: float
    spread_method: str
    market_impact: str
    regulatory_fees: bool

    @classmethod
    def from_name(cls, name: Literal["low", "base", "stress"]) -> CostScenario:
        """Build a CostScenario from the protocol-defined scenarios."""
        params = COST_SCENARIOS[name]
        return cls(name=name, **params)


#---------------------------------------------------------------------------
#Spread estimation
#---------------------------------------------------------------------------

def get_static_spread(ticker: str) -> float:
    """Return the calibrated static spread for a ticker (fraction)."""
    asset_class = TICKER_ASSET_CLASS.get(ticker, "Equity")
    return CALIBRATED_SPREAD_BY_CLASS.get(asset_class, 0.0003)  # default 3 bps


def estimate_spread_ohlc_proxy(
    high: pd.Series  float,
    low: pd.Series  float,
) -> pd.Series  float:
    """Raw OHLC range proxy for intraday realized volatility (NOT a direct spread).

    Proxy formula: range_proxy ≈ 2 * (H - L) / (H + L)
    Used only as a dynamic scaling component, never as the sole spread estimate.
    """
    denom = high + low
    if isinstance(denom, (pd.Series, pd.DataFrame)):
        denom = denom.replace(0.0, np.nan)
    elif denom == 0.0:
        return np.nan
    return 2.0 * (high - low) / denom


def build_spread_panel(
    highs_panel: pd.DataFrame,
    lows_panel: pd.DataFrame,
    dynamic_scale: float = DYNAMIC_SPREAD_SCALE,
) -> pd.DataFrame:
    """Build a spread panel combining static calibration + dynamic OHLC scaling.

    For each ticker and date:
        spread_effective = spread_static + dynamic_scale * range_proxy

    On normal days, the range_proxy contributes minimally (≈0.05 * 0.005 = 0.025 bps
    for a typical ETF). On stress days, it captures microstructural widening.

    Parameters
    ----------
    highs_panel : pd.DataFrame
        Adjusted high prices (dates × tickers).
    lows_panel : pd.DataFrame
        Adjusted low prices (dates × tickers).
    dynamic_scale : float
        Multiplicative factor for the OHLC proxy component (default 0.05).

    Returns
    -------
    pd.DataFrame
        Effective spread in fraction (dates × tickers).
    """
    tickers = highs_panel.columns
    dates = highs_panel.index

    # Static component: broadcast per-ticker static spread
    static_spreads = pd.Series(
        {t: get_static_spread(t) for t in tickers}
    )
    static_panel = pd.DataFrame(
        np.tile(static_spreads.values, (len(dates), 1)),
        index=dates,
        columns=tickers,
    )

    # Dynamic component: OHLC range proxy * scale
    ohlc_proxy = estimate_spread_ohlc_proxy(highs_panel, lows_panel)
    dynamic_panel = ohlc_proxy * dynamic_scale

    # Combine: static base + dynamic widening
    spread_effective = static_panel + dynamic_panel.fillna(0.0)

    # Floor: never below static minimum
    spread_effective = spread_effective.clip(lower=static_panel)

    return spread_effective


#---------------------------------------------------------------------------
#Legacy alias kept for backward compatibility with tests
#---------------------------------------------------------------------------
def estimate_spread_bps(
    high: pd.Series  float,
    low: pd.Series  float,
) -> pd.Series  float:
    """Legacy alias — returns raw OHLC range proxy.

    DEPRECATED for production use. Use build_spread_panel() instead.
    Kept for unit test backward compatibility.
    """
    return estimate_spread_ohlc_proxy(high, low)


#---------------------------------------------------------------------------
#Cost calculation
#---------------------------------------------------------------------------

def calculate_trade_cost(
    trade_value_usd: float,
    price_per_share: float,
    spread_frac: float,
    adv_usd: float,
    scenario: CostScenario,
) -> float:
    """Calculate the total cost for a single trade (one asset, one rebalance).

    Parameters
    ----------
    trade_value_usd : float
        Absolute value of the notional trade (ΔW * PortfolioValue).
    price_per_share : float
        Price per share used to compute number of shares.
    spread_frac : float
        Spread as a fraction (e.g. 0.001 = 10 bps).
    adv_usd : float
        Average daily volume in USD (last 20 days).
    scenario : CostScenario
        Cost scenario configuration.

    Returns
    -------
    float
        Total cost in USD for this trade leg.
    """
    if trade_value_usd <= 0.0:
        return 0.0

    # Number of shares traded
    if price_per_share <= 0.0:
        return 0.0
    n_shares = trade_value_usd / price_per_share

    # 1. Commission
    commission = max(
        n_shares * scenario.commission_per_share_usd,
        scenario.min_commission_per_order_usd,
    )

    # 2. Slippage = fraction of spread applied to notional
    slippage = trade_value_usd * spread_frac * scenario.slippage_pct_of_spread

    # 3. Spread cost (half-spread crossing)
    spread_cost = trade_value_usd * spread_frac * 0.5

    # 4. Market impact
    if scenario.market_impact == "none":
        impact = 0.0
    elif scenario.market_impact == "linear_by_adv":
        # Linear model: cost proportional to trade_value / ADV
        participation = trade_value_usd / adv_usd if adv_usd > 0 else 0.0
        impact = trade_value_usd * participation * 0.10  # 10 bps per 1% participation
    elif scenario.market_impact == "quadratic":
        participation = trade_value_usd / adv_usd if adv_usd > 0 else 0.0
        impact = trade_value_usd * (participation ** 2) * 0.50
    else:
        impact = 0.0

    # 5. Regulatory fees (SEC fee ~$8 per million on sells, simplified)
    reg_fee = 0.0
    if scenario.regulatory_fees:
        reg_fee = trade_value_usd * 8.0 / 1_000_000.0

    return commission + slippage + spread_cost + impact + reg_fee


def calculate_rebalance_cost(
    old_weights: pd.Series,
    new_weights: pd.Series,
    portfolio_value: float,
    prices: pd.Series,
    spreads: pd.Series,
    advs: pd.Series,
    scenario: CostScenario,
) -> tuple[float, pd.Series]:
    """Calculate total rebalance cost across all assets.

    Parameters
    ----------
    old_weights : pd.Series
        Current portfolio weights indexed by ticker.
    new_weights : pd.Series
        Target portfolio weights indexed by ticker.
    portfolio_value : float
        Current portfolio NAV in USD.
    prices : pd.Series
        Last close prices per asset.
    spreads : pd.Series
        Spread estimates (fraction) per asset.
    advs : pd.Series
        Average daily volume (USD) per asset.
    scenario : CostScenario
        Cost scenario to use.

    Returns
    -------
    tuple[float, pd.Series]
        (total_cost_usd, per_asset_cost_series)
    """
    # Align all series to a common set of tickers
    all_tickers = old_weights.index.union(new_weights.index)
    old_w = old_weights.reindex(all_tickers, fill_value=0.0)
    new_w = new_weights.reindex(all_tickers, fill_value=0.0)

    per_asset_cost = pd.Series(0.0, index=all_tickers)

    for ticker in all_tickers:
        delta_w = abs(new_w[ticker] - old_w[ticker])
        trade_val = delta_w * portfolio_value

        price = prices.get(ticker, 0.0)
        spread = spreads.get(ticker, get_static_spread(ticker))
        adv = advs.get(ticker, 1e9)  # default very liquid

        cost = calculate_trade_cost(
            trade_value_usd=trade_val,
            price_per_share=price if price > 0 else 1.0,
            spread_frac=spread,
            adv_usd=adv,
            scenario=scenario,
        )
        per_asset_cost[ticker] = cost

    return float(per_asset_cost.sum()), per_asset_cost
