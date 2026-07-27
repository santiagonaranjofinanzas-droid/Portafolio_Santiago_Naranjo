import os
import sys
import zipfile
from functools import lru_cache

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from Capa_4.backtest_metrics import BacktestAssumptions, compute_backtest_metrics
from Capa_4.sovereign_execution import CFinancialEngine
from SUB_RAMA_MEAN_REVERSION.run_reversion_pipeline import ASSETS, build_assumptions


RESULTS_DIR = os.path.join(ROOT, "SUB_RAMA_MEAN_REVERSION", "resultados")
UNIVERSE_TICKS_DIR = os.path.join(ROOT, "Universo de activos", "Datos_Crudos_Zip")
UNIVERSE_TICKS_PARQUET = os.path.join(ROOT, "Universo de activos", "ticks_parquet")
XAU_TICKS_DIR = os.path.join(ROOT, "gold_data_parquet", "Datos__Crudos 2024_2026")

MR_PARAMS = {
    "NSXUSD": (3.0, 3.25, 3.5),
    "XAGUSD": (3.0, 3.25, 3.0),
    "XAUUSD": (3.0, 3.0, 3.5),
}


def _month_key(ts: pd.Timestamp) -> str:
    ts = pd.Timestamp(ts)
    return f"{ts.year}{ts.month:02d}"


def _tick_zip_path(asset: str, yyyymm: str) -> str  None:
    if asset in {"NSXUSD", "XAGUSD"}:
        p = os.path.join(UNIVERSE_TICKS_DIR, asset, f"DAT_ASCII_{asset}_T_{yyyymm}.zip")
        return p if os.path.exists(p) else None

    if asset == "XAUUSD":
        candidates = [
            os.path.join(XAU_TICKS_DIR, f"HISTDATA_COM_ASCII_XAUUSD_T{yyyymm}.zip"),
            os.path.join(XAU_TICKS_DIR, f"HISTDATA_COM_ASCII_XAUUSD_T{yyyymm} (1).zip"),
            os.path.join(XAU_TICKS_DIR, f"HISTDATA_COM_ASCII_XAUUSD_T{yyyymm} (2).zip"),
            os.path.join(XAU_TICKS_DIR, f"HISTDATA_COM_ASCII_XAUUSD_T{yyyymm} (3).zip"),
        ]
        for p in candidates:
            if os.path.exists(p):
                return p
    return None


@lru_cache(maxsize=96)
def load_tick_month(asset: str, yyyymm: str) -> pd.DataFrame:
    parquet_path = os.path.join(
        UNIVERSE_TICKS_PARQUET,
        asset,
        f"year={yyyymm[:4]}",
        f"month={int(yyyymm[4:])}",
        f"ticks_{asset}_{yyyymm}.parquet",
    )
    if os.path.exists(parquet_path):
        try:
            pq.ParquetFile(parquet_path)
            df = pd.read_parquet(parquet_path, columns=["timestamp", "bid", "ask"])
        except Exception:
            return pd.DataFrame(columns=["bid", "ask"])
        df = df.drop_duplicates("timestamp").sort_values("timestamp")
        return df.set_index("timestamp")[["bid", "ask"]]
    if asset in {"NSXUSD", "XAGUSD"}:
        return pd.DataFrame(columns=["bid", "ask"])

    if asset == "XAUUSD":
        xau_parquet = os.path.join(
            ROOT,
            "gold_data_parquet",
            f"year={yyyymm[:4]}",
            f"month={int(yyyymm[4:])}",
            f"part_histdata_{yyyymm}_0.parquet",
        )
        if os.path.exists(xau_parquet):
            df = pd.read_parquet(xau_parquet, columns=["timestamp", "bid", "ask"])
            df = df.drop_duplicates("timestamp").sort_values("timestamp")
            return df.set_index("timestamp")[["bid", "ask"]]

    path = _tick_zip_path(asset, yyyymm)
    if path is None:
        return pd.DataFrame(columns=["bid", "ask"])

    with zipfile.ZipFile(path) as zf:
        csv_name = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        name = csv_name[0] if csv_name else zf.namelist()[0]
        with zf.open(name) as fh:
            df = pd.read_csv(
                fh,
                header=None,
                names=["timestamp", "bid", "ask", "volume"],
                usecols=[0, 1, 2],
            )

    df["timestamp"] = pd.to_datetime(df["timestamp"], format="%Y%m%d %H%M%S%f", errors="coerce")
    df = df.dropna(subset=["timestamp", "bid", "ask"])
    df = df.drop_duplicates("timestamp").sort_values("timestamp")
    df = df.set_index("timestamp")[["bid", "ask"]]
    return df


