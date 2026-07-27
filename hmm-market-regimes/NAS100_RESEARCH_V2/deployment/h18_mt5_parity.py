"""Independent Python/MQL parity audit for the two frozen H18 demo EAs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from NAS100_RESEARCH_V2.trend_v2.config import SlowTrendConfig
from NAS100_RESEARCH_V2.trend_v2.signals import (
    build_slow_trend_features,
    generate_slow_trend_signals,
)
from NAS100_RESEARCH_V2.risk import (
    InstitutionalRiskGovernor,
    InstrumentSpec,
    RiskSnapshot,
)


H18_BY_MAGIC: dict[int, dict[str, Any]] = {
    6001: {
        "candidate_id": "TREND_10_MEDIUM_LONG",
        "momentum_horizons_h1": (12, 24, 48),
        "stop_atr_multiple": 6.0,
    },
    6002: {
        "candidate_id": "TREND_11_ULTRASLOW_LONG",
        "momentum_horizons_h1": (24, 48, 96),
        "stop_atr_multiple": 6.0,
    },
}

DECISION_COLUMNS = (
    "decision_utc_time",
    "score",
    "atr_h1",
    "vol_h1",
    "entry_signal",
    "exit_signal",
)

RISK_COLUMNS = (
    "magic",
    "approved",
    "reason",
    "volume",
    "executive_stop",
    "disaster_stop",
    "requested_risk_cash",
    "authorized_risk_cash",
    "existing_portfolio_risk_cash",
    "throttle",
)

RISK_INPUT_COLUMNS = (
    "entry_price", "atr_h1", "vol_h1", "equity", "balance", "free_margin",
    "margin_level_pct", "day_start_equity", "high_water_equity", "tick_size",
    "tick_value", "volume_min", "volume_max", "volume_step", "margin_per_lot",
    "maximum_volume",
)


def _require_magic(magic: int) -> dict[str, Any]:
    try:
        return H18_BY_MAGIC[int(magic)]
    except KeyError as exc:
        raise ValueError(f"unsupported H18 magic: {magic}") from exc


def load_bars(path: str  Path) -> pd.DataFrame:
    source = Path(path)
    if source.suffix.lower() in {".parquet", ".pq"}:
        bars = pd.read_parquet(source)
    else:
        bars = pd.read_csv(source)
        time_column = next(
            (name for name in ("time", "timestamp", "datetime", "date") if name in bars.columns),
            None,
        )
        if time_column is None:
            raise ValueError("CSV bars require time/timestamp/datetime/date column")
        bars.index = pd.to_datetime(bars.pop(time_column), utc=True, errors="raise")
    if not isinstance(bars.index, pd.DatetimeIndex):
        raise TypeError("bars require a DatetimeIndex")
    if bars.index.tz is None:
        raise ValueError("bars timezone must be explicit UTC")
    bars = bars.copy()
    bars.index = bars.index.tz_convert("UTC")
    bars.columns = [str(column).strip().lower() for column in bars.columns]
    required = {"open", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"bars missing OHLC columns: {sorted(missing)}")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("bars must be unique and increasing")
    return bars


def python_h18_decisions(
    bars: pd.DataFrame,
    *,
    magic: int,
    start_utc: str  pd.Timestamp,
) -> pd.DataFrame:
    """Generate the golden-reference decisions from a flat, armed start state."""

    spec = _require_magic(magic)
    start = pd.Timestamp(start_utc)
    if start.tzinfo is None:
        raise ValueError("start_utc must be timezone-aware")
    start = start.tz_convert("UTC")
    cfg = SlowTrendConfig(momentum_horizons_h1=spec["momentum_horizons_h1"])
    features = build_slow_trend_features(bars, cfg)
    # Feature context is retained, while signal state intentionally begins at
    # the recorded EA incubation start, matching a fresh MQL GlobalVariable set.
    incubation = features.loc[features.index >= start].copy()
    signals = generate_slow_trend_signals(incubation, cfg)
    decisions = signals.loc[signals["slow_decision"]].copy()
    result = pd.DataFrame(
        {
            "decision_utc_time": decisions.index,
            "score": decisions["slow_momentum_score"].to_numpy(float),
            "atr_h1": decisions["slow_atr_h1"].to_numpy(float),
            "vol_h1": decisions["slow_vol_h1"].to_numpy(float),
            "entry_signal": decisions["entry_signal"].to_numpy(int),
            "exit_signal": decisions["exit_signal"].astype(int).to_numpy(),
        }
    )
    return result.loc[:, DECISION_COLUMNS].reset_index(drop=True)


def load_mt5_decisions(path: str  Path, *, magic: int) -> pd.DataFrame:
    _require_magic(magic)
    frame = pd.read_csv(path)
    required = {
        "magic",
        "decision_utc_time",
        "score",
        "atr_h1",
        "vol_h1",
        "entry_signal",
        "exit_signal",
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"MT5 signal log missing columns: {sorted(missing)}")
    if set(pd.to_numeric(frame["magic"], errors="raise").astype(int)) != {int(magic)}:
        raise ValueError("MT5 signal log contains an unexpected magic number")
    result = frame.copy()
    result["decision_utc_time"] = pd.to_datetime(
        result["decision_utc_time"], utc=True, errors="raise"
    )
    for column in ("score", "atr_h1", "vol_h1"):
        result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
    for column in ("entry_signal", "exit_signal"):
        result[column] = pd.to_numeric(result[column], errors="raise").astype(int)
    return result.loc[:, DECISION_COLUMNS].reset_index(drop=True)


def compare_h18_decisions(
    python_decisions: pd.DataFrame,
    mt5_decisions: pd.DataFrame,
    *,
    score_tolerance: float = 1e-9,
    price_tolerance: float = 0.01,
    volatility_tolerance: float = 1e-10,
) -> dict[str, Any]:
    for label, frame in (("python", python_decisions), ("mt5", mt5_decisions)):
        missing = set(DECISION_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"{label} decisions missing columns: {sorted(missing)}")
    left = python_decisions.loc[:, DECISION_COLUMNS].reset_index(drop=True).copy()
    right = mt5_decisions.loc[:, DECISION_COLUMNS].reset_index(drop=True).copy()
    for frame in (left, right):
        frame["decision_utc_time"] = pd.to_datetime(
            frame["decision_utc_time"], utc=True, errors="raise"
        )
    count_equal = len(left) == len(right)
    time_equal = bool(count_equal and left["decision_utc_time"].equals(right["decision_utc_time"]))
    signal_equal = bool(
        count_equal
        and left[["entry_signal", "exit_signal"]].equals(
            right[["entry_signal", "exit_signal"]]
        )
    )

    def maximum_difference(column: str) -> float:
        if not count_equal:
            return float("inf")
        if len(left) == 0:
            return 0.0
        return float(
            np.max(np.abs(left[column].to_numpy(float) - right[column].to_numpy(float)))
        )

    max_score = maximum_difference("score")
    max_atr = maximum_difference("atr_h1")
    max_vol = maximum_difference("vol_h1")
    result = {
        "decision_count_equal": count_equal,
        "decision_time_parity_100pct": time_equal,
        "entry_exit_signal_parity_100pct": signal_equal,
        "maximum_score_difference": max_score,
        "score_tolerance": float(score_tolerance),
        "maximum_atr_difference": max_atr,
        "atr_tolerance": float(price_tolerance),
        "maximum_volatility_difference": max_vol,
        "volatility_tolerance": float(volatility_tolerance),
    }
    result["approved"] = bool(
        count_equal
        and time_equal
        and signal_equal
        and max_score <= score_tolerance
        and max_atr <= price_tolerance
        and max_vol <= volatility_tolerance
    )
    return result


def load_mt5_risk_decisions(path: str  Path, *, magic: int) -> pd.DataFrame:
    """Load the immutable MQL risk ledger for independent Python replay."""

    _require_magic(magic)
    frame = pd.read_csv(path)
    missing = set(RISK_COLUMNS).difference(frame.columns)
    if missing:
        raise ValueError(f"MT5 risk log missing columns: {sorted(missing)}")
    result = frame.loc[pd.to_numeric(frame["magic"]).astype(int) == magic].copy()
    result["magic"] = magic
    result["approved"] = pd.to_numeric(result["approved"], errors="raise").astype(int)
    result["reason"] = result["reason"].astype(str)
    for column in RISK_COLUMNS[3:]:
        result[column] = pd.to_numeric(result[column], errors="raise").astype(float)
    return result.loc[:, RISK_COLUMNS].reset_index(drop=True)


def replay_mt5_risk_inputs(path: str  Path, *, magic: int) -> pd.DataFrame:
    """Independently recompute MQL authorizations from its immutable inputs."""

    raw = pd.read_csv(path)
    missing = set(RISK_COLUMNS + RISK_INPUT_COLUMNS).difference(raw.columns)
    if missing:
        raise ValueError(f"MT5 risk replay log missing columns: {sorted(missing)}")
    raw = raw.loc[pd.to_numeric(raw["magic"]).astype(int) == magic].reset_index(drop=True)
    governor = InstitutionalRiskGovernor()
    rows: list[dict[str, Any]] = []
    for _, item in raw.iterrows():
        if str(item["reason"]) == "PORTFOLIO_LOCK_BUSY":
            rows.append({column: item[column] for column in RISK_COLUMNS})
            continue
        values = {column: float(item[column]) for column in RISK_INPUT_COLUMNS}
        spec = InstrumentSpec(
            "NAS100.fs", values["tick_size"], values["tick_value"],
            values["volume_min"], values["volume_max"], values["volume_step"],
            max(values["margin_per_lot"], 1e-12),
        )
        decision = governor.authorize_long(
            magic=magic,
            entry_price=values["entry_price"],
            atr_h1=values["atr_h1"],
            vol_h1=values["vol_h1"],
            snapshot=RiskSnapshot(
                values["equity"], values["balance"], values["free_margin"],
                values["margin_level_pct"], values["day_start_equity"],
                values["high_water_equity"],
            ),
            spec=spec,
            maximum_volume=values["maximum_volume"],
            existing_risk_cash_override=float(item["existing_portfolio_risk_cash"]),
        )
        rows.append({
            "magic": magic,
            "approved": int(decision.approved),
            "reason": decision.reason,
            "volume": decision.volume,
            "executive_stop": decision.executive_stop,
            "disaster_stop": decision.disaster_stop,
            "requested_risk_cash": decision.requested_risk_cash,
            "authorized_risk_cash": decision.authorized_risk_cash,
            "existing_portfolio_risk_cash": decision.existing_portfolio_risk_cash,
            "throttle": decision.throttle,
        })
    return pd.DataFrame(rows, columns=RISK_COLUMNS)


def compare_h18_risk_decisions(
    python_risk: pd.DataFrame,
    mt5_risk: pd.DataFrame,
    *,
    volume_tolerance: float = 1e-12,
    price_tolerance: float = 0.01,
    cash_tolerance: float = 0.01,
) -> dict[str, Any]:
    """Require one-for-one risk authorization parity after replaying one feed."""

    for label, frame in (("python", python_risk), ("mt5", mt5_risk)):
        missing = set(RISK_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"{label} risk decisions missing columns: {sorted(missing)}")
    left = python_risk.loc[:, RISK_COLUMNS].reset_index(drop=True)
    right = mt5_risk.loc[:, RISK_COLUMNS].reset_index(drop=True)
    count_equal = len(left) == len(right)
    categorical = bool(
        count_equal
        and left[["magic", "approved", "reason"]].astype(str).equals(
            right[["magic", "approved", "reason"]].astype(str)
        )
    )

    def difference(column: str) -> float:
        if not count_equal:
            return float("inf")
        if len(left) == 0:
            return 0.0
        return float(np.max(np.abs(left[column].to_numpy(float) - right[column].to_numpy(float))))

    differences = {column: difference(column) for column in RISK_COLUMNS[3:]}
    approved = bool(
        count_equal
        and categorical
        and differences["volume"] <= volume_tolerance
        and differences["executive_stop"] <= price_tolerance
        and differences["disaster_stop"] <= price_tolerance
        and differences["requested_risk_cash"] <= cash_tolerance
        and differences["authorized_risk_cash"] <= cash_tolerance
        and differences["existing_portfolio_risk_cash"] <= cash_tolerance
        and differences["throttle"] <= 1e-12
    )
    return {
        "risk_decision_count_equal": count_equal,
        "authorization_reason_parity_100pct": categorical,
        "maximum_differences": differences,
        "approved": approved,
    }


def aggregate_mt5_deals(path: str  Path, *, magic: int) -> pd.DataFrame:
    """Aggregate the EA's immutable deal ledger into parity-ready trades."""

    _require_magic(magic)
    deals = pd.read_csv(path)
    required = {
        "magic",
        "position_id",
        "utc_time",
        "entry_type",
        "deal_type",
        "volume",
        "price",
        "profit",
        "commission",
        "swap",
        "fee",
    }
    missing = required.difference(deals.columns)
    if missing:
        raise ValueError(f"MT5 deal log missing columns: {sorted(missing)}")
    deals = deals.loc[pd.to_numeric(deals["magic"]).astype(int) == int(magic)].copy()
    deals["utc_time"] = pd.to_datetime(deals["utc_time"], utc=True, errors="raise")
    numeric = ("entry_type", "deal_type", "volume", "price", "profit", "commission", "swap", "fee")
    for column in numeric:
        deals[column] = pd.to_numeric(deals[column], errors="raise")
    trades: list[dict[str, Any]] = []
    for position_id, group in deals.groupby("position_id", sort=False):
        group = group.sort_values("utc_time")
        entries = group.loc[group["entry_type"] == 0]
        exits = group.loc[group["entry_type"].isin([1, 2, 3])]
        if entries.empty or exits.empty:
            continue
        entry_volume = float(entries["volume"].sum())
        exit_volume = float(exits["volume"].sum())
        if entry_volume <= 0.0 or exit_volume <= 0.0:
            continue
        side = 1 if int(entries.iloc[0]["deal_type"]) == 0 else -1
        net = float(group[["profit", "commission", "swap", "fee"]].sum().sum())
        trades.append(
            {
                "position_id": int(position_id),
                "entry_time": entries["utc_time"].iloc[0],
                "exit_time": exits["utc_time"].iloc[-1],
                "side": side,
                "entry_price": float(np.average(entries["price"], weights=entries["volume"])),
                "exit_price": float(np.average(exits["price"], weights=exits["volume"])),
                "volume": min(entry_volume, exit_volume),
                "pnl": net,
            }
        )
    return pd.DataFrame(trades)


