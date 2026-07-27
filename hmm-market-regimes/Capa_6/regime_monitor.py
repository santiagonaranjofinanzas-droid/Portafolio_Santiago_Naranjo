import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RegimePolicy:
    recent_trades_window: int = 60
    watch_pf: float = 1.05
    defensive_pf: float = 0.90
    pause_pf: float = 0.75
    max_loss_streak_watch: int = 6
    max_loss_streak_pause: int = 9
    defensive_risk_multiplier: float = 0.50
    pause_risk_multiplier: float = 0.00
    threshold_step: float = 0.05
    min_strength_step: float = 0.05


def _profit_factor(pnl: np.ndarray) -> float:
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    if len(losses) == 0 or abs(np.sum(losses)) <= 0:
        return float("inf") if len(wins) else 0.0
    return float(np.sum(wins) / abs(np.sum(losses)))


def _loss_streak(pnl: np.ndarray) -> int:
    best = 0
    current = 0
    for value in pnl:
        if value <= 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return int(best)


def _current_streak(pnl: np.ndarray) -> int:
    if len(pnl) == 0:
        return 0
    sign = pnl[-1] > 0
    count = 0
    for value in pnl[::-1]:
        if (value > 0) == sign:
            count += 1
        else:
            break
    return int(count if sign else -count)


def _drawdown_pct(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0.0, np.nan)
    return float(dd.min() * 100.0) if not dd.dropna().empty else 0.0


def quarterly_trade_report(trades: pd.DataFrame) -> pd.DataFrame:
    local = trades.copy()
    local["exit_time"] = pd.to_datetime(local["exit_time"])
    local = local.set_index("exit_time").sort_index()
    rows = []
    for period, chunk in local.groupby(pd.Grouper(freq="QE")):
        if chunk.empty:
            continue
        pnl = chunk["pnl"].to_numpy(dtype=float)
        rows.append({
            "period": period,
            "closed_trades": len(chunk),
            "net_pnl": float(np.sum(pnl)),
            "avg_pnl": float(np.mean(pnl)),
            "profit_factor": _profit_factor(pnl),
            "win_rate_pct": float(np.mean(pnl > 0) * 100.0),
            "max_loss_streak": _loss_streak(pnl),
        })
    report = pd.DataFrame(rows)
    if not report.empty:
        report["profit_factor_rolling_4q"] = report["profit_factor"].replace([np.inf, -np.inf], np.nan).rolling(4, min_periods=1).mean()
        report["avg_pnl_rolling_4q"] = report["avg_pnl"].rolling(4, min_periods=1).mean()
    return report


def classify_regime(trades: pd.DataFrame, equity: pd.Series, policy: RegimePolicy  None = None) -> tuple[dict, pd.DataFrame]:
    cfg = policy or RegimePolicy()
    q_report = quarterly_trade_report(trades)
    pnl = trades["pnl"].to_numpy(dtype=float) if not trades.empty else np.array([], dtype=float)
    recent = pnl[-cfg.recent_trades_window:]
    recent_pf = _profit_factor(recent)
    recent_loss_streak = _loss_streak(recent)
    current_streak = _current_streak(pnl)
    full_dd = _drawdown_pct(equity)

    last_q = q_report.iloc[-1].to_dict() if not q_report.empty else {}
    last_q_pf = float(last_q.get("profit_factor", 0.0))
    last_q_pnl = float(last_q.get("net_pnl", 0.0))
    rolling_pf = float(last_q.get("profit_factor_rolling_4q", 0.0))

    status = "NORMAL"
    reasons = []
    if last_q_pf < cfg.watch_pf or recent_pf < cfg.watch_pf:
        status = "WATCH"
        reasons.append("PF reciente bajo el umbral de vigilancia")
    if last_q_pf < cfg.defensive_pf or recent_pf < cfg.defensive_pf or last_q_pnl < 0:
        status = "DEFENSIVE"
        reasons.append("Tramo reciente con edge negativo o PF defensivo")
    if last_q_pf < cfg.pause_pf or recent_loss_streak >= cfg.max_loss_streak_pause:
        status = "PAUSE_AND_RETRAIN"
        reasons.append("Riesgo alto de cambio de regimen: pausar nuevas entradas y reentrenar")
    elif recent_loss_streak >= cfg.max_loss_streak_watch and status == "NORMAL":
        status = "WATCH"
        reasons.append("Racha de perdidas elevada")

    if rolling_pf < 1.0 and status != "PAUSE_AND_RETRAIN":
        status = "DEFENSIVE"
        reasons.append("PF rolling 4 trimestres bajo 1.0")

    if status == "NORMAL":
        action = {
            "risk_multiplier": 1.0,
            "threshold_delta": 0.0,
            "min_strength_delta": 0.0,
            "allow_new_entries": True,
            "retrain_required": False,
        }
    elif status == "WATCH":
        action = {
            "risk_multiplier": 0.75,
            "threshold_delta": 0.0,
            "min_strength_delta": cfg.min_strength_step,
            "allow_new_entries": True,
            "retrain_required": False,
        }
    elif status == "DEFENSIVE":
        action = {
            "risk_multiplier": cfg.defensive_risk_multiplier,
            "threshold_delta": cfg.threshold_step,
            "min_strength_delta": cfg.min_strength_step,
            "allow_new_entries": True,
            "retrain_required": True,
        }
    else:
        action = {
            "risk_multiplier": cfg.pause_risk_multiplier,
            "threshold_delta": cfg.threshold_step,
            "min_strength_delta": cfg.min_strength_step,
            "allow_new_entries": False,
            "retrain_required": True,
        }

    diagnostics = {
        "status": status,
        "reasons": reasons,
        "last_quarter_profit_factor": last_q_pf,
        "last_quarter_net_pnl": last_q_pnl,
        "rolling_4q_profit_factor": rolling_pf,
        "recent_window_trades": int(len(recent)),
        "recent_window_profit_factor": recent_pf,
        "recent_window_loss_streak": int(recent_loss_streak),
        "current_trade_streak_positive_negative": int(current_streak),
        "full_oos_max_drawdown_pct": full_dd,
        "action": action,
    }
    return diagnostics, q_report


def write_regime_status(diagnostics: dict, q_report: pd.DataFrame, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "regime_status.json", "w", encoding="utf-8") as handle:
        json.dump(diagnostics, handle, indent=2)
    q_report.to_csv(out_dir / "regime_quarterly_diagnostics.csv", index=False)