def get_ticks(asset: str, start, end) -> pd.DataFrame:
    start = pd.Timestamp(start)
    end = pd.Timestamp(end)
    months = pd.period_range(start.to_period("M"), end.to_period("M"), freq="M")
    frames = [load_tick_month(asset, f"{p.year}{p.month:02d}") for p in months]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["bid", "ask"])
    ticks = pd.concat(frames).sort_index()
    return ticks.loc[(ticks.index >= start) & (ticks.index < end)]


def _pnl_money(price_diff: float, lot: float, tick_value: float, tick_size: float) -> float:
    return price_diff * lot * (tick_value / tick_size)


def _first_tick_at_or_after_from(ticks: pd.DataFrame, ts: pd.Timestamp) -> pd.Series  None:
    if ticks.empty:
        return None
    pos = ticks.index.searchsorted(pd.Timestamp(ts), side="left")
    if pos >= len(ticks):
        return None
    return ticks.iloc[pos]


def _tick_window(ticks: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    if ticks.empty:
        return ticks
    left = ticks.index.searchsorted(pd.Timestamp(start), side="left")
    right = ticks.index.searchsorted(pd.Timestamp(end), side="left")
    return ticks.iloc[left:right]


def replay_trade_on_ticks(
    asset: str,
    trade: pd.Series,
    signals: pd.DataFrame,
    cfg: BacktestAssumptions,
    sl_mult: float,
) -> dict:
    entry_i = int(trade["entry_i"])
    exit_i = int(trade["exit_i"])
    side = str(trade["side"])
    entry_time = pd.Timestamp(trade["entry_time"])
    exit_time = pd.Timestamp(trade["exit_time"])

    trade_ticks = get_ticks(asset, entry_time, exit_time + pd.Timedelta(minutes=15))
    if trade_ticks.empty:
        return {"tick_status": "NO_TICKS_IN_TRADE_WINDOW"}

    entry_tick = _first_tick_at_or_after_from(trade_ticks, entry_time)
    if entry_tick is None:
        return {"tick_status": "NO_ENTRY_TICK"}

    entry_price = float(entry_tick["ask"] if side == "BUY" else entry_tick["bid"])
    atr_i = float(signals["ATR_14"].shift(1).iloc[entry_i])
    atr_i = max(atr_i, 1e-6)
    sl_dist = sl_mult * atr_i
    stop_loss = entry_price - sl_dist if side == "BUY" else entry_price + sl_dist
    initial_lot = float(trade.get("initial_lot", trade.get("lot", 0.0)))
    current_lot = initial_lot
    partial_done = False
    balance_delta = 0.0
    cashflows = []

    for bar_i in range(entry_i + 1, min(exit_i + 2, len(signals))):
        bar_time = pd.Timestamp(signals.index[bar_i])
        next_time = pd.Timestamp(signals.index[bar_i + 1]) if bar_i + 1 < len(signals) else bar_time + pd.Timedelta(minutes=15)
        open_tick = _first_tick_at_or_after_from(trade_ticks, bar_time)
        regime = int(signals["Regime_Buffer_18"].shift(1).iloc[bar_i])
        current_kalman = float(signals["Kalman_Precio_Medio"].shift(1).iloc[bar_i])

        if regime != 0 and open_tick is not None:
            exit_price = float(open_tick["bid"] if side == "BUY" else open_tick["ask"])
            reason = "REGIME_CHANGE"
            price_diff = exit_price - entry_price if side == "BUY" else entry_price - exit_price
            pnl = _pnl_money(price_diff, current_lot, cfg.tick_value, cfg.tick_size)
            pnl -= current_lot * 2.0 * cfg.commission_per_lot
            balance_delta += pnl
            cashflows.append((bar_time, "final", pnl))
            return {
                "tick_status": "OK",
                "tick_entry_time": entry_tick.name,
                "tick_exit_time": bar_time,
                "tick_entry_price": entry_price,
                "tick_exit_price": exit_price,
                "tick_pnl": balance_delta,
                "tick_reason": reason,
                "tick_cashflows": len(cashflows),
            }

        ticks = _tick_window(trade_ticks, bar_time, next_time)
        if ticks.empty:
            continue

        def first_true(mask: np.ndarray) -> int  None:
            hits = np.flatnonzero(mask)
            return int(hits[0]) if len(hits) else None

        if side == "BUY":
            prices = ticks["bid"].to_numpy(dtype=float)
            idx = ticks.index
            partial_target = entry_price + max((current_kalman - entry_price) * 0.50, cfg.point)

            sl_pos = first_true(prices <= stop_loss)
            tp_pos = first_true(prices >= current_kalman)
            partial_pos = None
            if (not partial_done) and current_kalman > entry_price:
                partial_pos = first_true(prices >= partial_target)

            events = [(p, name) for p, name in [(sl_pos, "SL"), (partial_pos, "PARTIAL"), (tp_pos, "TP")] if p is not None]
            if not events:
                continue
            pos, event = min(events, key=lambda x: x[0])

            if event == "PARTIAL":
                closed_lot = round((current_lot * 0.50) / cfg.lot_step) * cfg.lot_step
                closed_lot = round(closed_lot, 4)
                remaining_lot = round(current_lot - closed_lot, 4)
                if closed_lot >= cfg.min_lot and remaining_lot >= cfg.min_lot:
                    exit_price = float(prices[pos])
                    pnl = _pnl_money(exit_price - entry_price, closed_lot, cfg.tick_value, cfg.tick_size)
                    pnl -= closed_lot * 2.0 * cfg.commission_per_lot
                    balance_delta += pnl
                    cashflows.append((idx[pos], "partial", pnl))
                    current_lot = remaining_lot
                    stop_loss = entry_price
                    partial_done = True

                    rest_prices = prices[pos + 1:]
                    rest_idx = idx[pos + 1:]
                    be_pos = first_true(rest_prices <= stop_loss)
                    tp2_pos = first_true(rest_prices >= current_kalman)
                    rest_events = [(p, name) for p, name in [(be_pos, "BE_AFTER_PARTIAL"), (tp2_pos, "TP")] if p is not None]
                    if not rest_events:
                        continue
                    rpos, reason = min(rest_events, key=lambda x: x[0])
                    exit_price = float(rest_prices[rpos])
                    pnl = _pnl_money(exit_price - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
                    pnl -= current_lot * 2.0 * cfg.commission_per_lot
                    balance_delta += pnl
                    cashflows.append((rest_idx[rpos], "final", pnl))
                    return {
                        "tick_status": "OK",
                        "tick_entry_time": entry_tick.name,
                        "tick_exit_time": rest_idx[rpos],
                        "tick_entry_price": entry_price,
                        "tick_exit_price": exit_price,
                        "tick_pnl": balance_delta,
                        "tick_reason": reason,
                        "tick_cashflows": len(cashflows),
                    }
                continue

            exit_price = float(prices[pos])
            reason = "SL" if event == "SL" and not partial_done else event
            pnl = _pnl_money(exit_price - entry_price, current_lot, cfg.tick_value, cfg.tick_size)
            pnl -= current_lot * 2.0 * cfg.commission_per_lot
            balance_delta += pnl
            cashflows.append((idx[pos], "final", pnl))
            return {
                "tick_status": "OK",
                "tick_entry_time": entry_tick.name,
                "tick_exit_time": idx[pos],
                "tick_entry_price": entry_price,
                "tick_exit_price": exit_price,
                "tick_pnl": balance_delta,
                "tick_reason": reason,
                "tick_cashflows": len(cashflows),
            }

        prices = ticks["ask"].to_numpy(dtype=float)
        idx = ticks.index
        partial_target = entry_price - max((entry_price - current_kalman) * 0.50, cfg.point)

        sl_pos = first_true(prices >= stop_loss)
        tp_pos = first_true(prices <= current_kalman)
        partial_pos = None
        if (not partial_done) and current_kalman < entry_price:
            partial_pos = first_true(prices <= partial_target)

        events = [(p, name) for p, name in [(sl_pos, "SL"), (partial_pos, "PARTIAL"), (tp_pos, "TP")] if p is not None]
        if not events:
            continue
        pos, event = min(events, key=lambda x: x[0])

        if event == "PARTIAL":
            closed_lot = round((current_lot * 0.50) / cfg.lot_step) * cfg.lot_step
            closed_lot = round(closed_lot, 4)
            remaining_lot = round(current_lot - closed_lot, 4)
            if closed_lot >= cfg.min_lot and remaining_lot >= cfg.min_lot:
                exit_price = float(prices[pos])
                pnl = _pnl_money(entry_price - exit_price, closed_lot, cfg.tick_value, cfg.tick_size)
                pnl -= closed_lot * 2.0 * cfg.commission_per_lot
                balance_delta += pnl
                cashflows.append((idx[pos], "partial", pnl))
                current_lot = remaining_lot
                stop_loss = entry_price
                partial_done = True

                rest_prices = prices[pos + 1:]
                rest_idx = idx[pos + 1:]
                be_pos = first_true(rest_prices >= stop_loss)
                tp2_pos = first_true(rest_prices <= current_kalman)
                rest_events = [(p, name) for p, name in [(be_pos, "BE_AFTER_PARTIAL"), (tp2_pos, "TP")] if p is not None]
                if not rest_events:
                    continue
                rpos, reason = min(rest_events, key=lambda x: x[0])
                exit_price = float(rest_prices[rpos])
                pnl = _pnl_money(entry_price - exit_price, current_lot, cfg.tick_value, cfg.tick_size)
                pnl -= current_lot * 2.0 * cfg.commission_per_lot
                balance_delta += pnl
                cashflows.append((rest_idx[rpos], "final", pnl))
                return {
                    "tick_status": "OK",
                    "tick_entry_time": entry_tick.name,
                    "tick_exit_time": rest_idx[rpos],
                    "tick_entry_price": entry_price,
                    "tick_exit_price": exit_price,
                    "tick_pnl": balance_delta,
                    "tick_reason": reason,
                    "tick_cashflows": len(cashflows),
                }
            continue

        exit_price = float(prices[pos])
        reason = "SL" if event == "SL" and not partial_done else event
        pnl = _pnl_money(entry_price - exit_price, current_lot, cfg.tick_value, cfg.tick_size)
        pnl -= current_lot * 2.0 * cfg.commission_per_lot
        balance_delta += pnl
        cashflows.append((idx[pos], "final", pnl))
        return {
            "tick_status": "OK",
            "tick_entry_time": entry_tick.name,
            "tick_exit_time": idx[pos],
            "tick_entry_price": entry_price,
            "tick_exit_price": exit_price,
            "tick_pnl": balance_delta,
            "tick_reason": reason,
            "tick_cashflows": len(cashflows),
        }

    last_tick = _tick_window(trade_ticks, exit_time, exit_time + pd.Timedelta(minutes=15))
    if last_tick.empty:
        return {"tick_status": "NO_EXIT_TICK"}
    row = last_tick.iloc[0]
    exit_price = float(row["bid"] if side == "BUY" else row["ask"])
    pnl = _pnl_money(exit_price - entry_price if side == "BUY" else entry_price - exit_price, current_lot, cfg.tick_value, cfg.tick_size)
    pnl -= current_lot * 2.0 * cfg.commission_per_lot
    balance_delta += pnl
    return {
        "tick_status": "FORCED_EXIT",
        "tick_entry_time": entry_tick.name,
        "tick_exit_time": last_tick.index[0],
        "tick_entry_price": entry_price,
        "tick_exit_price": exit_price,
        "tick_pnl": balance_delta,
        "tick_reason": "FORCED_EXIT",
        "tick_cashflows": len(cashflows) + 1,
    }


def audit_asset(asset: str, limit: int  None = None) -> dict:
    if asset not in ASSETS:
        raise ValueError(asset)

    z_l, z_s, sl_mult = MR_PARAMS[asset]
    cfg = build_assumptions(ASSETS[asset])
    signals_path = os.path.join(RESULTS_DIR, f"{asset}_mr_signals_OOS.csv")
    trades_path = os.path.join(RESULTS_DIR, asset, f"{asset}_mr_trades_OOS.csv")

    if not os.path.exists(signals_path) or not os.path.exists(trades_path):
        return {"asset": asset, "status": "MISSING_MR_RESULTS"}

    signals = pd.read_csv(signals_path, index_col=0, parse_dates=True)
    trades = pd.read_csv(trades_path, parse_dates=["entry_time", "exit_time"])
    total_trades = len(trades)
    if limit is not None and limit > 0:
        trades = trades.head(limit).copy()
    rows = []
    for _, trade in trades.iterrows():
        replay = replay_trade_on_ticks(asset, trade, signals, cfg, sl_mult)
        row = trade.to_dict()
        row.update(replay)
        rows.append(row)

    out_dir = os.path.join(RESULTS_DIR, asset)
    os.makedirs(out_dir, exist_ok=True)
    audit = pd.DataFrame(rows)
    audit_path = os.path.join(out_dir, f"{asset}_mr_tick_audit_OOS.csv")
    audit.to_csv(audit_path, index=False)

    ok = audit[audit["tick_status"].isin(["OK", "FORCED_EXIT"])].copy()
    summary = {
        "asset": asset,
        "status": "OK" if len(ok) else "NO_TICK_REPLAYS",
        "trades_ohlc": int(len(trades)),
        "trades_ohlc_total_available": int(total_trades),
        "trades_tick_replayed": int(len(ok)),
        "missing_or_failed": int(len(audit) - len(ok)),
        "ohlc_pnl": float(trades["pnl"].sum()) if not trades.empty else 0.0,
        "tick_pnl": float(ok["tick_pnl"].sum()) if len(ok) else 0.0,
        "pnl_delta_tick_minus_ohlc": float(ok["tick_pnl"].sum() - trades.loc[ok.index, "pnl"].sum()) if len(ok) else 0.0,
        "ohlc_win_rate_pct": float((trades["pnl"] > 0).mean() * 100.0) if len(trades) else 0.0,
        "tick_win_rate_pct": float((ok["tick_pnl"] > 0).mean() * 100.0) if len(ok) else 0.0,
        "tick_audit_path": audit_path,
    }
    return summary


def write_report(summaries: list[dict]) -> str:
    path = os.path.join(ROOT, "SUB_RAMA_MEAN_REVERSION", "REPORTE_TICK_LEVEL_MR.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Auditoria Tick-Level Mean Reversion OOS\n\n")
        fh.write("Reejecucion de trades MR robustos usando ticks bid/ask reales. Las decisiones de regimen y objetivos Kalman permanecen en M15; el orden intrabar de SL/parcial/TP se resuelve con ticks.\n\n")
        fh.write(" Activo  Estado  Trades Auditados  Total Disponible  Trades Tick  Fallidos  PnL OHLC  PnL Tick  Delta  Win OHLC  Win Tick \n")
        fh.write(" :---  :---  ---:  ---:  ---:  ---:  ---:  ---:  ---:  ---:  ---: \n")
        for s in summaries:
            fh.write(
                f" {s['asset']}  {s['status']}  {s.get('trades_ohlc', 0)}  {s.get('trades_ohlc_total_available', 0)}  {s.get('trades_tick_replayed', 0)}  {s.get('missing_or_failed', 0)}  "
                f"${s.get('ohlc_pnl', 0.0):.2f}  ${s.get('tick_pnl', 0.0):.2f}  ${s.get('pnl_delta_tick_minus_ohlc', 0.0):.2f}  "
                f"{s.get('ohlc_win_rate_pct', 0.0):.2f}%  {s.get('tick_win_rate_pct', 0.0):.2f}% \n"
            )
        fh.write("\n## Notas\n\n")
        fh.write("- NSXUSD y XAGUSD usan ticks desde `Universo de activos/Datos_Crudos_Zip`.\n")
        fh.write("- XAUUSD no esta en esa carpeta; se usa `gold_data_parquet/Datos__Crudos 2024_2026` si el archivo mensual existe.\n")
        fh.write("- Esta auditoria valida microestructura de ejecucion; no reentrena HMM/Kalman sobre barras de rango o volumen.\n")
    return path


def main():
    limit = None
    args = []
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        else:
            args.append(sys.argv[i])
            i += 1
    requested = args if args else ["NSXUSD", "XAGUSD", "XAUUSD"]
    summaries = []
    for asset in requested:
        print(f"[*] Tick audit {asset}", flush=True)
        summary = audit_asset(asset, limit=limit)
        summaries.append(summary)
        print(summary, flush=True)

    summary_df = pd.DataFrame(summaries)
    summary_path = os.path.join(RESULTS_DIR, "MR_TICK_AUDIT_SUMMARY.csv")
    summary_df.to_csv(summary_path, index=False)
    report_path = write_report(summaries)
    print(f"[+] Summary: {summary_path}")
    print(f"[+] Report: {report_path}")


if __name__ == "__main__":
    main()