def _main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars", required=True, type=Path)
    parser.add_argument("--mt5-signals", required=True, type=Path)
    parser.add_argument("--magic", required=True, type=int, choices=sorted(H18_BY_MAGIC))
    parser.add_argument("--start-utc", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mt5-risk", type=Path)
    parser.add_argument("--python-risk", type=Path)
    args = parser.parse_args()
    expected = python_h18_decisions(
        load_bars(args.bars), magic=args.magic, start_utc=args.start_utc
    )
    observed = load_mt5_decisions(args.mt5_signals, magic=args.magic)
    signal_result = compare_h18_decisions(expected, observed)
    risk_result: dict[str, Any] = {
        "approved": False,
        "reason": "MT5_RISK_LEDGER_REQUIRED_FOR_INDEPENDENT_PYTHON_REPLAY",
    }
    if args.mt5_risk is not None:
        if args.python_risk is not None:
            python_risk = pd.read_csv(args.python_risk)
            python_risk = python_risk.loc[
                pd.to_numeric(python_risk["magic"], errors="raise").astype(int) == args.magic
            ].copy()
        else:
            python_risk = replay_mt5_risk_inputs(args.mt5_risk, magic=args.magic)
        risk_result = compare_h18_risk_decisions(
            python_risk, load_mt5_risk_decisions(args.mt5_risk, magic=args.magic)
        )
    result = {
        "signal_approved": bool(signal_result["approved"]),
        "risk_approved": bool(risk_result["approved"]),
        "approved": bool(signal_result["approved"] and risk_result["approved"]),
        "signal_parity": signal_result,
        "risk_parity": risk_result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    _main()
