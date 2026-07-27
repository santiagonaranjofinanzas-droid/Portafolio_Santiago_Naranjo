from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from Capa_4.backtest_metrics import (
    BacktestAssumptions,
    compute_backtest_metrics,
    deflated_sharpe_ratio,
    run_backtest,
)
from SUB_RAMA_MEAN_REVERSION.backtest_mean_reversion import run_mean_reversion_backtest
from SUB_RAMA_MEAN_REVERSION.mean_reversion_signal import calculate_z_dev_in_memory
from SUB_RAMA_MEAN_REVERSION.run_reversion_pipeline import optimize_mr_params


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
REPORTS = HERE / "reports"
PROFILE_PATH = HERE / "config" / "broker_profile_nas100_fs.json"
POLICY_PATH = HERE / "config" / "release_policy.json"
UNIVERSE_RESULTS = ROOT / "Universo de activos" / "resultados" / "NSXUSD"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assumptions(profile: dict) -> BacktestAssumptions:
    return BacktestAssumptions(
        initial_balance=10_000.0,
        risk_percent=1.0,
        min_strength=0.35,
        vol_multiplier=2.5,
        reward_risk=1.5,
        use_partials=True,
        max_lot=float(profile["volume_max"]),
        point=float(profile["point"]),
        tick_size=float(profile["tick_size"]),
        tick_value=float(profile["tick_value"]),
        spread_price=float(profile["snapshot_spread_price"]),
        slippage_price=float(profile["slippage_price_assumption"]),
        commission_per_lot=float(profile["commission_per_lot_per_side_assumption"]),
        min_lot=float(profile["volume_min"]),
        lot_step=float(profile["volume_step"]),
        periods_per_year=24 * 4 * 252,
        intrabar_mode="pessimistic",
    )


def _daily_metrics(trades: pd.DataFrame, start, end, initial_balance: float, trials: int) -> dict:
    if trades.empty:
        return {"daily_sharpe": 0.0, "daily_dsr_probability": 0.0, "daily_max_drawdown_pct": 0.0}
    exits = pd.to_datetime(trades["exit_time"], errors="coerce")
    pnl = pd.Series(trades["pnl"].to_numpy(float), index=exits).dropna()
    daily = pnl.groupby(pnl.index.floor("D")).sum()
    index = pd.date_range(pd.Timestamp(start).floor("D"), pd.Timestamp(end).floor("D"), freq="D")
    daily = daily.reindex(index, fill_value=0.0)
    equity = initial_balance + daily.cumsum()
    previous = equity.shift(1).fillna(initial_balance)
    returns = (daily / previous.replace(0.0, np.nan)).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    std = float(returns.std(ddof=1))
    period_sr = float(returns.mean() / std) if std > 0 else 0.0
    sharpe = period_sr * np.sqrt(252.0)
    dsr, z = deflated_sharpe_ratio(returns.to_numpy(float), period_sr, trials=trials)
    peak = equity.cummax()
    dd_pct = ((equity - peak) / peak.replace(0.0, np.nan) * 100.0).min()
    return {
        "daily_sharpe": float(sharpe),
        "daily_dsr_probability": float(dsr),
        "daily_dsr_z": float(z),
        "daily_max_drawdown_pct": float(dd_pct),
    }


