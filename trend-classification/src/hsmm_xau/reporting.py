from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .evaluation import cscv_pbo, deflated_sharpe_probability, economic_metrics, probability_metrics
from .portfolio import mark_to_market_daily_returns, non_overlapping_mask, portfolio_metrics


def _json_portfolio(metrics: dict) -> dict:
    return {key: value for key, value in metrics.items() if key != "daily_returns"}


def _strategy_ablation(
    predictions: pd.DataFrame,
    bars: pd.DataFrame,
    probability_column: str,
    walk_dir: Path,
    cfg: dict,
) -> dict:
    expected_value = np.full(len(predictions), np.nan)
    for fold in sorted(predictions.fold.unique()):
        bundle = joblib.load(walk_dir / f"fold_{int(fold):02d}.joblib")
        mask = predictions.fold.to_numpy() == fold
        probability = predictions.loc[mask, probability_column].to_numpy(float)
        expected_value[mask] = probability * float(bundle["calibration_gain"]) - (
            1.0 - probability
        ) * float(bundle["calibration_loss"])
    if bool(cfg["decision"].get("use_regime_hard_gate", True)):
        regime_gate = (
            predictions.p_mean_reversion >= float(cfg["decision"]["mr_probability_threshold"])
        ) & (predictions.p_breakout < float(cfg["decision"]["max_breakout_probability"]))
    else:
        regime_gate = pd.Series(True, index=predictions.index)
    eligible = (
        predictions.label.notna()
        & regime_gate
        & (predictions[probability_column] >= float(cfg["decision"]["min_success_probability"]))
        & (expected_value > float(cfg["decision"]["min_expected_value"]))
    ).to_numpy(bool)
    selected = non_overlapping_mask(predictions.index, predictions.exit_time, eligible)
    daily = mark_to_market_daily_returns(
        bars,
        predictions.entry_time,
        predictions.exit_time,
        predictions.net_pnl.to_numpy(float),
        predictions.entry_price.to_numpy(float),
        predictions.side.to_numpy(int),
        selected,
    )
    return {
        "economics": economic_metrics(predictions.net_pnl.to_numpy(float)[selected]),
        "portfolio": _json_portfolio(
            portfolio_metrics(daily, int(cfg["portfolio"]["annualization_days"]))
        ),
    }


