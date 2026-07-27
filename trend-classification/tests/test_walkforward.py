import pandas as pd

from hsmm_xau.walkforward import make_folds


def test_walk_forward_is_strictly_ordered():
    index = pd.date_range("2021-01-01", "2026-06-01", freq="15min")
    cfg = {
        "walk_forward": {
            "train_years": 3,
            "calibration_months": 3,
            "test_months": 3,
            "step_months": 3,
        }
    }
    folds = make_folds(index, cfg)
    assert folds
    for fold in folds:
        assert fold.train_start < fold.train_end <= fold.calibration_start
        assert fold.calibration_start < fold.calibration_end <= fold.test_start
        assert fold.test_start < fold.test_end
