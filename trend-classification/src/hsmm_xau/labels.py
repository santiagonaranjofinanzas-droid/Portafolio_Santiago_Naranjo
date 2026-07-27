from __future__ import annotations

import numpy as np
import pandas as pd


def triple_barrier_labels(
    frame: pd.DataFrame,
    horizon: int,
    event_z: float = 1.5,
    target_z: float = 0.25,
    stop_z: float = 2.5,
    intrabar: bool = True,
    same_bar_policy: str = "stop_first",
) -> pd.DataFrame:
    """Path-dependent labels; future information is isolated to target columns."""
    z = frame.residual_z.to_numpy(float)
    equilibrium_log = frame.get("equilibrium_log", np.log(frame.mid_close)).to_numpy(float)
    residual_center = frame.get("residual_center", pd.Series(0.0, index=frame.index)).to_numpy(
        float
    )
    residual_scale = frame.get("residual_scale", pd.Series(1.0, index=frame.index)).to_numpy(float)
    spread = frame.get("spread_mean", pd.Series(0.0, index=frame.index)).to_numpy(float)
    mid_open = frame.get("mid_open", frame.mid_close).to_numpy(float)
    mid_close = frame.get("mid_close", frame.mid_close).to_numpy(float)
    mid_high = frame.get("mid_high", frame.mid_close).to_numpy(float)
    mid_low = frame.get("mid_low", frame.mid_close).to_numpy(float)
    bid_open = frame.get("bid_open", frame.mid_close).to_numpy(float)
    ask_open = frame.get("ask_open", frame.mid_close).to_numpy(float)
    bid_close = frame.get("bid_close", frame.mid_close).to_numpy(float)
    ask_close = frame.get("ask_close", frame.mid_close).to_numpy(float)
    n = len(frame)
    label = np.full(n, np.nan)
    exit_offset = np.full(n, np.nan)
    gross = np.full(n, np.nan)
    execution = np.full(n, np.nan)
    observed_cost = np.full(n, np.nan)
    entry_price = np.full(n, np.nan)
    exit_time = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    entry_time = np.full(n, np.datetime64("NaT"), dtype="datetime64[ns]")
    side = np.zeros(n, dtype=np.int8)
    outcome_code = np.full(n, -2, dtype=np.int8)  # TP=1, SL=0, timeout=-1, censored=-2
    candidate = np.zeros(n, dtype=bool)
    observed = np.zeros(n, dtype=bool)
    for i in np.flatnonzero(np.isfinite(z) & (np.abs(z) >= event_z)):
        candidate[i] = True
        if i + horizon >= n or i + 1 >= n:
            continue
        direction = -1 if z[i] > 0 else 1
        side[i] = direction
        entry_price[i] = ask_open[i + 1] if direction == 1 else bid_open[i + 1]
        entry_time[i] = frame.index[i + 1].to_datetime64()
        observed[i] = True
        # Freeze both barriers using only information available at signal time.
        target_level = -target_z if direction == 1 else target_z
        stop_level = -stop_z if direction == 1 else stop_z
        target_mid = np.exp(
            equilibrium_log[i] + residual_center[i] + target_level * residual_scale[i]
        )
        stop_mid = np.exp(equilibrium_log[i] + residual_center[i] + stop_level * residual_scale[i])
        end = i + horizon + 1
        outcome = np.nan
        for j in range(i + 1, end):
            if not np.isfinite(mid_close[j]):
                continue
            if intrabar:
                reverted = (direction == -1 and mid_low[j] <= target_mid) or (
                    direction == 1 and mid_high[j] >= target_mid
                )
                stopped = (direction == -1 and mid_high[j] >= stop_mid) or (
                    direction == 1 and mid_low[j] <= stop_mid
                )
            else:
                reverted = (direction == -1 and mid_close[j] <= target_mid) or (
                    direction == 1 and mid_close[j] >= target_mid
                )
                stopped = (direction == -1 and mid_close[j] >= stop_mid) or (
                    direction == 1 and mid_close[j] <= stop_mid
                )
            if reverted or stopped:
                if reverted and stopped:
                    outcome = 0.0 if same_bar_policy == "stop_first" else 1.0
                else:
                    outcome = 1.0 if reverted else 0.0
                exit_offset[i] = j - i
                barrier_mid = target_mid if outcome == 1.0 else stop_mid
                gap_crossed = (
                    (outcome == 1.0 and direction == 1 and mid_open[j] >= target_mid)
                    or (outcome == 1.0 and direction == -1 and mid_open[j] <= target_mid)
                    or (outcome == 0.0 and direction == 1 and mid_open[j] <= stop_mid)
                    or (outcome == 0.0 and direction == -1 and mid_open[j] >= stop_mid)
                )
                fill_mid = mid_open[j] if gap_crossed else barrier_mid
                if gap_crossed:
                    exit_quote = bid_open[j] if direction == 1 else ask_open[j]
                else:
                    exit_quote = (
                        fill_mid - spread[j] / 2.0 if direction == 1 else fill_mid + spread[j] / 2.0
                    )
                gross[i] = direction * (fill_mid - mid_open[i + 1])
                execution[i] = direction * (exit_quote - entry_price[i])
                observed_cost[i] = gross[i] - execution[i]
                exit_time[i] = frame.index[j].to_datetime64()
                outcome_code[i] = 1 if outcome == 1.0 else 0
                break
        if not np.isfinite(outcome):
            # Every fully observable event exits at the horizon; it is a failed TP event.
            j = i + horizon
            outcome = 0.0
            outcome_code[i] = -1
            exit_offset[i] = horizon
            gross[i] = direction * (mid_close[j] - mid_open[i + 1])
            execution[i] = (
                bid_close[j] - entry_price[i] if direction == 1 else entry_price[i] - ask_close[j]
            )
            observed_cost[i] = gross[i] - execution[i]
            exit_time[i] = frame.index[j].to_datetime64()
        label[i] = outcome
    result = pd.DataFrame(index=frame.index)
    result[f"label_h{horizon}"] = label
    result[f"side_h{horizon}"] = side
    result[f"exit_bars_h{horizon}"] = exit_offset
    result[f"entry_time_h{horizon}"] = entry_time
    result[f"exit_time_h{horizon}"] = exit_time
    result[f"entry_price_h{horizon}"] = entry_price
    result[f"gross_pnl_h{horizon}"] = gross
    result[f"cost_proxy_h{horizon}"] = observed_cost
    result[f"net_pnl_h{horizon}"] = execution
    result[f"outcome_code_h{horizon}"] = outcome_code
    result[f"event_candidate_h{horizon}"] = candidate
    result[f"event_observed_h{horizon}"] = observed
    return result


def _event_sample_mask(frame: pd.DataFrame, horizon: int) -> np.ndarray:
    """Causal first-event sampling: training examples never overlap in time."""
    observed = frame[f"event_observed_h{horizon}"].to_numpy(bool)
    exits = pd.to_datetime(frame[f"exit_time_h{horizon}"]).to_numpy(dtype="datetime64[ns]")
    selected = np.zeros(len(frame), dtype=bool)
    last_exit = np.datetime64("NaT")
    for i in np.flatnonzero(observed):
        signal_time = frame.index[i].to_datetime64()
        if np.isnat(last_exit) or signal_time > last_exit:
            selected[i] = True
            last_exit = exits[i]
    return selected


def add_all_labels(frame: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    result = frame.copy()
    lcfg = cfg["labels"]
    for horizon in lcfg["horizons"]:
        result = result.join(
            triple_barrier_labels(
                result,
                int(horizon),
                float(lcfg["event_z"]),
                float(lcfg["target_z"]),
                float(lcfg["stop_z"]),
                bool(lcfg.get("intrabar", False)),
                str(lcfg.get("same_bar_policy", "stop_first")),
            )
        )
        result[f"event_sample_h{int(horizon)}"] = _event_sample_mask(result, int(horizon))
    return result
