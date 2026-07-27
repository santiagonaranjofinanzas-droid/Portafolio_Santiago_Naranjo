from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import RobustScaler

from .evaluation import economic_metrics, probability_metrics
from .models import (
    ExplicitDurationHSMM,
    HMMBenchmark,
    hungarian_state_map,
    semantic_state_map,
)
from .opportunity import OpportunityModel
from .portfolio import mark_to_market_daily_returns, non_overlapping_mask, portfolio_metrics


@dataclass
class Fold:
    fold: int
    train_start: str
    train_end: str
    calibration_start: str
    calibration_end: str
    test_start: str
    test_end: str


def make_folds(index: pd.DatetimeIndex, cfg: dict) -> list[Fold]:
    wcfg = cfg["walk_forward"]
    start = index.min().normalize()
    final = index.max()
    train_years = int(wcfg["train_years"])
    calibration_months = int(wcfg["calibration_months"])
    test_months = int(wcfg["test_months"])
    step_months = int(wcfg["step_months"])
    train_end = start + pd.DateOffset(years=train_years)
    folds = []
    fold_id = 0
    while True:
        calibration_end = train_end + pd.DateOffset(months=calibration_months)
        test_end = calibration_end + pd.DateOffset(months=test_months)
        if test_end > final:
            break
        folds.append(
            Fold(
                fold=fold_id,
                train_start=start.isoformat(),
                train_end=train_end.isoformat(),
                calibration_start=train_end.isoformat(),
                calibration_end=calibration_end.isoformat(),
                test_start=calibration_end.isoformat(),
                test_end=test_end.isoformat(),
            )
        )
        fold_id += 1
        train_end += pd.DateOffset(months=step_months)
        start = train_end - pd.DateOffset(years=train_years)
    return folds


