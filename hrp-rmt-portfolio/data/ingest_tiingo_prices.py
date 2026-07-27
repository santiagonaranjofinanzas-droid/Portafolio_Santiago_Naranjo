"""Download Tiingo daily ETF prices for the V1 universe.

Outputs one CSV per ticker plus a JSON manifest. API keys are read from `.env`
or the `TIINGO_API_KEY` environment variable and are never printed.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNIVERSE = PROJECT_ROOT / "config" / "universe_v1_etf_longonly.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "raw" / "tiingo" / "prices"
ENV_PATH = PROJECT_ROOT / ".env"

PRICE_FIELDS = [
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "adjOpen",
    "adjHigh",
    "adjLow",
    "adjClose",
    "adjVolume",
    "divCash",
    "splitFactor",
]


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_universe(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def request_json(url: str, headers: dict[str, str], timeout: int = 45) -> Any:
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc.reason}") from exc


def fetch_prices(ticker: str, start_date: str, end_date: str, api_key: str) -> list[dict[str, Any]]:
    query = urlencode({"startDate": start_date, "endDate": end_date})
    url = f"https://api.tiingo.com/tiingo/daily/{ticker}/prices?{query}"
    data = request_json(url, headers={"Authorization": f"Token {api_key}"})
    if not isinstance(data, list):
        raise RuntimeError("Unexpected Tiingo response type")
    return data


def write_prices(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRICE_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"rows": 0, "first_date": None, "last_date": None, "missing_fields": PRICE_FIELDS}
    fields = set(rows[0].keys())
    missing = [field for field in PRICE_FIELDS if field not in fields]
    return {
        "rows": len(rows),
        "first_date": rows[0].get("date"),
        "last_date": rows[-1].get("date"),
        "missing_fields": missing,
        "zero_volume_rows": sum(1 for row in rows if row.get("volume") in {0, 0.0, "0"}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download Tiingo prices for the V1 ETF universe.")
    parser.add_argument("--universe", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--start-date", default="2010-01-01")
    parser.add_argument("--end-date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--tickers", nargs="*", help="Optional subset of tickers.")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("TIINGO_API_KEY")
    if not api_key:
        raise SystemExit("Missing TIINGO_API_KEY")

    universe = read_universe(args.universe)
    selected = {ticker.upper() for ticker in args.tickers} if args.tickers else None
    if selected:
        universe = [row for row in universe if row["ticker"].upper() in selected]

    manifest = {
        "vendor": "tiingo",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "universe_file": str(args.universe),
        "output_dir": str(args.output_dir),
        "tickers": [],
    }

    failures = 0
    for asset in universe:
        ticker = asset["ticker"].upper()
        record = {"ticker": ticker, "ok": False, "asset_class": asset.get("asset_class", "")}
        try:
            rows = fetch_prices(ticker, args.start_date, args.end_date, api_key)
            write_prices(args.output_dir / f"{ticker}.csv", rows)
            record.update({"ok": True, **summarize_rows(rows)})
        except RuntimeError as exc:
            failures += 1
            record["error"] = str(exc)
        manifest["tickers"].append(record)
        status = "OK" if record["ok"] else "FAIL"
        print(f"{ticker},{status},rows={record.get('rows', 0)}")

    manifest["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["failures"] = failures
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
