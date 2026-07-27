"""Direction and entry/exit policies for Trend V2."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DirectionMode, SignalConfig, SlowTrendConfig


@dataclass(frozen=True)
class SignalState:
    """State carried across consecutive OOS chunks."""

    active_episode: bool = False
    confirmation_count: int = 0
    episode_consumed: bool = False
    logical_position: int = 0


def _completed_h1_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Aggregate only complete UTC hours, labelled at the final M15 close.

    Missing or duplicated quarter-hours invalidate that hour. No interpolation
    or backward fill is allowed, so incomplete hours cannot see later bars.
    """

    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is None:
        raise ValueError("slow trend requires an explicit timezone-aware DatetimeIndex")
    if str(bars.index.tz).upper() != "UTC":
        raise ValueError("slow trend requires UTC bars")
    required = {"open", "high", "low", "close"}
    missing = required.difference(bars.columns)
    if missing:
        raise ValueError(f"slow trend missing OHLC columns: {sorted(missing)}")
    if not bars.index.is_monotonic_increasing or bars.index.has_duplicates:
        raise ValueError("slow trend requires unique increasing M15 bars")

    frame = bars.loc[:, ["open", "high", "low", "close"]].copy()
    frame["hour"] = frame.index.floor("h")
    frame["minute"] = frame.index.minute
    rows: list[dict[str, object]] = []
    expected = (0, 15, 30, 45)
    for _, group in frame.groupby("hour", sort=True):
        minutes = tuple(int(value) for value in group["minute"].to_numpy())
        if len(group) != 4 or minutes != expected:
            continue
        rows.append(
            {
                "timestamp": group.index[-1],
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
            }
        )
    if not rows:
        empty_index = pd.DatetimeIndex([], tz="UTC", name="timestamp")
        return pd.DataFrame(columns=["open", "high", "low", "close"], index=empty_index)
    return pd.DataFrame(rows).set_index("timestamp")