def _slice(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    return frame[(frame.index >= pd.Timestamp(start)) & (frame.index < pd.Timestamp(end))]


def _ordered_state_block(
    probabilities: np.ndarray,
    ages: np.ndarray,
    state_map: dict[str, int],
    state_names: list[str],
) -> np.ndarray:
    columns = [probabilities[:, state_map[name]] for name in state_names]
    columns += [ages[:, state_map[name]] for name in state_names]
    return np.column_stack(columns)


def _opportunity_matrix(
    part: pd.DataFrame,
    base_features: list[str],
    probabilities: np.ndarray,
    ages: np.ndarray,
    state_map: dict[str, int],
    state_names: list[str],
    mode: str = "all",
) -> np.ndarray:
    market = part[base_features].to_numpy(float)
    state = _ordered_state_block(probabilities, ages, state_map, state_names)
    derived = np.column_stack(
        [
            np.abs(part.residual_z.to_numpy(float)),
            np.sign(part.residual_z.to_numpy(float)),
        ]
    )
    if mode == "market_only":
        return np.column_stack([market, derived])
    if mode == "regime_only":
        return np.column_stack([state, derived])
    return np.column_stack([market, state, derived])


def _fit_opportunity(
    train_matrix: np.ndarray,
    train_y: np.ndarray,
    calibration_matrix: np.ndarray,
    calibration_y: np.ndarray,
    cfg: dict,
    seed: int,
) -> OpportunityModel:
    ocfg = cfg["opportunity"]
    return OpportunityModel(
        c=float(ocfg["c"]),
        l1_ratio=float(ocfg["l1_ratio"]),
        max_iter=int(ocfg["max_iter"]),
        random_state=seed,
        calibrator_names=tuple(ocfg["calibrators"]),
    ).fit(train_matrix, train_y, calibration_matrix, calibration_y)


def _json_portfolio_metrics(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key != "daily_returns"}


def run_walk_forward(frame: pd.DataFrame, cfg: dict, output: Path) -> dict:
    feature_names = list(cfg["features"]["selected"])
    opportunity_features = list(cfg["opportunity"]["features"])
    primary_opportunity_mode = str(cfg["opportunity"].get("primary_mode", "all"))
    state_names = list(cfg["model"]["state_names"])
    primary_horizon = int(cfg["labels"]["primary_horizon"])
    label_col = f"label_h{primary_horizon}"
    gross_col = f"gross_pnl_h{primary_horizon}"
    cost_col = f"cost_proxy_h{primary_horizon}"
    entry_col = f"entry_price_h{primary_horizon}"
    exit_time_col = f"exit_time_h{primary_horizon}"
    entry_time_col = f"entry_time_h{primary_horizon}"
    side_col = f"side_h{primary_horizon}"
    sample_col = f"event_sample_h{primary_horizon}"
    outcome_col = f"outcome_code_h{primary_horizon}"
    threshold = float(cfg["decision"]["mr_probability_threshold"])
    success_threshold = float(cfg["decision"]["min_success_probability"])
    purge = int(cfg["labels"]["purge_bars"])
    folds = make_folds(frame.index, cfg)
    if not folds:
        raise ValueError("Available history is too short for configured walk-forward splits")
    output.mkdir(parents=True, exist_ok=True)
    results = []
    predictions = []
    anchor_centroids: dict[str, np.ndarray]  None = None
    anchor_scale: np.ndarray  None = None
    for fold in folds:
        train = _slice(frame, fold.train_start, fold.train_end).iloc[:-purge]
        calibration = _slice(frame, fold.calibration_start, fold.calibration_end).iloc[:-purge]
        test = _slice(frame, fold.test_start, fold.test_end)
        imputer = SimpleImputer(strategy="median").fit(train[feature_names])
        scaler = RobustScaler(quantile_range=(10, 90)).fit(imputer.transform(train[feature_names]))

        def transform(part: pd.DataFrame) -> np.ndarray:
            return np.clip(scaler.transform(imputer.transform(part[feature_names])), -10, 10)

        x_train, x_cal, x_test = transform(train), transform(calibration), transform(test)
        best_hsmm = None
        best_score = -np.inf
        for seed_offset in range(int(cfg["model"]["n_seeds"])):
            model = ExplicitDurationHSMM(
                n_states=int(cfg["model"]["states"]),
                max_duration=int(cfg["model"]["max_duration"]),
                max_iter=int(cfg["model"]["max_iter"]),
                tolerance=float(cfg["model"]["tolerance"]),
                random_state=int(cfg["project"]["seed"]) + seed_offset,
                emission_family=str(cfg["model"].get("emission_family", "gaussian")),
                emission_df=float(cfg["model"].get("emission_df", 5.0)),
                robust_location=bool(cfg["model"].get("robust_location", False)),
            ).fit(x_train)
            score = model.score_filtered(x_cal) / max(len(x_cal), 1)
            if score > best_score:
                best_hsmm, best_score = model, score
        assert best_hsmm is not None
        hmm = HMMBenchmark(
            n_states=int(cfg["model"]["states"]),
            max_iter=int(cfg["model"]["max_iter"]),
            tolerance=float(cfg["model"]["tolerance"]),
            random_state=int(cfg["project"]["seed"]),
        ).fit(x_train)

        raw_centroids = scaler.inverse_transform(best_hsmm.means_)
        if anchor_centroids is None:
            state_map = semantic_state_map(best_hsmm.means_, feature_names)
            anchor_centroids = {name: raw_centroids[state_map[name]].copy() for name in state_names}
            anchor_scale = np.where(np.asarray(scaler.scale_) > 0, scaler.scale_, 1.0)
            matching_distance = {name: 0.0 for name in state_names}
        else:
            normalized_anchor = {
                name: anchor_centroids[name] / anchor_scale for name in state_names
            }
            state_map, matching_distance = hungarian_state_map(
                normalized_anchor, raw_centroids / anchor_scale
            )
        hmm_map, _ = hungarian_state_map(
            {name: best_hsmm.means_[state_map[name]] for name in state_names}, hmm.model_.means_
        )

        train_prob, train_ages, _ = best_hsmm.filtered_proba(x_train, return_age=True)
        cal_prob, cal_ages, _ = best_hsmm.filtered_proba(x_cal, return_age=True)
        test_prob, test_ages, test_ll = best_hsmm.filtered_proba(x_test, return_age=True)
        p_hmm = hmm.filtered_proba(x_test)[:, hmm_map["mean_reversion"]]

        def cost_adjusted_pnl(part: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
            part_cost = part[cost_col].to_numpy(float) * float(cfg["costs"]["spread_multiplier"])
            part_pnl = (
                part[gross_col].to_numpy(float)
                - part_cost * (1.0 + float(cfg["costs"]["slippage_spread_fraction"]))
                - float(cfg["costs"]["commission_price"])
            )
            return part_pnl, part_cost

        train_pnl, _ = cost_adjusted_pnl(train)
        cal_pnl, _ = cost_adjusted_pnl(calibration)
        pnl, observed_cost = cost_adjusted_pnl(test)
        train_barrier = train[label_col].to_numpy(float)
        cal_barrier = calibration[label_col].to_numpy(float)
        test_barrier = test[label_col].to_numpy(float)
        train_sample = train[sample_col].to_numpy(bool)
        cal_sample = calibration[sample_col].to_numpy(bool)
        test_sample = test[sample_col].to_numpy(bool)
        if cfg["opportunity"].get("target", "barrier_success") == "net_profitable":
            train_y = np.where(np.isfinite(train_barrier), (train_pnl > 0).astype(float), np.nan)
            cal_y = np.where(np.isfinite(cal_barrier), (cal_pnl > 0).astype(float), np.nan)
            test_y = np.where(np.isfinite(test_barrier), (pnl > 0).astype(float), np.nan)
        else:
            train_y, cal_y, test_y = train_barrier, cal_barrier, test_barrier
        train_y = np.where(train_sample, train_y, np.nan)
        cal_y = np.where(cal_sample, cal_y, np.nan)
        test_y = np.where(test_sample, test_y, np.nan)
        opportunity_models = {}
        test_success = {}
        for mode in ("all", "market_only", "regime_only"):
            train_matrix = _opportunity_matrix(
                train,
                opportunity_features,
                train_prob,
                train_ages,
                state_map,
                state_names,
                mode,
            )
            cal_matrix = _opportunity_matrix(
                calibration,
                opportunity_features,
                cal_prob,
                cal_ages,
                state_map,
                state_names,
                mode,
            )
            test_matrix = _opportunity_matrix(
                test,
                opportunity_features,
                test_prob,
                test_ages,
                state_map,
                state_names,
                mode,
            )
            opportunity_models[mode] = _fit_opportunity(
                train_matrix,
                train_y,
                cal_matrix,
                cal_y,
                cfg,
                int(cfg["project"]["seed"]) + fold.fold,
            )
            test_success[mode] = opportunity_models[mode].predict_proba(test_matrix)

        economic_mask = opportunity_models[primary_opportunity_mode].economic_calibration_mask_
        finite_cal = cal_pnl[economic_mask & np.isfinite(cal_pnl)]
        gain = float(finite_cal[finite_cal > 0].mean()) if (finite_cal > 0).any() else 0.0
        loss = float(-finite_cal[finite_cal < 0].mean()) if (finite_cal < 0).any() else np.inf
        p_success = test_success[primary_opportunity_mode]
        expected_value = p_success * gain - (1.0 - p_success) * loss
        p_mr = test_prob[:, state_map["mean_reversion"]]
        p_breakout = test_prob[:, state_map["breakout"]]
        event = np.isfinite(test_y)
        if bool(cfg["decision"].get("use_regime_hard_gate", True)):
            regime_gate = (p_mr >= threshold) & (
                p_breakout < float(cfg["decision"]["max_breakout_probability"])
            )
        else:
            regime_gate = np.ones(len(test), dtype=bool)
        eligible = (
            event
            & regime_gate
            & (p_success >= success_threshold)
            & (expected_value > float(cfg["decision"]["min_expected_value"]))
        )
        selected = non_overlapping_mask(test.index, test[exit_time_col], eligible)
        daily = mark_to_market_daily_returns(
            test,
            test[entry_time_col],
            test[exit_time_col],
            pnl,
            test[entry_col].to_numpy(float),
            test[side_col].to_numpy(int),
            selected,
        )
        portfolio = portfolio_metrics(daily, int(cfg["portfolio"]["annualization_days"]))
        fold_result = {
            "fold": asdict(fold),
            "state_map": state_map,
            "matching_distance": matching_distance,
            "mean_duration": best_hsmm.mean_duration_.tolist(),
            "hsmm_loglik_per_bar": float(test_ll / max(len(test), 1)),
            "hmm_loglik_per_bar": float(hmm.score_filtered(x_test) / max(len(test), 1)),
            "opportunity_probability": probability_metrics(test_y[event], p_success[event]),
            "market_only_probability": probability_metrics(
                test_y[event], test_success["market_only"][event]
            ),
            "regime_only_probability": probability_metrics(
                test_y[event], test_success["regime_only"][event]
            ),
            "hmm_probability": probability_metrics(test_y[event], p_hmm[event]),
            "economics": economic_metrics(pnl[selected]),
            "portfolio": _json_portfolio_metrics(portfolio),
            "calibrator": opportunity_models[primary_opportunity_mode].calibrator_name_,
            "primary_opportunity_mode": primary_opportunity_mode,
        }
        results.append(fold_result)
        pred = pd.DataFrame(index=test.index)
        pred["fold"] = fold.fold
        for name in state_names:
            pred[f"p_{name}"] = test_prob[:, state_map[name]]
        pred["p_opportunity"] = p_success
        pred["p_opportunity_market_only"] = test_success["market_only"]
        pred["p_opportunity_regime_only"] = test_success["regime_only"]
        pred["p_hmm_mean_reversion"] = p_hmm
        pred["expected_regime_age"] = test_ages[:, state_map["mean_reversion"]]
        pred["expected_net_value"] = expected_value
        pred["label"] = test_y
        pred["barrier_label"] = test_barrier
        pred["outcome_code"] = test[outcome_col].to_numpy(int)
        pred["gross_pnl"] = test[gross_col].to_numpy(float)
        pred["observed_cost"] = observed_cost
        pred["net_pnl"] = pnl
        pred["entry_price"] = test[entry_col].to_numpy(float)
        pred["entry_time"] = pd.to_datetime(test[entry_time_col]).to_numpy()
        pred["exit_time"] = pd.to_datetime(test[exit_time_col]).to_numpy()
        pred["side"] = test[side_col].to_numpy(int)
        pred["eligible"] = eligible
        pred["trade_allowed"] = selected
        predictions.append(pred)
        joblib.dump(
            {
                "model": best_hsmm,
                "imputer": imputer,
                "scaler": scaler,
                "opportunity_model": opportunity_models[primary_opportunity_mode],
                "opportunity_mode": primary_opportunity_mode,
                "state_map": state_map,
                "feature_names": feature_names,
                "opportunity_features": opportunity_features,
                "state_names": state_names,
                "calibration_gain": gain,
                "calibration_loss": loss,
                "decision": cfg["decision"],
                "config_version": cfg["project"]["version"],
            },
            output / f"fold_{fold.fold:02d}.joblib",
        )
    prediction_frame = pd.concat(predictions).sort_index()
    prediction_frame.to_parquet(output / "predictions.parquet")
    summary = {"folds": results, "n_folds": len(results)}
    (output / "walk_forward.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return summary
