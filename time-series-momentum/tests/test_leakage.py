import pytest
import pandas as pd
import numpy as np
from src.optimization import get_purged_train_slice

def test_get_purged_train_slice_weekend():
    dates = [pd.to_datetime("2021-01-01"), pd.to_datetime("2021-01-04"), pd.to_datetime("2021-01-05")]
    df = pd.DataFrame({"Close": [100, 101, 102]}, index=dates)
    
    purged = get_purged_train_slice(df, pd.to_datetime("2021-01-04"), label_horizon=1, execution_lag=1)
    assert len(purged) == 0
    
    purged_tue = get_purged_train_slice(df, pd.to_datetime("2021-01-05"))
    assert len(purged_tue) == 1
    assert purged_tue.index[0] == pd.to_datetime("2021-01-01")

def test_purged_index_validations():
    dates = [pd.to_datetime("2021-01-05"), pd.to_datetime("2021-01-01")]
    df = pd.DataFrame({"Close": [100, 101]}, index=dates)
    with pytest.raises(ValueError, match="Index must be monotonically increasing."):
        get_purged_train_slice(df, pd.to_datetime("2021-01-06"))
        
    dates_dup = [pd.to_datetime("2021-01-01"), pd.to_datetime("2021-01-01")]
    df_dup = pd.DataFrame({"Close": [100, 101]}, index=dates_dup)
    with pytest.raises(ValueError, match="Index must be unique."):
        get_purged_train_slice(df_dup, pd.to_datetime("2021-01-02"))
