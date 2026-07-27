import pytest
import pandas as pd
import numpy as np
from src.optimization import get_purged_train_slice

def test_purging_sorted_unique():
    dates = pd.to_datetime(["2020-01-03", "2020-01-01", "2020-01-02"])
    df = pd.DataFrame({"target": [1, 2, 3]}, index=dates)
    with pytest.raises(ValueError, match="Index must be monotonically increasing."):
        get_purged_train_slice(df, pd.to_datetime("2020-01-03"))

    dates = pd.to_datetime(["2020-01-01", "2020-01-01", "2020-01-02"])
    df = pd.DataFrame({"target": [1, 2, 3]}, index=dates)
    with pytest.raises(ValueError, match="Index must be unique."):
        get_purged_train_slice(df, pd.to_datetime("2020-01-02"))

def test_purging_leakage_exclusion():
    dates = pd.date_range("2020-01-01", periods=10, freq="D")
    df = pd.DataFrame({"target": range(10)}, index=dates)
    
    current_date = pd.to_datetime("2020-01-08")
    train = get_purged_train_slice(df, current_date, label_horizon=1, execution_lag=1)
    
    assert len(train) > 0
    assert train.index[-1] == pd.to_datetime("2020-01-06")
    
    current_pos = df.index.searchsorted(current_date)
    last_train_pos = df.index.get_loc(train.index[-1])
    assert last_train_pos <= current_pos - 2

def test_purging_holiday_fallback():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"])
    df = pd.DataFrame({"target": range(5)}, index=dates)
    
    current_date = pd.to_datetime("2020-01-05")
    train = get_purged_train_slice(df, current_date, label_horizon=1, execution_lag=1)
    
    assert train.index[-1] == pd.to_datetime("2020-01-02")

def test_purging_large_gap():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-08", "2020-01-09"])
    df = pd.DataFrame({"target": range(4)}, index=dates)
    
    current_date = pd.to_datetime("2020-01-07")
    train = get_purged_train_slice(df, current_date, label_horizon=1, execution_lag=1)
    
    assert train.index[-1] == pd.to_datetime("2020-01-01")

def test_purging_empty_when_not_enough_history():
    dates = pd.to_datetime(["2020-01-01", "2020-01-02"])
    df = pd.DataFrame({"target": [1, 2]}, index=dates)

    train = get_purged_train_slice(
        df,
        pd.to_datetime("2020-01-02"),
        label_horizon=1,
        execution_lag=1
    )

    assert train.empty
