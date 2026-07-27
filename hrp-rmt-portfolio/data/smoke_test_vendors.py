"""Smoke tests for market data vendors used by the HRP-RMT protocol.

The script validates that credentials are available and that each vendor can
return a minimal, auditable payload for the configured ETF universe.

It never prints API keys.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class CheckResult:
    vendor: str
    check: str
    ticker: str
    ok: bool
    rows: int = 0
    fields: list[str]  None = None
    message: str = ""


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def request_json(url: str, headers: dict[str, str]  None = None, timeout: int = 25) -> tuple[int, Any]:
    request = Request(url, headers=headers or {})
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
            return response.status, json.loads(payload)
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def tiingo_prices(ticker: str, start_date: str, end_date: str) -> CheckResult:
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        return CheckResult("tiingo", "daily_prices", ticker, False, message="Missing TIINGO_API_KEY")

    query = urlencode({"startDate": start_date, "endDate": end_date})
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?{query}"
    headers = {"Authorization": f"Token {api_key}"}

    try:
        _, data = request_json(url, headers=headers)
        rows = len(data) if isinstance(data, list) else 0
        fields = sorted(data[0].keys()) if rows else []
        required = {"date", "open", "high", "low", "close", "volume", "adjClose", "divCash", "splitFactor"}
        missing = sorted(required - set(fields))
        ok = rows > 0 and not missing
        message = "ok" if ok else f"missing_fields={missing}" if rows else "no_rows"
        return CheckResult("tiingo", "daily_prices", ticker, ok, rows, fields, message)
    except RuntimeError as exc:
        return CheckResult("tiingo", "daily_prices", ticker, False, message=str(exc))


def nasdaq_tickers(ticker: str) -> CheckResult:
    api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
    if not api_key:
        return CheckResult("nasdaq_sharadar", "tickers_metadata", ticker, False, message="Missing NASDAQ_DATA_LINK_API_KEY")

    query = urlencode({"ticker": ticker, "api_key": api_key})
    url = f"https://data.nasdaq.com/api/v3/datatables/SHARADAR/TICKERS.json?{query}"

    try:
        _, data = request_json(url)
        datatable = data.get("datatable", {})
        rows_data = datatable.get("data", [])
        columns = [col.get("name", "") for col in datatable.get("columns", [])]
        rows = len(rows_data)
        fields = [field for field in columns if field]
        if rows:
            row = rows_data[0]
            mapped = dict(zip(columns, row))
            table = mapped.get("table", "")
            category = mapped.get("category", "")
            currency = mapped.get("currency", "")
            is_delisted = mapped.get("isdelisted", "")
            ok = table in {"SFP", "SEP"} and category in {"ETF", "CEF", "ETD", "Fund"} and currency == "USD"
            message = f"table={table}; category={category}; currency={currency}; isdelisted={is_delisted}"
        else:
            ok = False
            message = "no_rows"
        return CheckResult("nasdaq_sharadar", "tickers_metadata", ticker, ok, rows, fields, message)
    except RuntimeError as exc:
        return CheckResult("nasdaq_sharadar", "tickers_metadata", ticker, False, message=str(exc))


def nasdaq_sfp_prices(ticker: str, start_date: str, end_date: str) -> CheckResult:
    api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY")
    if not api_key:
        return CheckResult("nasdaq_sharadar", "sfp_prices", ticker, False, message="Missing NASDAQ_DATA_LINK_API_KEY")

    query = urlencode(
        {
            "ticker": ticker,
            "date.gte": start_date,
            "date.lte": end_date,
            "api_key": api_key,
        }
    )
    url = f"https://data.nasdaq.com/api/v3/datatables/SHARADAR/SFP.json?{query}"

    try:
        _, data = request_json(url)
        datatable = data.get("datatable", {})
        rows_data = datatable.get("data", [])
        fields = [col.get("name", "") for col in datatable.get("columns", [])]
        rows = len(rows_data)
        required = {"ticker", "date", "open", "high", "low", "close", "volume", "closeadj", "closeunadj"}
        missing = sorted(required - set(fields))
        ok = rows > 0 and not missing
        message = "ok" if ok else f"no_rows; fields_present={not missing}" if rows == 0 else f"missing_fields={missing}"
        return CheckResult("nasdaq_sharadar", "sfp_prices", ticker, ok, rows, fields, message)
    except RuntimeError as exc:
        return CheckResult("nasdaq_sharadar", "sfp_prices", ticker, False, message=str(exc))


def run_checks(tickers: list[str], start_date: str, end_date: str, include_nasdaq: bool = False) -> list[CheckResult]:
    results: list[CheckResult] = []
    for ticker in tickers:
        symbol = ticker.upper().strip()
        if not symbol:
            continue
        results.append(tiingo_prices(symbol, start_date, end_date))
        if include_nasdaq:
            results.append(nasdaq_tickers(symbol))
            results.append(nasdaq_sfp_prices(symbol, start_date, end_date))
    return results


def print_table(results: list[CheckResult]) -> None:
    print("vendor,check,ticker,status,rows,message")
    for result in results:
        status = "OK" if result.ok else "FAIL"
        safe_message = result.message.replace("\n", " ").replace(",", ";")
        print(f"{result.vendor},{result.check},{result.ticker},{status},{result.rows},{safe_message}")


def main(argv: list[str]  None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate configured market data vendors without exposing secrets.")
    parser.add_argument("--tickers", nargs="+", default=["SPY", "AGG", "GLD"], help="ETF tickers to validate.")
    parser.add_argument("--start-date", default="2024-01-02", help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end-date", default="2024-01-03", help="End date in YYYY-MM-DD format.")
    parser.add_argument("--include-nasdaq", action="store_true", help="Also test optional Nasdaq Data Link / Sharadar endpoints.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of CSV-style table.")
    args = parser.parse_args(argv)

    load_dotenv()
    results = run_checks(args.tickers, args.start_date, args.end_date, include_nasdaq=args.include_nasdaq)

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2, ensure_ascii=False))
    else:
        print_table(results)

    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
