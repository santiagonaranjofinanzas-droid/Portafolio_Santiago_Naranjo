import numpy as np
import pandas as pd

from hsmm_xau.data import _batch_bar_parts, add_gap_segments, join_context


def test_bars_are_right_labeled_and_causal():
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2024-01-01 00:00:00", "2024-01-01 00:00:01", "2024-01-01 00:15:00"]
            ),
            "bid": [10.0, 11.0, 12.0],
            "ask": [10.2, 11.2, 12.2],
        }
    )
    bars = _batch_bar_parts(frame, "15min").set_index("bar_time")
    assert bars.loc["2024-01-01 00:00:00", "mid_close"] == 10.1
    assert bars.loc["2024-01-01 00:15:00", "mid_open"] == 11.1
    assert bars.loc["2024-01-01 00:15:00", "mid_close"] == 12.1


def test_context_join_never_uses_future_bar():
    primary = pd.DataFrame(
        {"x": [1, 2]}, index=pd.to_datetime(["2024-01-01 00:10", "2024-01-01 00:20"])
    )
    primary.index.name = "timestamp"
    context = pd.DataFrame(
        {"mid_close": [100, 200]},
        index=pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:15"]),
    )
    context.index.name = "timestamp"
    joined = join_context(primary, {"CTX": context})
    np.testing.assert_array_equal(joined.ctx_close, [100, 200])


def test_large_gaps_start_new_segments():
    index = pd.to_datetime(["2024-01-01 00:00", "2024-01-01 00:15", "2024-01-02 00:00"])
    frame = pd.DataFrame({"x": [1, 2, 3]}, index=index)
    segmented = add_gap_segments(frame, "15min", 4)
    np.testing.assert_array_equal(segmented.segment_id, [0, 0, 1])
