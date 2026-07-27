from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
PROFILE = json.loads((HERE / "config" / "broker_profile_nas100_fs.json").read_text(encoding="utf-8"))
OUT = HERE / "forward_axi"
TICKS = OUT / "ticks"
START = datetime(2026, 6, 20, tzinfo=timezone.utc)


def main() -> None:
    if not mt5.initialize():
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}")
    try:
        symbol = PROFILE["symbol"]
        if not mt5.symbol_select(symbol, True):
            raise RuntimeError(f"Cannot select {symbol}: {mt5.last_error()}")
        info = mt5.symbol_info(symbol)
        tick = mt5.symbol_info_tick(symbol)
        if info is None or tick is None:
            raise RuntimeError(f"No symbol information for {symbol}")
        checks = {
            "point": float(info.point),
            "tick_size": float(info.trade_tick_size),
            "tick_value": float(info.trade_tick_value),
            "volume_min": float(info.volume_min),
            "volume_max": float(info.volume_max),
            "volume_step": float(info.volume_step),
        }
        for key, actual in checks.items():
            expected = float(PROFILE[key])
            if not np.isclose(actual, expected, rtol=0.0, atol=1e-12):
                raise RuntimeError(f"Broker profile drift: {key} expected={expected} actual={actual}")
        end = datetime.fromtimestamp(tick.time, tz=timezone.utc)
        if end <= START:
            raise RuntimeError(f"Terminal tick time {end} does not cover forward start {START}")
        TICKS.mkdir(parents=True, exist_ok=True)
        day = START
        daily_rows = []
        aggregated_bars = []
        while day < end:
            next_day = min(day + timedelta(days=1), end)
            raw = mt5.copy_ticks_range(symbol, day, next_day, mt5.COPY_TICKS_INFO)
            if raw is None:
                raise RuntimeError(f"copy_ticks_range failed {day}..{next_day}: {mt5.last_error()}")
            frame = pd.DataFrame(raw)
            if not frame.empty:
                frame["timestamp"] = pd.to_datetime(frame["time_msc"], unit="ms", utc=True).dt.tz_convert(None)
                frame = frame.loc[(frame["bid"] > 0.0) & (frame["ask"] > 0.0), ["timestamp", "bid", "ask", "flags"]]
                frame = frame.drop_duplicates("timestamp").sort_values("timestamp")
                partition = TICKS / f"year={day.year}" / f"month={day.month}"
                partition.mkdir(parents=True, exist_ok=True)
                path = partition / f"ticks_{symbol.replace('.', '_')}_{day:%Y%m%d}.parquet"
                frame.to_parquet(path, index=False)
                spread = frame["ask"] - frame["bid"]
                indexed = frame.set_index("timestamp")
                ohlc = indexed["bid"].resample("15min").ohlc().dropna()
                ohlc["spread_median"] = (indexed["ask"] - indexed["bid"]).resample("15min").median()
                ohlc["spread_p95"] = (indexed["ask"] - indexed["bid"]).resample("15min").quantile(0.95)
                ohlc["tick_count"] = indexed["bid"].resample("15min").count()
                aggregated_bars.append(ohlc)
                daily_rows.append({
                    "date": f"{day:%Y-%m-%d}",
                    "rows": len(frame),
                    "start": str(frame["timestamp"].min()),
                    "end": str(frame["timestamp"].max()),
                    "spread_median": float(spread.median()),
                    "spread_p95": float(spread.quantile(0.95)),
                    "spread_max": float(spread.max()),
                })
            day = next_day

        if not aggregated_bars:
            raise RuntimeError("No Bid/Ask ticks were captured for M15 aggregation")
        bars = pd.concat(aggregated_bars).sort_index()
        bars = bars[~bars.index.duplicated(keep="last")].sort_index()
        bars.to_parquet(OUT / "NAS100_fs_M15_FORWARD.parquet")
        daily = pd.DataFrame(daily_rows)
        daily.to_csv(OUT / "tick_capture_manifest.csv", index=False)
        manifest = {
            "symbol": symbol,
            "source": "Axi MT5 copy_ticks_range COPY_TICKS_INFO; M15 Bid OHLC aggregated locally",
            "start_requested_utc": START.isoformat(),
            "end_terminal_utc": end.isoformat(),
            "tick_rows": int(daily["rows"].sum()) if not daily.empty else 0,
            "tick_days": int(len(daily)),
            "bar_rows": int(len(bars)),
            "bar_start": str(bars.index.min()),
            "bar_end": str(bars.index.max()),
            "profile_checks": checks,
        }
        (OUT / "capture_summary.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(json.dumps(manifest, indent=2))
    finally:
        mt5.shutdown()


if __name__ == "__main__":
    main()