def build_slow_trend_features(
    bars: pd.DataFrame,
    config: SlowTrendConfig  None = None,
) -> pd.DataFrame:
    """Map completed-H1 slow momentum features onto their final M15 bar."""

    cfg = config or SlowTrendConfig()
    hourly = _completed_h1_bars(bars)
    out = bars.copy()
    for column in (
        "slow_momentum_score",
        "slow_atr_h1",
        "slow_vol_h1",
        "realized_vol_slow",
        "atr",
    ):
        out[column] = np.nan
    out["slow_decision"] = False
    if hourly.empty:
        return out

    log_close = np.log(hourly["close"].astype(float))
    log_return = log_close.diff()
    vol = log_return.rolling(
        cfg.volatility_window_h1, min_periods=cfg.volatility_window_h1
    ).std(ddof=1)
    scores = [
        log_close.diff(horizon) / (vol * np.sqrt(horizon) + 1e-12)
        for horizon in cfg.momentum_horizons_h1
    ]
    score = pd.concat(scores, axis=1).median(axis=1, skipna=False)
    previous_close = hourly["close"].shift(1)
    true_range = pd.concat(
        [
            hourly["high"] - hourly["low"],
            (hourly["high"] - previous_close).abs(),
            (hourly["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.rolling(cfg.atr_window_h1, min_periods=cfg.atr_window_h1).mean()
    valid_index = hourly.index.intersection(out.index)
    out.loc[valid_index, "slow_momentum_score"] = score.reindex(valid_index).to_numpy(float)
    out.loc[valid_index, "slow_atr_h1"] = atr.reindex(valid_index).to_numpy(float)
    out.loc[valid_index, "slow_vol_h1"] = vol.reindex(valid_index).to_numpy(float)
    # Existing sizing annualises M15. H1 sigma / sqrt(4) is the equivalent M15 scale.
    out.loc[valid_index, "realized_vol_slow"] = vol.reindex(valid_index).to_numpy(float) / 2.0
    out.loc[valid_index, "atr"] = atr.reindex(valid_index).to_numpy(float)
    out.loc[valid_index, "slow_decision"] = True
    return out


def generate_slow_trend_signals(
    features: pd.DataFrame,
    config: SlowTrendConfig  None = None,
) -> pd.DataFrame:
    """Generate long-only H18 signals with confirmation, hysteresis and rearm."""

    cfg = config or SlowTrendConfig()
    required = {"slow_momentum_score", "slow_decision", "slow_atr_h1", "slow_vol_h1"}
    missing = required.difference(features.columns)
    if missing:
        raise ValueError(f"slow trend features missing columns: {sorted(missing)}")
    out = features.copy()
    entries = np.zeros(len(out), dtype=np.int8)
    exits = np.zeros(len(out), dtype=bool)
    positions = np.zeros(len(out), dtype=np.int8)
    confirmations = np.zeros(len(out), dtype=np.int16)
    held_h1 = np.zeros(len(out), dtype=np.int32)
    armed_values = np.zeros(len(out), dtype=bool)
    reasons = np.full(len(out), "", dtype=object)

    armed = True
    confirmation = 0
    position = 0
    holding = 0
    score_values = out["slow_momentum_score"].to_numpy(float)
    decisions = out["slow_decision"].fillna(False).to_numpy(bool)
    atr_values = out["slow_atr_h1"].to_numpy(float)
    vol_values = out["slow_vol_h1"].to_numpy(float)
    for row in range(len(out)):
        score = score_values[row]
        valid_decision = bool(
            decisions[row]
            and np.isfinite(score)
            and np.isfinite(atr_values[row])
            and atr_values[row] > 0.0
            and np.isfinite(vol_values[row])
            and vol_values[row] > 0.0
        )
        if valid_decision:
            if position == 1:
                holding += 1
                if holding >= cfg.minimum_holding_h1 and score <= cfg.exit_threshold:
                    exits[row] = True
                    reasons[row] = "slow_momentum_exit"
                    position = 0
                    holding = 0
                    armed = False
                    confirmation = 0
            else:
                if not armed and score <= cfg.rearm_threshold:
                    armed = True
                    confirmation = 0
                if armed:
                    confirmation = confirmation + 1 if score >= cfg.entry_threshold else 0
                    if confirmation >= cfg.confirmation_closes:
                        entries[row] = 1
                        reasons[row] = "slow_confirmed_entry"
                        position = 1
                        holding = 0
                        armed = False
                        confirmation = 0
        positions[row] = position
        confirmations[row] = confirmation
        held_h1[row] = holding
        armed_values[row] = armed
    out["entry_signal"] = entries
    out["exit_signal"] = exits
    out["logical_position"] = positions
    out["slow_confirmation_count"] = confirmations
    out["slow_holding_h1"] = held_h1
    out["slow_armed"] = armed_values
    out["signal_reason"] = reasons
    return out


def _allowed_direction(score: float, threshold: float, mode: DirectionMode) -> int:
    if not np.isfinite(score) or abs(score) < threshold:
        return 0
    direction = 1 if score > 0.0 else -1
    if mode == "long" and direction < 0:
        return 0
    if mode == "short" and direction > 0:
        return 0
    return direction


def generate_trend_signals(
    transformed: pd.DataFrame,
    config: SignalConfig  None = None,
    initial_state: SignalState  None = None,
) -> pd.DataFrame:
    """Generate one entry per confirmed TRENDABLE episode.

    The confirmation bar is the only possible entry bar for the episode. Once
    consumed, a stop or momentum exit cannot re-arm the strategy until the
    filtered regime first leaves TRENDABLE. This is the explicit no-reentry
    invariant.
    """

    cfg = config or SignalConfig()
    if cfg.confirmation_bars < 1:
        raise ValueError("confirmation_bars must be at least one")
    required = {"p_trendable", "p_range", "p_shock", "momentum_score"}
    missing = required.difference(transformed.columns)
    if missing:
        raise ValueError(f"Missing transformed columns: {sorted(missing)}")

    out = transformed.copy()
    entries = np.zeros(len(out), dtype=np.int8)
    exits = np.zeros(len(out), dtype=bool)
    active_values = np.zeros(len(out), dtype=bool)
    confirmation_values = np.zeros(len(out), dtype=np.int16)
    consumed_values = np.zeros(len(out), dtype=bool)
    logical_positions = np.zeros(len(out), dtype=np.int8)
    reasons = np.full(len(out), "", dtype=object)
    regime_names = np.full(len(out), "UNAVAILABLE", dtype=object)

    state = initial_state or SignalState()
    active_episode = bool(state.active_episode)
    confirmation_count = int(state.confirmation_count)
    episode_consumed = bool(state.episode_consumed)
    logical_position = int(state.logical_position)

    probability_columns = ["p_trendable", "p_range", "p_shock"]
    probabilities = out[probability_columns].to_numpy(dtype=float)
    momentum = out["momentum_score"].to_numpy(dtype=float)

    for row in range(len(out)):
        probability = probabilities[row]
        valid = bool(np.isfinite(probability).all() and np.isfinite(momentum[row]))
        if valid:
            winning_state = int(np.argmax(probability))
            regime_names[row] = ("TRENDABLE", "RANGE", "SHOCK")[winning_state]
            currently_active = bool(
                winning_state == 0
                and probability[0] >= cfg.trend_probability
                and probability[2] <= cfg.maximum_shock_probability
            )
        else:
            currently_active = False

        if not currently_active:
            if logical_position != 0:
                exits[row] = True
                reasons[row] = "regime_exit"
                logical_position = 0
            active_episode = False
            confirmation_count = 0
            episode_consumed = False
        else:
            if not active_episode:
                active_episode = True
                confirmation_count = 1
                episode_consumed = False
            else:
                confirmation_count += 1

            # Entry is allowed exactly once, at the confirmation boundary.
            if confirmation_count == cfg.confirmation_bars and not episode_consumed:
                direction = _allowed_direction(
                    momentum[row], cfg.momentum_threshold, cfg.direction_mode
                )
                episode_consumed = True
                if direction != 0:
                    entries[row] = direction
                    logical_position = direction
                    reasons[row] = "confirmed_transition"

            if logical_position != 0 and cfg.exit_on_momentum_flip:
                direction_now = _allowed_direction(
                    momentum[row], cfg.momentum_threshold, "both"
                )
                if direction_now == -logical_position:
                    exits[row] = True
                    entries[row] = 0
                    logical_position = 0
                    reasons[row] = "momentum_flip"
                    # episode_consumed remains true: no re-entry.

        active_values[row] = currently_active
        confirmation_values[row] = confirmation_count
        consumed_values[row] = episode_consumed
        logical_positions[row] = logical_position

    out["regime_state"] = regime_names
    out["trend_active"] = active_values
    out["confirmation_count"] = confirmation_values
    out["episode_consumed"] = consumed_values
    out["entry_signal"] = entries
    out["exit_signal"] = exits
    out["logical_position"] = logical_positions
    out["signal_reason"] = reasons
    out.attrs["final_signal_state"] = SignalState(
        active_episode=active_episode,
        confirmation_count=confirmation_count,
        episode_consumed=episode_consumed,
        logical_position=logical_position,
    )
    return out


def generate_momentum_benchmark_signals(
    features: pd.DataFrame,
    threshold: float = 0.20,
    direction_mode: DirectionMode = "both",
) -> pd.DataFrame:
    """Simple time-series momentum benchmark without a regime model."""

    if "momentum_score" not in features.columns:
        raise ValueError("features must contain momentum_score")
    out = features.copy()
    momentum = out["momentum_score"].to_numpy(dtype=float)
    entries = np.zeros(len(out), dtype=np.int8)
    exits = np.zeros(len(out), dtype=bool)
    positions = np.zeros(len(out), dtype=np.int8)
    position = 0
    for row, score in enumerate(momentum):
        desired = _allowed_direction(score, threshold, direction_mode)
        if desired != position:
            if position != 0:
                exits[row] = True
            if desired != 0:
                entries[row] = desired
            position = desired
        positions[row] = position
    out["entry_signal"] = entries
    out["exit_signal"] = exits
    out["logical_position"] = positions
    out["signal_reason"] = np.where(entries != 0, "momentum_transition", "")
    return out


def generate_momentum_benchmarks(
    features: pd.DataFrame,
    threshold: float = 0.20,
) -> dict[str, pd.DataFrame]:
    """Preregistered comparators used to test incremental HMM value."""

    return {
        "momentum_long_only": generate_momentum_benchmark_signals(
            features, threshold=threshold, direction_mode="long"
        ),
        "momentum_long_short": generate_momentum_benchmark_signals(
            features, threshold=threshold, direction_mode="both"
        ),
    }