def _robustness(trades: pd.DataFrame, seed: int = 50001, samples: int = 5000) -> dict:
    pnl = trades["pnl"].to_numpy(float) if not trades.empty else np.array([], dtype=float)
    if len(pnl) == 0:
        return {"bootstrap_pf_p05": 0.0, "bootstrap_probability_net_positive": 0.0,
                "minimum_quarter_profit_factor": 0.0, "top_5_winner_gross_profit_share_pct": 100.0}
    rng = np.random.default_rng(seed)
    draw = rng.choice(pnl, size=(samples, len(pnl)), replace=True)
    gross_win = np.where(draw > 0.0, draw, 0.0).sum(axis=1)
    gross_loss = np.abs(np.where(draw <= 0.0, draw, 0.0).sum(axis=1))
    pf = np.divide(gross_win, gross_loss, out=np.full(samples, np.inf), where=gross_loss > 0.0)
    frame = trades.copy()
    frame["exit_time"] = pd.to_datetime(frame["exit_time"], errors="coerce")
    quarter_pf = []
    for _, group in frame.dropna(subset=["exit_time"]).groupby(frame["exit_time"].dt.to_period("Q")):
        values = group["pnl"].to_numpy(float)
        win = values[values > 0].sum()
        loss = abs(values[values <= 0].sum())
        quarter_pf.append(float(win / loss) if loss > 0 else float("inf"))
    winners = np.sort(pnl[pnl > 0])[::-1]
    gross_profit = winners.sum()
    concentration = float(winners[:5].sum() / gross_profit * 100.0) if gross_profit > 0 else 100.0
    return {
        "bootstrap_pf_p05": float(np.quantile(pf, 0.05)),
        "bootstrap_probability_net_positive": float((draw.sum(axis=1) > 0.0).mean()),
        "minimum_quarter_profit_factor": float(min(quarter_pf)) if quarter_pf else 0.0,
        "top_5_winner_gross_profit_share_pct": concentration,
    }