def create_report(walk_dir: Path, output: Path, cfg: dict) -> dict:
    predictions = pd.read_parquet(walk_dir / "predictions.parquet").sort_index()
    bars = pd.read_parquet(
        Path(cfg["_root"]) / cfg["paths"]["artifacts"] / "research_dataset.parquet"
    )
    walk_summary = json.loads((walk_dir / "walk_forward.json").read_text(encoding="utf-8"))
    event = predictions.label.notna()
    selected = event & predictions.trade_allowed
    y = predictions.loc[event, "label"].to_numpy()
    probability = probability_metrics(y, predictions.loc[event, "p_opportunity"].to_numpy())
    economics = economic_metrics(predictions.loc[selected, "net_pnl"].to_numpy())
    selected_outcomes = predictions.loc[selected, "outcome_code"]
    terminal_mix = {
        "TP": int((selected_outcomes == 1).sum()),
        "SL": int((selected_outcomes == 0).sum()),
        "TIMEOUT": int((selected_outcomes == -1).sum()),
    }
    daily = mark_to_market_daily_returns(
        bars,
        predictions.entry_time,
        predictions.exit_time,
        predictions.net_pnl.to_numpy(float),
        predictions.entry_price.to_numpy(float),
        predictions.side.to_numpy(int),
        selected.to_numpy(bool),
    )
    portfolio = portfolio_metrics(daily, int(cfg["portfolio"]["annualization_days"]))
    prevalence = float(predictions.loc[event, "label"].mean())
    constant_probability = np.full(int(event.sum()), prevalence)
    all_event_selected = non_overlapping_mask(
        predictions.index, predictions.exit_time, event.to_numpy(bool)
    )
    benchmarks = {
        "constant_probability": probability_metrics(y, constant_probability),
        "market_only_opportunity": probability_metrics(
            y, predictions.loc[event, "p_opportunity_market_only"].to_numpy()
        ),
        "regime_only_opportunity": probability_metrics(
            y, predictions.loc[event, "p_opportunity_regime_only"].to_numpy()
        ),
        "hmm_probability": probability_metrics(
            y, predictions.loc[event, "p_hmm_mean_reversion"].to_numpy()
        ),
        "all_non_overlapping_events": economic_metrics(
            predictions.net_pnl.to_numpy(float)[all_event_selected]
        ),
        "v2_selected_economics": economics,
    }
    benchmarks["market_only_strategy"] = _strategy_ablation(
        predictions, bars, "p_opportunity_market_only", walk_dir, cfg
    )
    benchmarks["regime_only_strategy"] = _strategy_ablation(
        predictions, bars, "p_opportunity_regime_only", walk_dir, cfg
    )
    benchmarks["incremental_auc_from_regime"] = (probability.get("roc_auc") or np.nan) - (
        benchmarks["market_only_opportunity"].get("roc_auc") or np.nan
    )

    threshold_grid = np.array([0.50, 0.55, 0.60, 0.65, 0.70])
    folds = sorted(predictions.fold.unique())
    probability_columns = [
        "p_opportunity",
        "p_opportunity_market_only",
        "p_opportunity_regime_only",
    ]
    candidate_matrix = np.zeros((len(folds), len(threshold_grid) * len(probability_columns)))
    for i, fold in enumerate(folds):
        part = predictions[predictions.fold == fold]
        for mode_index, probability_column in enumerate(probability_columns):
            for j, threshold in enumerate(threshold_grid):
                if bool(cfg["decision"].get("use_regime_hard_gate", True)):
                    regime_gate = (
                        part.p_mean_reversion >= float(cfg["decision"]["mr_probability_threshold"])
                    ) & (part.p_breakout < float(cfg["decision"]["max_breakout_probability"]))
                else:
                    regime_gate = pd.Series(True, index=part.index)
                eligible = (
                    part.label.notna()
                    & regime_gate
                    & (part[probability_column] >= threshold)
                    & (part.expected_net_value > float(cfg["decision"]["min_expected_value"]))
                ).to_numpy(bool)
                chosen = non_overlapping_mask(part.index, part.exit_time, eligible)
                candidate_daily = mark_to_market_daily_returns(
                    bars,
                    part.entry_time,
                    part.exit_time,
                    part.net_pnl.to_numpy(float),
                    part.entry_price.to_numpy(float),
                    part.side.to_numpy(int),
                    chosen,
                )
                candidate_matrix[i, mode_index * len(threshold_grid) + j] = (
                    candidate_daily.mean() if len(candidate_daily) else 0.0
                )
    daily_values = portfolio.get("daily_returns", pd.Series(dtype=float)).to_numpy(float)
    registry_path = Path(cfg["_root"]) / cfg["research_control"]["trial_registry"]
    trial_registry = json.loads(registry_path.read_text(encoding="utf-8"))
    total_trials = int(sum(item["trials"] for item in trial_registry["experiments"]))
    dsr = deflated_sharpe_probability(daily_values, trials=total_trials)
    pbo = cscv_pbo(candidate_matrix)

    stresses = {}
    selected_gross = predictions.loc[selected, "gross_pnl"].to_numpy(float)
    selected_cost = predictions.loc[selected, "observed_cost"].to_numpy(float)
    selected_entry = predictions.loc[selected, "entry_price"].to_numpy(float)
    selected_exit = predictions.loc[selected, "exit_time"]
    slippage = float(cfg["costs"]["slippage_spread_fraction"])
    commission = float(cfg["costs"]["commission_price"])
    for multiplier in (1.0, 1.25, 1.5, 2.0):
        stressed_pnl = selected_gross - selected_cost * (multiplier + slippage) - commission
        stress_daily = mark_to_market_daily_returns(
            bars,
            predictions.loc[selected, "entry_time"],
            selected_exit,
            stressed_pnl,
            selected_entry,
            predictions.loc[selected, "side"].to_numpy(int),
            np.ones(len(stressed_pnl), dtype=bool),
        )
        stresses[f"cost_x{multiplier}"] = {
            "economics": economic_metrics(stressed_pnl),
            "portfolio": _json_portfolio(
                portfolio_metrics(stress_daily, int(cfg["portfolio"]["annualization_days"]))
            ),
        }

    fold_portfolios = [fold["portfolio"] for fold in walk_summary["folds"]]
    positive_fraction = float(
        np.mean([item.get("total_return", -np.inf) > 0 for item in fold_portfolios])
    )
    hsmm_ll_wins = sum(
        fold["hsmm_loglik_per_bar"] > fold["hmm_loglik_per_bar"] for fold in walk_summary["folds"]
    )
    model_comparison = {
        "hsmm_loglik_wins": int(hsmm_ll_wins),
        "folds": int(walk_summary["n_folds"]),
        "mean_matching_distance": {
            state: float(
                np.mean(
                    [fold["matching_distance"].get(state, np.nan) for fold in walk_summary["folds"]]
                )
            )
            for state in cfg["model"]["state_names"]
        },
        "calibrator_counts": pd.Series([fold["calibrator"] for fold in walk_summary["folds"]])
        .value_counts()
        .to_dict(),
    }
    approval = cfg["approval"]
    constant = benchmarks["constant_probability"]
    market_only = benchmarks["market_only_opportunity"]
    checks = {
        "brier_better_than_constant": probability.get("brier", np.inf)
        < constant.get("brier", -np.inf),
        "log_loss_better_than_constant": probability.get("log_loss", np.inf)
        < constant.get("log_loss", -np.inf),
        "regime_adds_auc": (probability.get("roc_auc") or -np.inf)
        > (market_only.get("roc_auc") or np.inf),
        "duration_likelihood_majority": hsmm_ll_wins > walk_summary["n_folds"] / 2,
        "ece": probability.get("ece", np.inf) <= float(approval["max_ece"]),
        "roc_auc": (probability.get("roc_auc") or -np.inf) >= float(approval["min_roc_auc"]),
        "mcc": (probability.get("mcc") or -np.inf) >= float(approval["min_mcc"]),
        "profit_factor": (economics.get("profit_factor") or -np.inf)
        >= float(approval["min_profit_factor"]),
        "daily_sharpe": (portfolio.get("sharpe_daily") or -np.inf) >= float(approval["min_sharpe"]),
        "positive_fold_fraction": positive_fraction
        >= float(approval["min_positive_fold_fraction"]),
        "dsr_probability": np.isfinite(dsr) and dsr >= float(approval["min_dsr_probability"]),
        "pbo": np.isfinite(pbo) and pbo <= float(approval["max_pbo"]),
    }
    approval_allowed = bool(cfg.get("research_control", {}).get("allow_shadow_approval", True))
    decision = (
        "approve_for_shadow"
        if all(checks.values()) and approval_allowed
        else "historical_only_no_shadow"
        if all(checks.values())
        else "review_or_reject"
    )
    result = {
        "version": cfg["project"]["version"],
        "probability": probability,
        "economics": economics,
        "selected_terminal_mix": terminal_mix,
        "portfolio": _json_portfolio(portfolio),
        "benchmarks": benchmarks,
        "model_comparison": model_comparison,
        "positive_fold_fraction": positive_fraction,
        "deflated_sharpe_probability": dsr,
        "pbo": pbo,
        "trial_control": {
            "dsr_total_trials": total_trials,
            "pbo_current_candidates": int(candidate_matrix.shape[1]),
            "registry": str(registry_path),
        },
        "cost_stress": stresses,
        "checks": checks,
        "decision": decision,
        "limitations": [
            "XAUUSD history still begins in 2021 and uses one provider.",
            "XAUUSD ends at 2026-05-29 17:00 UTC; zero rows exist in the required new holdout.",
            "Intrabar ordering is conservative stop-first; exact tick barrier reconstruction remains future work.",
            "Existing historical OOS blocks were observed during v1 and are comparative pseudo-OOS.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown = [
        f"# Version {cfg['project']['version']} historical research decision",
        "",
        f"Decision: **{decision}**",
        "",
        "## Acceptance checks",
        "",
    ]
    markdown.extend(f"- [{'x' if value else ' '}] `{key}`" for key, value in checks.items())
    markdown.extend(["", "## Metrics", "", "```json", json.dumps(result, indent=2), "```", ""])
    output.with_suffix(".md").write_text("\n".join(markdown), encoding="utf-8")
    return result
