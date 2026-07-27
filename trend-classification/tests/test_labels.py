import numpy as np
import pandas as pd

from hsmm_xau.labels import triple_barrier_labels


def test_triple_barrier_win_and_loss():
    index = pd.date_range("2024-01-01", periods=8, freq="15min")
    frame = pd.DataFrame(index=index)
    frame["residual_z"] = [2.0, 1.0, 0.2, 0.0, -2.0, -2.6, -1.0, 0.0]
    frame["mid_close"] = [102, 100, 99, 99, 98, 97, 98, 99]
    frame["mid_open"] = frame.mid_close
    frame["bid_open"] = frame.mid_close - 0.05
    frame["ask_open"] = frame.mid_close + 0.05
    frame["bid_close"] = frame.mid_close - 0.05
    frame["ask_close"] = frame.mid_close + 0.05
    frame["spread_mean"] = 0.1
    frame["equilibrium_log"] = np.log(100.0)
    frame["residual_center"] = 0.0
    frame["residual_scale"] = 0.01
    labels = triple_barrier_labels(frame, horizon=3)
    assert labels.iloc[0].label_h3 == 1
    assert labels.iloc[4].label_h3 == 0
    assert labels.iloc[0].cost_proxy_h3 > 0


def test_timeout_is_an_explicit_horizon_exit_and_barriers_are_frozen():
    index = pd.date_range("2024-01-01", periods=6, freq="15min")
    frame = pd.DataFrame(index=index)
    frame["residual_z"] = [2.0, 1.9, 1.8, 1.7, 1.6, 1.5]
    frame["mid_close"] = [102.0, 102.0, 102.0, 102.0, 102.0, 102.0]
    frame["mid_open"] = frame.mid_close
    frame["mid_high"] = 102.1
    frame["mid_low"] = 101.9
    frame["bid_open"] = frame.mid_open - 0.05
    frame["ask_open"] = frame.mid_open + 0.05
    frame["bid_close"] = frame.mid_close - 0.05
    frame["ask_close"] = frame.mid_close + 0.05
    frame["spread_mean"] = 0.1
    frame["equilibrium_log"] = np.log(100.0)
    frame["residual_center"] = 0.0
    frame["residual_scale"] = 0.01
    labels = triple_barrier_labels(frame, horizon=3)
    assert labels.iloc[0].label_h3 == 0
    assert labels.iloc[0].outcome_code_h3 == -1
    assert labels.iloc[0].exit_bars_h3 == 3
    assert pd.notna(labels.iloc[0].exit_time_h3)
    assert np.isfinite(labels.iloc[0].net_pnl_h3)

    changed = frame.copy()
    changed.loc[index[1] :, "equilibrium_log"] = np.log(1000.0)
    changed_labels = triple_barrier_labels(changed, horizon=3)
    assert changed_labels.iloc[0].outcome_code_h3 == -1
    assert changed_labels.iloc[0].net_pnl_h3 == labels.iloc[0].net_pnl_h3
