"""Generate frozen-model daily target weights for F8 shadow paper."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from portfolio.hrp import calculate_hrp_weights
from production.io_utils import PROD_DATA, append_csv_row, read_csv, read_universe, utc_now
from risk.cov_estimators import calculate_oas_covariance


MODEL_VERSION = "HRP_UNCONDITIONAL_CORE_V1"


def load_price_panel(tickers: list[str]) -> pd.DataFrame:
    series = {}
    for ticker in tickers:
        rows = read_csv(PROD_DATA / "master_prices" / f"{ticker}.csv")
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        df["adjClose"] = pd.to_numeric(df["adjClose"], errors="coerce")
        series[ticker] = df.set_index("date")["adjClose"]
    return pd.DataFrame(series).sort_index()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate daily frozen-model target weights.")
    parser.add_argument("--date", required=True)
    parser.add_argument("--lookback", type=int, default=504)
    parser.add_argument("--vol-target", type=float, default=0.12)
    parser.add_argument("--max-weight", type=float, default=0.15)
    parser.add_argument("--cash-ticker", default="BIL")
    args = parser.parse_args()

    tickers = read_universe()
    prices = load_price_panel(tickers)
    prices = prices[prices.index <= pd.Timestamp(args.date)]
    returns = prices.pct_change().dropna(how="all")
    window = returns.tail(args.lookback).dropna(axis=1)
    if len(window) < args.lookback:
        raise SystemExit(f"Insufficient lookback rows: {len(window)}")

    cov = calculate_oas_covariance(window)
    weights = calculate_hrp_weights(
        cov,
        linkage_method="single",
        cap=args.max_weight,
        redistribution_method="proportional",
        cash_ticker=args.cash_ticker,
    )
    restricted = weights["weights_restricted"].copy()
    restricted = restricted / restricted.sum()

    daily_portfolio_returns = window[restricted.index].dot(restricted)
    sigma_forecast = float(daily_portfolio_returns.std() * (252 ** 0.5))
    vol_scalar = min(1.0, args.vol_target / sigma_forecast) if sigma_forecast > 0 else 1.0
    final = restricted * vol_scalar
    if args.cash_ticker in final.index:
        final.loc[args.cash_ticker] += 1.0 - final.sum()

    for ticker in final.index:
        append_csv_row(
            PROD_DATA / "target_weights.csv",
            [
                "timestamp_utc", "date", "model_version", "ticker", "target_weight_raw",
                "target_weight_capped", "vol_scalar", "final_target_weight",
                "sigma_forecast", "quality_status", "rebalance_eligible",
            ],
            {
                "timestamp_utc": utc_now(),
                "date": args.date,
                "model_version": MODEL_VERSION,
                "ticker": ticker,
                "target_weight_raw": weights.loc[ticker, "weights_pure"],
                "target_weight_capped": restricted.loc[ticker],
                "vol_scalar": vol_scalar,
                "final_target_weight": final.loc[ticker],
                "sigma_forecast": sigma_forecast,
                "quality_status": "OK",
                "rebalance_eligible": "MONTH_END_ONLY",
            },
        )
    print(f"weights_written={len(final)} sigma_forecast={sigma_forecast:.6f} vol_scalar={vol_scalar:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