def _gate(model: str, metrics: dict, robust: dict, policy: dict, is_pf: float, nested_pf: float  None,
          nested_complete: bool, tick_validated: bool, forward_trades: int = 0,
          forward_pf: float = 0.0) -> list[dict]:
    minimums = policy["minimums"]
    maximums = policy["maximums"]
    checks = [
        ("tick_bid_ask_backtest", tick_validated, tick_validated, True),
        ("closed_trades", metrics["closed_trades"] >= minimums["closed_trades"], metrics["closed_trades"], minimums["closed_trades"]),
        ("profit_factor", metrics["profit_factor"] >= minimums["profit_factor"], metrics["profit_factor"], minimums["profit_factor"]),
        ("daily_sharpe", metrics["daily_sharpe"] >= minimums["daily_sharpe"], metrics["daily_sharpe"], minimums["daily_sharpe"]),
        ("deflated_sharpe_probability", metrics["daily_dsr_probability"] >= minimums["deflated_sharpe_probability"], metrics["daily_dsr_probability"], minimums["deflated_sharpe_probability"]),
        ("max_drawdown_pct", abs(metrics["daily_max_drawdown_pct"]) <= maximums["drawdown_pct_absolute"], metrics["daily_max_drawdown_pct"], -maximums["drawdown_pct_absolute"]),
        ("bootstrap_pf_p05", robust["bootstrap_pf_p05"] >= minimums["bootstrap_pf_p05"], robust["bootstrap_pf_p05"], minimums["bootstrap_pf_p05"]),
        ("minimum_quarter_profit_factor", robust["minimum_quarter_profit_factor"] >= minimums["minimum_quarter_profit_factor"], robust["minimum_quarter_profit_factor"], minimums["minimum_quarter_profit_factor"]),
        ("winner_concentration", robust["top_5_winner_gross_profit_share_pct"] <= maximums["top_5_winner_gross_profit_share_pct"], robust["top_5_winner_gross_profit_share_pct"], maximums["top_5_winner_gross_profit_share_pct"]),
        ("is_median_profit_factor", is_pf >= minimums["is_median_profit_factor"], is_pf, minimums["is_median_profit_factor"]),
        ("nested_min_fold_profit_factor", nested_pf is not None and nested_pf >= minimums["nested_minimum_fold_profit_factor"], nested_pf, minimums["nested_minimum_fold_profit_factor"]),
        ("nested_walk_forward_complete", nested_complete, nested_complete, True),
        ("virgin_holdout", False, False, True),
        ("python_mt5_signal_parity", False, False, True),
        ("mt5_every_tick_parity", False, False, True),
        ("paper_forward_closed_trades", forward_trades >= policy["operational_requirements"]["paper_forward_closed_trades"], forward_trades, policy["operational_requirements"]["paper_forward_closed_trades"]),
        ("paper_forward_profit_factor", forward_pf >= policy["operational_requirements"]["paper_forward_profit_factor"], forward_pf, policy["operational_requirements"]["paper_forward_profit_factor"]),
    ]
    return [{"model": model, "check": name, "passed": bool(passed), "value": value, "required": required}
            for name, passed, value, required in checks]


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    cfg = _assumptions(profile)
    is_path = UNIVERSE_RESULTS / "NSXUSD_signals_IS.csv"
    oos_path = UNIVERSE_RESULTS / "NSXUSD_signals_OOS.csv"
    is_signals = calculate_z_dev_in_memory(pd.read_csv(is_path, index_col=0, parse_dates=True))
    oos_signals = calculate_z_dev_in_memory(pd.read_csv(oos_path, index_col=0, parse_dates=True))

    z_l, z_s, sl_mult, mr_score, mr_rank = optimize_mr_params(is_signals, cfg)
    mr_rank.to_csv(RESULTS / "mean_reversion_is_ranking_broker_real.csv", index=False)
    mr_cf, mr_trades, mr_equity = run_mean_reversion_backtest(oos_signals, cfg, z_l, z_s, sl_mult)
    mr_base = compute_backtest_metrics(mr_trades, mr_cf, mr_equity, cfg, dsr_trials=len(mr_rank))
    mr_daily = _daily_metrics(mr_trades, oos_signals.index.min(), oos_signals.index.max(), cfg.initial_balance, len(mr_rank))
    mr_metrics = {**mr_base, **mr_daily}
    mr_robust = _robustness(mr_trades)
    mr_trades.to_csv(RESULTS / "mean_reversion_ohlc_trades_broker_real.csv", index=False)

    trend_ohlc_trades, trend_ohlc_cf, trend_ohlc_eq = run_backtest(oos_signals, cfg)
    trend_ohlc = compute_backtest_metrics(trend_ohlc_trades, trend_ohlc_cf, trend_ohlc_eq, cfg, dsr_trials=81)
    tick_trades_path = RESULTS / "trend_tick_trades.csv"
    tick_metrics_path = RESULTS / "trend_tick_metrics.json"
    tick_validated = tick_trades_path.exists() and tick_metrics_path.exists()
    trend_trades = pd.read_csv(tick_trades_path) if tick_validated else trend_ohlc_trades
    trend_base = json.loads(tick_metrics_path.read_text(encoding="utf-8")) if tick_validated else trend_ohlc
    trend_daily = _daily_metrics(trend_trades, oos_signals.index.min(), oos_signals.index.max(), cfg.initial_balance, 81)
    trend_metrics = {**trend_base, **trend_daily}
    trend_robust = _robustness(trend_trades)
    forward_path = HERE / "forward_axi" / "evaluation" / "forward_evaluation.json"
    forward = json.loads(forward_path.read_text(encoding="utf-8")) if forward_path.exists() else None
    forward_trades = int(forward["tick_metrics"]["closed_trades"]) if forward else 0
    forward_pf = float(forward["tick_metrics"]["profit_factor"]) if forward else 0.0

    nested_root = RESULTS / "trend_nested_walk_forward"
    nested_path = nested_root / "nested_stability_ranking.csv"
    selected_walk_forward_path = RESULTS / "trend_selected_walk_forward" / "selected_trend_walk_forward.csv"
    nested_min_pf = None
    nested_median_pf = None
    nested_completed_folds = 0
    nested_complete = False
    nested_fold_pfs: list[float] = []
    if selected_walk_forward_path.exists():
        selected = pd.read_csv(selected_walk_forward_path)
        selected = selected.sort_values("fold_id")
        nested_fold_pfs = selected["profit_factor"].astype(float).tolist()
        nested_completed_folds = int(selected["fold_id"].nunique())
        nested_min_pf = float(selected["profit_factor"].min())
        nested_median_pf = float(selected["profit_factor"].median())
        nested_complete = nested_completed_folds == 4
    elif nested_path.exists():
        nested = pd.read_csv(nested_path)
        selected = nested[(nested["threshold"].sub(0.65).abs() < 1e-12) &
                          (nested["min_strength"].sub(0.35).abs() < 1e-12) &
                          (nested["vol_multiplier"].sub(2.5).abs() < 1e-12) &
                          (nested["reward_risk"].sub(1.5).abs() < 1e-12)]
        if not selected.empty:
            nested_min_pf = float(selected.iloc[0]["min_pf"])
            nested_median_pf = float(selected.iloc[0]["mean_pf"])
        nested_completed_folds = 4
        nested_complete = True
    else:
        partial_pf = []
        for fold_path in sorted(nested_root.glob("fold_*/ranking_fold.csv")):
            fold = pd.read_csv(fold_path)
            selected = fold[(fold["threshold"].sub(0.65).abs() < 1e-12) &
                            (fold["min_strength"].sub(0.35).abs() < 1e-12) &
                            (fold["vol_multiplier"].sub(2.5).abs() < 1e-12) &
                            (fold["reward_risk"].sub(1.5).abs() < 1e-12)]
            if not selected.empty:
                partial_pf.append(float(selected.iloc[0]["profit_factor"]))
        nested_completed_folds = len(partial_pf)
        if partial_pf:
            nested_min_pf = min(partial_pf)
            nested_median_pf = float(np.median(partial_pf))

    gates = []
    gates += _gate("MEAN_REVERSION", mr_metrics, mr_robust, policy,
                   float(mr_rank.iloc[0]["median_profit_factor"]), None, False, False)
    gates += _gate("TREND_FOLLOW", trend_metrics, trend_robust, policy,
                   nested_median_pf or 0.0, nested_min_pf, nested_complete, tick_validated,
                   forward_trades, forward_pf)
    gate_df = pd.DataFrame(gates)
    gate_df.to_csv(RESULTS / "release_gates.csv", index=False)
    decisions = {model: ("APPROVED" if group["passed"].all() else "REJECTED")
                 for model, group in gate_df.groupby("model")}
    decisions["PORTFOLIO"] = "APPROVED" if all(v == "APPROVED" for v in decisions.values()) else "REJECTED"

    payload = {
        "as_of_utc": profile["captured_utc"],
        "broker_profile": profile,
        "data": {
            "training_start": str(is_signals.index.min()),
            "training_end": str(is_signals.index.max()),
            "oos_start": str(oos_signals.index.min()),
            "oos_end": str(oos_signals.index.max()),
            "is_signals_sha256": _sha256(is_path),
            "oos_signals_sha256": _sha256(oos_path),
        },
        "mean_reversion": {"parameters": {"z_long": z_l, "z_short": z_s, "sl_atr_mult": sl_mult},
                           "is_robust_score": mr_score, "metrics": mr_metrics, "robustness": mr_robust},
        "trend_follow": {"parameters": {"threshold": 0.65, "min_strength": 0.35, "vol_multiplier": 2.5,
                                           "reward_risk": 1.5, "kalman_gate": True},
                         "ohlc_metrics": trend_ohlc, "metrics": trend_metrics, "robustness": trend_robust,
                         "nested_min_pf": nested_min_pf, "nested_completed_folds": nested_completed_folds,
                         "nested_median_pf": nested_median_pf, "nested_complete": nested_complete},
        "decisions": decisions,
        "forward_axi": forward,
        "live_trading_locked": True,
    }
    (RESULTS / "release_decision.json").write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    failures = gate_df.loc[~gate_df["passed"]]
    lines = [
        "# Auditoría institucional NAS100 / NAS100.fs",
        "",
        f"**Decisión Mean Reversion:** {decisions['MEAN_REVERSION']}",
        f"**Decisión Trend Following:** {decisions['TREND_FOLLOW']}",
        f"**Decisión de cartera:** {decisions['PORTFOLIO']}",
        "",
        "> La operación en cuenta real permanece bloqueada. Los artefactos son aptos únicamente para investigación, Strategy Tester y forward demo.",
        "",
        "## Contrato real del bróker",
        "",
        f"Símbolo `{profile['symbol']}`; point `{profile['point']}`; tick size `{profile['tick_size']}`; tick value `${profile['tick_value']}`; volumen `{profile['volume_min']}`–`{profile['volume_max']}`; spread flotante observado `{profile['snapshot_spread_price']}` puntos de precio.",
        "",
        "Los resultados históricos anteriores usaban `point=1.0`, `tick_value=1.0` y spread fijo `1.0`; no son transferibles al contrato actual.",
        "",
        "## Resultados recalculados",
        "",
        " Modelo  Motor  Trades  Retorno  PF  Sharpe diario  DSR  DD diario  Bootstrap PF p05  Peor PF trimestral ",
        " :---  :---  ---:  ---:  ---:  ---:  ---:  ---:  ---:  ---: ",
        f" Mean Reversion  OHLC pesimista, contrato real  {mr_metrics['closed_trades']}  {mr_metrics['total_return_pct']:.2f}%  {mr_metrics['profit_factor']:.3f}  {mr_metrics['daily_sharpe']:.3f}  {mr_metrics['daily_dsr_probability']:.3f}  {mr_metrics['daily_max_drawdown_pct']:.2f}%  {mr_robust['bootstrap_pf_p05']:.3f}  {mr_robust['minimum_quarter_profit_factor']:.3f} ",
        f" Trend Following  {'Tick Bid/Ask' if tick_validated else 'OHLC'}  {trend_metrics['closed_trades']}  {trend_metrics['total_return_pct']:.2f}%  {trend_metrics['profit_factor']:.3f}  {trend_metrics['daily_sharpe']:.3f}  {trend_metrics['daily_dsr_probability']:.3f}  {trend_metrics['daily_max_drawdown_pct']:.2f}%  {trend_robust['bootstrap_pf_p05']:.3f}  {trend_robust['minimum_quarter_profit_factor']:.3f} ",
        "",
        "## Forward Axi posterior",
        "",
        (f"El baseline Trend congelado produjo `{forward_trades}` operaciones, retorno `{forward['tick_metrics']['total_return_pct']:.2f}%` y PF `{forward_pf:.3f}` sobre ticks Axi entre `{forward['period_start']}` y `{forward['period_end']}`. La muestra queda marcada como consumida y no puede usarse para optimización." if forward else "No existe todavía una evaluación forward del bróker."),
        "",
        "## Nested walk-forward del Trend seleccionado",
        "",
        ("PF por fold con HMM recalibrado dentro de cada train: `" + " / ".join(f"{value:.3f}" for value in nested_fold_pfs) + f"`. Mediana `{nested_median_pf:.3f}` y mínimo `{nested_min_pf:.3f}`." if nested_fold_pfs else "La validación nested todavía no está disponible."),
        "",
        "## Fallos del release gate",
        "",
        " Modelo  Control  Valor  Requerido ",
        " :---  :---  ---:  ---: ",
    ]
    for row in failures.itertuples(index=False):
        lines.append(f" {row.model}  {row.check}  {row.value}  {row.required} ")
    lines += [
        "",
        "## Conclusión",
        "",
        "Mean Reversion pierde su edge al usar el contrato real del bróker y falla ya en los folds IS; debe retirarse del portafolio candidato. Trend Following conserva un edge histórico pequeño, pero falla el nested walk-forward y comenzó el forward Axi con dos pérdidas. Ningún modelo está aprobado para despliegue institucional.",
        "",
        "Para desbloquear real se requieren: paridad Python/MT5, backtest MT5 Every tick sobre ticks del bróker, nested walk-forward completo bajo el contrato actual y al menos 60 operaciones de forward demo con PF >= 1.10.",
    ]
    (REPORTS / "AUDITORIA_INSTITUCIONAL_NAS100.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(decisions, indent=2))
    return 0 if decisions["PORTFOLIO"] == "APPROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
