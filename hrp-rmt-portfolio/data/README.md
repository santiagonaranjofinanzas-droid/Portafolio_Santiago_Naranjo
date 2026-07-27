#Data Layer V1

V1 uses Tiingo as the primary source for ETF daily prices and corporate-action-adjusted fields. Nasdaq Data Link / Sharadar is treated as an optional paid upgrade for security-master and survivorship-bias controls.

##Smoke Test

Run from the project root:

```powershell
python .\data\smoke_test_vendors.py --tickers SPY AGG GLD --start-date 2024-01-02 --end-date 2024-01-03
```

Optional Nasdaq / Sharadar check:

```powershell
python .\data\smoke_test_vendors.py --tickers SPY AGG GLD --start-date 2024-01-02 --end-date 2024-01-03 --include-nasdaq
```

The script loads credentials from `.env` or from user/system environment variables:

- `TIINGO_API_KEY`
- `NASDAQ_DATA_LINK_API_KEY` (optional)

It does not print API keys.

##Interpretation

- `tiingo,daily_prices,OK`: Tiingo can return daily OHLCV, adjusted prices, dividends and split factors.
- `nasdaq_sharadar,tickers_metadata,OK`: Nasdaq Data Link can access Sharadar security master metadata.
- `nasdaq_sharadar,sfp_prices,OK`: Nasdaq Data Link can access Sharadar fund prices for ETFs.

##Tiingo Ingestion

Download the complete V1 universe:

```powershell
python .\data\ingest_tiingo_prices.py --start-date 2010-01-01
```

Download only a subset:

```powershell
python .\data\ingest_tiingo_prices.py --tickers SPY AGG GLD --start-date 2020-01-01 --end-date 2024-12-31
```

Outputs:

- `data/raw/tiingo/prices/{TICKER}.csv`
- `data/raw/tiingo/prices/_manifest.json`

##Coverage Report

```powershell
python .\data\coverage_report.py
```

Output:

- `data/quality/tiingo_coverage_report.csv`

For institutional use with a Tiingo-only stack, ETF price ingestion should not be accepted until:

1. Tiingo returns historical ETF prices for the full configured universe;
2. required adjusted and unadjusted price fields are present;
3. missing/stale/zero-volume observations are reported;
4. the universe limitation is disclosed as Tiingo-only rather than full paid PIT Sharadar.

If Sharadar `SFP` returns metadata but no price rows, verify the Nasdaq Data Link subscription includes Sharadar Fund Prices.
