from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.preprocessing import RobustScaler


def _logit(probability: np.ndarray) -> np.ndarray:
    probability = np.clip(np.asarray(probability, float), 1e-6, 1 - 1e-6)
    return np.log(probability / (1.0 - probability))


@dataclass
class OpportunityModel:
    c: float = 0.1
    l1_ratio: float = 0.25
    max_iter: int = 3000
    random_state: int = 0
    calibrator_names: tuple[str, ...] = ("platt", "isotonic", "identity")

    def fit(
        self,
        x_train: np.ndarray,
        y_train: np.ndarray,
        x_calibration: np.ndarray,
        y_calibration: np.ndarray,
    ) -> "OpportunityModel":
        train_mask = np.isfinite(y_train)
        calibration_mask = np.isfinite(y_calibration)
        self.imputer_ = SimpleImputer(strategy="median").fit(x_train[train_mask])
        imputed_train = self.imputer_.transform(x_train[train_mask])
        self.scaler_ = RobustScaler(quantile_range=(10, 90)).fit(imputed_train)
        transformed_train = np.clip(self.scaler_.transform(imputed_train), -10, 10)
        if len(np.unique(y_train[train_mask])) < 2:
            self.model_ = None
            self.constant_ = float(np.mean(y_train[train_mask]))
        else:
            self.model_ = LogisticRegression(
                solver="saga",
                C=self.c,
                l1_ratio=self.l1_ratio,
                class_weight="balanced",
                max_iter=self.max_iter,
                random_state=self.random_state,
            ).fit(transformed_train, y_train[train_mask].astype(int))
            self.constant_ = None
        valid_indices = np.flatnonzero(calibration_mask)
        raw_calibration = self.predict_raw(x_calibration[valid_indices])
        y_cal = y_calibration[valid_indices].astype(int)
        first = max(1, len(y_cal) // 3)
        second = max(first + 1, 2 * len(y_cal) // 3)
        second = min(second, len(y_cal))
        fit_raw, fit_y = raw_calibration[:first], y_cal[:first]
        select_raw, select_y = raw_calibration[first:second], y_cal[first:second]
        self.economic_calibration_mask_ = np.zeros(len(x_calibration), dtype=bool)
        self.economic_calibration_mask_[valid_indices[second:]] = True
        candidates: list[tuple[str, object  None, np.ndarray]] = []
        if "identity" in self.calibrator_names:
            candidates.append(("identity", None, select_raw))
        if len(fit_y) >= 20 and len(select_y) and len(np.unique(fit_y)) == 2:
            if "platt" in self.calibrator_names:
                platt = LogisticRegression(C=1e6, solver="lbfgs").fit(
                    _logit(fit_raw).reshape(-1, 1), fit_y
                )
                candidates.append(
                    (
                        "platt",
                        platt,
                        platt.predict_proba(_logit(select_raw).reshape(-1, 1))[:, 1],
                    )
                )
            if "isotonic" in self.calibrator_names:
                isotonic = IsotonicRegression(out_of_bounds="clip", y_min=0.001, y_max=0.999).fit(
                    fit_raw, fit_y
                )
                candidates.append(("isotonic", isotonic, isotonic.predict(select_raw)))
        if not candidates:
            candidates.append(("identity", None, select_raw))
        scored = []
        for name, calibrator, probability in candidates:
            probability = np.clip(probability, 1e-6, 1 - 1e-6)
            score = (
                float(brier_score_loss(select_y, probability)),
                float(log_loss(select_y, probability, labels=[0, 1])),
            )
            scored.append((score, name, calibrator))
        _, self.calibrator_name_, self.calibrator_ = min(scored, key=lambda item: item[0])
        # Once the family is selected out-of-sample, refit it on fit+selection only.
        refit_raw, refit_y = raw_calibration[:second], y_cal[:second]
        if self.calibrator_name_ == "platt":
            self.calibrator_ = LogisticRegression(C=1e6, solver="lbfgs").fit(
                _logit(refit_raw).reshape(-1, 1), refit_y
            )
        elif self.calibrator_name_ == "isotonic":
            self.calibrator_ = IsotonicRegression(
                out_of_bounds="clip", y_min=0.001, y_max=0.999
            ).fit(refit_raw, refit_y)
        self.calibration_scores_ = {name: score for score, name, _ in scored}
        return self

    def _transform(self, x: np.ndarray) -> np.ndarray:
        return np.clip(self.scaler_.transform(self.imputer_.transform(x)), -10, 10)

    def predict_raw(self, x: np.ndarray) -> np.ndarray:
        if self.model_ is None:
            return np.full(len(x), self.constant_, dtype=float)
        return self.model_.predict_proba(self._transform(x))[:, 1]

    def predict_proba(self, x: np.ndarray) -> np.ndarray:
        raw = self.predict_raw(x)
        if self.calibrator_name_ == "platt":
            return self.calibrator_.predict_proba(_logit(raw).reshape(-1, 1))[:, 1]
        if self.calibrator_name_ == "isotonic":
            return self.calibrator_.predict(raw)
        return raw
